import datetime
import json
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

from app.cache import RedisClusterCache
from app.models import App, Device
from app.tasks import log_to_db, task_incoming_call_notify, task_notify_old_token

from .authentication import VoipgridAuthentication
from .renderers import PlainTextRenderer
from .serializers import (CallResponseSerializer, IncomingCallSerializer,
                          DeviceSerializer, DeleteDeviceSerializer)

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
            logger.info('BAD REQUEST! Serialization failed with following errors:\n\n{0}\n\nData:\n\n{1}'.format(
                serializer.errors,
                data,
            ))
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

        logger.info('{0} | Incoming call for SIP:{1} FROM:\'{2}/{3}\' (POST:{4})'.format(
            unique_key,
            sip_user_id,
            phonenumber,
            caller_id,
            json.dumps(request.POST, ensure_ascii=False))
        )
        try:
            # Check if there is a registered device for given sip_user_id.
            device = get_object_or_404(Device, sip_user_id=sip_user_id)
        except Http404:
            logger.warning('{0} | Failed to find a device for SIP_user_ID : {1} sending NAK'.format(
                unique_key,
                sip_user_id)
            )
        except Exception:
            logger.exception('{0} | EXCEPTION WHILE FINDING DEVICE FOR SIP_USER_ID : {1}'.format(
                unique_key,
                sip_user_id)
            )
        else:

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
            redis_cache = RedisClusterCache()
            # Create cache entry with device platform as placeholder for the
            # available flag. Done for logging purposes.
            redis_cache.set(cache_key, device.app.platform)

            logger.info('{0} | {1} Starting \'wait for it\' loop until {2} ({3}msec)'.format(
                unique_key,
                device.app.platform.upper(),
                datetime.datetime.fromtimestamp(wait_until).strftime('%H:%M:%S.%f'),
                settings.APP_PUSH_ROUNDTRIP_WAIT)
            )
            # We have to wait till the app responds and sets the cache value.
            while time.time() < wait_until:
                available = redis_cache.get(cache_key)
                # Get on an empty key returns None so we need to check for
                # True and False.
                if available == 'True':
                    logger.info('{0} | {1} Device checked in on time, sending ACK on {2}'.format(
                        unique_key,
                        device.app.platform.upper(),
                        datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S.%f'))
                    )
                    # Succes status for asterisk.
                    return Response('status=ACK')
                elif available == 'False':
                    logger.info('{0} | {1} Device not available, sending NAK on {2}'.format(
                        unique_key,
                        device.app.platform.upper(),
                        datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S.%f'))
                    )
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

            logger.info('{0} | {1} Device did NOT check in on time, sending NAK on {2}'.format(
                unique_key,
                device.app.platform.upper(),
                datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S.%f'))
            )

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

        logger.info('{0} | Device responded. Message round trip-time: {1} sec'.format(
            unique_key,
            roundtrip)
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

        app = get_object_or_404(App, app_id=app_id, platform=platform)

        created = False

        try:
            device = Device.objects.get(sip_user_id=sip_user_id)
        except Device.DoesNotExist:
            device = Device.objects.create(
                sip_user_id=sip_user_id,
                app_id=app.id,
                token=token,
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

        logger.info('{0} {1} device:{2} registered for SIP_USER_ID: {3}. Status: {4}.'.format(
            app.app_id,
            device.app.platform.upper(),
            device.token,
            sip_user_id,
            status)
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
            logger.warning('Could not unregister device {0} for SIP_USER_ID {1}'.format(token, sip_user_id))
            raise
        except Exception:
            logger.exception('EXCEPTION WHILE UNREGISTERING DEVICE {0} FOR SIP_USER_ID : {1}'.format(
                token,
                sip_user_id)
            )
            raise
        logger.info('Unregistered device {0} for SIP_USER_ID {1}'.format(token, sip_user_id))
        return Response('', status=HTTP_200_OK)
