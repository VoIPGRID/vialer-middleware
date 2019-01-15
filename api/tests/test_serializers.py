import time

from django.test import TestCase

from ..serializers import (
    CallResponseSerializer,
    DeviceSerializer,
    IncomingCallSerializer,
    SipUserIdSerializer,
    TokenSerializer,
)


class TestTokenSerializer(TestCase):

    def setUp(self):
        self.serializer = TokenSerializer

    def test_required_fields(self):
        """
        Test if the token field is required.
        """
        data = {'no_token': 'blaat'}

        self.assertFalse(self.serializer(data=data).is_valid())

        data = {'token': 'blaat'}

        self.assertTrue(self.serializer(data=data).is_valid())

    def test_validation(self):
        """
        Test if validation is done right.
        """
        data = {'token': 'foo bar'}

        self.assertFalse(self.serializer(data=data).is_valid())


class TestSipUserIdSerializer(TestCase):

    def setUp(self):
        self.serializer = SipUserIdSerializer

    def test_required_fields(self):
        """
        Test if the sip_user_id field is required.
        """
        data = {'no_sip_user_id': '123456789'}

        self.assertFalse(self.serializer(data=data).is_valid())

        data = {'sip_user_id': '123456789'}

        self.assertTrue(self.serializer(data=data).is_valid())

    def test_validation(self):
        """
        Test if validation is done right.
        """
        data = {'sip_user_id': '1234567890986'}

        self.assertFalse(self.serializer(data=data).is_valid())


class TestRegisterDeviceSerializer(TestCase):

    def setUp(self):
        self.serializer = DeviceSerializer

    def test_required_fields(self):
        """
        Test if app_id, sip_user_id and token are required.
        """
        data = {
            'sip_user_id': '123456789',
            'token': 'blaat',
            'no_app_id': 'com.org.name',
        }

        self.assertFalse(self.serializer(data=data).is_valid())

        data = {
            'sip_user_id': '123456789',
            'token': 'blaat',
            'app': 'com.org.name',
        }

        self.assertTrue(self.serializer(data=data).is_valid())

    def test_default_sandbox_value(self):
        """
        Test if sandbox is default false when no value given.
        """
        data = {
            'sip_user_id': '123456789',
            'token': 'blaat',
            'app': 'com.org.name',
        }

        serializer = self.serializer(data=data)
        serializer.is_valid()

        sandbox = serializer.validated_data['sandbox']

        self.assertFalse(sandbox)

    def test_sandbox_value(self):
        """
        Test if sandbox is set to true when given.
        """
        data = {
            'sip_user_id': '123456789',
            'token': 'blaat',
            'app': 'com.org.name',
            'sandbox': 'True',
        }

        serializer = self.serializer(data=data)
        self.assertTrue(serializer.is_valid())

        sandbox = serializer.validated_data['sandbox']

        self.assertTrue(sandbox)


class TestCallResponseSerializer(TestCase):

    def setUp(self):
        self.serializer = CallResponseSerializer

    def test_required_fields(self):
        """
        Test if the unique_key and message_start_time fields are required.
        """
        now = time.time()

        data = {
            'no_unique_key': 'aghadgfagsdfjagsdjkfgakjdf',
            'message_start_time': now,
        }

        self.assertFalse(self.serializer(data=data).is_valid())

        data = {
            'unique_key': 'aghadgfagsdfjagsdjkfgakjdf',
            'no_message_start_time': '871926ahkjgjhkgf',
        }

        self.assertFalse(self.serializer(data=data).is_valid())

        data = {
            'unique_key': 'aghadgfagsdfjagsdjkfgakjdf',
            'message_start_time': now,
        }

        self.assertTrue(self.serializer(data=data).is_valid())


class TestIncomingCallSerializer(TestCase):

    def setUp(self):
        self.serializer = IncomingCallSerializer

    def test_required_fields(self):
        """
        Test if sip_user_id, caller_id and phonenumber are required.
        """
        data = {
            'sip_user_id': '123456789',
            'caller_id': 'aghadgfagsdfjagsdjkfgakjdf',
        }

        self.assertFalse(self.serializer(data=data).is_valid())

        data = {
            'sip_user_id': '123456789',
            'phonenumber': '0123456789',
        }

        self.assertTrue(self.serializer(data=data).is_valid())

        data = {
            'sip_user_id': '123456789',
            'caller_id': '',
            'phonenumber': '0123456789',
        }

        self.assertTrue(self.serializer(data=data).is_valid())

    def test_validation(self):
        """
        Test if validation is done right.
        """
        data = {
            'sip_user_id': '123456789',
            'caller_id': 'aghadgfagsdfjagsdjkfgakjdf',
            'phonenumber': '0123456789avb',
        }

        self.assertFalse(self.serializer(data=data).is_valid())
