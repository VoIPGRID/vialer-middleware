import logging

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import (AuthenticationFailed, NotAuthenticated,
                                       ParseError, PermissionDenied)
import requests

from .exceptions import UnavailableException
from .serializers import SipUserIdSerializer

logger = logging.getLogger('django')


class VoipgridAuthentication(BaseAuthentication):
    """
    Custom authentication.
    """
    def _check_status_code(self, status_code):
        """
        Function for checking the status code.

        Args:
            status_code(int): That status code of a response.
        """
        if status_code == 200:
            return
        elif status_code == 401:
            raise AuthenticationFailed(detail=None)
        elif status_code == 403:
            raise PermissionDenied(detail=None)
        else:
            # Temporarily unavailable.
            logger.warning('Unsupported VG response code {0}'.format(status_code))
            raise UnavailableException(detail=None)

    def authenticate(self, request):
        """
        Function for authentication against VoIPGRID api.
        """
        if settings.TESTING:
            return (AnonymousUser, None)

        # Get auth headers.
        auth = get_authorization_header(request)

        if not auth:
            # Raises 'Authentication credentials were not provided'.
            raise NotAuthenticated(detail=None)

        # Serialize data to check for sip_user_id.
        serializer = SipUserIdSerializer(data=request.data)
        if not serializer.is_valid(raise_exception=False):
            logger.info('BAD REQUEST! Authentication failed due to invalid sip_user_id in data:\n\n{1}'.format(
                request.data,
            ))
            # This raises a bad request response.
            raise ParseError(detail=None)

        # Get sip_user_id.
        sip_user_id = serializer.validated_data['sip_user_id']

        # Created new headers with old auth data.
        headers = {'Authorization': auth}

        # Get user profile.
        response = requests.get(settings.VG_API_USER_URL, headers=headers)
        # Check status code.
        self._check_status_code(response.status_code)

        # Parse to json.
        json_response = response.json()

        # Get app account reference on systemuser.
        app_account_url = json_response['app_account']

        if not app_account_url:
            # Has no app account and thus no access to api.
            logger.info('No app account for systemuser {0} - {1}'.format(
                json_response['id'],
                json_response['email'],
                ))
            raise PermissionDenied(detail=None)

        # Get url for app account.
        app_account_api_url = settings.VG_API_BASE_URL + app_account_url

        # Get app account.
        response = requests.get(app_account_api_url, headers=headers)
        # Check status code.
        self._check_status_code(response.status_code)
        # Get account id.
        account_id = response.json()['account_id']

        # Compare account id to sip user id the request is meant for.
        if str(sip_user_id) != str(account_id):
            # Raise permissions denied.
            raise PermissionDenied(detail=None)

        # All good.
        return (AnonymousUser, None)

    def authenticate_header(self, request):
        return 'Basic'
