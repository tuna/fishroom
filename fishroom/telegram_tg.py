#!/usr/bin/env python3
import json
from socket import socket, AF_INET, SOCK_STREAM
from collections import namedtuple
from .base import BaseBotInstance
from .models import Message, ChannelType, MessageType
from .helpers import timestamp_date_time, get_now_date_time
from .telegram import BaseNickStore, MemNickStore
from .config import config


TeleMessage = namedtuple(
    'TeleMessage',
    ('msg_id', 'user_id', 'username', 'chat_id', 'content', 'mtype', 'ts',)
)


class TgTelegram(BaseBotInstance):

    ChanTag = ChannelType.Telegram

    def __init__(self, ip_addr='127.0.0.1', port='4444', nick_store=None):
        self._socket_init(ip_addr, port)
        self.main_session()
        if not isinstance(nick_store, BaseNickStore):
            raise Exception("Invalid Nickname storage")
        self.nick_store = nick_store

    def __del__(self):
        self.sock.close()

    def _socket_init(self, ip_addr, port):
        s = socket(AF_INET, SOCK_STREAM)
        s.connect((ip_addr, port))
        self.sock = s

    def _send_cmd(self, cmd):
        if '\n' != cmd[-1]:
            cmd += '\n'
        self.sock.send(cmd.encode())

    def main_session(self):
        self._send_cmd('main_session')

    def parse_msg(self, jmsg):
        """Parse message.

        Returns:
            TeleMessage(user_id, username, chat_id, content, mtype) if jmsg is normal
            None if else.
        """
        mtype = jmsg.get('event', None)
        ts = jmsg.get('date', None)

        if mtype == "message":
            msg_id = jmsg["id"]
            from_info = jmsg["from"]
            user_id, username = from_info["id"], from_info.get("username", "")

            to_info = jmsg["to"]
            chat_id = to_info["id"] if to_info["type"] == "chat" else None

            if "text" in jmsg:
                content = jmsg["text"]
                mtype = MessageType.Command \
                    if self.is_cmd(jmsg["text"]) \
                    else MessageType.Text

                return TeleMessage(
                    msg_id=msg_id, user_id=user_id, username=username,
                    chat_id=chat_id, content=content, mtype=mtype, ts=ts,
                )

    def recv_header(self):
        """Receive and parse message head like `ANSWER XXX\n`

        Returns:
            next message size
        """

        # states = ("ANS", "NUM")
        state = "ANS"
        ans = b""
        size = b""
        while 1:
            r = self.sock.recv(1)
            if state == "ANS":
                if r == b" " and ans == b"ANSWER":
                    state = "NUM"
                else:
                    ans = ans + r
            elif state == "NUM":
                if r == b"\n":
                    break
                else:
                    size = size + r

        return int(size) + 1

    def message_stream(self, id_blacklist=None):
        """Iterator of messages.

        Yields:
            Fishroom Message instances
        """
        if isinstance(id_blacklist, (list, set, tuple)):
            id_blacklist = set(id_blacklist)
        else:
            id_blacklist = []

        while True:
            buf_size = self.recv_header()

            ret = self.sock.recv(buf_size)

            if '' == ret:
                break

            if ret[-2:] != b"\n\n":
                print("Error: buffer receive failed")
                break

            try:
                jmsg = json.loads(ret[:-2].decode("utf-8"))
            except ValueError:
                print("Error parsing: ", ret[:-2])
            # pprint.pprint(msg)
            # return self.parse_msg(jmsg)

            telemsg = self.parse_msg(jmsg)
            if (telemsg is None or
                    telemsg.chat_id is None or
                    telemsg.user_id in id_blacklist):
                continue

            nickname = self.nick_store.get_nickname(
                telemsg.user_id, telemsg.username)

            receiver = str(-telemsg.chat_id)

            date, time = timestamp_date_time(telemsg.ts) \
                if telemsg.ts else get_now_date_time()

            yield Message(
                ChannelType.Telegram, nickname, receiver,
                telemsg.content, telemsg.mtype, date=date, time=time
            )


def TgTelegramThread(tg, bus):
    tele_me = [int(x) for x in config["telegram"]["me"]]
    for msg in tg.message_stream(id_blacklist=tele_me):
        if msg.mtype == MessageType.Command:
            continue
        bus.publish(msg)


if __name__ == '__main__':
    tele = TgTelegram('127.0.0.1', 27219, nick_store=MemNickStore())
    # tele.send_msg('user#67655173', 'hello')
    for msg in tele.message_stream():
        print(msg.dumps())
