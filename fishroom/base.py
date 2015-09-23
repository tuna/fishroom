#!/usr/bin/env python3
from .command import LEADING_CHARS


class BaseBotInstance(object):

    ChanTag = None
    SupportMultiline = False

    def send_msg(self, target, content):
        pass

    def is_cmd(self, content):
        return (
            len(content) > 2
            and content[0] in LEADING_CHARS
            and content[1] not in LEADING_CHARS
        )

# vim: ts=4 sw=4 sts=4 expandtab
