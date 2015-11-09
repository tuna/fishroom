#!/usr/bin/env python
# -*- coding:utf-8 -*-
from datetime import timedelta
from collections import Counter

from ..db import get_redis
from ..command import command
from ..models import Message
from ..helpers import get_now
from ..chatlogger import ChatLogger
from .ratelimit import RateLimiter

rlimiter = RateLimiter()

r = get_redis()


@command("hualao", desc="show top-n talkative individuals", usage="hualao [topn] [days]")
def hualao(cmd, *args, **kwargs):
    if 'room' not in kwargs:
        return None
    room = kwargs['room']
    log_key_tmpl = ChatLogger.LOG_QUEUE_TMPL

    if rlimiter.check(room, cmd, period=30, count=2) is False:
        return

    days = 7
    topn = 10

    if len(args) == 1:
        topn = int(args[0])
    elif len(args) == 2:
        topn, days = map(int, args)
    elif len(args) > 2:
        return "hualao: invalid arguments"

    if topn > 10:
        return "hualao: toooooo many hualaos"

    days = min(days, 21)

    c = Counter()
    today = get_now()
    for _ in range(days):
        key = log_key_tmpl.format(date=today.strftime("%Y-%m-%d"), channel=room)
        senders = [Message.loads(bmsg).sender for bmsg in r.lrange(key, 0, -1)]
        c.update(senders)
        today -= timedelta(days=1)

    hualaos = c.most_common(topn)
    most = hualaos[0][1]

    def to_star(n):
        return '⭐️' * round(5 * n / most) or '⭐️'

    head = "Most talkative {} individuals within {} days:\n".format(topn, days)
    return head + "\n".join(
        ["{}: {} {}".format(u, to_star(c), c) for u, c in hualaos])


# vim: ts=4 sw=4 sts=4 expandtab
