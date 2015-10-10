#!/usr/bin/env python3
import re
import threading

from .bus import MessageBus
from .models import MessageType, Message
from .chatlogger import ChatLogger
from .photostore import Imgur, VimCN
from .textstore import Pastebin, Vinergy, RedisStore, ChatLoggerStore
from .telegram import (RedisNickStore, RedisStickerURLStore,
                       Telegram, TelegramThread)
from .telegram_tg import TgTelegram, TgTelegramThread
from .irchandle import IRCHandle, IRCThread
from .xmpp import XMPPHandle, XMPPThread
from .api_client import APIClientManager
from .command import get_command_handler, parse_command
from .helpers import download_file

from .config import config
from .db import get_redis


redis_client = get_redis()
message_bus = MessageBus(redis_client)
chat_logger = ChatLogger(redis_client)
api_mgr = APIClientManager(redis_client)


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


def init_telegram():

    def photo_store_init():
        provider = config['photo_store']['provider']
        if provider == "imgur":
            options = config['photo_store']['options']
            return Imgur(**options)
        elif provider == "vim-cn":
            return VimCN()

    nick_store = RedisNickStore(redis_client)
    sticker_url_store = RedisStickerURLStore(redis_client)
    photo_store = photo_store_init()

    return (
        Telegram(
            config["telegram"]["token"],
            sticker_url_store=sticker_url_store,
            nick_store=nick_store,
            photo_store=photo_store,
        ),
        TgTelegram(
            config["telegram"]["server"], config["telegram"]["port"],
            nick_store=nick_store,
        ))


def init_irc():
    irc_channels = [b["irc"] for _, b in config['bindings'].items()]
    server = config['irc']['server']
    port = config['irc']['port']
    nickname = config['irc']['nick']
    usessl = config['irc']['ssl']
    blacklist = config['irc']['blacklist']
    return IRCHandle(server, port, usessl, nickname, irc_channels, blacklist)


def init_xmpp():
    rooms = [b["xmpp"] for _, b in config['bindings'].items()]
    server = config['xmpp']['server']
    port = config['xmpp']['port']
    nickname = config['xmpp']['nick']
    jid = config['xmpp']['jid']
    password = config['xmpp']['password']
    return XMPPHandle(server, port, jid, password, rooms, nickname)


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

        print(msg, msg.room, len(msg.content.encode('utf-8')))

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
                botmsg=True, opt=opt
            )
            message_bus.publish(bot_msg)

        msg_id = chat_logger.log(room, msg)
        # Event Message
        if msg.mtype == MessageType.Event:
            for c in channels:
                target = b[c.ChanTag.lower()]
                c.send_msg(target, msg.content, sender=None)
            continue

        # Other Message
        if msg.botmsg:
            send_back = True

        if (msg.content.count('\n') > 5
                or len(msg.content.encode('utf-8')) >= 400):
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
                line for line in msg.content.split("\n")
                if not re.match(r'^\s*$', line)
            ]

        for c in channels:
            if c.ChanTag == msg.channel and send_back is False:
                continue
            target = b.get(c.ChanTag.lower(), None)
            if target is None:
                continue

            if (msg.mtype == MessageType.Photo and c.SupportPhoto):
                if msg.media_url:
                    photo_data, ptype = download_file(msg.media_url)
                    ptype.startswith("image")
                    c.send_msg(target, "image", sender=msg.sender, **msg.opt)
                    c.send_photo(target, photo_data)
                    continue

            if c.SupportMultiline:
                sender = None if msg.botmsg else msg.sender
                c.send_msg(target, msg.content, sender=sender, **msg.opt)
                continue

            for line in contents:
                sender = None if msg.botmsg else msg.sender
                c.send_msg(target, content=line, sender=sender, **msg.opt)


def main():

    load_plugins()

    irchandle = init_irc()
    tghandle, tgtghandle = init_telegram()
    xmpphandle = init_xmpp()
    text_store = init_text_store()
    tasks = []

    for target, args in (
            (TelegramThread, (tghandle, message_bus), ),
            (TgTelegramThread, (tgtghandle, message_bus), ),
            (IRCThread, (irchandle, message_bus), ),
            (XMPPThread, (xmpphandle, message_bus), ),
            (
                ForwardingThread,
                ((tghandle, irchandle, xmpphandle, ), text_store, ),
            ),
    ):
        t = threading.Thread(target=target, args=args)
        t.setDaemon(True)
        t.start()
        tasks.append(t)

    for t in tasks:
        t.join()

if __name__ == "__main__":
    main()


# vim: ts=4 sw=4 sts=4 expandtab
