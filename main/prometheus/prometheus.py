#!/usr/bin/env python
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

import sys
project_root = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../../')
sys.path.append(project_root)

import django
django.setup()

from ast import literal_eval
from random import randint, random
import time

from django.conf import settings
from django.db import connection, DatabaseError
from prometheus_client import Counter, Gauge, start_http_server
from raven.contrib.django.models import client as raven_client
from redis import RedisError
from rediscluster.exceptions import RedisClusterException

from app.cache import RedisClusterCache
from app.models import GCM_PLATFORM, ResponseLog
from main.prometheus.consts import (
    ACTION_KEY,
    APP_VERSION_KEY,
    CONNECTION_TYPE_KEY,
    DIRECTION_KEY,
    FAILED_REASON_KEY,
    HANGUP_REASON_KEY,
    NETWORK_KEY,
    NETWORK_OPERATOR_KEY,
    OS_KEY,
    OS_VERSION_KEY,
    VIALER_CALL_FAILURE_TOTAL_KEY,
    VIALER_CALL_SUCCESS_TOTAL_KEY,
    VIALER_HANGUP_REASON_TOTAL_KEY,
    VIALER_MIDDLEWARE_INCOMING_CALL_FAILED_TOTAL_KEY,
    VIALER_MIDDLEWARE_INCOMING_CALL_SUCCESS_TOTAL_KEY,
    VIALER_MIDDLEWARE_PUSH_NOTIFICATION_FAILED_TOTAL_KEY,
    VIALER_MIDDLEWARE_PUSH_NOTIFICATION_SUCCESS_TOTAL_KEY)

# Middleware health metrics.
MYSQL_HEALTH = Gauge('mysql_health', 'See if MySQL is still reachable through the ORM.')
REDIS_CLUSTER_CLIENT = RedisClusterCache()
REDIS_HEALTH = Gauge('redis_health', 'See if Redis is still reachable.')
DOCKER_TAG = Counter('docker_tag', 'See which docker tag is running.', ['docker_tag'])

# Vialer call metrics.
VIALER_CALL_SUCCESS_TOTAL = Counter(
    VIALER_CALL_SUCCESS_TOTAL_KEY,
    'The amount of successful calls that were made using the Vialer app',
    ['os', 'os_version', 'app_version', 'network', 'network_operator', 'connection_type', 'direction'],
)

VIALER_CALL_FAILURE_TOTAL = Counter(
    VIALER_CALL_FAILURE_TOTAL_KEY,
    'The amount of calls that failed during setup using the Vialer app',
    ['os', 'os_version', 'app_version', 'network', 'connection_type', 'network_operator', 'direction',
     'failed_reason'],
)

VIALER_HANGUP_REASON_TOTAL = Counter(
    VIALER_HANGUP_REASON_TOTAL_KEY,
    'The amount of why a call was ended for the Vialer app',
    ['os', 'os_version', 'app_version', 'network', 'network_operator', 'connection_type', 'direction',
     'hangup_reason'],
)

VIALER_MIDDLEWARE_PUSH_NOTIFICATION_FAILED_TOTAL = Counter(
    VIALER_MIDDLEWARE_PUSH_NOTIFICATION_FAILED_TOTAL_KEY,
    'The amount of failed called due to the device not responding to a push notification',
    ['os', 'direction', 'failed_reason'],
)

VIALER_MIDDLEWARE_PUSH_NOTIFICATION_SUCCESS_TOTAL = Counter(
    VIALER_MIDDLEWARE_PUSH_NOTIFICATION_SUCCESS_TOTAL_KEY,
    'The amount of push notifications that were successful processed by the app',
    ['os', 'direction'],
)

VIALER_MIDDLEWARE_INCOMING_CALL_SUCCESS_TOTAL = Counter(
    VIALER_MIDDLEWARE_INCOMING_CALL_SUCCESS_TOTAL_KEY,
    'The amount of times an incoming call was presented at the middleware',
    ['os', 'action'],
)

VIALER_MIDDLEWARE_INCOMING_CALL_FAILED_TOTAL = Counter(
    VIALER_MIDDLEWARE_INCOMING_CALL_FAILED_TOTAL_KEY,
    'The amount of times an incoming call that were presented but couldn\'t be handled',
    ['os', 'action', 'failed_reason'],
)


def ping_redis():
    """
    Write a key value to Redis to see if it is up

    Returns:
        bool: True if we can read and write to Redis
    """
    result = REDIS_CLUSTER_CLIENT.execute_command('PING')
    for key, value in result.items():
        if value is False:
            return False
    return True


def write_read_orm():
    """
    Write a ResponseLog object to the database to see if it is up.

    Returns:
         bool: True if we can read and write using the ORM.
    """
    random_roundtrip = randint(1, 1000)
    random_available = random() > 0.5

    try:
        connection.ensure_connection()
    except:
        raven_client.captureException()
        return False

    try:
        response_log = ResponseLog.objects.create(
            platform=GCM_PLATFORM,
            roundtrip_time=random_roundtrip,
            available=random_available,
        )
    except DatabaseError:
        connection.close()

        raven_client.captureException()
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
            network_operator=value_dict.get(NETWORK_OPERATOR_KEY, ''),
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
            network_operator=value_dict.get(NETWORK_OPERATOR_KEY, ''),
            connection_type=value_dict[CONNECTION_TYPE_KEY],
            direction=value_dict[DIRECTION_KEY],
            failed_reason=value_dict[FAILED_REASON_KEY],
        ).inc()

    # Trim the list, this means that the values that are outside
    # of the selected range are deleted. In this case we are keeping
    # all of the values we did not yet process in the list.
    REDIS_CLUSTER_CLIENT.client.ltrim(VIALER_CALL_FAILURE_TOTAL_KEY, list_length, -1)


