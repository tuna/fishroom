#!/usr/bin/env python3
import sleekxmpp
from .base import BaseBotInstance
from .models import Message, ChannelType


class XMPPHandle(sleekxmpp.ClientXMPP, BaseBotInstance):
    ChanTag = ChannelType.XMPP

    def __init__(self, server, port, jid, password, rooms, nick):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)

        self.rooms = rooms
        self.nick = nick

        self.add_event_handler("session_start", self.on_start)
        self.add_event_handler("groupchat_message", self.on_muc_message)

        self.register_plugin('xep_0045')  # Multi-User Chat
        self.register_plugin('xep_0199')  # XMPP Ping

        if not self.connect((server, port)):
            raise Exception("Unable to connect to XMPP server")

    def on_start(self, event):
        self.get_roster()
        self.send_presence()
        for room in self.rooms:
            self.plugin['xep_0045'].joinMUC(
                room, self.nick, wait=True)

    def on_muc_message(self, msg):
        if msg['mucnick'] != self.nick and msg['id']:
            msg = Message(ChannelType.XMPP,
                          msg['mucnick'], msg['from'].bare, msg['body'])
            self.send_to_bus(self, msg)

    def send_msg(self, target, content):
        self.send_message(mto=target, mbody=content, mtype='groupchat')

    def send_to_bus(self, msg):
        raise Exception("Not implemented")


def XMPPThread(xmpp_handle, bus):
    def send_to_bus(self, msg):
        bus.publish(msg)
    xmpp_handle.send_to_bus = send_to_bus
    xmpp_handle.process(block=True)


if __name__ == "__main__":
    from .config import config

    rooms = [b["xmpp"] for _, b in config['bindings'].items()]
    server = config['xmpp']['server']
    port = config['xmpp']['port']
    nickname = config['xmpp']['nick']
    jid = config['xmpp']['jid']
    password = config['xmpp']['password']

    xmpp_handle = XMPPHandle(server, port, jid, password, rooms, nickname)

    def send_to_bus(self, msg):
        print(msg.dumps())
    xmpp_handle.send_to_bus = send_to_bus
    xmpp_handle.process(block=True)

# vim: ts=4 sw=4 sts=4 expandtab
