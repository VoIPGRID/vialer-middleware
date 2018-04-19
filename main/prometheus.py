#!/usr/bin/env python
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

import sys
project_root = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..')
sys.path.append(project_root)

import django
django.setup()

import time
from random import randint, random

from django.conf import settings
from django.db import DatabaseError
from prometheus_client import Gauge, start_http_server
from redis import RedisError

from app.cache import RedisClusterCache
from app.models import GCM_PLATFORM, ResponseLog

MYSQL_HEALTH = Gauge('mysql_health', 'See if MySQL is still reachable through the ORM.')
REDIS_CLUSTER_CLIENT = RedisClusterCache()
REDIS_KEY = 'test_if_redis_works'
REDIS_HEALTH = Gauge('redis_health', 'See if Redis is still reachable.')


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
        time.sleep(10)
