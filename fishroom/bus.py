#!/usr/bin/env python
import typing
from enum import Enum

from .models import Message
from .config import config


class MsgDirection(Enum):
    im2fish = 1
    fish2im = 2


class MessageBus(object):

    CHANNELS = {
        MsgDirection.im2fish: config["redis"]["prefix"] + ":" + "im_msg_channel",
        MsgDirection.fish2im: config["redis"]["prefix"] + ":" + "fish_msg_channel",
    }

    def __init__(self, redis_client, direction: MsgDirection):
        self.r = redis_client
        self.d = direction

    @property
    def channel(self) -> str:
        return self.CHANNELS[self.d]

    def publish(self, msg: Message):
        self.r.publish(self.channel, msg.dumps())

    def message_stream(self) -> typing.Iterator[Message]:
        p = self.r.pubsub()
        p.subscribe(self.channel)
        for rmsg in p.listen():
            if rmsg is not None and rmsg['type'] == "message":
                yield Message.loads(rmsg['data'].decode('utf-8'))


# vim: ts=4 sw=4 sts=4 expandtab
