#!/usr/bin/env python
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

import sys
project_root = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..')
sys.path.append(project_root)

import django
django.setup()

from ast import literal_eval
from random import randint, random
import time

from django.conf import settings
from django.db import DatabaseError
from prometheus_client import Counter, Gauge, start_http_server
from redis import RedisError

from app.cache import RedisClusterCache
from app.models import GCM_PLATFORM, ResponseLog


# JSON keys.
OS_KEY = 'os'
OS_VERSION_KEY = 'os_version'
APP_VERSION_KEY = 'app_version'
APP_STATUS_KEY = 'app_status'
MIDDLEWARE_UNIQUE_KEY = 'middleware_unique_key'
BLUETOOTH_AUDIO_KEY = 'bluetooth_audio'
BLUETOOTH_DEVICE_KEY = 'bluetooth_device'
NETWORK_KEY = 'network'
NETWORK_OPERATOR_KEY = 'network_operator'
NETWORK_SIGNAL_STRENGTH_KEY = 'network_signal_strength'
DIRECTION_KEY = 'direction'
CONNECTION_TYPE_KEY = 'connection_type'
CALL_SETUP_SUCCESSFUL_KEY = 'call_setup_successful'
CLIENT_COUNTRY_KEY = 'client_country'
CALL_ID_KEY = 'call_id'
LOG_ID_KEY = 'log_id'
TIME_TO_INITIAL_RESPONSE_KEY = 'time_to_initial_respone'
FAILED_REASON_KEY = 'failed_reason'

# Redis keys.
VIALER_CALL_SUCCESS_TOTAL_KEY = 'vialer_call_success_total'
VIALER_CALL_FAILURE_TOTAL_KEY = 'vialer_call_failure_total'
VIALER_HANGUP_REASON_TOTAL_KEY = 'vialer_heangup_reason_total'
VIALER_MIDDLEWARE_PUSH_NOTIFICATION_FAILED_TOTAL_KEY = 'vialer_middleware_push_notification_failed_total'

# Middleware health metrics.
MYSQL_HEALTH = Gauge('mysql_health', 'See if MySQL is still reachable through the ORM.')
REDIS_CLUSTER_CLIENT = RedisClusterCache()
REDIS_KEY = 'test_if_redis_works'
REDIS_HEALTH = Gauge('redis_health', 'See if Redis is still reachable.')

# Vialer call metrics.
VIALER_CALL_SUCCESS_TOTAL = Counter(
    VIALER_CALL_SUCCESS_TOTAL_KEY,
    'The amount of successful calls that were made using the Vialer app',
    ['os', 'os_version', 'app_version', 'network', 'connection_type', 'direction'],
)

VIALER_CALL_FAILURE_TOTAL = Counter(
    VIALER_CALL_FAILURE_TOTAL_KEY,
    'The amount of calls that failed during setup using the Vialer app',
    ['os', 'os_version', 'app_version', 'network', 'connection_type', 'direction', 'failed_reason'],
)

VIALER_HANGUP_REASON_TOTAL = Counter(
    VIALER_HANGUP_REASON_TOTAL_KEY,
    'The amount of calls that failed during the call using the Vialer app',
    ['os', 'os_version', 'app_version', 'network', 'connection_type', 'direction', 'failed_reason'],
)

VIALER_MIDDLEWARE_PUSH_NOTIFICATION_FAILED_TOTAL = Counter(
    VIALER_MIDDLEWARE_PUSH_NOTIFICATION_FAILED_TOTAL_KEY,
    'The amount of failed called due to the device not responding to a push notification',
    ['os', 'direction', 'failed_reason'],
)


def write_read_redis():
    """
    Write a key value to Redis to see if it is up

    Returns:
        bool: True if we can read and write to Redis
    """
    random_value = str(randint(1, 1000))

    try:
        REDIS_CLUSTER_CLIENT.set(REDIS_KEY, random_value)
    except RedisError:
        return False
    else:
        if REDIS_CLUSTER_CLIENT.get(REDIS_KEY) == random_value:
            REDIS_CLUSTER_CLIENT.client.delete(REDIS_KEY)
            return True
        return False


def write_read_orm():
    """
    Write a ResponseLog object to the database to see if it is up.

    Returns:
         bool: True if we can read and write using the ORM.
    """
    random_roundtrip = randint(1, 1000)
    random_available = random() > 0.5

    try:
        response_log = ResponseLog.objects.create(
            platform=GCM_PLATFORM,
            roundtrip_time=random_roundtrip,
            available=random_available,
        )
    except DatabaseError:
        return False
    else:
        if response_log.available == random_available and response_log.roundtrip_time == random_roundtrip:
            response_log.delete()
            return True
        return False


def increment_vialer_call_success_metric_counter():
    """
    Function that increments the vialer_call_success_total counter.
    """
    # Get the length of the list in redis.
    list_length = REDIS_CLUSTER_CLIENT.client.llen(VIALER_CALL_SUCCESS_TOTAL_KEY)

    # Get the values from the list in redis.
    data_list = REDIS_CLUSTER_CLIENT.client.lrange(VIALER_CALL_SUCCESS_TOTAL_KEY, 0, list_length)

    for value_str in data_list:
        # Parse the string to a dict.
        value_dict = literal_eval(value_str)
        VIALER_CALL_SUCCESS_TOTAL.labels(
            os=value_dict[OS_KEY],
            os_version=value_dict[OS_VERSION_KEY],
            app_version=value_dict[APP_VERSION_KEY],
            network=value_dict[NETWORK_KEY],
            connection_type=value_dict[CONNECTION_TYPE_KEY],
            direction=value_dict[DIRECTION_KEY],
        ).inc()

    # Trim the list, this means that the values that are outside
    # of the selected range are deleted. In this case we are keeping
    # all of the values we did not yet process in the list.
    REDIS_CLUSTER_CLIENT.client.ltrim(VIALER_CALL_SUCCESS_TOTAL_KEY, list_length, -1)


