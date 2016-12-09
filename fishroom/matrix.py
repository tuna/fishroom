#!/usr/bin/env python3

from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError
from requests.exceptions import MissingSchema
from .bus import MessageBus, MsgDirection
from .base import BaseBotInstance, EmptyBot
from .models import Message, ChannelType, MessageType
from .helpers import get_now_date_time
from .config import config
import sys

class MatrixHandle(BaseBotInstance):

    ChanTag = ChannelType.Matrix

    def __init__(self, server, username, password, rooms, nick=None):
        client = MatrixClient(server)

        try:
            client.login_with_password(username, password)
        except MatrixRequestError as e:
            print(e)
            if e.code == 403:
                print("Bad username or password.")
                sys.exit(4)
            else:
                print("Check your server details are correct.")
                sys.exit(2)
        except MissingSchema as e:
            print("Bad URL format.")
            print(e)
            sys.exit(3)

        self.username = client.user_id
        print("logged in as: {}".format(self.username))

        if nick is not None:
            u = client.get_user(client.user_id)
            print("Setting display name to {}".format(nick))
            try:
                u.set_display_name(nick)
            except MatrixRequestError as e:
                print("Fail to set display name: error = {}".format(e))

        self.joined_rooms = {}
        self.room_id_to_alias = {}
        self.displaynames = {}

        for room_id_alias in rooms:
            try:
                room = client.join_room(room_id_alias)
            except MatrixRequestError as e:
                print(e)
                if e.code == 400:
                    print("Room ID/Alias in the wrong format")
                    sys.exit(11)
                else:
                    print("Couldn't find room {}".format(room_id_alias))
                    sys.exit(12)
            print("Joined room {}".format(room_id_alias))
            self.joined_rooms[room_id_alias] = room
            self.room_id_to_alias[room.room_id] = room_id_alias
            room.add_listener(self.on_message)

        self.client = client

    def on_message(self, room, event):
        if event['sender'] == self.username:
            return
        print("event received, type: {}".format(event['type']))
        if event['type'] == "m.room.member":
            if event['membership'] == "join":
                print("{0} joined".format(event['content']['displayname']))
        elif event['type'] == "m.room.message":
            sender = event['sender']
            if sender not in self.displaynames.keys():
                u_send = self.client.get_user(sender)
                self.displaynames[sender] = u_send.get_display_name()
            sender = self.displaynames[sender]

            if event['content']['msgtype'] == "m.text":
                print("{0}: {1}".format(sender, event['content']['body']))
                date, time = get_now_date_time()
                mtype = MessageType.Text
                msg = Message(
                    ChannelType.Matrix,
                    sender, self.room_id_to_alias[room.room_id],
                    event['content']['body'],
                    mtype=mtype, date=date, time=time)
                self.send_to_bus(self, msg)

    def send_to_bus(self, msg):
        raise NotImplementedError()

    def listen_message_stream(self):
        self.client.start_listener_thread()

    def send_msg(self, target, content, sender=None, first=False, **kwargs):
        target_room = self.joined_rooms[target]
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
        print(msg.dumps())
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
