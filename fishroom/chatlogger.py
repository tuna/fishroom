#!/usr/bin/env python3
import pytz
from datetime import datetime

from .config import config


class ChatLogger(object):

    LOG_QUEUE_TMPL = ":".join(
        [config["redis"]["prefix"], "log", "{target}", "{date}"])

    def __init__(self, redis_client, tz="utc"):
        self.r = redis_client
        self.tz = pytz.timezone(tz)

    def log(self, target, msg):
        self.r.rpush(self.key(target), msg.dumps())

    def key(self, target):
        return self.LOG_QUEUE_TMPL.format(
            target=target,
            date=datetime.now(tz=self.tz).strftime("%Y-%m-%d")
        )


# vim: ts=4 sw=4 sts=4 expandtab
