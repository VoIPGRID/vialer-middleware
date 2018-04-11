from datetime import datetime, timedelta
import time
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase
from freezegun import freeze_time
from rest_framework.test import APIClient
from testfixtures import LogCapture

from app.models import App, Device, ResponseLog

from .utils import mocked_send_apns_message, mocked_send_fcm_message, ThreadWithReturn


class RegisterDeviceTest(TestCase):

    def setUp(self):
        super(RegisterDeviceTest, self).setUp()
        self.client = APIClient()

        self.ios_app, created = App.objects.get_or_create(platform='apns', app_id='com.voipgrid.vialer')
        self.android_app, created = App.objects.get_or_create(platform='android', app_id='com.voipgrid.vialer')
        self.data = {
            'name': 'test device',
            'token': 'a652aee84bdec6c2859eec89a6e5b1a42c400fba43070f404148f27b502610b6',
            'sip_user_id': '123456789',
            'os_version': '8.3',
            'client_version': '1.0',
            'app': 'com.voipgrid.vialer',
            'remote_logging_id': 'a1b2c3d4e5',
        }

        self.ios_url = '/api/apns-device/'
        self.android_url = '/api/android-device/'

    @mock.patch('app.push.send_apns_message', side_effect=mocked_send_apns_message)
    def test_register_apns_device(self, *mocks):
        """
        This tests more than its name suggests. It also tests, unregister,
        token update, sip_id update etc!
        """
        # New APNS registration.
        response = self.client.post(self.ios_url, self.data)
        self.assertEqual(response.status_code, 201, msg='Wrong status code for create')

        device = Device.objects.get(sip_user_id=self.data['sip_user_id'])

        # Register again.
        response = self.client.post(self.ios_url, self.data)
        self.assertEqual(response.status_code, 200, msg='Wrong status code for update')

        # Register other token
        self.data['token'] = 'b652aee84bdec6c2859eec89a6e5b1a42c400fba43070f404148f27b502610b6'
        response = self.client.post(self.ios_url, self.data)
        self.assertEqual(response.status_code, 200, msg='Wrong status code for update')

        # Check if change is stored.
        device = Device.objects.get(sip_user_id=self.data['sip_user_id'])
        self.assertEqual(device.name, self.data['name'], msg='Wrong value for name')
        self.assertEqual(device.token, self.data['token'], msg='Wrong value for token')
        self.assertEqual(device.os_version, self.data['os_version'], msg='Wrong value for os_version')
        self.assertEqual(device.client_version, self.data['client_version'], msg='Wrong value for client_version')

        # Check if linked app is correct one!
        self.assertEqual(device.app, self.ios_app, 'Wrong linked app!')
        self.assertEqual(device.app.platform, 'apns', 'Wrong value for platform!')
        self.assertEqual(device.app.app_id, 'com.voipgrid.vialer', 'Wrong value for app_id')

        # Register same token for other sip id (Which means update).
        self.data['sip_user_id'] = '234567890'
        response = self.client.post(self.ios_url, self.data)
        self.assertEqual(response.status_code, 201, msg='Must be a 200 because of updated')

        # Do unregister for changed token.
        response = self.client.delete(self.ios_url, {
            'token': 'b652aee84bdec6c2859eec89a6e5b1a42c400fba43070f404148f27b502610b6',
            'sip_user_id': '234567890',
            'app': self.data['app'],
        })
        self.assertEqual(response.status_code, 200, msg='Wrong status code for unregister, expected 200')

        # Check if old token is gone.
        response = self.client.delete(self.ios_url, {
            'token': 'b652aee84bdec6c2859eec89a6e5b1a42c400fba43070f404148f27b502610b6',
            'sip_user_id': '234567890',
            'app': self.data['app'],
        })
        self.assertEqual(response.status_code, 404, msg='Wrong status code for unregister, expected 404')

    @mock.patch('app.push.send_fcm_message', side_effect=mocked_send_fcm_message)
    def test_register_android_device(self, *mocks):
        """
        Test if android registration succeeds
        """
        response = self.client.post(self.android_url, self.data)
        self.assertEqual(response.status_code, 201, 'Update sip_id to android account failed!')

        device = Device.objects.get(sip_user_id=self.data['sip_user_id'])

        self.assertEqual(device.name, self.data['name'], msg='Wrong value for name')
        self.assertEqual(device.token, self.data['token'], msg='Wrong value for token')
        self.assertEqual(device.os_version, self.data['os_version'], msg='Wrong value for os_version')
        self.assertEqual(device.client_version, self.data['client_version'], msg='Wrong value for client_version')

        # Check if linked app is correct one!
        self.assertEqual(device.app, self.android_app, 'Wrong linked app!')
        self.assertEqual(device.app.platform, 'android', 'Wrong value for platform!')
        self.assertNotEqual(device.app.platform, 'apns', 'Indeed wrong value for platform!')
        self.assertEqual(device.app.app_id, 'com.voipgrid.vialer', 'Wrong value for app_id')

        # Do unregister for changed token.
        response = self.client.delete(self.android_url, {
            'token': self.data['token'],
            'sip_user_id': self.data['sip_user_id'],
            'app': self.data['app'],
        })
        self.assertEqual(response.status_code, 200, msg='Wrong status code for unregister, expected 200')

    def test_register_unexisting_app(self):
        """
        Test registration of an unexisting app
        """
        self.data['app'] = 'com.myapp.doesnotexists'
        response = self.client.post(self.ios_url, self.data)
        self.assertEqual(response.status_code, 404, msg='Wrong status code for create')

        response = self.client.post(self.android_url, self.data)
        self.assertEqual(response.status_code, 404, msg='Wrong status code for create')

    @mock.patch('app.push.send_fcm_message', side_effect=mocked_send_fcm_message)
    @mock.patch('app.push.send_apns_message', side_effect=mocked_send_apns_message)
    def test_switch_sip_ios_to_android(self, *mocks):
        """
        Test the switch a sip_user_id from an ios to an android client.
        """
        response = self.client.post(self.ios_url, self.data)
        self.assertEqual(response.status_code, 201, msg='Wrong status code for create')

        self.data['token'] = 'iosaee84bdec6c2859eec89a6e5b1a42c400fba43070f404148f27b502610b6'
        response = self.client.post(self.android_url, self.data)
        self.assertEqual(response.status_code, 200, msg='Wrong status code for update!')

        self.assertTrue(Device.objects.count() == 1, 'There should be only one updated device!')

    @mock.patch('app.push.send_apns_message', side_effect=mocked_send_apns_message)
    @mock.patch('app.push.send_fcm_message', side_effect=mocked_send_fcm_message)
    def test_switch_sip_android_to_ios(self, *mocks):
        """
        Test the switch a sip_user_id from an android to an ios client.
        """
        response = self.client.post(self.android_url, self.data)
        self.assertEqual(response.status_code, 201, msg='Wrong status code for update!')

        self.data['token'] = 'android4bdec6c2859eec89a6e5b1a42c400fba43070f404148f27b502610b6'
        response = self.client.post(self.ios_url, self.data)
        self.assertEqual(response.status_code, 200, msg='Wrong status code for create')

        self.assertTrue(Device.objects.count() == 1, 'There should be only one updated device!')


