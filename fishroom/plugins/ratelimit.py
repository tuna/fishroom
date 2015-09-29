#!/usr/bin/env python
import pytz
from datetime import datetime

from ..db import get_redis
from ..config import config

tz = pytz.timezone(config.get("timezone", "utc"))


class RateLimiter(object):

    key = config["redis"]["prefix"] + ":rate_limit:{room}:{cmd}"

    def __init__(self):
        self.r = get_redis()

    def trigger(self, room, cmd):
        key = self.key.format(room=room, cmd=cmd)
        now_ts = datetime.now(tz=tz).strftime("%s")
        self.r.rpush(key, now_ts)

    def check(self, room, cmd, period=30, count=5):
        key = self.key.format(room=room, cmd=cmd)
        l = self.r.llen(key)
        if l < count:
            self.trigger(room, cmd)
            return True

        self.r.ltrim(key, -count, -1)
        first = int(self.r.lindex(key, 0))
        now_ts = int(datetime.now(tz=tz).strftime("%s"))
        if now_ts - first <= period:
            return False

        self.trigger(room, cmd)
        return True

# vim: ts=4 sw=4 sts=4 expandtab
