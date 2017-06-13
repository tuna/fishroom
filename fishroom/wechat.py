#!/usr/bin/env python3
# Using the ItChat web WeChat API (https://github.com/littlecodersh/itchat)
# to forward WeChat messages

import itchat
from itchat.content import TEXT,MAP,CARD,NOTE,SHARING,PICTURE,RECORDING,VOICE,ATTACHMENT,VIDEO,FRIENDS,SYSTEM

from requests.exceptions import MissingSchema
from .bus import MessageBus, MsgDirection
from .base import BaseBotInstance, EmptyBot
from .models import Message, ChannelType, MessageType
from .helpers import get_now_date_time, get_logger
from .config import config
import sys
from .db import get_redis
from .filestore import get_qiniu
from .photostore import Imgur, VimCN, BasePhotoStore
import io
import imghdr

logger = get_logger("WeChat")

# TODO: Do not use global variables if we have better solutions
wxHandle, wxRooms, wxRoomNicks, myUid = None, {}, {}, ''
photo_store = None


def upload_photo(data):
    global photo_store

    if not photo_store:
        return None, "No photo store available"

    url = photo_store.upload_image(filedata=data)
    if url is None:
        return None, "Failed to upload Image"

    return url, None


def log_message(msgtype, msg):
    logger.info(msgtype + " message.")
    logger.info(msg)


def handle_message(msg, content):
    global wxHandle, wxRooms, myUid
    room = msg["FromUserName"]
    nick = msg["ActualNickName"]
    if wxRooms.get(room) is None:
        logger.info("Not in rooms to forward!!!")
        return
    if msg["ActualUserName"] == myUid:
        logger.info("My own message:)")
        return

    date, time = get_now_date_time()
    fish_msg = Message(
        ChannelType.Wechat, nick, wxRooms[room], content,
        mtype=MessageType.Text, date=date, time=time)
    wxHandle.send_to_bus(wxHandle,fish_msg)


def wechatExit():
    global wxHandle, wxRoomNicks
    date, time = get_now_date_time()
    for i in list(wxRoomNicks.keys()):
        exit_msg = Message(
            ChannelType.Wechat, "_fishroom_", i, "Wechat is logged out!",
            mtype=MessageType.Text, date=date, time=time)
        wxHandle.send_to_bus(wxHandle, exit_msg)


@itchat.msg_register(TEXT, isFriendChat=False, isGroupChat=True, isMpChat=False)
def on_text_message(msg):
    log_message(TEXT, msg)
    content = msg["Content"]
    handle_message(msg, content)


@itchat.msg_register(MAP, isFriendChat=False, isGroupChat=True, isMpChat=False)
def on_map_message(msg):
    log_message(MAP, msg)
    content = "(Map message received)"
    handle_message(msg, content)


@itchat.msg_register(CARD, isFriendChat=False, isGroupChat=True, isMpChat=False)
def on_card_message(msg):
    log_message(CARD, msg)
    content = "(Card message received)"
    handle_message(msg, content)


@itchat.msg_register(NOTE, isFriendChat=False, isGroupChat=True, isMpChat=False)
def on_note_message(msg):
    log_message(NOTE, msg)
    content = "(Note message received)"
    handle_message(msg, content)


@itchat.msg_register(SHARING, isFriendChat=False, isGroupChat=True, isMpChat=False)
def on_sharing_message(msg):
    log_message(SHARING, msg)
    content = msg["Url"]
    handle_message(msg, content)


@itchat.msg_register(PICTURE, isFriendChat=False, isGroupChat=True, isMpChat=False)
def on_picture_message(msg):
    log_message(PICTURE, msg)
    dlfn = msg["Text"]
    filename = msg["FileName"]
    photo = dlfn()
    if len(photo) == 0:
        return
    url, err = upload_photo(photo)
    if url is None:
        logger.info("Failed to upload photo")
    else:
        handle_message(msg, url)


@itchat.msg_register(RECORDING, isFriendChat=False, isGroupChat=True, isMpChat=False)
def on_recording_message(msg):
    log_message(RECORDING, msg)
    content = "(Recording message received)"
    handle_message(msg, content)


@itchat.msg_register(VOICE, isFriendChat=False, isGroupChat=True, isMpChat=False)
def on_voice_message(msg):
    log_message(VOICE, msg)
    content = "(Voice message received)"
    handle_message(msg, content)


@itchat.msg_register(ATTACHMENT, isFriendChat=False, isGroupChat=True, isMpChat=False)
def on_attachment_message(msg):
    log_message(ATTACHMENT, msg)
    dlfn = msg["Text"]
    filename = msg["FileName"]
    att = dlfn()
    if len(att)==0:
        return
    url, err = upload_photo(att)
    if url is None:
        logger.info("Failed to upload attachment.")
    else:
        handle_message(msg, url)


