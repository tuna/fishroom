#!/usr/bin/env python
# -*- coding:utf-8 -*-
import re
from ..models import MessageType
from ..command import command

url_regex = re.compile(r'https?://[^\s<>"]+')


@command("imglink", desc="set message type as image", usage="imglink <link>")
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
