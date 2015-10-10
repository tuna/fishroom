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
from ..bus import MessageBus
from ..helpers import get_now, tz
from ..models import Message, ChannelType
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
        url = "/log/{room}/today".format(
            room=config["chatlog"]["default_channel"]
        )
        self.redirect(url)


class TextStoreHandler(tornado.web.RequestHandler):

    @gen.coroutine
    def get(self, room, date, msg_id):
        key = ChatLogger.LOG_QUEUE_TMPL.format(channel=room, date=date)
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
    def get(self, room, date):
        if room not in config["bindings"]:
            self.set_status(404)
            self.finish("Room not found")
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

        key = ChatLogger.LOG_QUEUE_TMPL.format(channel=room, date=date)
        mlen = yield gen.Task(r.llen, key)

        embedded = self.get_argument("embedded", None)
        limit = int(self.get_argument("limit", 15 if embedded else mlen))

        logs = yield gen.Task(r.lrange, key, -limit, -1)
        msgs = [Message.loads(msg) for msg in logs]
        for msg in msgs:
            if msg is None:
                continue
            msg.name_style_num = self.name_style_num(msg.sender)

        baseurl = config["baseurl"]
        p = urlparse(baseurl)

        self.render(
            "chat_log.html",
            title="#{room} @ {date}".format(
                room=room, date=date),
            msgs=msgs,
            next_id=mlen,
            enable_ws=enable_ws,
            room=room,
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
            self._listen(msg["room"])
        except:
            self.close()

    @gen.engine
    def _listen(self, room):
        print("polling on room: ", room)
        self.redis_chan = ChatLogger.CHANNEL.format(channel=room)
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


class APIRequestHandler(tornado.web.RequestHandler):

    mgr = APIClientManager(pr)


class APILongPollingHandler(APIRequestHandler):

    @gen.coroutine
    def get(self):
        token_id = self.get_argument("id")
        token_key = self.get_argument("key")
        fine = self.mgr.auth(token_id, token_key)
        if not fine:
            self.set_status(403, "Invalid tokens")
            self.finish()

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


class APIPostMessageHandler(APIRequestHandler):

    def prepare(self):
        if self.request.body:
            try:
                self.json_data = json.loads(self.request.body)
            except ValueError:
                message = 'Unable to parse JSON.'
                self.write_json(400, message=message)  # Bad Request
            return

        self.write_json(400, message="Bad Request")  # Bad Request

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    def write_json(self, status_code, **kwargs):
        self.write(json.dumps(kwargs))

    def post(self, room):
        token_id = self.json_data.get("id", "NONE")
        token_key = self.json_data.get("key", "NONE")
        fine = self.mgr.auth(token_id, token_key)
        if not fine:
            self.write_json(403, "Invalid tokens")
            return

        content = self.json_data.get("content", None)
        if not content:
            self.write_json(400, "Cannot send empty message")

        sender = self.mgr.get_name(token_id)
        now = get_now()
        date, time = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
        msg = Message(
            ChannelType.API, sender, room, content=content,
            date=date, time=time, room=room
        )

        pr.publish(MessageBus.CHANNEL, msg.dumps())
        self.write("OK")
        self.finish()




