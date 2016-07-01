#!/usr/bin/env python3
import re
from .command import LEADING_CHARS, parse_command


class BaseBotInstance(object):

    ChanTag = None
    SupportMultiline = False
    SupportPhoto = False

    def send_msg(self, target, content, sender=None, **kwargs):
        pass

    def send_photo(self, target, photo_data):
        pass

    @classmethod
    def is_cmd(self, content):
        if not (
            (len(content) > 2) and
            (content[0] in LEADING_CHARS) and
            (content[1] not in LEADING_CHARS)
        ):
            return False

        try:
            cmd, args = parse_command(content)
        except:
            return False
        return (cmd is not None)

    def msg_tmpl(self, sender=None):
        return "{content}" if sender is None else "[{sender}] {content}"

    def match_nickname_content(self, content):
        m = re.match(
            r'^\[(?P<nick>.+?)\] (?P<content>.*)',
            content, flags=re.UNICODE
        )
        return (m.group('nick'), m.group('content')) if m else (None, None)


class EmptyBot(BaseBotInstance):
    ChanTag = "__NULL__"


# vim: ts=4 sw=4 sts=4 expandtab