@itchat.msg_register(VIDEO, isFriendChat=False, isGroupChat=True, isMpChat=False)
def on_video_message(msg):
    log_message(VIDEO, msg)
    content = "(Video message received)"
    handle_message(msg, content)


def wxdebug():
    # Test if these global variables are set
    global wxHandle, wxRooms, wxRoomNicks, myUid
    logger.info("Debugging...")
    logger.info(wxHandle)
    logger.info(wxRooms)
    logger.info(wxRoomNicks)
    logger.info(myUid)


class WechatHandle(BaseBotInstance):

    ChanTag = ChannelType.Wechat
    SupportMultiline = True
    SupportPhoto = True

    def __init__(self, roomNicks):
        global wxRooms, myUid
        itchat.auto_login(hotReload=True, enableCmdQR=2, exitCallback=wechatExit)
        all_rooms = itchat.get_chatrooms(update=True)
        for r in all_rooms:
            if r['NickName'] in roomNicks:
                wxRooms[r['UserName']] = r['NickName']
                wxRoomNicks[r['NickName']] = r['UserName']
                logger.info('Room {} found.'.format(r["NickName"]))
            else:
                logger.info('{}: {}'.format(r['UserName'], r['NickName']))

        friends = itchat.get_friends()
        myUid = friends[0]["UserName"]

    def send_to_bus(self, msg):
        raise NotImplementedError()

    def send_photo(self, target, photo_data, sender=None):
        ft = imghdr.what('', photo_data)
        if ft is None:
            return
        filename = "image." + ft
        data_io = io.BytesIO(photo_data)
        roomid = wxRoomNicks[target]
        if sender is not None:
            itchat.send(msg="{} sent a photo...".format(sender), toUserName=roomid)
        itchat.send_image(fileDir=filename, toUserName=roomid, file_=data_io)

    def send_msg(self, target, content, sender=None, first=False, **kwargs):
        logger.info("Sending message to " + target)
        roomid = wxRoomNicks[target]
        if sender is not None:
            itchat.send(msg="[{}] {}".format(sender,content), toUserName=roomid)
        else:
            itchat.send(content, toUserName=roomid)


def Wechat2FishroomThread(wx: WechatHandle, bus: MessageBus):
    if wx is None or isinstance(wx, EmptyBot):
        return

    def send_to_bus(self, msg):
        bus.publish(msg)

    wx.send_to_bus = send_to_bus


def Fishroom2WechatThread(wx: WechatHandle, bus: MessageBus):
    if wx is None or isinstance(wx, EmptyBot):
        logger.info("Error creating Fishroom2WechatThread")
        return
    for msg in bus.message_stream():
        logger.info("message opt from bus is: " + str(msg.opt))
        myid_chn = config[msg.channel].get("me")

        if msg.opt is not None:
            id_chn = msg.opt.get(msg.channel)

        if myid_chn is not None and myid_chn == id_chn:
            logger.info("message from " + id_chn + ", setting sender to None.")
            msg.sender = None
        wx.forward_msg_from_fishroom(msg)


def init():
    global photo_store, wxHandle
    redis_client = get_redis()

    provider = config['photo_store']['provider']
    if provider == "imgur":
        options = config['photo_store']['options']
        photo_store = Imgur(**options)
    elif provider == "vim-cn":
        photo_store = VimCN()
    elif provider == "qiniu":
        photo_store = get_qiniu(redis_client, config)

    im2fish_bus = MessageBus(redis_client, MsgDirection.im2fish)
    fish2im_bus = MessageBus(redis_client, MsgDirection.fish2im)

    roomNicks = [b["wechat"]
                for _, b in config['bindings'].items() if "wechat" in b]
    wxHandle = WechatHandle(roomNicks)

    return (
        wxHandle,
        im2fish_bus, fish2im_bus,
    )


def main():
    if "wechat" not in config:
        return

    from .runner import run_threads
    bot, im2fish_bus, fish2im_bus = init()
    wxdebug()
    # The two threads and itchat.run are all blocking,
    # so put all of them in run_threads
    run_threads([
        (Wechat2FishroomThread, (bot, im2fish_bus, ), ),
        (Fishroom2WechatThread, (bot, fish2im_bus, ), ),
        (itchat.run, (), )
    ])


def test():
    global wxHandle
    roomNicks = [b["wechat"] for _, b in config['bindings'].items()]
    wxHandle = WechatHandle(roomNicks)

    def send_to_bus(self, msg):
        logger.info(msg.dumps())
    wxHandle.send_to_bus = send_to_bus
    wxHandle.process(block=True)


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