class IOSIncomingCallTest(TransactionTestCase):

    def setUp(self):
        super(IOSIncomingCallTest, self).setUp()
        self.client = APIClient()

        # URL's.
        self.response_url = '/api/call-response/'
        self.incoming_url = '/api/incoming-call/'

        self.ios_app, created = App.objects.get_or_create(platform='apns', app_id='com.voipgrid.vialer')

    @mock.patch('app.push.send_apns_message', side_effect=mocked_send_apns_message)
    def test_available_incoming_call(self, *mocks):
        """
        Test a call when the device is available (default).
        """
        call_data = {
            'sip_user_id': '123456789',
            'caller_id': 'Test name',
            'phonenumber': '0123456789',
        }

        # Call non existing device
        response = self.client.post(self.incoming_url, call_data)

        self.assertEqual(response.content, b'status=NAK')

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
        call_data['call_id'] = 'sduiqayduiryqwuioeryqwer76789'

        # Now the device exists, call it again in seperate thread.
        thread = ThreadWithReturn(target=self.client.post, args=(self.incoming_url, call_data))
        thread.start()

        # Simulate some wait-time before device responds.
        time.sleep(1.5)

        app_data = {
            'unique_key': call_data['call_id'],
            'message_start_time': time.time(),
        }
        # Send the fake response from device.
        self.client.post(self.response_url, app_data)

        # Wait for the incoming-call to finish.
        response = thread.join()

        # Check if incoming-call got accepted.
        self.assertEqual(response.content, b'status=ACK')
        self.assertEqual(cache.get('attempts'), 2)

    @mock.patch('app.push.send_apns_message', side_effect=mocked_send_apns_message)
    def test_not_available_incoming_call(self, *mocks):
        """
        Test a call when device is not available.
        """
        call_data = {
            'sip_user_id': '123456789',
            'caller_id': 'Test name',
            'phonenumber': '0123456789',
        }

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
        call_data['call_id'] = 'sduiqayduiryqwuioeryqwer76789'

        # Now the device exists, call it again in seperate thread.
        thread = ThreadWithReturn(target=self.client.post, args=(self.incoming_url, call_data))
        thread.start()

        # Simulate some wait-time before device responds.
        time.sleep(1.5)

        app_data = {
            'unique_key': call_data['call_id'],
            'message_start_time': time.time(),
            'available': 'False',
        }
        # Send the fake response from device.
        self.client.post(self.response_url, app_data)

        # Wait for the incoming-call to finish.
        response = thread.join()

        # Check if incoming-call got accepted.
        self.assertEqual(response.content, b'status=NAK')
        self.assertEqual(cache.get('attempts'), 2)

    @mock.patch('app.push.send_apns_message', side_effect=mocked_send_apns_message)
    def test_too_late_incoming_call(self, *mocks):
        """
        Test a call when device is too late.
        """
        call_data = {
            'sip_user_id': '123456789',
            'caller_id': 'Test name',
            'phonenumber': '0123456789',
        }

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
        call_data['call_id'] = 'sduiqayduiryqwuioeryqwer76789'

        # Start thread to simulate asteriks waiting for response.
        thread = ThreadWithReturn(target=self.client.post, args=(self.incoming_url, call_data))
        thread.start()

        too_late_time = time.time()
        # Wait the wait time + 1 second.
        too_late_wait_time = (settings.APP_PUSH_ROUNDTRIP_WAIT + 1000) / 1000

        # Simulate some too long wait time for device to respond.
        time.sleep(too_late_wait_time)

        app_data = {
            'unique_key': call_data['call_id'],
            'message_start_time': too_late_time,
        }

        # Send the fake response from device which should be too late.
        too_late_response = self.client.post(self.response_url, app_data)

        self.assertEqual(too_late_response.status_code, 404)

        # Wait for the incoming-call to finish.
        response = thread.join()

        # Check if incoming-call resulted in a NAK.
        self.assertEqual(response.content, b'status=NAK')
        self.assertEqual(cache.get('attempts'), 3)

    @mock.patch('app.push.send_apns_message', side_effect=mocked_send_apns_message)
    def test_log_to_db(self, *mocks):
        """
        Test a call when device is too late.
        """
        call_data = {
            'sip_user_id': '123456789',
            'caller_id': 'Test name',
            'phonenumber': '0123456789',
        }

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
        call_data['call_id'] = 'sduiqayduiryqwuioeryqwer76789'

        start_time = time.time()

        # Start thread to simulate asteriks waiting for response.
        thread = ThreadWithReturn(target=self.client.post, args=(self.incoming_url, call_data))
        thread.start()

        # Simulate some wait time for device to respond.
        time.sleep(1)

        app_data = {
            'unique_key': call_data['call_id'],
            'message_start_time': start_time,
        }

        # Send the fake response from device which should be too late.
        response = self.client.post(self.response_url, app_data)

        self.assertEqual(response.status_code, 202)

        # Wait for the incoming-call to finish.
        response = thread.join()

        # Check if incoming-call resulted in a ACK.
        self.assertEqual(response.content, b'status=ACK')

        # Wait 1 second to be sure the thread that writes to log is finished.
        time.sleep(1)

        # Get the amount of response log entries.
        log_count = ResponseLog.objects.filter(platform=self.ios_app.platform).count()

        # Check if there is a log entry.
        self.assertGreater(log_count, 0)


