#!/usr/bin/env python2
# -*- coding:utf-8 -*-
from __future__ import print_function, division, unicode_literals
import re
from ..models import MessageType
from ..command import command

url_regex = re.compile(r'https?://[^\s<>"]+')


@command("imglink")
def pia(cmd, *args, **kwargs):
    msg = kwargs.get("msg", None)
    if msg is None:
        return
    candidates = url_regex.findall(msg.content)
    if len(candidates) == 0:
        return

    msg.mtype = MessageType.Photo
    msg.media_url = candidates[0]

# vim: ts=4 sw=4 sts=4 expandtab
