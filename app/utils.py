import logging

from django.db.models import Avg, Max, Min
from logentries import LogentriesHandler

from .models import ResponseLog


LOG_SIP_USER_ID = 'sip_user_id'
LOG_CALLER_ID = 'caller_id'
LOG_CALL_TO = 'call_to'
LOG_CALL_FROM = 'call_from'
LOG_CONTACT = 'contact'
LOG_DIGEST_USERNAME = 'digest_username'
LOG_NONCE = 'nonce'
LOG_USERNAME = 'username'
LOG_EMAIL = 'email'

LOGENTRIES_HANDLERS = {}

django_logger = logging.getLogger('django')


def get_metrics(start_date, end_date, platform):
    """
    Function to get a dict with metrics for the given date range and platform.

    Args:
        start_date (date): Start date to get metrics for.
        end_date (date): End date to get metrics for.
        platform (string): Platform to get metrics for.

    Returns:
        Dict containing the metrics.
    """
    def _get_min(query):
        return query.aggregate(Min('roundtrip_time'))['roundtrip_time__min']

    def _get_max(query):
        return query.aggregate(Max('roundtrip_time'))['roundtrip_time__max']

    def _get_avg(query):
        return query.aggregate(Avg('roundtrip_time'))['roundtrip_time__avg']

    base_query = ResponseLog.objects.filter(
        platform=platform, date__range=(start_date, end_date)).order_by('roundtrip_time')
    total_count = base_query.count()

    percentile = int(total_count * 0.95)

    available_query = base_query.filter(available=True)
    available_count = available_query.count()
    avg_available = _get_avg(available_query[:percentile])
    min_available = _get_min(available_query[:percentile])
    max_available = _get_max(available_query[:percentile])

    not_available_query = base_query.filter(available=False)
    not_available_count = not_available_query.count()
    avg_not_available = _get_avg(not_available_query[:percentile])
    min_not_available = _get_min(not_available_query[:percentile])
    max_not_available = _get_max(not_available_query[:percentile])

    results = {
        'platform': platform,
        'start_date': start_date,
        'end_date': end_date,
        'total_count': total_count,
        'available': {
            'count': available_count,
            'avg': avg_available,
            'min': min_available,
            'max': max_available,
        },
        'not_available': {
            'count': not_available_count,
            'avg': avg_not_available,
            'min': min_not_available,
            'max': max_not_available,
        },
    }

    return results


def log_data_to_metrics_log(log_data, sip_user_id):
    """
    Function that handles logging data to the metrics log.

    Args:
        log_data (dict): The dict that is going to be logged.
        sip_user_id (str): The SIP user id linked to the log statement.
    """
    metrics_logger = logging.getLogger('metrics')
    metrics_logger.info('SIP_USER_ID: {} DATA: {}'.format(sip_user_id, log_data))


def log_middleware_information(log_statement, dict_with_variables, log_level, device=None):
    """
    Function that handles the logging for the middleware.

    Args:
        log_statement (str): The message to log.
        dict_with_variables (OrderedDict): OrderedDict that contains the
            variables we want to insert into the logging statement.
        log_level (int): The level on which to log.
        device (Device): The device for which we want to log to Logentries.
    """
    remote_logging_id = device.remote_logging_id if device and device.remote_logging_id else 'No remote logging ID'
    django_log_statement = fill_log_statement(log_statement, dict_with_variables)
    django_logger.log(log_level, '{0} - middleware - {1}'.format(remote_logging_id, django_log_statement))

    if device and device.remote_logging_id:
        log_statement = fill_log_statement(log_statement, dict_with_variables, anonymize=True)
        logentries_token = device.app.logentries_token
        log_to_logentries(log_statement, log_level, logentries_token, device, remote_logging_id)
        if device.app.partner_logentries_token:
            # Log to the Logentries environment of the partner with a different token.
            logentries_token = device.app.partner_logentries_token
            log_to_logentries(log_statement, log_level, logentries_token, device, remote_logging_id)


def log_to_logentries(log_statement, log_level, logentries_token, device, remote_logging_id):
    """
    Function that logs information to Logentries.

    Args:
        log_statement (str): The message to log.
        log_level (int): The level on which to log.
        logentries_token (str): The token of the logset in Logentries.
        device (Device): The device for which we want to log to Logentries.
        remote_logging_id (str): The remote logging id of the device.
    """
    if logentries_token not in LOGENTRIES_HANDLERS:
        LOGENTRIES_HANDLERS[logentries_token] = LogentriesHandler(logentries_token)

    if LOGENTRIES_HANDLERS[logentries_token].good_config:
        logentries_logger = logging.getLogger('logentries')
        logentries_logger.handlers = [LOGENTRIES_HANDLERS[logentries_token]]
        logentries_logger.log(log_level, '{0} - middleware - {1}'.format(remote_logging_id, log_statement))
    else:
        LOGENTRIES_HANDLERS.pop(logentries_token)
        log_statement = 'The logentries token is invalid - {0}'.format(device.app.app_id)
        django_logger.log(log_level, '{0} - middleware - {1}'.format(remote_logging_id, log_statement))


def fill_log_statement(log_statement, dict_with_variables, anonymize=False):
    """
    Function that anonymizes and inserts variables into log statements.

    Args:
        log_statement (str): The message to log.
        dict_with_variables (OrderedDict): OrderedDict that contains the
            variables we want to insert into the logging statement.
        anonymize (bool): Boolean to check if we want to anonymize.

    Returns:
        str: String containing the given variables.
    """
    anonymize_keys = [
        LOG_SIP_USER_ID,
        LOG_CALLER_ID,
        LOG_CALL_TO,
        LOG_CALL_FROM,
        LOG_CONTACT,
        LOG_DIGEST_USERNAME,
        LOG_NONCE,
        LOG_USERNAME,
        LOG_EMAIL,
    ]

    if anonymize:
        for key in dict_with_variables.keys():
            if key in anonymize_keys:
                dict_with_variables[key] = key.upper()

    list_with_variables = [dict_with_variables[x] for x in dict_with_variables]
    updated_log_statement = log_statement.format(*list_with_variables)
    return updated_log_statement
