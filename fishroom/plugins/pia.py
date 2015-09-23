#!/usr/bin/env python2
# -*- coding:utf-8 -*-
from __future__ import print_function, division, unicode_literals
from ..command import command


@command("pia", desc="Pia somebody", usage="pia [name]")
def pia(cmd, *args, **kwargs):
    if len(args) == 0:
        # pia the bot
        msg = kwargs.get("msg", None)
        to = msg.sender if msg is not None else ""
        return "Pia ☆ ～ %s" % to
    elif len(args) == 1:
        return "Pia ☆ ～ %s" % args[0]
    elif len(args) > 1:
        return "Too many persons to Pia"

# vim: ts=4 sw=4 sts=4 expandtab
