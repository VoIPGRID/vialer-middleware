from .decorators import threaded
from .models import ResponseLog
from .push import send_call_message, send_text_message


@threaded
def task_incoming_call_notify(device, unique_key, phonenumber, caller_id):
    """
    Threaded task to send a call push notification.
    """
    send_call_message(device, unique_key, phonenumber, caller_id)


@threaded
def task_notify_old_token(device, app):
    """
    Threaded task to send a text push notification.
    """
    msg = 'A other device has registered for the same account. You won\'t be reachable on this device'
    send_text_message(device, app, msg)


@threaded
def log_to_db(platform, roundtrip_time, available):
    """
    Log the info in a seperate thread to the DB to make sure the log write
    does not block the api requests.
    """
    ResponseLog.objects.create(
        platform=platform,
        roundtrip_time=roundtrip_time,
        available=available,
    )
