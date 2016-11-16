from django.test import TestCase
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from ..authentication import VoipgridAuthentication
from ..exceptions import UnavailableException


class VoipgridAuthenticationTestCase(TestCase):
    """
    Class to test the VG authentication.
    """
    def setUp(self):
        """
        Setup authentication class.
        """
        super(VoipgridAuthenticationTestCase, self).setUp()

        self.authentication = VoipgridAuthentication()

    def test_check_status_code(self):
        """
        Test status codes and exceptions raised.
        """
        # Step 1: Status code 200.
        self.authentication._check_status_code(200)

        # Step 2: Status code 401.
        with self.assertRaises(AuthenticationFailed):
            self.authentication._check_status_code(401)

        # Step 3: Status code 403.
        with self.assertRaises(PermissionDenied):
            self.authentication._check_status_code(403)

        # Step 4: Status code other than tested.
        with self.assertRaises(UnavailableException):
            self.authentication._check_status_code(500)
