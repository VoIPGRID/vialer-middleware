from collections import OrderedDict
import datetime
import logging
import os
from time import time
from urllib.parse import urljoin

from apns_clerk import APNs, Message, Session
from apns2.client import APNsClient
from apns2.errors import BadDeviceToken, DeviceTokenNotForTopic, APNsException, Unregistered
from apns2.payload import Payload
from django.conf import settings
from gcm.gcm import GCM, GCMAuthenticationException
from pyfcm import FCMNotification
from pyfcm.errors import AuthenticationError, FCMServerError, InternalPackageError

from app.utils import log_middleware_information

from .models import ANDROID_PLATFORM, APNS_PLATFORM, GCM_PLATFORM


TYPE_CALL = 'call'
TYPE_MESSAGE = 'message'


def send_call_message(device, unique_key, phonenumber, caller_id, attempt):
    """
    Function to send the call push notification.

    Args:
        device (Device): A Device object.
        unique_key (string): String with the unique_key.
        phonenumber (string): Phonenumber that is calling.
        caller_id (string): ID of the caller.
        attempt (int): The amount of attempts made.
    """
    data = {
        'unique_key': unique_key,
        'phonenumber': phonenumber,
        'caller_id': caller_id,
        'attempt': attempt,
    }
    if device.app.platform == APNS_PLATFORM:
        send_apns_message(device, device.app, TYPE_CALL, data)
    elif device.app.platform == GCM_PLATFORM:
        send_gcm_message(device, device.app, TYPE_CALL, data)
    elif device.app.platform == ANDROID_PLATFORM:
        send_fcm_message(device, device.app, TYPE_CALL, data)
    else:
        log_middleware_information(
            '{0} | Trying to sent \'call\' notification to unknown platform:{1} device:{2}',
            OrderedDict([
                ('unique_key', unique_key),
                ('platform', device.app.platform),
                ('token', device.token),
            ]),
            logging.WARNING,
            device=device,
        )


def send_text_message(device, app, message):
    """
    Function to send a push notification with a message.

    Args:
        device (Device): A Device object.
        message (string): The message that needs to be send to the device.
    """
    if app.platform == APNS_PLATFORM:
        send_apns_message(device, app, TYPE_MESSAGE, {'message': message})
    elif app.platform == GCM_PLATFORM:
        send_gcm_message(device, app, TYPE_MESSAGE, {'message': message})
    elif app.platform == ANDROID_PLATFORM:
        send_fcm_message(device, app, TYPE_MESSAGE, {'message': message})
    else:
        log_middleware_information(
            'Trying to sent \'message\' notification to unknown platform:{0} device:{1}',
            OrderedDict([
                ('platform', device.app.platform),
                ('token', device.token),
            ]),
            logging.WARNING,
            device=device,
        )


def get_call_push_payload(unique_key, phonenumber, caller_id, attempt):
    """
    Function to create a dict used in the call push notification.

    Args:
        unique_key (string): The unique_key for the call.
        phonenumber (string): The phonenumber that is calling.
        caller_id (string): ID of the caller.
        attempt (int): The amount of attempts made.

    Returns:
        dict: A dictionary with the following keys:
                type
                unique_key
                phonenumber
                caller_id
                response_api
                message_start_time
    """
    response_url = urljoin(settings.APP_API_URL, 'api/call-response/')

    payload = {
        'type': TYPE_CALL,
        'unique_key': unique_key,
        'phonenumber': phonenumber,
        'caller_id': caller_id,
        'response_api': response_url,
        'message_start_time': time(),
        'attempt': attempt,
    }
    return payload


def get_message_push_payload(message):
    """
    Function to create a dict used in the message push notification.

    Args:
        message (string): The message send in the notification.

    Returns:
        dict: A dictionary with the following keys:
                type
                message
    """
    payload = {
        'type': TYPE_MESSAGE,
        'message': message,
    }
    return payload


def send_apns_message(device, app, message_type, data=None):
    """
    Send an Apple Push Notification message.
    """
    if device.sip_user_id not in settings.APNS2_DEVICES:
        send_legacy_apns_message(device, app, message_type, data)
    else:
        send_apns2_message(device, app, message_type, data)


