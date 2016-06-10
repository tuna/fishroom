#!/usr/bin/env python3
import re
import os, sys
import signal
import threading
import time

from .base import EmptyBot
from .bus import MessageBus
from .models import MessageType, Message, ChannelType
from .chatlogger import ChatLogger
from .counter import Counter
from .filestore import QiniuStore
from .photostore import Imgur, VimCN
from .textstore import Pastebin, Vinergy, RedisStore, ChatLoggerStore
from .telegram import (RedisNickStore, RedisStickerURLStore,
                       Telegram, TelegramThread)
# from .telegram_tg import TgTelegram, TgTelegramThread
from .irchandle import IRCHandle, IRCThread
from .xmpp import XMPPHandle, XMPPThread
from .gitter import Gitter, GitterThread
from .api_client import APIClientManager
from .command import get_command_handler, parse_command
from .helpers import download_file

from .config import config
from .db import get_redis


redis_client = get_redis()
message_bus = MessageBus(redis_client)
chat_logger = ChatLogger(redis_client)
api_mgr = APIClientManager(redis_client)
single_instances = {}


def load_plugins():
    from importlib import import_module
    for plugin in config['plugins']:
        module = ".plugins." + plugin
        import_module(module, package="fishroom")


def init_text_store():
    provider = config['text_store']['provider']
    if provider == "pastebin":
        options = config['text_store']['options']
        return Pastebin(**options)
    elif provider == "vinergy":
        return Vinergy()
    elif provider == "redis":
        return RedisStore(redis_client)
    elif provider == "chat_logger":
        return ChatLoggerStore()


def get_qiniu():
    if 'qiniu' not in config:
        return None

    if 'qiniu' not in single_instances:
        c = config['qiniu']
        counter = Counter(redis_client, 'qiniu')
        q = QiniuStore(
            c['access_key'], c['secret_key'], c['bucket'],
            counter, c['base_url'],
        )
        single_instances['qiniu'] = q

    return single_instances['qiniu']


def init_telegram():
    if "telegram" not in config:
        return EmptyBot()

    def photo_store_init():
        provider = config['photo_store']['provider']
        if provider == "imgur":
            options = config['photo_store']['options']
            return Imgur(**options)
        elif provider == "vim-cn":
            return VimCN()
        elif provider == "qiniu":
            return get_qiniu()

    nick_store = RedisNickStore(redis_client)
    sticker_url_store = RedisStickerURLStore(redis_client)
    photo_store = photo_store_init()
    file_store = None

    if "file_store" in config:
        provider = config["file_store"]["provider"]
        if provider == "qiniu":
            file_store = get_qiniu()

    return \
        Telegram(
            config["telegram"]["token"],
            sticker_url_store=sticker_url_store,
            nick_store=nick_store,
            photo_store=photo_store,
            file_store=file_store,
        )


def init_irc():
    if "irc" not in config:
        return EmptyBot()

    irc_channels = [b["irc"] for _, b in config['bindings'].items() if "irc" in b]
    server = config['irc']['server']
    port = config['irc']['port']
    nickname = config['irc']['nick']
    usessl = config['irc']['ssl']
    blacklist = config['irc']['blacklist']
    return IRCHandle(server, port, usessl, nickname, irc_channels, blacklist)


def init_xmpp():
    if "xmpp" not in config:
        return EmptyBot()

    rooms = [b["xmpp"] for _, b in config['bindings'].items() if "xmpp" in b]
    server = config['xmpp']['server']
    port = config['xmpp']['port']
    nickname = config['xmpp']['nick']
    jid = config['xmpp']['jid']
    password = config['xmpp']['password']
    return XMPPHandle(server, port, jid, password, rooms, nickname)


def init_gitter():
    if "gitter" not in config:
        return EmptyBot()

    rooms = [b["gitter"] for _, b in config['bindings'].items() if 'gitter' in b]
    token = config['gitter']['token']
    me = config['gitter']['me']

    return Gitter(token, rooms, me)


