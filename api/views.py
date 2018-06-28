from collections import OrderedDict
import datetime
import logging
import random
import time

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import views
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.status import (HTTP_200_OK, HTTP_201_CREATED,
                                   HTTP_202_ACCEPTED, HTTP_404_NOT_FOUND)

from api.utils import get_metrics_base_data
from app.cache import RedisClusterCache
from app.models import App, Device
from app.tasks import log_to_db, task_incoming_call_notify, task_notify_old_token
from app.utils import (
    LOG_CALL_FROM,
    LOG_CALLER_ID,
    log_data_to_metrics_log,
    log_middleware_information,
    LOG_SIP_USER_ID)
from main.prometheus import (
    ACTION_KEY,
    CALL_SETUP_SUCCESSFUL_KEY,
    DIRECTION_KEY,
    FAILED_REASON_KEY,
    OS_KEY,
    VIALER_CALL_FAILURE_TOTAL_KEY,
    VIALER_CALL_SUCCESS_TOTAL_KEY,
    VIALER_HANGUP_REASON_TOTAL_KEY,
    VIALER_MIDDLEWARE_INCOMING_CALL_TOTAL_KEY,
    VIALER_MIDDLEWARE_INCOMING_CALL_FAILED_TOTAL_KEY,
    VIALER_MIDDLEWARE_INCOMING_VALUE,
    VIALER_MIDDLEWARE_PUSH_NOTIFICATION_FAILED_TOTAL_KEY,
    VIALER_MIDDLEWARE_PUSH_NOTIFICATION_SUCCESS_TOTAL_KEY)

from .authentication import VoipgridAuthentication
from .renderers import PlainTextRenderer
from .serializers import (
    CallResponseSerializer,
    DeleteDeviceSerializer,
    DeviceSerializer,
    HangupReasonSerializer,
    IncomingCallSerializer,
)

logger = logging.getLogger('django')


class VialerAPIView(views.APIView):
    """
    Super class that provides a few handy methods that are used in most of
    the api views we provide.
    """
    serializer_class = None

    def _serialize_data(self, data, serializer_class=None):
        """
        Function to serialize data with the serializer given in the
        serializer_class attribute. Also validates the data and responds with
        a HTTP_400_BAD_REQUEST when validation failed. Due to being an open
        api we do not want to give away the required fields and their
        requirements.

        Args:
            data(dict): Dictonary with that data that need to be serialized.
            serializer_class(Serializer): Class to use for serialization.

        Returns:
            dict: Dictionary with the validated data.

        Raises:
            NotImplementedError: When serializer_class attribute is not set.
            ParseError: When validation fails but because it's an open API we
                do not want to give away what failed. ParseError returns a
                HTTP_400_BAD_REQUEST.
        """
        if serializer_class is None:
            if self.serializer_class is None:
                raise NotImplementedError('serializer_class Attribute should be set')
        else:
            self.serializer_class = serializer_class

        serializer = self.serializer_class(data=data)
        if not serializer.is_valid(raise_exception=False):
            # Log errors.
            log_middleware_information(
                'BAD REQUEST! Serialization failed with following errors:\n\n{0}\n\nData:\n\n{1}',
                OrderedDict([
                    ('serializer_errors', serializer.errors),
                    ('data', data),
                ]),
                logging.INFO,
            )
            # This raises a bad request response.
            raise ParseError(detail=None)

        return serializer.validated_data

    def _serialize_request(self, request, serializer_class=None):
        """
        Funtion that serializes a request object.

        Args:
            request(Request): Django request object with data.
            serializer_class(Serializer): Class to use for serialization.

        Returns:
            dict: Dictionary with the validated data.
        """
        return self._serialize_data(request.data, serializer_class=serializer_class)


