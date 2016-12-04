#!/usr/bin/env python3
import re
import os, sys
import signal
import threading
import time

from .base import EmptyBot
from .bus import MessageBus, MsgDirection
from .models import MessageType, Message
from .chatlogger import ChatLogger
from .textstore import Pastebin, Vinergy, RedisStore, ChatLoggerStore
# from .telegram_tg import TgTelegram, TgTelegramThread
from .api_client import APIClientManager
from .command import get_command_handler, parse_command
from .helpers import get_logger

from .config import config
from .db import get_redis



redis_client = get_redis()
msgs_from_im = MessageBus(redis_client, MsgDirection.im2fish)
msgs_to_im = MessageBus(redis_client, MsgDirection.fish2im)

chat_logger = ChatLogger(redis_client)
api_mgr = APIClientManager(redis_client)

logger = get_logger("Fishroom")


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


def main():
    load_plugins()
    text_store = init_text_store()
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
            logger.exception("failed to execute command: {}".format(cmd))

    for msg in msgs_from_im.message_stream():
        logger.info(msg)
        if msg.room is None:
            room, b = get_binding(msg)
            msg.room = room
        else:
            room = msg.room
            b = bindings.get(room, None)

        if b is None:
            continue

        # Deliver to api clients
        api_mgr.publish(msg)
        msg_id = chat_logger.log(room, msg)

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
            # bot replies will be furthor processed by this function
            msgs_from_im.publish(bot_msg)

        # attach routing infomation
        msg.route = {c: t for c, t in b.items()}

        # get url or for long text
        if (msg.content.count('\n') > 5 or
                len(msg.content.encode('utf-8')) >= 400):
            text_url = text_store.new_paste(
                msg.content, msg.sender,
                channel=room, date=msg.date, time=msg.time, msg_id=msg_id
            )

            if text_url is None:
                # Fail
                logger.error("Failed to publish text")
                continue

            msg.opt['text_url'] = text_url

        # push to IM
        msgs_to_im.publish(msg)


if __name__ == "__main__":
    main()


# vim: ts=4 sw=4 sts=4 expandtab
