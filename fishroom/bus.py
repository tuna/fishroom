#!/usr/bin/env python
from .models import Message
from .config import config


class MessageBus(object):

    CHANNEL = config["redis"]["prefix"] + ":" + "msg_channel"

    def __init__(self, redis_client):
        self.r = redis_client

    def publish(self, msg):
        self.r.publish(self.CHANNEL, msg.dumps())

    def message_stream(self):
        p = self.r.pubsub()
        p.subscribe(self.CHANNEL)
        for rmsg in p.listen():
            if rmsg is not None and rmsg['type'] == "message":
                yield Message.loads(rmsg['data'].decode('utf-8'))


# vim: ts=4 sw=4 sts=4 expandtab
