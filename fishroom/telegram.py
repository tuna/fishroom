#!/usr/bin/env python3
import json
import re
from socket import socket, AF_INET, SOCK_STREAM
from collections import namedtuple
from .base import BaseBotInstance
from .photostore import BasePhotoStore
from .textstore import BaseTextStore
from .models import Message, ChannelType, MessageType
from .helpers import timestamp_date_time, get_now_date_time
from .config import config


TeleMessage = namedtuple(
    'TeleMessage',
    ('user_id', 'username', 'chat_id', 'content', 'mtype', 'ts')
)

PhotoContext = namedtuple(
    'PhotoContext',
    ('user_id', 'username', 'chat_id', 'photo_id')
)


class InvalidMessage(Exception):
    pass


class BaseNickStore(object):
    """\
    Save nicknames for telegram
    """
    def get_nickname(self, user_id, username=None):
        pass

    def set_nickname(self, user_id, nickname):
        pass


class RedisNickStore(BaseNickStore):
    """\
    Save nicknames for telegram in redis

    Attributes:
        NICKNAME_KEY: redis key
        r: redis client
    """

    NICKNAME_KEY = config["redis"]["prefix"] + ":" + "telegram_nicks"

    def __init__(self, redis_client):
        self.r = redis_client

    def get_nickname(self, user_id, username=None):
        nick = self.r.hget(self.NICKNAME_KEY, user_id)
        if (not nick) and username:
            self.set_nickname(user_id, username)
            nick = username
        return nick or "tg-{}".format(user_id)

    def set_nickname(self, user_id, nickname):
        self.r.hset(self.NICKNAME_KEY, user_id, nickname)


class MemNickStore(BaseNickStore):
    """\
    Save nicknames for telegram in memory (volatile)
    """

    def __init__(self):
        self.usernicks = {}

    def get_nickname(self, user_id, username=None):
        nick = self.usernicks.get(user_id)
        if (not nick) and username:
            self.set_nickname(user_id, username)
            nick = username
        return nick or "tg-{}".format(user_id)

    def set_nickname(self, user_id, nickname):
        self.usernicks[user_id] = nickname


class Telegram(BaseBotInstance):

    ChanTag = ChannelType.Telegram

    def __init__(self, ip_addr='127.0.0.1', port='4444',
                 nick_store=None, photo_store=None, text_store=None):
        self._socket_init(ip_addr, port)
        self.main_session()
        if not isinstance(nick_store, BaseNickStore):
            raise Exception("Invalid Nickname storage")
        self.nick_store = nick_store
        self.photo_store = photo_store \
            if isinstance(photo_store, BasePhotoStore) else None
        self.photo_context = None  # PhotoContext if not None
        self.text_store = text_store \
            if isinstance(text_store, BaseTextStore) else None

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

    def send_msg(self, peer, msg):
        peer = peer.replace(' ', '_')
        cmd = 'msg ' + peer + ' ' + msg
        self._send_cmd(cmd)

    def send_user_msg(self, userid, msg):
        peer = 'user#' + str(userid)
        self.send_msg(peer, msg)

    def send_chat_msg(self, chatid, msg):
        peer = 'chat#' + str(chatid)
        self.send_msg(peer, msg)

    def download_photo(self, msg_id):
        self._send_cmd("load_photo" + ' ' + str(msg_id))

    def parse_msg(self, jmsg):
        """Parse message.

        Returns:
            TeleMessage(user_id, username, chat_id, content, mtype) if jmsg is normal
            None if else.
        """
        mtype = jmsg.get('event', None)
        ts = jmsg.get('date', None)

        if mtype == "message":
            from_info = jmsg["from"]
            user_id, username = from_info["id"], from_info.get("username", "")

            to_info = jmsg["to"]
            chat_id = to_info["id"] if to_info["type"] == "chat" else None

            if "text" not in jmsg:
                media_type = jmsg.get("media", {}).get("type", None)
                if media_type == "photo":
                    photo_id = jmsg["id"]
                    content = "[photo {}]".format(photo_id)
                    if self.photo_store is not None:
                        self.download_photo(photo_id)
                        self.photo_context = \
                            PhotoContext(user_id, username, chat_id, photo_id)
                else:
                    content = "[{}]".format(media_type)
            else:
                content = jmsg["text"]

            return TeleMessage(
                user_id=user_id, username=username,
                chat_id=chat_id, content=content,
                mtype=MessageType.Text, ts=ts,
            )

        elif mtype == "download":
            # should be `{'result': '/paht/to/image.jpg', 'type': 'download'}`
            filename = jmsg.get("result", None)
            if filename is None:
                return None
            if self.photo_context is None:
                return None

            url = self.photo_store.upload_image(filename)
            if url is None:
                return None

            ctx = self.photo_context
            self.photo_context = None

            return TeleMessage(
                user_id=ctx.user_id,
                username=ctx.username,
                chat_id=ctx.chat_id,
                content="{} (photo {})".format(url, ctx.photo_id),
                mtype=MessageType.Photo,
                ts=ts,
            )

        return None

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

    def handle_command(self, msg):
        # handle command
        user_id = msg.user_id
        target = "user#" + str(user_id)
        try:
            tmp = msg.content.split()
            cmd = tmp[0][1:].lower()
            args = tmp[1:]
        except:
            self.send_msg(target, "Invalid Command")
            return

        if cmd == "nick":
            nick = args[0]
            self.nick_store.set_nickname(user_id, nick)
            self.send_msg(target, "Changed nickname to '%s'" % nick)
        else:
            self.send_msg(
                target,
                "Invalid Command, user '.nick nickname'"
                "to change nickname."
            )

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
            if telemsg is None or telemsg.user_id in id_blacklist:
                continue

            if telemsg.chat_id is None and telemsg.content.startswith("."):
                self.handle_command(telemsg)
                continue

            nickname = self.nick_store.get_nickname(
                telemsg.user_id, telemsg.username)

            receiver = "chat#" + str(telemsg.chat_id)

            date, time = timestamp_date_time(telemsg.ts) \
                if telemsg.ts else get_now_date_time()

            if not self.text_store:
                yield Message(
                    ChannelType.Telegram,
                    nickname, receiver, telemsg.content, telemsg.mtype,
                    date=date, time=time,
                )
            else:
                # if too long, post to text_store
                if telemsg.content.count('\n') > 3:
                    text_url = self.text_store.new_paste(
                        telemsg.content, nickname)
                    yield Message(
                        ChannelType.Telegram,
                        nickname, receiver, text_url + " (long text)",
                        date=date, time=time,
                    )
                else:
                    for content in telemsg.content.split('\n'):
                        if re.match(r'^\s*$', content):
                            continue
                        yield Message(
                            ChannelType.Telegram,
                            nickname, receiver, content, telemsg.mtype,
                            date=date, time=time,
                        )


def TelegramThread(tg, bus):
    tele_me = int(config["telegram"]["me"])
    for msg in tg.message_stream(id_blacklist=[tele_me]):

        bus.publish(msg)


if __name__ == '__main__':
    from .photostore import VimCN
    from .textstore import Vinergy

    tele = Telegram('127.0.0.1', 27219, nick_store=MemNickStore(),
                    photo_store=VimCN(), text_store=Vinergy())
    # tele.send_msg('user#67655173', 'hello')
    for msg in tele.message_stream():
        print(msg.dumps())
