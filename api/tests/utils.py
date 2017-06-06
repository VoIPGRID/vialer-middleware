from threading import Thread

from django.core.cache import cache


def mocked_send_apns_message(device, app, message_type, data=None):
    cache.set('attempts', data.get('attempt', 1), 300)
    print('WORKED APNS')
    print(data.get('attempt', 1))


def mocked_send_fcm_message(device, app, message_type, data=None):
    cache.set('attempts', data.get('attempt', 1), 300)
    print('WORKED FCM')
    print(data.get('attempt', 1))


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
