from threading import Thread


def mocked_send_apns_message(device, app, message_type, data=None):
    print('WORKED APNS')


def mocked_send_fcm_message(device, app, message_type, data=None):
    print('WORKED FCM')


class ThreadWithReturn(Thread):
    def __init__(self, *args, **kwargs):
        super(ThreadWithReturn, self).__init__(*args, **kwargs)

        self._return = None

    def run(self):
        if self._target:
            self._return = self._target(*self._args, **self._kwargs)

    def join(self, *args, **kwargs):
        super(ThreadWithReturn, self).join(*args, **kwargs)

        return self._return
