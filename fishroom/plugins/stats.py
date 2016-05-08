#!/usr/bin/env python
# -*- coding:utf-8 -*-
from datetime import datetime, timedelta

from ..db import get_redis
from ..command import command
from ..models import Message
from ..helpers import get_now, tz
from ..chatlogger import ChatLogger
from .ratelimit import RateLimiter

rlimiter = RateLimiter()

r = get_redis()


@command("stats", desc="channel message statistics", usage="stats [days]")
def hualao(cmd, *args, **kwargs):
    if 'room' not in kwargs:
        return None
    room = kwargs['room']
    log_key_tmpl = ChatLogger.LOG_QUEUE_TMPL

    if rlimiter.check(room, cmd, period=30, count=2) is False:
        return

    days = 1

    if len(args) == 1:
        days = int(args[0])

    if days <= 0:
        return "stats: invalid days"

    days = min(days, 21)

    total = 0
    senders = set()
    today = get_now()
    day = today
    for _ in range(days):
        key = log_key_tmpl.format(date=day.strftime("%Y-%m-%d"), channel=room)
        senders.update(Message.loads(bmsg).sender for bmsg in r.lrange(key, 0, -1))
        total += r.llen(key)
        day -= timedelta(days=1)

    talked = len(senders)
    today_seconds = (today - datetime(today.year, today.month, today.day,
        0, 0, 0, 0, tz)).total_seconds()
    seconds = 86400 * (days - 1) + today_seconds

    avg_person = total / talked
    avg_second = total / seconds

    msg = "Total {} messages in the past {} days\n".format(total, days)
    msg += "Average {:.2f}/person, {:.2f}/second".format(avg_person, avg_second)

    return msg

# vim: ts=4 sw=4 sts=4 expandtab