def increment_vialer_hangup_reason_metric_counter():
    """
        Function that increments the vialer_hangup_total counter.
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
            network_operator=value_dict.get(NETWORK_OPERATOR_KEY, ''),
            connection_type=value_dict[CONNECTION_TYPE_KEY],
            direction=value_dict[DIRECTION_KEY],
            hangup_reason=value_dict[HANGUP_REASON_KEY],
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


def increment_vialer_middleware_success_push_notifications_metric_counter():
    """
    Function that increments the
    vialer_middleware_push_notification_success_total counter.
    """
    # Get the length of the list in redis.
    list_length = REDIS_CLUSTER_CLIENT.client.llen(VIALER_MIDDLEWARE_PUSH_NOTIFICATION_SUCCESS_TOTAL_KEY)

    # Get the values from the list in redis.
    data_list = REDIS_CLUSTER_CLIENT.client.lrange(
        VIALER_MIDDLEWARE_PUSH_NOTIFICATION_SUCCESS_TOTAL_KEY,
        0,
        list_length,
    )

    for value_str in data_list:
        # Parse the string to a dict.
        value_dict = literal_eval(value_str)
        VIALER_MIDDLEWARE_PUSH_NOTIFICATION_SUCCESS_TOTAL.labels(
            os=value_dict[OS_KEY],
            direction=value_dict[DIRECTION_KEY],
        ).inc()

    # Trim the list, this means that the values that are outside
    # of the selected range are deleted. In this case we are keeping
    # all of the values we did not yet process in the list.
    REDIS_CLUSTER_CLIENT.client.ltrim(VIALER_MIDDLEWARE_PUSH_NOTIFICATION_SUCCESS_TOTAL_KEY, list_length, -1)


def increment_vialer_middleware_incoming_call_metric_counter():
    """
    Function that increments the
    vialer_middleware_incoming_call_total counter.
    """
    # Get the length of the list in redis.
    list_length = REDIS_CLUSTER_CLIENT.client.llen(VIALER_MIDDLEWARE_INCOMING_CALL_SUCCESS_TOTAL_KEY)

    # Get the values from the list in redis.
    data_list = REDIS_CLUSTER_CLIENT.client.lrange(
        VIALER_MIDDLEWARE_INCOMING_CALL_SUCCESS_TOTAL_KEY,
        0,
        list_length,
    )

    for value_str in data_list:
        # Parse the string to a dict.
        value_dict = literal_eval(value_str)
        VIALER_MIDDLEWARE_INCOMING_CALL_SUCCESS_TOTAL.labels(
            os=value_dict[OS_KEY],
            action=value_dict[ACTION_KEY],
        ).inc()

    # Trim the list, this means that the values that are outside
    # of the selected range are deleted. In this case we are keeping
    # all of the values we did not yet process in the list.
    REDIS_CLUSTER_CLIENT.client.ltrim(VIALER_MIDDLEWARE_INCOMING_CALL_SUCCESS_TOTAL_KEY, list_length, -1)


def increment_vialer_middleware_failed_incoming_call_metric_counter():
    """
        Function that increments the
        vialer_middleware_incoming_call_failed_total counter.
        """
    # Get the length of the list in redis.
    list_length = REDIS_CLUSTER_CLIENT.client.llen(VIALER_MIDDLEWARE_INCOMING_CALL_FAILED_TOTAL_KEY)

    # Get the values from the list in redis.
    data_list = REDIS_CLUSTER_CLIENT.client.lrange(
        VIALER_MIDDLEWARE_INCOMING_CALL_FAILED_TOTAL_KEY,
        0,
        list_length,
    )

    for value_str in data_list:
        # Parse the string to a dict.
        value_dict = literal_eval(value_str)
        VIALER_MIDDLEWARE_INCOMING_CALL_FAILED_TOTAL.labels(
            os=value_dict[OS_KEY],
            action=value_dict[ACTION_KEY],
            failed_reason=value_dict[FAILED_REASON_KEY],
        ).inc()

    # Trim the list, this means that the values that are outside
    # of the selected range are deleted. In this case we are keeping
    # all of the values we did not yet process in the list.
    REDIS_CLUSTER_CLIENT.client.ltrim(VIALER_MIDDLEWARE_INCOMING_CALL_FAILED_TOTAL_KEY, list_length, -1)


if __name__ == '__main__':
    try:
        start_http_server(int(settings.PROMETHEUS_PORT))
    except ValueError:
        print('Invalid port supplied, port needs to be a number.')

    is_redis_down = False
    DOCKER_TAG.labels(docker_tag=settings.DOCKER_TAG).inc()
    while True:
        redis = ping_redis()
        orm = write_read_orm()
        if redis:
            REDIS_HEALTH.set(1)
            is_redis_down = False
        else:
            REDIS_HEALTH.set(0)
        if orm:
            MYSQL_HEALTH.set(1)
        else:
            MYSQL_HEALTH.set(0)

        # Increment counters.
        try:
            increment_vialer_call_success_metric_counter()
            increment_vialer_call_failure_metric_counter()
            increment_vialer_hangup_reason_metric_counter()
            increment_vialer_middleware_failed_push_notifications_metric_counter()
            increment_vialer_middleware_success_push_notifications_metric_counter()
            increment_vialer_middleware_incoming_call_metric_counter()
            increment_vialer_middleware_failed_incoming_call_metric_counter()
        except (RedisError, RedisClusterException):
            # Log exception to Sentry each time Redis changes state.
            if not is_redis_down:
                raven_client.captureException()
                is_redis_down = True

        # Sleep before going for a new round.
        time.sleep(10)
