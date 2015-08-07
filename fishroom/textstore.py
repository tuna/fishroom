#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import requests
import requests.exceptions
import hashlib
import json
import pytz
from datetime import datetime
from .config import config


class BaseTextStore(object):
    def new_paste(self, text, sender):
        """\
        Upload text to text store

        Args:
            text: text content
            sender: sender's nickname

        Returns:
            url: URL to pasted text page
        """
        raise Exception("Not Implemented")


class Pastebin(BaseTextStore):

    api_url = "http://pastebin.com/api/api_post.php"

    def __init__(self, api_dev_key):
        self.api_dev_key = api_dev_key

    def new_paste(self, text, sender):
        filename = "{sender}.{ts}.txt".format(
            sender=sender,
            ts=datetime.now().strftime("%Y%m%d%H%M"),
        )
        data = {
            'api_option': "paste",
            'api_dev_key': self.api_dev_key,
            'api_paste_code': text,
            'api_paste_name': filename,
        }
        try:
            r = requests.post(self.api_url, data=data, timeout=5)
        except requests.exceptions.Timeout:
            print("Error: Timeout uploading to Pastebin")
            return None

        if r.text.startswith("http"):
            return r.text.strip()

        return None


class Vinergy(BaseTextStore):

    api_url = "http://cfp.vim-cn.com/"

    def __init__(self, **kwargs):
        pass

    def new_paste(self, text, sender):
        data = {
            'vimcn': text,
        }
        try:
            r = requests.post(self.api_url, data=data, timeout=5)
        except requests.exceptions.Timeout:
            print("Error: Timeout uploading to Vinergy")
            return None

        if r.text.startswith("http"):
            return r.text.strip()

        return None


class RedisStore(BaseTextStore):

    KEY_TMPL = ":".join([config["redis"]["prefix"], "text_store", "{id}"])
    URL_TMPL = config["baseurl"] + "/text/{id}"

    def __init__(self, redis_client, tz="utc", **kwargs):
        self.r = redis_client
        self.tz = pytz.timezone(tz)

    def new_paste(self, text, sender):
        now = datetime.now(tz=self.tz).strftime("%Y-%m-%d %H:%M:%S")
        s = hashlib.sha1()
        s.update((text+sender+now).encode("utf-8"))
        _id = s.hexdigest()[:16]
        key = self.KEY_TMPL.format(id=_id)
        value = json.dumps({
            "title": "Text from {}".format(sender),
            "time": now,
            "content": text,
        })
        self.r.set(key, value)
        return self.URL_TMPL.format(id=_id)

# vim: ts=4 sw=4 sts=4 expandtab