def increment_vialer_call_failure_metric_counter():
    """
    Function that increments the vialer_call_failure_total counter.
    """
    # Get the length of the list in redis.
    list_length = REDIS_CLUSTER_CLIENT.client.llen(VIALER_CALL_FAILURE_TOTAL_KEY)

    # Get the values from the list in redis.
    data_list = REDIS_CLUSTER_CLIENT.client.lrange(VIALER_CALL_FAILURE_TOTAL_KEY, 0, list_length)

    for value_str in data_list:
        # Parse the string to a dict.
        value_dict = literal_eval(value_str)
        VIALER_CALL_FAILURE_TOTAL.labels(
            os=value_dict[OS_KEY],
            os_version=value_dict[OS_VERSION_KEY],
            app_version=value_dict[APP_VERSION_KEY],
            network=value_dict[NETWORK_KEY],
            connection_type=value_dict[CONNECTION_TYPE_KEY],
            direction=value_dict[DIRECTION_KEY],
            failed_reason=value_dict[FAILED_REASON_KEY],
        ).inc()

    # Trim the list, this means that the values that are outside
    # of the selected range are deleted. In this case we are keeping
    # all of the values we did not yet process in the list.
    REDIS_CLUSTER_CLIENT.client.ltrim(VIALER_CALL_FAILURE_TOTAL_KEY, list_length, -1)


def increment_vialer_call_hangup_reason_metric_counter():
    """
    Function that increments the vialer_hangup_reason_total counter.
    """
    # Get the length of the list in redis.
    list_length = REDIS_CLUSTER_CLIENT.client.llen(VIALER_HANGUP_REASON_TOTAL_KEY)

    # Get the values from the list in redis.
    data_list = REDIS_CLUSTER_CLIENT.client.lrange(VIALER_HANGUP_REASON_TOTAL_KEY, 0, list_length)

    for value_str in data_list:
        # Parse the string to a dict.
        value_dict = literal_eval(value_str)
        VIALER_HANGUP_REASON_TOTAL.labels(
            os=value_dict[OS_KEY],
            os_version=value_dict[OS_VERSION_KEY],
            app_version=value_dict[APP_VERSION_KEY],
            network=value_dict[NETWORK_KEY],
            connection_type=value_dict[CONNECTION_TYPE_KEY],
            direction=value_dict[DIRECTION_KEY],
            failed_reason=value_dict[FAILED_REASON_KEY],
        ).inc()

    # Trim the list, this means that the values that are outside
    # of the selected range are deleted. In this case we are keeping
    # all of the values we did not yet process in the list.
    REDIS_CLUSTER_CLIENT.client.ltrim(VIALER_HANGUP_REASON_TOTAL_KEY, list_length, -1)


def increment_vialer_middleware_failed_push_notifications_metric_counter():
    """
    Function that increments the
    vialer_middleware_push_notification_failed_total counter.
    """
    # Get the length of the list in redis.
    list_length = REDIS_CLUSTER_CLIENT.client.llen(VIALER_MIDDLEWARE_PUSH_NOTIFICATION_FAILED_TOTAL_KEY)

    # Get the values from the list in redis.
    data_list = REDIS_CLUSTER_CLIENT.client.lrange(
        VIALER_MIDDLEWARE_PUSH_NOTIFICATION_FAILED_TOTAL_KEY,
        0,
        list_length,
    )

    for value_str in data_list:
        # Parse the string to a dict.
        value_dict = literal_eval(value_str)
        VIALER_MIDDLEWARE_PUSH_NOTIFICATION_FAILED_TOTAL.labels(
            os=value_dict[OS_KEY],
            direction=value_dict[DIRECTION_KEY],
            failed_reason=value_dict[FAILED_REASON_KEY],
        ).inc()

    # Trim the list, this means that the values that are outside
    # of the selected range are deleted. In this case we are keeping
    # all of the values we did not yet process in the list.
    REDIS_CLUSTER_CLIENT.client.ltrim(VIALER_MIDDLEWARE_PUSH_NOTIFICATION_FAILED_TOTAL_KEY, list_length, -1)


if __name__ == '__main__':
    try:
        start_http_server(int(settings.PROMETHEUS_PORT))
    except ValueError:
        print('Invalid port supplied, port needs to be a number.')

    while True:
        redis = write_read_redis()
        orm = write_read_orm()
        if redis:
            REDIS_HEALTH.set(1)
        else:
            REDIS_HEALTH.set(0)
        if orm:
            MYSQL_HEALTH.set(1)
        else:
            MYSQL_HEALTH.set(0)

        # Increment counters.
        increment_vialer_call_success_metric_counter()
        increment_vialer_call_failure_metric_counter()
        increment_vialer_call_hangup_reason_metric_counter()
        increment_vialer_middleware_failed_push_notifications_metric_counter()

        # Sleep before going for a new round.
        time.sleep(10)