def send_legacy_apns_message(device, app, message_type, data=None):
    """
    Send an Apple Push Notification message via the legacy API.
    """
    token_list = [device.token]
    unique_key = device.token

    if message_type == TYPE_CALL:
        unique_key = data['unique_key']
        message = Message(token_list, payload=get_call_push_payload(
            unique_key,
            data['phonenumber'],
            data['caller_id'],
            data['attempt'],
        ))
    elif message_type == TYPE_MESSAGE:
        message = Message(token_list, payload=get_message_push_payload(data['message']))
    else:
        log_middleware_information(
            '{0} | TRYING TO SENT MESSAGE OF UNKNOWN TYPE: {1}',
            OrderedDict([
                ('unique_key', unique_key),
                ('message_type', message_type),
            ]),
            logging.WARNING,
            device=device,
        )

    session = Session()

    push_mode = settings.APNS_PRODUCTION
    if device.sandbox:
        # Sandbox push mode.
        push_mode = settings.APNS_SANDBOX

    full_cert_path = os.path.join(settings.CERT_DIR, app.push_key)

    con = session.get_connection(push_mode, cert_file=full_cert_path)
    srv = APNs(con)

    try:
        log_middleware_information(
            '{0} | Sending legacy APNS \'{1}\' message at time:{2} to {3}',
            OrderedDict([
                ('unique_key', unique_key),
                ('message_type', message_type),
                ('message_time', datetime.datetime.fromtimestamp(time()).strftime('%H:%M:%S.%f')),
                ('token', device.token),
            ]),
            logging.INFO,
            device=device,
        )

        start_time = time()
        res = srv.send(message)

    except Exception:
        log_middleware_information(
            '{0} | Error sending APNS message',
            OrderedDict(
                unique_key=unique_key,
            ),
            logging.CRITICAL,
            device=device,
        )

    else:
        # Check failures. Check codes in APNs reference docs.
        for token, reason in res.failed.items():
            code, errmsg = reason
            # According to APNs protocol the token reported here
            # is garbage (invalid or empty), stop using and remove it.
            log_middleware_information(
                '{0} | Sending APNS message failed for device: {1}, reason: {2}',
                OrderedDict([
                    ('unique_key', unique_key),
                    ('token', device.token),
                    ('error_msg', errmsg),
                ]),
                logging.WARNING,
                device=device,
            )

        # Check failures not related to devices.
        for code, errmsg in res.errors:
            log_middleware_information(
                '{0} | Error sending APNS message. \'{1}\'',
                OrderedDict([
                    ('unique_key', unique_key),
                    ('error_msg', errmsg),
                ]),
                logging.WARNING,
                device=device,
            )

        # Check if there are tokens that can be retried.
        if res.needs_retry():
            log_middleware_information(
                '{0} | Could not sent APNS message, retrying...',
                OrderedDict([
                    ('unique_key', unique_key),
                ]),
                logging.INFO,
                device=device,
            )
            # Repeat with retry_message or reschedule your task.
            res.retry()

        elapsed_time = time() - start_time
        log_middleware_information(
            '{0} | Sending message to legacy APNS took {1:.2f}s',
            OrderedDict([
                ('unique_key', unique_key),
                ('conn_time', elapsed_time),
            ]),
            logging.INFO,
            device=device,
        )


