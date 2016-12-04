#!/usr/bin/env python3
import re
from typing import Tuple
from .models import Message, MessageType, Color
from .helpers import download_file
from .command import LEADING_CHARS, parse_command


class BaseBotInstance(object):

    ChanTag = None
    SupportMultiline = False
    SupportPhoto = False

    def send_msg(self, target: str, content: str, sender=None, **kwargs):
        pass

    def send_photo(self, target: str, photo_data: bytes):
        pass

    @classmethod
    def is_cmd(self, content) -> bool:
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

    def msg_tmpl(self, sender=None) -> str:
        return "{content}" if sender is None else "[{sender}] {content}"

    def match_nickname_content(self, content: str) -> Tuple[str, str]:
        m = re.match(
            r'^\[(?P<nick>.+?)\] (?P<content>.*)',
            content, flags=re.UNICODE
        )
        return (m.group('nick'), m.group('content')) if m else (None, None)

    def forward_msg_from_fishroom(self, msg: Message):
        if self.ChanTag == msg.channel and (not msg.botmsg):
            return

        route = msg.route
        if route is None:
            return

        target = route.get(self.ChanTag.lower())
        if target is None:
            return

        if (msg.mtype == MessageType.Photo and self.SupportPhoto):
            if msg.media_url:
                photo_data, ptype = download_file(msg.media_url)
                if ptype is not None and ptype.startswith("image"):
                    self.send_photo(target, photo_data, sender=msg.sender)
                    return

        if msg.mtype == MessageType.Event:
            self.send_msg(target, msg.content, sender=None)
            return

        if self.SupportMultiline:
            sender = None if msg.botmsg else msg.sender
            self.send_msg(
                target, msg.content, sender=sender, rich_text=msg.rich_text,
                raw=msg, **msg.opt,
            )
            return

        # when the agent does not support multi-line text, prefer long text URL
        # to line-by-line content
        text_url = msg.opt.get('text_url', None)
        if text_url is not None:
            lines = [text_url + " (long text)", ]
        else:
            lines = msg.lines

        for i, line in enumerate(lines):
            sender = None if msg.botmsg else msg.sender
            self.send_msg(
                target, content=line, sender=sender, rich_text=msg.rich_text,
                first=(i == 0), raw=msg, **msg.opt,
            )


class EmptyBot(BaseBotInstance):
    ChanTag = "__NULL__"


# vim: ts=4 sw=4 sts=4 expandtab
