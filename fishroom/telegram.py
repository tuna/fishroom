#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import re
import json
import imghdr
import requests
import requests.exceptions
import mimetypes
from collections import namedtuple
from .base import BaseBotInstance
from .photostore import BasePhotoStore
from .filestore import BaseFileStore
from .models import Message, ChannelType, MessageType
from .helpers import timestamp_date_time, get_now_date_time, webp2png, md5
from .config import config

TeleMessage = namedtuple(
    'TeleMessage',
    ('msg_id', 'user_id', 'username', 'chat_id',
     'content', 'mtype', 'ts', 'media_url')
)


class BaseNickStore(object):
    """\
    Save nicknames for telegram
    """
    def get_nickname(self, user_id, username=None):
        return None

    def set_nickname(self, user_id, nickname):
        return None

    def set_username(self, nickname, username):
        return None

    def get_username(self, nickname):
        return None


class RedisNickStore(BaseNickStore):
    """\
    Save nicknames for telegram in redis

    Attributes:
        NICKNAME_KEY: redis key
        r: redis client
    """

    NICKNAME_KEY = config["redis"]["prefix"] + ":" + "telegram_nicks"
    USERNAME_KEY = config["redis"]["prefix"] + ":" + "telegram_usernames"

    def __init__(self, redis_client):
        self.r = redis_client

    def get_nickname(self, user_id, username=None):
        nick = self.r.hget(self.NICKNAME_KEY, user_id)
        if (not nick) and username:
            self.set_nickname(user_id, username)
            nick = username
        if nick and username:
            self.set_username(nick, username)
        nick = nick.decode('utf-8') if isinstance(nick, bytes) else nick
        return nick or "tg-{}".format(user_id)

    def set_nickname(self, user_id, nickname):
        self.r.hset(self.NICKNAME_KEY, user_id, nickname)

    def set_username(self, nickname, username):
        self.r.hset(self.USERNAME_KEY, nickname, username)

    def get_username(self, nickname):
        n = self.r.hget(self.USERNAME_KEY, nickname)
        return n.decode('utf-8') if isinstance(n, bytes) else n


class MemNickStore(BaseNickStore):
    """\
    Save nicknames for telegram in memory (volatile)
    """

    def __init__(self):
        self.usernicks = {}
        self.nickusers = {}

    def get_nickname(self, user_id, username=None):
        nick = self.usernicks.get(user_id)
        if (not nick) and username:
            self.set_nickname(user_id, username)
            nick = username
        if nick and username:
            self.set_username(nick, username)
        return nick or "tg-{}".format(user_id)

    def set_nickname(self, user_id, nickname):
        self.usernicks[user_id] = nickname

    def set_username(self, nickname, username):
        self.nickusers[nickname] = username

    def get_username(self, nickname):
        return self.nickusers.get(nickname, None)


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
        u = self.r.hget(self.STICKER_KEY, sticker_id)
        if u:
            return u.decode('utf-8')

    def set_sticker(self, sticker_id, url):
        self.r.hset(self.STICKER_KEY, sticker_id, url)


