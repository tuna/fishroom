#!/usr/bin/env python3
import ssl
import time
import irc
import irc.client
from .base import BaseBotInstance
from .models import Message, ChannelType
from .config import config


class IRCHandle(BaseBotInstance):
    """\
    Handle IRC connection
    """

    ChanTag = ChannelType.IRC

    def __init__(self, server, port, usessl, nickname, channels, blacklist=[]):
        irc.client.ServerConnection.buffer_class.errors = 'replace'

        self.nickname = nickname
        self.channels = channels
        self.blacklist = set(blacklist)

        self.reactor = irc.client.Reactor()
        self.irc_conn = self.reactor.server()
        if usessl:
            ssl_factory = irc.connection.Factory(wrapper=ssl.wrap_socket)
            self.irc_conn.connect(
                server, port, nickname, connect_factory=ssl_factory)
        else:
            self.irc_conn.connect(server, port, nickname)
        self.irc_conn.last_pong = time.time()
        self.reactor.execute_every(60, self.keep_alive_ping)

        for msg in ("welcome", "join", "privmsg", "pubmsg",
                    "action", "pong", "nicknameinuse"):
            self.irc_conn.add_global_handler(msg, getattr(self, "on_"+msg))

    def __del__(self):
        self.irc_conn.disconnect("I'll be back")

    def keep_alive_ping(self):
        try:
            if time.time() - self.irc_conn.last_pong > 360:
                raise irc.client.ServerNotConnectedError('ping timeout!')
                self.irc_conn.last_pong = time.time()
            self.irc_conn.ping(self.irc_conn.get_server_name())
        except irc.client.ServerNotConnectedError:
            print('[irc]  Reconnecting...')
            self.irc_conn.reconnect()
            self.irc_conn.last_pong = time.time()

    def on_pong(self, conn, event):
        conn.last_pong = time.time()
        # print('[irc]  PONG from: ', event.source)

    def on_welcome(self, conn, event):
        for c in self.channels:
            if irc.client.is_channel(c):
                conn.join(c)

    def on_join(self, conn, event):
        print('[irc] ', event.source + ' ' + event.target)

    def on_privmsg(self, conn, event):
        # print('[irc] ', event.source + ' ' + event.target + ' ' + event.arguments[0])

        irc_nick = event.source[:event.source.index('!')]
        if irc_nick in self.blacklist:
            return
        content = event.arguments[0]
        msg = Message(ChannelType.IRC, irc_nick, event.target, content)
        self.send_to_bus(self, msg)

    def on_pubmsg(self, conn, event):
        return self.on_privmsg(conn, event)

    def on_action(self, conn, event):
        return self.on_privmsg(conn, event)

    def on_nicknameinuse(self, conn, event):
        conn.nick(conn.get_nickname() + "_")

    def send_msg(self, target, msg):
        self.irc_conn.privmsg(target, msg)

    def send_to_bus(self, msg):
        raise Exception("Not implemented")


def IRCThread(irc_handle, bus):
    def send_to_bus(self, msg):
        bus.publish(msg)
    irc_handle.send_to_bus = send_to_bus
    irc_handle.reactor.process_forever(60)


if __name__ == '__main__':
    irc_channels = [b["irc"] for _, b in config['bindings'].items()]
    server = config['irc']['server']
    port = config['irc']['port']
    nickname = config['irc']['nick']
    usessl = config['irc']['ssl']

    irc_handle = IRCHandle(server, port, usessl, nickname, irc_channels)

    def send_to_bus(self, msg):
        print(msg.dumps())
    irc_handle.send_to_bus = send_to_bus
    irc_handle.reactor.process_forever(60)

# vim: ts=4 sw=4 sts=4 expandtab
