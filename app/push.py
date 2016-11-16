import datetime
import logging
import os
from time import time
from urllib.parse import urljoin

from django.conf import settings

from apns_clerk import Session, APNs, Message
from gcm.gcm import GCM, GCMAuthenticationException
from pyfcm import FCMNotification
from pyfcm.errors import AuthenticationError, InternalPackageError, FCMServerError

from .models import APNS_PLATFORM, GCM_PLATFORM, ANDROID_PLATFORM

logger = logging.getLogger('django')


TYPE_CALL = 'call'
TYPE_MESSAGE = 'message'


def send_call_message(device, unique_key, phonenumber, caller_id):
    """
    Function to send the call push notification.

    Args:
        device (Device): A Device object.
        unique_key (string): String with the unique_key.
        phonenumber (string): Phonenumber that is calling.
        caller_id (string): ID of the caller.
    """
    data = {
        'unique_key': unique_key,
        'phonenumber': phonenumber,
        'caller_id': caller_id,
    }
    if device.app.platform == APNS_PLATFORM:
        send_apns_message(device, device.app, TYPE_CALL, data)
    elif device.app.platform == GCM_PLATFORM:
        send_gcm_message(device, device.app, TYPE_CALL, data)
    elif device.app.platform == ANDROID_PLATFORM:
        send_fcm_message(device, device.app, TYPE_CALL, data)
    else:
        logger.warning('{0} | Trying to sent \'call\' notification to unknown platform:{1} device:{2}'.format(
            unique_key, device.app.platform, device.token))


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
        logger.warning('Trying to sent \'message\' notification to unknown platform:{0} device:{1}'.format(
            app.platform, device.token))


def get_call_push_payload(unique_key, phonenumber, caller_id):
    """
    Function to create a dict used in the call push notification.

    Args:
        unique_key (string): The unique_key for the call.
        phonenumber (string): The phonenumber that is calling.
        caller_id (string): ID of the caller.

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
    token_list = [device.token]
    unique_key = device.token

    if message_type == TYPE_CALL:
        unique_key = data['unique_key']
        message = Message(token_list, payload=get_call_push_payload(unique_key, data['phonenumber'],
                                                                    data['caller_id']))
    elif message_type == TYPE_MESSAGE:
        message = Message(token_list, payload=get_message_push_payload(data['message']))
    else:
        logger.warning('{0} | TRYING TO SENT MESSAGE OF UNKNOWN TYPE: {1}', unique_key, message_type)

    session = Session()

    push_mode = settings.APNS_PRODUCTION
    if device.sandbox:
        # Sandbox push mode.
        push_mode = settings.APNS_SANDBOX

    full_cert_path = os.path.join(settings.CERT_DIR, app.push_key)

    con = session.get_connection(push_mode, cert_file=full_cert_path)
    srv = APNs(con)

    try:
        logger.info('{0} | Sending APNS \'{1}\' message at time:{2} to {3} Data:{4}'.
                    format(unique_key, message_type,
                           datetime.datetime.fromtimestamp(time()).strftime('%H:%M:%S.%f'), device.token, data))
        res = srv.send(message)

    except Exception:
        logger.exception('{0} | Error sending APNS message'.format(unique_key,))

    else:
        # Check failures. Check codes in APNs reference docs.
        for token, reason in res.failed.items():
            code, errmsg = reason
            # According to APNs protocol the token reported here
            # is garbage (invalid or empty), stop using and remove it.
            logger.warning('{0} | Sending APNS message failed for device: {1}, reason: {2}'.format(
                unique_key, token, errmsg)
            )

        # Check failures not related to devices.
        for code, errmsg in res.errors:
            logger.warning('{0} | Error sending APNS message. \'{1}\''.format(unique_key, errmsg))

        # Check if there are tokens that can be retried.
        if res.needs_retry():
            logger.info('{0} | Could not sent APNS message, retrying...')
            # Repeat with retry_message or reschedule your task.
            res.retry()


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
        )
    elif message_type == TYPE_MESSAGE:
        message = get_message_push_payload(data['message'])
    else:
        logger.warning('{0} | Trying to sent message of unknown type: {1}'.format(unique_key, message_type))

    push_service = FCMNotification(api_key=app.push_key)

    try:
        start_time = time()
        result = push_service.notify_single_device(registration_id=registration_id, data_message=message)
    except AuthenticationError:
        logger.error('{0} | Our Google API key was rejected!!!'.format(unique_key))
    except InternalPackageError:
        logger.error('{0} | Bad api request made by package.'.format(unique_key))
    except FCMServerError:
        logger.error('{0} | FCM Server error.'.format(unique_key))
    else:
        if result.get('success'):
            logger.info('{0} | FCM \'{1}\' message sent at time:{2} to {3} Data:{4}'
                        .format(unique_key,
                                message_type,
                                datetime.datetime.fromtimestamp(start_time).strftime('%H:%M:%S.%f'),
                                registration_id,
                                data,)
                        )

        if result.get('failure'):
            logger.warning('%s | Should remove %s because %s' % (unique_key, registration_id, result['results']))

        if result.get('canonical_ids'):
            logger.warning('%s | Should replace device token %s' % (unique_key, registration_id))


def send_gcm_message(device, app, message_type, data=None):
    """
    Send a Google Cloud Messaging message.
    """
    token_list = [device.token, ]
    unique_key = device.token

    key = "%d-cycle.key" % int(time())
    if message_type == TYPE_CALL:
        unique_key = data['unique_key']
        message = get_call_push_payload(
            unique_key,
            data['phonenumber'],
            data['caller_id'],
        )
    elif message_type == TYPE_MESSAGE:
        message = get_message_push_payload(data['message'])
    else:
        logger.warning('{0} | Trying to sent message of unknown type: {1}'.format(unique_key, message_type))

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
                logger.info('{0} | GCM \'{1}\' message sent at time:{2} to {3} Data:{4}'
                            .format(unique_key,
                                    message_type,
                                    datetime.datetime.fromtimestamp(start_time).strftime('%H:%M:%S.%f'),
                                    reg_id,
                                    data,)
                            )

        if canonical:
            for reg_id, new_reg_id in canonical.items():
                logger.warning('%s | Should replace device token %s with %s in database' % (
                               unique_key, reg_id, new_reg_id))

        if errors:
            for err_code, reg_id in errors.items():
                logger.warning(
                    '%s | Should remove %s because %s' % (unique_key, reg_id, err_code))

    except GCMAuthenticationException:
        # Stop and fix your settings.
        logger.error('{0} | Our Google API key was rejected!!!'.format(unique_key))
    except ValueError:
        # Probably your extra options, such as time_to_live,
        # are invalid. Read error message for more info.
        logger.error('{0} | Invalid message/option or invalid GCM response'.format(unique_key))
    except Exception:
        logger.exception('{0} | Error sending GCM message'.format(unique_key))
