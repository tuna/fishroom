#!/usr/bin/env python
# -*- coding:utf-8 -*-
from ..command import command
from .ratelimit import RateLimiter

rlimiter = RateLimiter()


@command("pia", desc="Pia somebody", usage="pia [name]")
def pia(cmd, *args, **kwargs):
    _pia = "Pia!<(=ｏ ‵-′)ノ☆ "
    room = kwargs.get('room', "ALL")
    if rlimiter.check(room, cmd, period=15, count=2) is False:
        return "Rate limited to " + _pia

    if len(args) == 0:
        # pia the bot
        msg = kwargs.get("msg", None)
        to = msg.sender if msg is not None else ""
        return "%s %s" % (_pia, to)
    elif len(args) == 1:
        return "%s %s" % (_pia, args[0])
    elif len(args) > 1:
        return "Too many persons to %s" % _pia

# vim: ts=4 sw=4 sts=4 expandtab