class AndroidIncomingCallTest(TransactionTestCase):

    def setUp(self):
        super(AndroidIncomingCallTest, self).setUp()
        self.client = APIClient()

        # URL's.
        self.response_url = '/api/call-response/'
        self.incoming_url = '/api/incoming-call/'

        self.android_app, created = App.objects.get_or_create(platform='android', app_id='com.voipgrid.vialer')

    @mock.patch('app.push.send_fcm_message', side_effect=mocked_send_fcm_message)
    def test_available_incoming_call(self, *mocks):
        """
        Test a call when the device is available (default).
        """
        call_data = {
            'sip_user_id': '123456789',
            'caller_id': 'Test name',
            'phonenumber': '0123456789',
        }

        # Call non existing device.
        response = self.client.post(self.incoming_url, call_data)
        self.assertEqual(response.content, b'status=NAK')

        two_weeks_ago = datetime.now() - timedelta(days=14)
        Device.objects.create(
            name='test device',
            token='a652aee84bdec6c2859eec89a6e5b1a42c400fba43070f404148f27b502610b6',
            sip_user_id='123456789',
            os_version='8.3',
            client_version='1.0',
            last_seen=two_weeks_ago,
            app=self.android_app,
        )
        call_data['call_id'] = 'asdr2378945auhfjkasdghf897eoiehajklh'

        # Now the device exists, call it again in seperate thread.
        thread = ThreadWithReturn(target=self.client.post, args=(self.incoming_url, call_data))
        thread.start()

        # Simulate some wait-time before device responds.
        time.sleep(1.5)

        app_data = {
            'unique_key': call_data['call_id'],
            'message_start_time': time.time(),
        }
        # Send the fake response from device.
        self.client.post(self.response_url, app_data)

        # Wait for the incoming-call to finish.
        response = thread.join()

        # Check if incoming-call got accepted.
        self.assertEqual(response.content, b'status=ACK')
        self.assertEqual(cache.get('attempts'), 2)

    @mock.patch('app.push.send_fcm_message', side_effect=mocked_send_fcm_message)
    def test_not_available_incoming_call(self, *mocks):
        """
        Test a call when device is not available.
        """
        call_data = {
            'sip_user_id': '123456789',
            'caller_id': 'Test name',
            'phonenumber': '0123456789',
        }

        two_weeks_ago = datetime.now() - timedelta(days=14)
        Device.objects.create(
            name='test device',
            token='a652aee84bdec6c2859eec89a6e5b1a42c400fba43070f404148f27b502610b6',
            sip_user_id='123456789',
            os_version='8.3',
            client_version='1.0',
            last_seen=two_weeks_ago,
            app=self.android_app,
        )
        call_data['call_id'] = 'asdr2378945auhfjkasdghf897eoiehajklh'

        # Now the device exists, call it again in seperate thread.
        thread = ThreadWithReturn(target=self.client.post, args=(self.incoming_url, call_data))
        thread.start()

        # Simulate some wait-time before device responds.
        time.sleep(1.5)

        app_data = {
            'unique_key': call_data['call_id'],
            'message_start_time': time.time(),
            'available': False,
        }
        # Send the fake response from device.
        self.client.post(self.response_url, app_data)

        # Wait for the incoming-call to finish.
        response = thread.join()

        # Check if incoming-call got accepted.
        self.assertEqual(response.content, b'status=NAK')
        self.assertEqual(cache.get('attempts'), 2)

    @mock.patch('app.push.send_fcm_message', side_effect=mocked_send_fcm_message)
    def test_too_late_incoming_call(self, *mocks):
        """
        Test a call when device is too late.
        """
        call_data = {
            'sip_user_id': '123456789',
            'caller_id': 'Test name',
            'phonenumber': '0123456789',
        }

        two_weeks_ago = datetime.now() - timedelta(days=14)
        Device.objects.create(
            name='test device',
            token='a652aee84bdec6c2859eec89a6e5b1a42c400fba43070f404148f27b502610b6',
            sip_user_id='123456789',
            os_version='8.3',
            client_version='1.0',
            last_seen=two_weeks_ago,
            app=self.android_app,
        )
        call_data['call_id'] = 'asdr2378945auhfjkasdghf897eoiehajklh'

        # Start thread to simulate asteriks waiting for response.
        thread = ThreadWithReturn(target=self.client.post, args=(self.incoming_url, call_data))
        thread.start()

        too_late_time = time.time()
        # Wait the wait time + 1 second.
        too_late_wait_time = (settings.APP_PUSH_ROUNDTRIP_WAIT + 1000) / 1000

        # Simulate some too long wait time for device to respond.
        time.sleep(too_late_wait_time)

        app_data = {
            'unique_key': call_data['call_id'],
            'message_start_time': too_late_time,
        }

        # Send the fake response from device which should be too late.
        too_late_response = self.client.post(self.response_url, app_data)

        self.assertEqual(too_late_response.status_code, 404)

        # Wait for the incoming-call to finish.
        response = thread.join()

        # Check if incoming-call resulted in a NAK.
        self.assertEqual(response.content, b'status=NAK')
        self.assertEqual(cache.get('attempts'), 3)

    @mock.patch('app.push.send_fcm_message', side_effect=mocked_send_fcm_message)
    def test_log_to_db(self, *mocks):
        """
        Test a call when device is too late.
        """
        call_data = {
            'sip_user_id': '123456789',
            'caller_id': 'Test name',
            'phonenumber': '0123456789',
        }

        two_weeks_ago = datetime.now() - timedelta(days=14)
        Device.objects.create(
            name='test device',
            token='a652aee84bdec6c2859eec89a6e5b1a42c400fba43070f404148f27b502610b6',
            sip_user_id='123456789',
            os_version='8.3',
            client_version='1.0',
            last_seen=two_weeks_ago,
            app=self.android_app,
        )
        call_data['call_id'] = 'asdr2378945auhfjkasdghf897eoiehajklh'

        start_time = time.time()

        # Start thread to simulate asteriks waiting for response.
        thread = ThreadWithReturn(target=self.client.post, args=(self.incoming_url, call_data))
        thread.start()

        # Simulate some wait time for device to respond.
        time.sleep(1)

        app_data = {
            'unique_key': call_data['call_id'],
            'message_start_time': start_time,
        }

        # Send the fake response from device which should be too late.
        response = self.client.post(self.response_url, app_data)

        self.assertEqual(response.status_code, 202)

        # Wait for the incoming-call to finish.
        response = thread.join()

        # Check if incoming-call resulted in a ACK.
        self.assertEqual(response.content, b'status=ACK')

        # Wait 1 second to be sure the thread that writes to log is finished.
        time.sleep(1)

        # Get the amount of response log entries.
        log_count = ResponseLog.objects.filter(platform=self.android_app.platform).count()

        # Check if there is a log entry.
        self.assertGreater(log_count, 0)