class IncomingCallView(VialerAPIView):
    """
    View for asterisk to initiate a incoming call.
    """
    serializer_class = IncomingCallSerializer
    renderer_classes = (PlainTextRenderer, )

    def post(self, request):
        """
        Handle post requests on this view.

        Args:
            request (Request): Containing the post data.

        Returns:
            string: With status=ACK or status=NAK based on succes or failure.

        Raises:
            Http404: When an app_id is provided that does not exist.
        """
        redis_cache = RedisClusterCache()
        serialized_data = self._serialize_request(request)

        sip_user_id = serialized_data['sip_user_id']
        caller_id = serialized_data['caller_id']
        phonenumber = serialized_data['phonenumber']
        call_id = serialized_data['call_id']

        if not call_id:
            # Generate unique_key for reference on incoming call answer.
            unique_key = random.getrandbits(128)
            unique_key = '%032x' % unique_key
        else:
            unique_key = call_id

        try:
            # Check if there is a registered device for given sip_user_id.
            device = get_object_or_404(Device, sip_user_id=sip_user_id)
        except Http404:
            log_middleware_information(
                '{0} | Failed to find a device for SIP_user_ID : {1} sending NAK',
                OrderedDict([
                    ('unique_key', unique_key),
                    (LOG_SIP_USER_ID, sip_user_id),
                ]),
                logging.WARNING,
            )

            # Push data to Redis for when a sip user id couldn't be found.
            redis_cache.client.rpush(
                VIALER_MIDDLEWARE_INCOMING_CALL_FAILED_TOTAL_KEY,
                {
                    OS_KEY: 'Middleware',
                    ACTION_KEY: 'Received',
                    FAILED_REASON_KEY: 'failed no sip_user_id',
                }
            )

            # Log to the metrics file.
            metrics_data = {
                OS_KEY: 'Middleware',
                ACTION_KEY: 'Received',
                FAILED_REASON_KEY: 'failed no sip_user_id',
                'unique_key': unique_key,
            }
            log_data_to_metrics_log(metrics_data, sip_user_id)
        except Exception:
            log_middleware_information(
                '{0} | EXCEPTION WHILE FINDING DEVICE FOR SIP_USER_ID : {1}',
                OrderedDict([
                    ('unique_key', unique_key),
                    (LOG_SIP_USER_ID, sip_user_id),
                ]),
                logging.CRITICAL,
            )
        else:
            log_middleware_information(
                '{0} | Incoming call for SIP:{1} FROM:\'{2}/{3}\'',
                OrderedDict([
                    ('unique_key', unique_key),
                    (LOG_SIP_USER_ID, sip_user_id),
                    (LOG_CALL_FROM, phonenumber),
                    (LOG_CALLER_ID, caller_id),
                ]),
                logging.INFO,
                device=device,
            )

            # Push data to Redis for when a incoming call is received.
            redis_cache.client.rpush(
                VIALER_MIDDLEWARE_INCOMING_CALL_TOTAL_KEY,
                {
                    OS_KEY: 'Middleware',
                    ACTION_KEY: 'Received',
                }
            )

            # Log to the metrics file.
            metrics_data = {
                OS_KEY: 'Middleware',
                ACTION_KEY: 'Received',
                'unique_key': unique_key,
            }
            log_data_to_metrics_log(metrics_data, sip_user_id)

            attempt = 1
            # Send push message to wake up app.
            task_incoming_call_notify(
                device,
                unique_key,
                phonenumber,
                caller_id,
                attempt,
            )

            # Time related settings.
            wait_interval = settings.APP_PUSH_ROUNDTRIP_WAIT / 1000
            wait_until = time.time() + wait_interval
            resend_interval = settings.APP_PUSH_RESEND_INTERVAL / 1000
            next_resend_time = time.time() + resend_interval

            # Determine max possible attempts. Avoid sending a push
            # close to the end of the loop.
            max_attemps = int(wait_interval / resend_interval) - 1

            cache_key = 'call_{0}'.format(unique_key)
            # Create cache entry with device platform as placeholder for the
            # available flag. Done for logging purposes.
            redis_cache.set(cache_key, device.app.platform)

            log_middleware_information(
                '{0} | {1} Starting \'wait for it\' loop until {2} ({3}msec)',
                OrderedDict([
                    ('unique_key', unique_key),
                    ('platform', device.app.platform.upper()),
                    ('wait_until', datetime.datetime.fromtimestamp(wait_until).strftime('%H:%M:%S.%f')),
                    ('roundtrip', settings.APP_PUSH_ROUNDTRIP_WAIT),
                ]),
                logging.INFO,
                device=device,
            )

            # We have to wait till the app responds and sets the cache value.
            while time.time() < wait_until:
                available = redis_cache.get(cache_key)
                # Get on an empty key returns None so we need to check for
                # True and False.
                if available == 'True':
                    log_middleware_information(
                        '{0} | {1} Device checked in on time, sending ACK on {2}',
                        OrderedDict([
                            ('unique_key', unique_key),
                            ('platform', device.app.platform.upper()),
                            ('ack_time', datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S.%f')),
                        ]),
                        logging.INFO,
                        device=device,
                    )

                    # Push data to Redis for when a device successful
                    # responded to the middleware.
                    redis_cache.client.rpush(
                        VIALER_MIDDLEWARE_PUSH_NOTIFICATION_SUCCESS_TOTAL_KEY,
                        {
                            OS_KEY: device.app.platform,
                            DIRECTION_KEY: VIALER_MIDDLEWARE_INCOMING_VALUE,
                        }
                    )

                    # Log to the metrics file.
                    metrics_data = {
                        OS_KEY: device.app.platform,
                        CALL_SETUP_SUCCESSFUL_KEY: 'true',
                    }
                    log_data_to_metrics_log(metrics_data, sip_user_id)

                    # Success status for asterisk.
                    return Response('status=ACK')
                elif available == 'False':
                    log_middleware_information(
                        '{0} | {1} Device not available, sending NAK on {2}',
                        OrderedDict([
                            ('unique_key', unique_key),
                            ('platform', device.app.platform.upper()),
                            ('nak_time', datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S.%f')),
                        ]),
                        logging.INFO,
                        device=device,
                    )

                    # Push data to Redis for when a device responded as not
                    # available to the middleware.
                    redis_cache.client.rpush(
                        VIALER_MIDDLEWARE_PUSH_NOTIFICATION_FAILED_TOTAL_KEY,
                        {
                            OS_KEY: device.app.platform,
                            DIRECTION_KEY: VIALER_MIDDLEWARE_INCOMING_VALUE,
                            FAILED_REASON_KEY: 'Device not available',
                        }
                    )

                    # Log to the metrics file.
                    metrics_data = {
                        OS_KEY: device.app.platform,
                        CALL_SETUP_SUCCESSFUL_KEY: 'false',
                        FAILED_REASON_KEY: 'Device not available',
                    }
                    log_data_to_metrics_log(metrics_data, sip_user_id)

                    # App is not available.
                    return Response('status=NAK')
                else:
                    # Try to resend the push message every X seconds or
                    # after exceeding the max_attempts.
                    if time.time() > next_resend_time and attempt < max_attemps:
                        attempt += 1
                        next_resend_time = time.time() + resend_interval
                        task_incoming_call_notify(
                            device,
                            unique_key,
                            phonenumber,
                            caller_id,
                            attempt,
                        )

                    time.sleep(.01)  # wait 10 ms

            log_middleware_information(
                '{0} | {1} Device did NOT check in on time, sending NAK on {2}',
                OrderedDict([
                    ('unique_key', unique_key),
                    ('platform', device.app.platform.upper()),
                    ('nak_time', datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S.%f')),
                ]),
                logging.INFO,
                device=device,
            )

            # Push data to Redis for when a device has not responded to the middleware.
            redis_cache.client.rpush(
                VIALER_MIDDLEWARE_PUSH_NOTIFICATION_FAILED_TOTAL_KEY,
                {
                    OS_KEY: device.app.platform,
                    DIRECTION_KEY: VIALER_MIDDLEWARE_INCOMING_VALUE,
                    FAILED_REASON_KEY: 'Unable to get response from phone',
                }
            )

            # Log to the metrics file.
            metrics_data = {
                OS_KEY: device.app.platform,
                CALL_SETUP_SUCCESSFUL_KEY: 'false',
                FAILED_REASON_KEY: 'Device did not respond in time',
            }
            log_data_to_metrics_log(metrics_data, sip_user_id)

        # Failed status for asterisk.
        return Response('status=NAK')


class CallResponseView(VialerAPIView):
    """
    View called by the app when it wake's up and responds to a incoming call.
    """
    serializer_class = CallResponseSerializer

    def post(self, request):
        """
        Handle the post request of this view.

        Args:
            request (Request): Containing the post data.

        Returns:
            json: Status key with OK value.
        """
        serialized_data = self._serialize_request(request)
        unique_key = serialized_data['unique_key']
        message_start_time = serialized_data['message_start_time']
        available = serialized_data['available']

        cache_key = 'call_{0}'.format(unique_key)

        redis_cache = RedisClusterCache()

        # Check if key exists to avoid endpoint probing spam.
        if not redis_cache.exists(cache_key):
            return Response('', status=HTTP_404_NOT_FOUND)

        # Wait loop for asterisk sets the device platform as placeholder
        # for the available flag.
        platform = redis_cache.get(cache_key)

        redis_cache.set(cache_key, available)

        roundtrip = time.time() - float(message_start_time)

        log_middleware_information(
            '{0} | Device responded. Message start-time: {1} sec, round trip-time: {2} sec',
            OrderedDict([
                ('unique_key', unique_key),
                ('starttime', datetime.datetime.fromtimestamp(message_start_time)),
                ('roundtrip', roundtrip),
            ]),
            logging.INFO,
        )

        # Threaded task to log information to the database.
        log_to_db(platform, roundtrip, available)

        # If device responded too late return 404 request (call) not found.
        if (roundtrip > (settings.APP_PUSH_ROUNDTRIP_WAIT / 1000)):
            return Response('', status=HTTP_404_NOT_FOUND)

        return Response('', status=HTTP_202_ACCEPTED)


class DeviceView(VialerAPIView):
    """
    View for creating, updating and deleting a device.
    """
    serializer_class = DeviceSerializer
    authentication_classes = (VoipgridAuthentication, )

    def post(self, request, platform):
        """
        Function to create or update a Device.
        """
        serialized_data = self._serialize_request(request)

        token = serialized_data['token']
        sip_user_id = serialized_data['sip_user_id']
        app_id = serialized_data['app']
        remote_logging_id = serialized_data.get('remote_logging_id')

        app = get_object_or_404(App, app_id=app_id, platform=platform)

        created = False

        try:
            device = Device.objects.get(sip_user_id=sip_user_id)
        except Device.DoesNotExist:
            device = Device.objects.create(
                sip_user_id=sip_user_id,
                app_id=app.id,
                token=token,
                remote_logging_id=remote_logging_id,
            )
            created = True

        # Track status.
        status = 'OK'

        # Update token.
        if device.token != token:
            if not created:
                task_notify_old_token(device, device.app)
                status += ' updated and send notify to old token'
            else:
                status += ' and updated token'
            device.token = token

        # Update remote_logging_id.
        if device.remote_logging_id != remote_logging_id:
            device.remote_logging_id = remote_logging_id
            status += ', updated the remote_logging_id'

        # Update fields.
        device.name = serialized_data.get('name', None)
        device.os_version = serialized_data.get('os_version', None)
        device.client_version = serialized_data.get('client_version', None)
        device.last_seen = timezone.now()
        device.sandbox = serialized_data['sandbox']

        device.app = app

        device.save()

        status_code = HTTP_200_OK
        if created:
            status_code = HTTP_201_CREATED

        log_middleware_information(
            '{0} {1} device:{2} registered for SIP_USER_ID: {3}. Status: {4}.',
            OrderedDict([
                ('app_id', app_id),
                ('platform', device.app.platform.upper()),
                ('device_token', device.token),
                (LOG_SIP_USER_ID, sip_user_id),
                ('status', status),
            ]),
            logging.INFO,
            device=device,
        )
        return Response('', status=status_code)

    def delete(self, request, platform):
        """
        Function for deleting a Device.
        """
        serialized_data = self._serialize_request(request, serializer_class=DeleteDeviceSerializer)

        token = serialized_data['token']
        sip_user_id = serialized_data['sip_user_id']
        app_id = serialized_data['app']

        try:
            device = get_object_or_404(
                Device,
                sip_user_id=sip_user_id,
                token=token,
                app__app_id=app_id,
                app__platform=platform,
            )
            device.delete()
        except Http404:
            log_middleware_information(
                'Could not unregister device {0} for SIP_USER_ID {1}',
                OrderedDict([
                    ('token', token),
                    (LOG_SIP_USER_ID, sip_user_id),
                ]),
                logging.WARNING,
            )
            raise
        except Exception:
            log_middleware_information(
                'EXCEPTION WHILE UNREGISTERING DEVICE {0} FOR SIP_USER_ID : {1}',
                OrderedDict([
                    ('token', token),
                    (LOG_SIP_USER_ID, sip_user_id),
                ]),
                logging.CRITICAL,
            )
            raise
        log_middleware_information(
            'Unregistered device {0} for SIP_USER_ID {1}',
            OrderedDict([
                ('token', token),
                (LOG_SIP_USER_ID, sip_user_id),
            ]),
            logging.INFO,
            device=device,
        )
        return Response('', status=HTTP_200_OK)


class HangupReasonView(VialerAPIView):
    """
    View to log a reason why a device did not answer a call.
    """
    serializer_class = HangupReasonSerializer
    authentication_classes = (VoipgridAuthentication, )

    def post(self, request):
        """
        Function to log the reason for a device.
        """
        serialized_data = self._serialize_request(request)

        reason = serialized_data['reason']
        unique_key = serialized_data['unique_key']
        sip_user_id = serialized_data['sip_user_id']

        try:
            # Check if there is a registered device for given sip_user_id.
            device = get_object_or_404(Device, sip_user_id=sip_user_id)
        except Http404:
            log_middleware_information(
                '{0} | Failed to find a device for SIP_user_ID : {1}',
                OrderedDict([
                    ('unique_key', unique_key),
                    (LOG_SIP_USER_ID, sip_user_id),
                ]),
                logging.WARNING,
            )
            raise

        log_middleware_information(
            '{0} | {1} Device not available because: {2} on {3}',
            OrderedDict([
                ('unique_key', unique_key),
                ('platform', device.app.platform.upper()),
                ('reason', reason),
                ('timestamp', datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S.%f')),
            ]),
            logging.INFO,
            device=device,
        )
        return Response(status=HTTP_200_OK)


class LogMetricsView(VialerAPIView):
    serializer_class = None
    authentication_classes = (VoipgridAuthentication,)

    def post(self, request):
        redis_cache = RedisClusterCache()
        json_data = request.data

        if CALL_SETUP_SUCCESSFUL_KEY in json_data:
            if json_data.get(CALL_SETUP_SUCCESSFUL_KEY) == 'true':
                metric_data = get_metrics_base_data(json_data)
                redis_cache.client.rpush(VIALER_CALL_SUCCESS_TOTAL_KEY, metric_data)

            elif json_data.get(CALL_SETUP_SUCCESSFUL_KEY) == 'false':
                metric_data = get_metrics_base_data(json_data)
                metric_data[FAILED_REASON_KEY] = json_data.get(FAILED_REASON_KEY)
                redis_cache.client.rpush(VIALER_CALL_FAILURE_TOTAL_KEY, metric_data)

            elif json_data.get(CALL_SETUP_SUCCESSFUL_KEY) == 'declined':
                metric_data = get_metrics_base_data(json_data)
                metric_data[FAILED_REASON_KEY] = json_data.get(FAILED_REASON_KEY)
                redis_cache.client.rpush(VIALER_HANGUP_REASON_TOTAL_KEY, metric_data)

        log_data_to_metrics_log(json_data, json_data.get(LOG_SIP_USER_ID))

        return Response(status=HTTP_200_OK)
