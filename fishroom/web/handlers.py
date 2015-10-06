#!/usr/bin/env python3
import json
import tornado.web
import tornado.websocket
import tornado.gen as gen
import tornadoredis

import hashlib
from urllib.parse import urlparse
from datetime import datetime, timedelta
from ..db import get_redis as get_pyredis
from ..helpers import get_now, tz
from ..models import Message
from ..chatlogger import ChatLogger
from ..api_client import APIClientManager
from ..config import config


def get_redis():
    r = tornadoredis.Client(
        host=config['redis']['host'], port=config['redis']['port'])
    r.connect()
    return r

r = get_redis()
pr = get_pyredis()


class DefaultHandler(tornado.web.RequestHandler):

    def get(self):
        url = "/log/{channel}/today".format(
            channel=config["chatlog"]["default_channel"]
        )
        self.redirect(url)


class TextStoreHandler(tornado.web.RequestHandler):

    @gen.coroutine
    def get(self, channel, date, msg_id):
        key = ChatLogger.LOG_QUEUE_TMPL.format(channel=channel, date=date)
        msg_id = int(msg_id)
        val = yield gen.Task(r.lrange, key, msg_id, msg_id)
        if not val:
            self.clear()
            self.set_status(404)
            self.finish("text not found")
            return
        msg = Message.loads(val[0])
        # self.set_header('Content-Type', 'text/html')
        self.render(
            "text_store.html",
            title="Text from {}".format(msg.sender),
            content=msg.content,
            time="{date} {time}".format(date=msg.date, time=msg.time),
        )


class ChatLogHandler(tornado.web.RequestHandler):

    @gen.coroutine
    def get(self, channel, date):
        if channel not in config["bindings"]:
            self.set_status(404)
            self.finish("Channel not found")
            return

        enable_ws = False
        if date == "today":
            enable_ws = True
            date = get_now().strftime("%Y-%m-%d")

        if (get_now() - tz.localize(datetime.strptime(date, "%Y-%m-%d"))
                > timedelta(days=7)):
            self.set_status(403)
            self.finish("Dark History Coverred")
            return

        key = ChatLogger.LOG_QUEUE_TMPL.format(channel=channel, date=date)
        mlen = yield gen.Task(r.llen, key)

        embedded = self.get_argument("embedded", None)
        limit = int(self.get_argument("limit", 15 if embedded else mlen))

        logs = yield gen.Task(r.lrange, key, -limit, -1)
        msgs = [Message.loads(msg) for msg in logs]
        for msg in msgs:
            msg.name_style_num = self.name_style_num(msg.sender)

        baseurl = config["baseurl"]
        p = urlparse(baseurl)

        self.render(
            "chat_log.html",
            title="#{channel} @ {date}".format(
                channel=channel, date=date),
            msgs=msgs,
            next_id=mlen,
            enable_ws=enable_ws,
            channel=channel,
            basepath=p.path,
            embedded=(embedded is not None),
            limit=int(limit),
        )

    def name_style_num(self, text):
        m = hashlib.md5(text.encode('utf-8'))
        return "%d" % (int(m.hexdigest()[:8], 16) & 0x07)


class MessageStreamHandler(tornado.websocket.WebSocketHandler):

    def __init__(self, *args, **kwargs):
        super(MessageStreamHandler, self).__init__(*args, **kwargs)
        self.r = None

    def check_origin(self, origin):
        return True

    def on_message(self, jmsg):
        try:
            msg = json.loads(jmsg)
            self.r = get_redis()
            self._listen(msg["channel"])
        except:
            self.close()

    @gen.engine
    def _listen(self, channel):
        print("polling on channel: ", channel)
        self.redis_chan = ChatLogger.CHANNEL.format(channel=channel)
        yield gen.Task(self.r.subscribe, self.redis_chan)
        self.r.listen(self._on_update)

    @gen.coroutine
    def _on_update(self, msg):
        if msg.kind == "message":
            self.write_message(msg.body)
        elif msg.kind == "subscribe":
            self.write_message("OK")
        elif msg.kind == "disconnect":
            self.close()

    def on_close(self):
        if self.r:
            if self.r.subscribed:
                self.r.unsubscribe(self.redis_chan)
            self.r.disconnect()


class APILongPollingHandler(tornado.web.RequestHandler):

    @gen.coroutine
    def get(self):
        token_id = self.get_argument("id")
        token_key = self.get_argument("key")
        mgr = APIClientManager(pr)
        fine = mgr.auth(token_id, token_key)
        if not fine:
            self.set_status(403, "Invalid tokens")
        # self.write("%s, %s, %s" % (fine, token_id, token_key))
        queue = APIClientManager.queue_key.format(token_id=token_id)
        l = yield gen.Task(r.llen, queue)
        msgs = []
        if l > 0:
            msgs = yield gen.Task(r.lrange, queue, 0, -1)
            pr.delete(queue)
        else:
            ret = yield gen.Task(r.blpop, queue, timeout=10)
            if ret:
                msgs = [ret]

        ret = {'messages': msgs}
        self.write(json.dumps(ret))
        self.finish()