def send_apns2_message(device, app, message_type, data=None):
    """
    Send an Apple Push Notification message via the new v2 API.
    """
    unique_key = device.token

    if message_type == TYPE_CALL:
        unique_key = data['unique_key']
        message = Payload(custom=get_call_push_payload(
            unique_key,
            data['phonenumber'],
            data['caller_id'],
            data['attempt'],
        ))
    elif message_type == TYPE_MESSAGE:
        message = Payload(custom=get_message_push_payload(data['message']))
    else:
        log_middleware_information(
            '{0} | TRYING TO SENT MESSAGE OF UNKNOWN TYPE: {1}',
            OrderedDict([
                ('unique_key', unique_key),
                ('message_type', message_type),
            ]),
            logging.WARNING,
            device=device,
        )

        # Unknown message type: ignore this message.
        return

    # Get the APNSv2 connection. There is one global connection.
    client = get_apns2_connection(app, device, unique_key)

    try:
        log_middleware_information(
            '{0} | Sending APNSv2 \'{1}\' message at time:{2} to {3}',
            OrderedDict([
                ('unique_key', unique_key),
                ('message_type', message_type),
                ('message_time', datetime.datetime.fromtimestamp(time()).strftime('%H:%M:%S.%f')),
                ('token', device.token),
            ]),
            logging.INFO,
            device=device,
        )

        start_time = time()
        try:
            client.send_notification(device.token, message)
        finally:
            elapsed_time = time() - start_time
            log_middleware_information(
                '{0} | Sending message to APNSv2 took {1:.2f}s',
                OrderedDict([
                    ('unique_key', unique_key),
                    ('conn_time', elapsed_time),
                ]),
                logging.INFO,
                device=device,
            )

    except (DeviceTokenNotForTopic, BadDeviceToken, Unregistered) as ex:
        # According to APNs protocol the token reported here
        # is garbage (invalid or empty), stop using and remove it.
        log_middleware_information(
            '{0} | Sending APNSv2 message failed for device: {1}, reason: {2}',
            OrderedDict([
                ('unique_key', unique_key),
                ('token', device.token),
                ('error_msg', type(ex).__name__),
            ]),
            logging.WARNING,
            device=device,
        )
    except APNsException as ex:
        # Failures not related to devices.
        log_middleware_information(
            '{0} | Error sending APNSv2 message. \'{1}\'',
            OrderedDict([
                ('unique_key', unique_key),
                ('error_msg', type(ex).__name__),
            ]),
            logging.WARNING,
            device=device,
        )
    except Exception:
        log_middleware_information(
            '{0} | Error sending APNSv2 message',
            OrderedDict(
                unique_key=unique_key,
            ),
            logging.CRITICAL,
            device=device,
        )


# The APNSv2 connection. This connection can be shared among multiple threads.
# Don't use this directly but use `get_apns2_connection`.
apns2_connection = None


def get_apns2_connection(app, device, unique_key):
    """
    Get the active APNSv2 connection.

    This returns a reference to the global connection object,
    and initializes it if the connection was not yet made.

    Args:
        app (App): App requesting the connection.
        device (Device): Device requesting the connection.
        unique_key (str): Unique key used for logging.

    Returns:
        APNsClient.
    """
    global apns2_connection
    if apns2_connection is None:
        full_cert_path = os.path.join(settings.CERT_DIR, app.push_key)
        apns2_connection = APNsClient(full_cert_path, use_sandbox=True)
        log_middleware_information(
            '{0} | Opened new connection to APNSv2',
            OrderedDict([
                ('token', unique_key),
            ]),
            logging.INFO,
            device=device,
        )
    else:
        # Test the existing connection, will throw an exception if this fails.
        apns2_connection.connect()

    return apns2_connection


def send_fcm_message(device, app, message_type, data=None):
    """
    Function for sending a push message using firebase.
    """
    registration_id = device.token
    unique_key = device.token
    if message_type == TYPE_CALL:
        unique_key = data['unique_key']
        message = get_call_push_payload(
            unique_key,
            data['phonenumber'],
            data['caller_id'],
            data['attempt'],
        )
    elif message_type == TYPE_MESSAGE:
        message = get_message_push_payload(data['message'])
    else:
        log_middleware_information(
            '{0} | Trying to sent message of unknown type: {1}',
            OrderedDict([
                ('unique_key', unique_key),
                ('message_type', message_type),
            ]),
            logging.WARNING,
            device=device,
        )

    push_service = FCMNotification(api_key=app.push_key)

    try:
        start_time = time()
        result = push_service.notify_single_device(registration_id=registration_id, data_message=message)
    except AuthenticationError:
        log_middleware_information(
            '{0} | Our Google API key was rejected!!!',
            OrderedDict([
                ('unique_key', unique_key),
            ]),
            logging.ERROR,
            device=device,
        )
    except InternalPackageError:
        log_middleware_information(
            '{0} | Bad api request made by package.',
            OrderedDict([
                ('unique_key', unique_key),
            ]),
            logging.ERROR,
            device=device,
        )
    except FCMServerError:
        log_middleware_information(
            '{0} | FCM Server error.',
            OrderedDict([
                ('unique_key', unique_key),
            ]),
            logging.ERROR,
            device=device,
        )
    else:
        if result.get('success'):
            log_middleware_information(
                '{0} | FCM \'{1}\' message sent at time:{2} to {3}',
                OrderedDict([
                    ('unique_key', unique_key),
                    ('message_type', message_type),
                    ('sent_time', datetime.datetime.fromtimestamp(start_time).strftime('%H:%M:%S.%f')),
                    ('registration_id', registration_id),
                ]),
                logging.INFO,
                device=device,
            )

        if result.get('failure'):
            log_middleware_information(
                '{0} | Should remove {1} because {2}',
                OrderedDict([
                    ('unique_key', unique_key),
                    ('registration_id', registration_id),
                    ('results', result['results']),
                ]),
                logging.WARNING,
                device=device,
            )

        if result.get('canonical_ids'):
            log_middleware_information(
                '{0} | Should replace device token {1}',
                OrderedDict([
                    ('unique_key', unique_key),
                    ('registration_id', registration_id),
                ]),
                logging.WARNING,
                device=device,
            )


