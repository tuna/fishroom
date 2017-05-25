#!/usr/bin/env python
# -*- coding:utf-8 -*-
from datetime import datetime, timedelta
from collections import Counter
from statistics import mean, stdev

from ..db import get_redis
from ..command import command
from ..models import Message
from ..helpers import get_now, tz, plural
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
    today = get_now()
    day = today
    c = Counter()
    for _ in range(days):
        key = log_key_tmpl.format(date=day.strftime("%Y-%m-%d"), channel=room)
        senders = [Message.loads(bmsg).sender for bmsg in r.lrange(key, 0, -1)]
        c.update(senders)
        day -= timedelta(days=1)

    today_seconds = (
        today - datetime(today.year, today.month, today.day, 0, 0, 0, 0, tz)
    ).total_seconds()

    seconds = 86400 * (days - 1) + today_seconds
    minutes = 1440 * (days - 1) + (today_seconds / 60)
    hours = 24 * (days - 1) + (today_seconds / 3600)

    mean_person = mean(c.values())
    std_person = stdev(c.values())

    total = sum(c.values())

    if total > seconds:
        time_average = total / seconds
        time_unit = "second"
    elif total > minutes:
        time_average = total / minutes
        time_unit = "minute"
    elif total > hours:
        time_average = total / hours
        time_unit = "hour"
    else:
        time_average = total / days
        time_unit = "day"

    msg = "Total {} in the past {}\n".format(
        plural(total, "message"), plural(days, "day"))
    msg += "Mean {:.2f} +/− {:.2f} per person , {:.2f} per {}".format(
        mean_person,
        std_person,
        time_average,
        time_unit
    )

    return msg

# vim: ts=4 sw=4 sts=4 expandtab
