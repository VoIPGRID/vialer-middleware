from django.conf import settings
from rediscluster import StrictRedisCluster

DEFAULT_TIMEOUT = 300


class RedisClusterCache(object):
    """
    Class used for accessing the redis cluster used for caching.
    """
    def __init__(self):
        self.client = self._create_client()

    def _create_client(self):
        """
        Function to connect to the redis cluster and init the client.
        """
        server_list = settings.REDIS_SERVER_LIST.replace(" ", "").split(',')

        nodes = []
        for server in server_list:
            if ':' not in server:
                continue
            host, port = server.split(':')
            nodes.append({'host': host, 'port': port})

        return StrictRedisCluster(startup_nodes=nodes, decode_responses=True)

    def get(self, key):
        return self.client.get(key)

    def exists(self, key):
        return self.client.exists(key)

    def set(self, key, value, timeout=DEFAULT_TIMEOUT):
        self.client.set(key, value, timeout)