class HangupReasonTest(TestCase):
    def setUp(self):
        """
        Initialize the data we need for the tests.
        """
        super(HangupReasonTest, self).setUp()
        self.client = APIClient()

        self.ios_app, created = App.objects.get_or_create(platform='apns', app_id='com.voipgrid.vialer')
        Device.objects.create(
            name='test device',
            token='a652aee84bdec6c2859eec89a6e5b1a42c400fba43070f404148f27b502610b6',
            sip_user_id='123456789',
            os_version='8.3',
            client_version='1.0',
            app=self.ios_app,
        )
        self.data = {
            'sip_user_id': '123456789',
            'unique_key': 'sduiqayduiryqwuioeryqwer76789',
        }

        self.hangup_reason_url = '/api/hangup-reason/'

    @freeze_time('2018-01-01 12:00:00.133700')
    def test_if_the_reason_is_logged_correctly(self):
        """
        Test if the reason is logged correctly when doing a correct
        call.
        """
        self.data['reason'] = 'Device did not now answer'
        with LogCapture() as log:
            self.client.post(self.hangup_reason_url, self.data)
        log.check(
            (
                'django',
                'INFO',
                'No remote logging ID - middleware - sduiqayduiryqwuioeryqwer76789 | APNS Device ',
                'not available because: Device did not now answer on 12:00:00.133700',
            ),
        )

    def test_incorrect_sip_user_id_log(self):
        """
        Test if the warning message is logged when a wrong sip user id is given.
        """
        self.data['reason'] = 'Device did not now answer'
        self.data['sip_user_id'] = '987654321'
        with LogCapture() as log:
            self.client.post(self.hangup_reason_url, self.data)
        log.check(
            (
                'django',
                'WARNING',
                'No remote logging ID - middleware - sduiqayduiryqwuioeryqwer76789 | Failed to '
                'find a device for SIP_user_ID : 987654321',
            ),
            (
                'django.request',
                'WARNING',
                'Not Found: /api/hangup-reason/',
            ),
        )
