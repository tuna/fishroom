#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import json
import requests
import requests.exceptions
from collections import namedtuple
from .base import BaseBotInstance
from .photostore import BasePhotoStore
from .models import Message, ChannelType, MessageType
from .helpers import timestamp_date_time, get_now_date_time, webp2png
from .config import config

TeleMessage = namedtuple(
    'TeleMessage',
    ('user_id', 'username', 'chat_id', 'content', 'mtype', 'ts')
)


class BaseNickStore(object):
    """\
    Save nicknames for telegram
    """
    def get_nickname(self, user_id, username=None):
        return None

    def set_nickname(self, user_id, nickname):
        return None


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


class BaseStickerURLStore(object):

    def get_sticker(self, sticker_id):
        return None

    def set_sticker(self, sticker_id, url):
        return None


class RedisStickerURLStore(BaseStickerURLStore):
    """\
    Save sticker url for telegram in redis

    Attributes:
        STICKER_KEY: redis key
        r: redis client
    """

    STICKER_KEY = config["redis"]["prefix"] + ":" + "telegram_stickers"

    def __init__(self, redis_client):
        self.r = redis_client

    def get_sticker(self, sticker_id):
        return self.r.hget(self.STICKER_KEY, sticker_id)

    def set_sticker(self, sticker_id, url):
        self.r.hset(self.STICKER_KEY, sticker_id, url)


class Telegram(BaseBotInstance):

    ChanTag = ChannelType.Telegram

    _api_base_tmpl = "https://api.telegram.org/bot{token}"
    _file_base_tmpl = "https://api.telegram.org/file/bot{token}/"

    def __init__(self, token="", nick_store=None,
                 sticker_url_store=None, photo_store=None):
        self._token = token
        self.api_base = self._api_base_tmpl.format(token=token)
        self.file_base = self._file_base_tmpl.format(token=token)

        if not isinstance(nick_store, BaseNickStore):
            raise Exception("Invalid Nickname storage")
        self.nick_store = nick_store
        self.photo_store = photo_store \
            if isinstance(photo_store, BasePhotoStore) \
            else None
        self.sticker_url_store = sticker_url_store \
            if isinstance(sticker_url_store, BaseStickerURLStore) \
            else BaseStickerURLStore()

    def _must_post(self, api, data={}, timeout=10):
        try:
            r = requests.post(
                api,
                data=data,
                timeout=timeout,
            )
            return r
        except requests.exceptions.Timeout:
            print("Error: Timeout uploading to Telegram")
        except KeyboardInterrupt:
            raise
        except:
            import traceback
            traceback.print_exc()
        return None

    def _flush(self):
        """
        Flush unprocessed messages
        """
        print("[Telegram] Flushing messages")

        api = self.api_base + "/getUpdates"

        for retry in range(3):
            r = self._must_post(api)
            if r is not None:
                break
            if retry == 3:
                raise Exception("Telegram API Server Error")

        ret = json.loads(r.text)
        if ret["ok"] is True:
            updates = ret['result']
            if len(updates) == 0:
                return 0
            latest = updates[-1]
            return latest["update_id"] + 1

    def download_file(self, file_id):
        api = self.api_base + "/getFile"
        r = self._must_post(api, data={'file_id': file_id})
        if r is None:
            return
        ret = json.loads(r.text)
        if ret["ok"] is False:
            print("[Telegram] {}".format(ret["description"]))
            return
        file_path = ret["result"]["file_path"]
        file_url = self.file_base + file_path
        r = requests.get(file_url)
        if r.status_code == 200:
            return r.content

    def parse_jmsg(self, jmsg):
        from_info = jmsg["from"]
        user_id, username = from_info["id"], from_info.get("username", "")
        chat_id = jmsg["chat"]["id"]
        ts = jmsg["date"]

        if "text" in jmsg:
            content = jmsg["text"]
            mtype = MessageType.Text

        elif "photo" in jmsg:
            file_id = jmsg["photo"][-1]["file_id"]
            photo = self.download_file(file_id)
            if photo is not None:
                url = self.photo_store.upload_image(filedata=photo)
                content = url + " (photo)"
            else:
                content = "(teleboto Faild to download file)"
            mtype = MessageType.Photo

        elif "sticker" in jmsg:
            file_id = jmsg["sticker"]["file_id"]
            url = self.sticker_url_store.get_sticker(file_id)
            if url is None:
                sticker = self.download_file(file_id)
                if sticker is not None:
                    photo = webp2png(sticker)
                    url = self.photo_store.upload_image(filedata=photo)
                else:
                    url = "(teleboto Faild to download file)"
            content = url + " (sticker)"
            mtype = MessageType.Sticker

        elif "new_chat_title" in jmsg:
            content = "{} {} changed group name to {}".format(
                from_info["first_name"], from_info["last_name"],
                jmsg["new_chat_title"],
            )
            mtype = MessageType.Text
        else:
            content = "(unsupported message type)"
            mtype = MessageType.Text

        if "forward_from" in jmsg:
            ffrom = jmsg["forward_from"]
            content = content + " <forwarded from {} {}>".format(
                ffrom["first_name"], ffrom["last_name"])

        return TeleMessage(
            user_id=user_id, username=username,
            chat_id=chat_id, content=content,
            mtype=mtype, ts=ts,
        )

    def message_stream(self, id_blacklist=None):
        """\
        Iterator of messages.

        Yields:
            Fishroom Message instances
        """

        if isinstance(id_blacklist, (list, set, tuple)):
            id_blacklist = set(id_blacklist)
        else:
            id_blacklist = []

        api = self.api_base + "/getUpdates"
        offset = self._flush()

        while True:
            r = self._must_post(
                api,
                data={
                    'offset': offset, 'timeout': 10
                },
                timeout=15
            )
            if r is None:
                continue

            ret = json.loads(r.text)
            if ret["ok"] is False:
                print("[Telegram Error] {}".format(ret["description"]))
                continue

            for update in ret["result"]:
                offset = update["update_id"] + 1
                jmsg = update["message"]

                telemsg = self.parse_jmsg(jmsg)
                if telemsg is None or telemsg.user_id in id_blacklist:
                    continue

                nickname = self.nick_store.get_nickname(
                    telemsg.user_id, telemsg.username)

                receiver = "%d" % telemsg.chat_id

                date, time = timestamp_date_time(telemsg.ts) \
                    if telemsg.ts else get_now_date_time()

                yield Message(
                    ChannelType.Telegram,
                    nickname, receiver, telemsg.content, telemsg.mtype,
                    date=date, time=time,
                )

    def send_msg(self, peer, msg):
        api = self.api_base + "/sendMessage"

        data = {
            'chat_id': int(peer),
            'text': msg,
            'disable_web_page_preview': True,
        }
        self._must_post(api, data)


def TelegramThread(tg, bus):
    for msg in tg.message_stream():
        bus.publish(msg)


if __name__ == '__main__':
    from .photostore import VimCN

    tele = Telegram(config['telegram']['token'],
                    nick_store=MemNickStore(), photo_store=VimCN())
    # tele.send_msg('user#67655173', 'hello')
    for msg in tele.message_stream():
        print(msg.dumps())
        tele.send_msg(msg.receiver, msg.content)


# vim: ts=4 sw=4 sts=4 expandtab
