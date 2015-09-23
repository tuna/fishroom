#!/usr/bin/env python3


class BaseBotInstance(object):

    ChanTag = None

    def send_msg(self, target, content):
        pass

    def is_cmd(self, content):
        return content.startswith("/") and not content.startswith("//")

# vim: ts=4 sw=4 sts=4 expandtab
