#!/usr/bin/env python3

from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError
from requests.exceptions import MissingSchema
from .bus import MessageBus, MsgDirection
from .base import BaseBotInstance, EmptyBot
from .models import Message, ChannelType, MessageType
from .helpers import get_now_date_time, get_logger
from .config import config
import sys
import re

logger = get_logger("Matrix")

class MatrixHandle(BaseBotInstance):

    ChanTag = ChannelType.Matrix
    SupportMultiline = True

    def __init__(self, server, username, password, rooms, nick=None):
        client = MatrixClient(server)
        self.viewer_url = server.strip('/') + "/_matrix/media/v1/download/"

        try:
            client.login_with_password(username, password)
        except MatrixRequestError as e:
            if e.code == 403:
                logger.error("403 Bad username or password.")
                sys.exit(4)
            else:
                logger.error("{} Check your server details are correct.".format(e))
                sys.exit(2)
        except MissingSchema as e:
            logger.error("{} Bad URL format.".format(e))
            sys.exit(3)

        self.username = client.user_id
        logger.info("logged in as: {}".format(self.username))

        if nick is not None:
            u = client.get_user(client.user_id)
            logger.info("Setting display name to {}".format(nick))
            try:
                u.set_display_name(nick)
            except MatrixRequestError as e:
                logger.error("Fail to set display name: error = {}".format(e))

        self.joined_rooms = {}
        self.room_id_to_alias = {}
        self.displaynames = {}

        for room_id_alias in rooms:
            try:
                room = client.join_room(room_id_alias)
            except MatrixRequestError as e:
                if e.code == 400:
                    logger.error("400 Room ID/Alias in the wrong format")
                    sys.exit(11)
                else:
                    logger.error("{} Couldn't find room {}".format(e, room_id_alias))
                    sys.exit(12)
            logger.info("Joined room {}".format(room_id_alias))
            self.joined_rooms[room_id_alias] = room
            self.room_id_to_alias[room.room_id] = room_id_alias
            room.add_listener(self.on_message)

        self.client = client
        self.bot_msg_pattern = config['matrix'].get('bot_msg_pattern', None)

    def on_message(self, room, event):
        if event['sender'] == self.username:
            return
        logger.info("event received, type: {}".format(event['type']))
        if event['type'] == "m.room.member":
            if event['content']['membership'] == "join":
                logger.info("{0} joined".format(event['content']['displayname']))
        elif event['type'] == "m.room.message":
            sender = event['sender']
            opt = {'matrix': sender}
            if sender not in self.displaynames.keys():
                u_send = self.client.get_user(sender)
                self.displaynames[sender] = u_send.get_display_name()
            sender = self.displaynames[sender]

            msgtype = event['content']['msgtype']
            room_alias = self.room_id_to_alias[room.room_id]
            date, time = get_now_date_time()
            mtype = None
            media_url = None
            typedict = {
                    "m.image": MessageType.Photo,
                    "m.audio": MessageType.Audio,
                    "m.video": MessageType.Video,
                    "m.file": MessageType.File
            }
            if msgtype == "m.text" or msgtype == "m.notice":
                mtype = MessageType.Text
                msg_content = event['content']['body']
            elif msgtype == "m.emote":
                mtype = MessageType.Text
                msg_content = "*{}* {}".format(sender, event['content']['body'])
            elif msgtype in ["m.image", "m.audio", "m.video", "m.file"]:
                new_url = event['content']['url'].replace("mxc://", self.viewer_url)
                mtype = typedict[msgtype]
                msg_content = "{} ({})\n{}".format(new_url, mtype, event['content']['body'])
                media_url = new_url
            else:
                pass

            logger.info("[{}] {}: {}".format(room_alias, sender, event['content']['body']))
            if mtype is not None:
                msg = Message(
                    ChannelType.Matrix,
                    sender, room_alias, msg_content,
                    mtype=mtype, date=date, time=time,
                    media_url=media_url, opt=opt)
                self.send_to_bus(self, msg)

    def send_to_bus(self, msg):
        raise NotImplementedError()

    def listen_message_stream(self):
        self.client.start_listener_thread()

    def send_msg(self, target, content, sender=None, first=False, **kwargs):
        target_room = self.joined_rooms[target]
        if self.bot_msg_pattern is not None and re.match(self.bot_msg_pattern, content) is not None:
            target_room.send_text("{} sent the following message:".format(sender))
            target_room.send_text(content)
        else:
            target_room.send_text("[{}] {}".format(sender, content))

def Matrix2FishroomThread(mx: MatrixHandle, bus: MessageBus):
    if mx is None or isinstance(mx, EmptyBot):
        return

    def send_to_bus(self, msg):
        bus.publish(msg)

    mx.send_to_bus = send_to_bus
    mx.listen_message_stream()

def Fishroom2MatrixThread(mx: MatrixHandle, bus: MessageBus):
    if mx is None or isinstance(mx, EmptyBot):
        return
    for msg in bus.message_stream():
        mx.forward_msg_from_fishroom(msg)


def init():
    from .db import get_redis
    redis_client = get_redis()
    im2fish_bus = MessageBus(redis_client, MsgDirection.im2fish)
    fish2im_bus = MessageBus(redis_client, MsgDirection.fish2im)

    rooms = [b["matrix"] for _, b in config['bindings'].items() if "matrix" in b]
    server = config['matrix']['server']
    user = config['matrix']['user']
    password = config['matrix']['password']
    nick = config['matrix'].get('nick', None)

    return (
        MatrixHandle(server, user, password, rooms, nick),
        im2fish_bus, fish2im_bus,
    )


def main():
    if "matrix" not in config:
        return

    from .runner import run_threads
    bot, im2fish_bus, fish2im_bus = init()
    run_threads([
        (Matrix2FishroomThread, (bot, im2fish_bus, ), ),
        (Fishroom2MatrixThread, (bot, fish2im_bus, ), ),
    ])


def test():
    rooms = [b["matrix"] for _, b in config['bindings'].items()]
    server = config['matrix']['server']
    user = config['matrix']['user']
    password = config['matrix']['password']

    matrix_handle = MatrixHandle(server, user, password, rooms)

    def send_to_bus(self, msg):
        logger.info(msg.dumps())
    matrix_handle.send_to_bus = send_to_bus
    matrix_handle.process(block=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", default=False, action="store_true")
    args = parser.parse_args()

    if args.test:
        test()
    else:
        main()

# vim: ts=4 sw=4 sts=4 expandtab
