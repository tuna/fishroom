#!/usr/bin/env python3
from .helpers import get_now
from .config import config


class ChatLogger(object):

    LOG_QUEUE_TMPL = ":".join(
        [config["redis"]["prefix"], "log", "{channel}", "{date}"])
    CHANNEL = ":".join(
        [config["redis"]["prefix"], "msg_channel", "{channel}"])

    def __init__(self, redis_client):
        self.r = redis_client

    def log(self, channel, msg):
        chan = self.CHANNEL.format(channel=channel)
        self.r.publish(chan, msg.dumps())
        return self.r.rpush(self.key(channel), msg.dumps()) - 1

    def key(self, channel):
        return self.LOG_QUEUE_TMPL.format(
            channel=channel,
            date=get_now().strftime("%Y-%m-%d")
        )


# vim: ts=4 sw=4 sts=4 expandtab
