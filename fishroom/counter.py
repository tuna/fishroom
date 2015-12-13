#!/usr/bin/env python
from .config import config


class Counter(object):

    COUNTER_KEY = ":".join(
        [config["redis"]["prefix"], "counter", "{name}"])

    def __init__(self, redis_client, name):
        self.r = redis_client
        self.key = self.COUNTER_KEY.format(name=name)

    def incr(self, amount=1):
        return int(self.r.incr(self.key, amount))

# vim: ts=4 sw=4 sts=4 expandtab