def ForwardingThread(channels, text_store):
    bindings = config['bindings']

    def get_binding(msg):
        for room, b in bindings.items():
            if msg.receiver == b.get(msg.channel.lower(), None):
                return room, b
        return (None, None)

    def try_command(msg):
        cmd, args = parse_command(msg.content)
        if cmd is None:
            msg.mtype = MessageType.Text
            return

        handler = get_command_handler(cmd)
        if handler is None:
            msg.mtype = MessageType.Text
            return

        try:
            return handler.func(cmd, *args, msg=msg, room=room)
        except:
            import traceback
            traceback.print_exc()

    for msg in message_bus.message_stream():
        send_back = False
        print(msg)
        if msg.room is None:
            room, b = get_binding(msg)
            msg.room = room
        else:
            room = msg.room
            b = bindings.get(room, None)

        if b is None:
            continue

        # print(msg, msg.room, len(msg.content.encode('utf-8')))

        # Deliver to api clients
        api_mgr.publish(msg)

        # Handle commands
        bot_reply = ""
        if msg.mtype == MessageType.Command:
            bot_reply = try_command(msg)

        if bot_reply:
            opt = None
            if isinstance(bot_reply, tuple) and len(bot_reply) == 2:
                bot_reply, opt = bot_reply
            bot_msg = Message(
                msg.channel, config.get("name", "bot"), msg.receiver,
                content=bot_reply, date=msg.date, time=msg.time,
                botmsg=True, room=room, opt=opt
            )
            message_bus.publish(bot_msg)

        msg_id = chat_logger.log(room, msg)
        # Event Message
        if msg.mtype == MessageType.Event:
            for c in channels:
                if c.ChanTag == msg.channel:
                    continue
                target = b.get(c.ChanTag.lower())
                if target is not None:
                    c.send_msg(target, msg.content, sender=None)
            continue

        # Other Message

        # msg from bot should be sent back to its channel
        if msg.botmsg:
            send_back = True

        if (msg.content.count('\n') > 5 or
                len(msg.content.encode('utf-8')) >= 400):
            text_url = text_store.new_paste(
                msg.content, msg.sender,
                channel=room, date=msg.date, time=msg.time, msg_id=msg_id
            )

            if text_url is None:
                # Fail
                print("Failed to publish text")
                continue
            # messages = msg
            contents = [text_url + " (long text)", ]
        else:
            contents = [
                line for line in msg.content.splitlines()
                if not re.match(r'^\s*$', line)
            ]

        for c in channels:
            if c.ChanTag == msg.channel and send_back is False:
                continue
            target = b.get(c.ChanTag.lower())
            if target is None:
                continue

            if (msg.mtype == MessageType.Photo and c.SupportPhoto):
                if msg.media_url:
                    photo_data, ptype = download_file(msg.media_url)
                    if ptype is not None and ptype.startswith("image"):
                        c.send_photo(target, photo_data, sender=msg.sender)
                        continue

            if c.SupportMultiline:
                sender = None if msg.botmsg else msg.sender
                c.send_msg(target, msg.content, sender=sender,
                           rich_text=msg.rich_text, raw=msg, **msg.opt)
                continue

            for i, line in enumerate(contents):
                sender = None if msg.botmsg else msg.sender
                c.send_msg(target, content=line, sender=sender,
                           rich_text=msg.rich_text, first=(i == 0),
                           raw=msg, **msg.opt)


def main():

    load_plugins()

    irchandle = init_irc()
    tghandle = init_telegram()
    xmpphandle = init_xmpp()
    text_store = init_text_store()
    gitter_handle = init_gitter()
    tasks = []

    DEAD = threading.Event()

    def die(f):
        def send_all(text):
            for adm_id in config["telegram"]["admin"]:
                try:
                    tghandle.send_msg(adm_id, text, escape=False)
                except:
                    pass

        def wrapper(*args, **kwargs):
            try:
                f(*args, **kwargs)
            except:
                print("[Traceback]")
                import traceback
                exc = traceback.format_exc()
                send_all("<code>%s</code>" % exc)
                print(exc)
                DEAD.set()

        return wrapper

    for target, args in (
        (TelegramThread, (tghandle, message_bus, ), ),
        (IRCThread, (irchandle, message_bus, ), ),
        (XMPPThread, (xmpphandle, message_bus, ), ),
        (GitterThread, (gitter_handle, message_bus, ), ),
        (
            ForwardingThread,
            ((tghandle, irchandle, xmpphandle, gitter_handle), text_store, ),
        ),
    ):
        t = threading.Thread(target=die(target), args=args)
        t.setDaemon(True)
        t.start()
        tasks.append(t)

    DEAD.wait()
    print("Everybody Died, I don't wanna live any more! T_T")
    os._exit(1)

if __name__ == "__main__":
    main()


# vim: ts=4 sw=4 sts=4 expandtab
