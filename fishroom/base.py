#!/usr/bin/env python3
from .command import LEADING_CHARS


class BaseBotInstance(object):

    ChanTag = None
    SupportMultiline = False
    SupportPhoto = False

    def send_msg(self, target, content, sender=None, **kwargs):
        pass

    def send_photo(self, target, photo_data):
        pass

    def is_cmd(self, content):
        return (
            len(content) > 2
            and content[0] in LEADING_CHARS
            and content[1] not in LEADING_CHARS
        )

    def msg_tmpl(self, sender=None):
        return "{content}" if sender is None else "[{sender}] {content}"

# vim: ts=4 sw=4 sts=4 expandtab
