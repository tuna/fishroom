#!/usr/bin/env python3
import ssl
import time
import irc
import irc.client
import random
from .base import BaseBotInstance
from .models import Message, ChannelType, MessageType
from .helpers import get_now_date_time
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

        print("[IRC] connecting to {}:{}".format(server, port))
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
        content = self.filter_color(event.arguments[0])

        date, time = get_now_date_time()
        mtype = MessageType.Command \
            if self.is_cmd(content) \
            else MessageType.Text

        msg = Message(
            ChannelType.IRC, irc_nick, event.target, content,
            mtype=mtype, date=date, time=time
        )
        self.send_to_bus(self, msg)

    def on_pubmsg(self, conn, event):
        return self.on_privmsg(conn, event)

    def on_action(self, conn, event):
        irc_nick = event.source[:event.source.index('!')]
        if irc_nick in self.blacklist:
            return
        content = random.choice(('🐸', '❤️', '💊', '🈲')) + \
            " {} {}".format(irc_nick, event.arguments[0])
        date, time = get_now_date_time()
        mtype = MessageType.Event
        msg = Message(
            ChannelType.IRC, irc_nick, event.target, content,
            mtype=mtype, date=date, time=time
        )
        self.send_to_bus(self, msg)

    def on_nicknameinuse(self, conn, event):
        conn.nick(conn.get_nickname() + "_")

    def msg_tmpl(self, sender=None, color=None, reply_quote="", reply_to=""):
        if color and sender:
            return "\x03{color}[{sender}]\x0f {reply_quote}{content}"
        else:
            return "{content}" if sender is None else "[{sender}] {content}"

    def send_msg(self, target, content, sender=None, first=False, **kwargs):
        # color that fits both dark and light background
        color_avail = (2, 3, 4, 5, 6, 7, 10, 12, 13)
        color = None

        if sender:
            # color defined at http://www.mirc.com/colors.html
            # background_num = sum([ord(i) for i in sender]) % 16
            cidx = sum([ord(i) for i in sender]) % len(color_avail)
            foreground_num = color_avail[cidx]
            color = str(foreground_num)  # + ',' + str(background_num)

        tmpl = self.msg_tmpl(sender, color)
        reply_quote = ""
        if first and 'reply_text' in kwargs:
            reply_to = kwargs['reply_to']
            reply_text = kwargs['reply_text']
            if len(reply_text) > 6:
                reply_text = reply_text[:6] + '...'
            reply_quote = "\x0315「Re {reply_to}: {reply_text}」\x0f".format(
                reply_text=reply_text, reply_to=reply_to)

        msg = tmpl.format(sender=sender, content=content,
                          reply_quote=reply_quote, color=color)

        try:
            self.irc_conn.privmsg(target, msg)
        except irc.client.ServerNotConnectedError:
            print("[irc] Server not connected")
            self.irc_conn.reconnect()
        time.sleep(0.5)

    def send_to_bus(self, msg):
        raise Exception("Not implemented")

    @classmethod
    def filter_color(cls, msg):
        # filter \x01 - \x19 control seq
        # filter \x03{foreground}[,{background}] color string
        def char_iter(msg):
            state = "char"
            for x in msg:
                if state == "char":
                    if x == '\x03':
                        state = "color"
                        continue
                    if 0 < ord(x) <= 0x1f:
                        continue
                    yield x
                elif state == "color":
                    if '0' < x < '9':
                        continue
                    elif x == ',':
                        continue
                    else:
                        state = 'char'
                        yield x

        return ''.join(char_iter(msg))


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