def send_gcm_message(device, app, message_type, data=None):
    """
    Send a Google Cloud Messaging message.
    """
    token_list = [device.token]
    unique_key = device.token

    key = '%d-cycle.key' % int(time())
    if message_type == TYPE_CALL:
        unique_key = data['unique_key']
        message = get_call_push_payload(
            unique_key,
            data['phonenumber'],
            data['caller_id'],
            data['attempt'],
        )
    elif message_type == TYPE_MESSAGE:
        message = get_message_push_payload(data['message'])
    else:
        log_middleware_information(
            '{0} | Trying to sent message of unknown type: {1}',
            OrderedDict([
                ('unique_key', unique_key),
                ('message_type', message_type),
            ]),
            logging.WARNING,
            device=device,
        )

    gcm = GCM(app.push_key)

    try:
        start_time = time()
        response = gcm.json_request(
            registration_ids=token_list,
            data=message,
            collapse_key=key,
            priority='high',
        )

        success = response.get('success')
        canonical = response.get('canonical')
        errors = response.get('errors')

        if success:
            for reg_id, msg_id in success.items():
                log_middleware_information(
                    '{0} | GCM \'{1}\' message sent at time:{2} to {3}',
                    OrderedDict([
                        ('unique_key', unique_key),
                        ('message_type', message_type),
                        ('sent_time', datetime.datetime.fromtimestamp(start_time).strftime('%H:%M:%S.%f')),
                        ('registration_id', reg_id),
                    ]),
                    logging.INFO,
                    device=device,
                )

        if canonical:
            for reg_id, new_reg_id in canonical.items():
                log_middleware_information(
                    '{0} | Should replace device token {1} with {2} in database',
                    OrderedDict([
                        ('unique_key', unique_key),
                        ('registration_id', reg_id),
                        ('new_registration_id', new_reg_id),
                    ]),
                    logging.WARNING,
                    device=device,
                )

        if errors:
            for err_code, reg_id in errors.items():
                log_middleware_information(
                    '{0} | Should remove {1} because {2}',
                    OrderedDict([
                        ('unique_key', unique_key),
                        ('registration_id', reg_id),
                        ('error_code', err_code),
                    ]),
                    logging.WARNING,
                    device=device,
                )

    except GCMAuthenticationException:
        # Stop and fix your settings.
        log_middleware_information(
            '{0} | Our Google API key was rejected!!!',
            OrderedDict([
                ('unique_key', unique_key),
            ]),
            logging.ERROR,
            device=device,
        )
    except ValueError:
        # Probably your extra options, such as time_to_live,
        # are invalid. Read error message for more info.
        log_middleware_information(
            '{0} | Invalid message/option or invalid GCM response',
            OrderedDict([
                ('unique_key', unique_key),
            ]),
            logging.ERROR,
            device=device,
        )
    except Exception:
        log_middleware_information(
            '{0} | Error sending GCM message',
            OrderedDict([
                ('unique_key', unique_key),
            ]),
            logging.CRITICAL,
            device=device,
        )
