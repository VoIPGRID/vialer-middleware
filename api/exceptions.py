from rest_framework.exceptions import APIException
from rest_framework.status import HTTP_503_SERVICE_UNAVAILABLE


class UnavailableException(APIException):
    status_code = HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Service temporarily unavailable, try again later.'
