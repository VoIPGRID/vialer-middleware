from datetime import datetime, timedelta
import time
from unittest import mock

from django.conf import settings
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from app.models import App, Device

from .utils import mocked_send_apns_message, ThreadWithReturn


class IncomingCallPerformanceTest(TransactionTestCase):

    def setUp(self):
        super(IncomingCallPerformanceTest, self).setUp()
        self.client = APIClient()

        self.ios_app, created = App.objects.get_or_create(platform='apns', app_id='com.voipgrid.vialer')

        two_weeks_ago = datetime.now() - timedelta(days=14)
        Device.objects.create(
            name='test device',
            token='a652aee84bdec6c2859eec89a6e5b1a42c400fba43070f404148f27b502610b6',
            sip_user_id='123456789',
            os_version='8.3',
            client_version='1.0',
            last_seen=two_weeks_ago,
            app=self.ios_app,
        )

    @mock.patch('app.push.send_apns_message', side_effect=mocked_send_apns_message)
    def _execute_call(self, *mocks):
        call_data = {
            'sip_user_id': '123456789',
            'caller_id': 'Test name',
            'phonenumber': '0123456789',
            'call_id': 'sduiqayduiryqwuioeryqwer76789',
        }

        # Now the device exists, call it again in seperate thread.
        thread = ThreadWithReturn(target=self.client.post, args=('/api/incoming-call/', call_data))
        thread.start()

        # Simulate some wait-time before device responds.
        time.sleep(1)

        app_data = {
            'unique_key': call_data['call_id'],
            'message_start_time': time.time(),
        }
        # Send the fake response from device.
        self.client.post('/api/call-response/', app_data)

        # Wait for the incoming-call to finish.
        response = thread.join()

        # Check if incoming-call got accepted.
        self.assertEqual(response.content, b'status=ACK')

    def test_performance(self):
        iterations = int(settings.PERFORMANCE_TEST_ITERATIONS)

        run_time = 0
        for i in range(iterations):
            start = time.time()
            self._execute_call()
            end = time.time()
            run_time += end - start

        print('Ended in {0} with {1} iterations'.format(run_time, iterations))
