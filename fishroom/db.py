#!/usr/bin/env python3
import redis
from .config import config

__dbctx = {}


def get_redis():
    if 'redis' not in __dbctx:
        if config['redis'].get('unix_socket_path') is not None:
            redis_client = redis.StrictRedis(
                unix_socket_path=config['redis']['unix_socket_path'])
        else:
            redis_client = redis.StrictRedis(
                host=config['redis']['host'], port=config['redis']['port'])

        __dbctx['redis'] = redis_client
    return __dbctx['redis']


# vim: ts=4 sw=4 sts=4 expandtab