class Telegram(BaseBotInstance):

    ChanTag = ChannelType.Telegram
    SupportMultiline = True
    SupportPhoto = True

    _api_base_tmpl = "https://api.telegram.org/bot{token}"
    _file_base_tmpl = "https://api.telegram.org/file/bot{token}/"

    nickuser_regexes = [
        re.compile(r'(?P<pre>.*\s|^)@(?P<nick>\w+)(?P<post>.*)'),
        re.compile(r'(?P<pre>^)(?P<nick>\w+)(?P<post>:.*)'),
    ]

    def __init__(self, token="", nick_store=None,
                 sticker_url_store=None, photo_store=None, file_store=None):
        self._token = token
        self.api_base = self._api_base_tmpl.format(token=token)
        self.file_base = self._file_base_tmpl.format(token=token)

        if not isinstance(nick_store, BaseNickStore):
            raise Exception("Invalid Nickname storage")
        self.nick_store = nick_store
        self.photo_store = photo_store \
            if isinstance(photo_store, BasePhotoStore) \
            else None
        self.file_store = file_store \
            if isinstance(file_store, BaseFileStore) \
            else None
        self.sticker_url_store = sticker_url_store \
            if isinstance(sticker_url_store, BaseStickerURLStore) \
            else BaseStickerURLStore()

    def _must_post(self, api, data=None, json=None, timeout=10, **kwargs):
        if data is not None:
            kwargs['data'] = data
        elif json is not None:
            kwargs['json'] = json
        else:
            kwargs['data'] = {}
        kwargs['timeout'] = timeout

        try:
            r = requests.post(api, **kwargs)
            return r
        except requests.exceptions.Timeout:
            print("Error: Timeout requesting Telegram")
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
        print("[Telegram] downloading file {}".format(file_id))
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

    def upload_photo(self, file_id):
        photo = self.download_file(file_id)
        if photo is None:
            return None, "teleboto Faild to download file"

        print("[Telegram] uploading photo {}".format(file_id))
        url = self.photo_store.upload_image(filedata=photo)
        if url is None:
            return None, "Failed to upload Image"

        return url, None

    def upload_sticker(self, file_id):
        url = self.sticker_url_store.get_sticker(file_id)
        if url is not None:
            return url, None

        sticker = self.download_file(file_id)
        print("[Telegram] uploading sticker {}".format(file_id))

        if sticker is None:
            return None, "teleboto failed to download file"

        m = md5(sticker)
        url = self.sticker_url_store.get_sticker(m)
        if url is not None:
            return url, None

        photo = webp2png(sticker)
        url = self.photo_store.upload_image(filedata=photo, tag="sticker")
        if url is None:
            return None, "Failed to upload Image"

        self.sticker_url_store.set_sticker(file_id, url)
        self.sticker_url_store.set_sticker(m, url)
        return url, None

    def upload_document(self, doc):
        filedata = self.download_file(doc["file_id"])
        if filedata is None:
            return None, "teleboto Faild to download file"

        print("[Telegram] uploading document {}".format(doc["file_id"]))
        url = self.file_store.upload_file(filedata, doc["file_name"])
        if url is None:
            return None, "Failed to upload Document"

        return url, None

    def upload_audio(self, file_id, mime):
        filedata = self.download_file(file_id)
        if filedata is None:
            return None, "teleboto Faild to download file"

        ext = mimetypes.guess_extension(mime)
        filename = "voice" + ext
        url = self.file_store.upload_file(filedata, filename, filetype="audio")
        if url is None:
            return None, "Failed to upload Document"

        return url, None

    def parse_jmsg(self, jmsg):
        msg_id = jmsg["message_id"]
        from_info = jmsg["from"]
        user_id, username = from_info["id"], from_info.get("username", "")
        chat_id = jmsg["chat"]["id"]
        ts = jmsg["date"]
        media_url = ""

        mtype = MessageType.Text

        if "text" in jmsg:
            content = jmsg["text"]
            mtype = MessageType.Command \
                if self.is_cmd(jmsg["text"]) \
                else MessageType.Text

        elif "photo" in jmsg:
            file_id = jmsg["photo"][-1]["file_id"]
            url, err = self.upload_photo(file_id)
            if err is not None:
                content = err
            else:
                content = url + " (photo)"
                media_url = url
                mtype = MessageType.Photo

        elif "sticker" in jmsg:
            file_id = jmsg["sticker"]["file_id"]
            url, err = self.upload_sticker(file_id)
            if err is not None:
                content = err
            else:
                content = url + " (sticker)"
                media_url = url
                mtype = MessageType.Sticker

        elif "document" in jmsg:
            doc = jmsg["document"]
            if doc["mime_type"].startswith("image/"):
                url, err = self.upload_photo(doc["file_id"])
                mtype = MessageType.Photo
            else:
                url, err = self.upload_document(doc)
                mtype = MessageType.File

            if err is not None:
                content = err
            else:
                content = url + (
                    " (file)" if mtype == MessageType.File else " (photo)"
                )
                media_url = url

        elif "voice" in jmsg:
            file_id = jmsg["voice"]["file_id"]
            mime_type = jmsg["voice"]["mime_type"]

            url, err = self.upload_audio(file_id, mime_type)

            if err is not None:
                content = err
            else:
                content = url + " (Voice Message)"
                media_url = url
                mtype = MessageType.Audio

        elif "new_chat_title" in jmsg:
            content = "{} {} changed group name to {}".format(
                from_info.get("first_name", ""),
                from_info.get("last_name", ""),
                jmsg["new_chat_title"],
            )
            mtype = MessageType.Event

        elif "location" in jmsg:
            loc = jmsg["location"]
            lon, lat = loc["longitude"], loc["latitude"]
            mtype = MessageType.Location
            content = (
                ("location {lat},{lon}\n"
                 "https://www.openstreetmap.org/?mlat={lat}&mlon={lon}")
                .format(lat=lat, lon=lon)
            )

        elif "new_chat_participant" in jmsg:
            newp = jmsg["new_chat_participant"]
            content = "{} {} joined chat".format(
                newp.get("first_name", ""), newp.get("last_name", ""))
            mtype = MessageType.Event

        else:
            content = "(unsupported message type)"

        if "forward_from" in jmsg:
            ffrom = jmsg["forward_from"]
            content = content + " <forwarded from {} {}>".format(
                ffrom.get("first_name", ""), ffrom.get("last_name", ""))

        return TeleMessage(
            msg_id=msg_id, user_id=user_id, username=username, chat_id=chat_id,
            content=content, mtype=mtype, ts=ts, media_url=media_url
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
        print("[Telegram] Ready!")

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

            try:
                ret = json.loads(r.text)
            except:
                print("Failed to parse json: %s" % r.text)
                continue

            if ret["ok"] is False:
                print("[Telegram Error] {}".format(ret["description"]))
                continue

            for update in ret["result"]:
                offset = update["update_id"] + 1
                jmsg = update["message"]

                telemsg = self.parse_jmsg(jmsg)
                if telemsg is None or telemsg.user_id in id_blacklist:
                    continue
                if telemsg.mtype == MessageType.Command:
                    if self.try_set_nick(telemsg) is not None:
                        continue

                nickname = self.nick_store.get_nickname(
                    telemsg.user_id, telemsg.username)

                receiver = "%d" % telemsg.chat_id

                date, time = timestamp_date_time(telemsg.ts) \
                    if telemsg.ts else get_now_date_time()

                yield Message(
                    ChannelType.Telegram,
                    nickname, receiver, telemsg.content, telemsg.mtype,
                    date=date, time=time, media_url=telemsg.media_url,
                    opt={'msg_id': telemsg.msg_id,
                         'username': telemsg.username}
                )

    def try_set_nick(self, msg):
        # handle command
        user_id = msg.user_id
        target = "%d" % msg.chat_id
        try:
            tmp = msg.content.split()
            cmd = tmp[0][1:].lower()
            args = tmp[1:]
        except:
            return

        if cmd == "nick":
            if len(args) == 1:
                nick = args[0]
                self.nick_store.set_nickname(user_id, nick)
                content = "Changed nickname to '%s'" % nick
                print(target, content)
                self.send_msg(target, content)
            else:
                self.send_msg(
                    target,
                    "Invalid Command, use '/nick nickname'"
                    "to change nickname."
                )
            return True

    def send_photo(self, target, photo_data):
        api = self.api_base + "/sendPhoto"
        ft = imghdr.what('', photo_data)
        if ft is None:
            return
        filename = "image." + ft
        data={'chat_id': target}
        files={'photo': (filename, photo_data)}
        self._must_post(api, data=data, files=files)

    def send_msg(self, peer, content, sender=None, escape=True, **kwargs):
        for r in self.nickuser_regexes:
            m = r.match(content)
            if m is None:
                continue
            nick = m.group("nick")
            username = self.nick_store.get_username(nick)
            if username is None:
                continue
            content = r.sub(r'\g<pre>@{}\g<post>'.format(username), content)

        if escape:
            content = re.sub(r'([\[\*_])', r'\\\1', content)

        tmpl = self.msg_tmpl(sender)
        api = self.api_base + "/sendMessage"

        data = {
            'chat_id': int(peer),
            'text': tmpl.format(sender=sender, content=content),
            'parse_mode': 'Markdown',
        }
        if 'telegram' in kwargs:
            for k, v in kwargs['telegram'].items():
                data[k] = v
        self._must_post(api, json=data)

    def msg_tmpl(self, sender=None):
        return "{content}" if sender is None else "*[{sender}]* {content}"


def TelegramThread(tg, bus):
    def send_all(text):
        for _, b in config["bindings"].items():
            if ChannelType.Telegram in b:
                to = b[ChannelType.Telegram]
                tg.send_msg(to, text, escape=False)

    tele_me = [int(x) for x in config["telegram"]["me"]]
    try:
        for msg in tg.message_stream(id_blacklist=tele_me):
            bus.publish(msg)
    except:
        send_all("**Bug Trapped! Save Me!**")
        print("[Telegram Traceback]")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    from .photostore import VimCN

    tele = Telegram(config['telegram']['token'],
                    nick_store=MemNickStore(), photo_store=VimCN())
    # tele.send_msg('user#67655173', 'hello')
    tele.send_photo('-34678255', open('test.png', 'rb').read())
    tele.send_msg('-34678255', "Back!")
    for msg in tele.message_stream():
        print(msg.dumps())
        tele.send_msg(msg.receiver, msg.content)


# vim: ts=4 sw=4 sts=4 expandtab
