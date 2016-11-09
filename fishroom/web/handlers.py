#!/usr/bin/env python3
import json
import re
import tornado.web
import tornado.websocket
import tornado.gen as gen
import tornadoredis

import hashlib
from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta
from ..db import get_redis as get_pyredis
from ..base import BaseBotInstance
from ..bus import MessageBus
from ..helpers import get_now, tz
from ..models import Message, ChannelType, MessageType
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
        url = "log/{room}/today".format(
            room=config["chatlog"]["default_channel"]
        )
        self.redirect(urljoin(config["baseurl"] + "/", url))


class RobotsTxtHandler(tornado.web.RequestHandler):

    def get(self):
        self.set_header('Content-Type', 'text/plain')
        self.write("User-agent: *\nDisallow: /")
        self.finish()


class TextStoreHandler(tornado.web.RequestHandler):

    @gen.coroutine
    def get(self, room, date, msg_id):
        key = ChatLogger.LOG_QUEUE_TMPL.format(channel=room, date=date)
        msg_id = int(msg_id)
        val = pr.lrange(key, msg_id, msg_id)
        if not val:
            self.clear()
            self.set_status(404)
            self.finish("text not found")
            return
        msg = Message.loads(val[0].decode('utf-8'))
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
        if room not in config["bindings"] or \
                room in config.get("private_rooms", []):
            self.set_status(404)
            self.finish("Room not found")
            return

        enable_ws = False
        if date == "today":
            enable_ws = True
            date = get_now().strftime("%Y-%m-%d")

        if ((get_now() - tz.localize(datetime.strptime(date, "%Y-%m-%d"))) >
                timedelta(days=7)):
            self.set_status(403)
            self.finish("Dark History Coverred")
            return

        embedded = self.get_argument("embedded", None)

        key = ChatLogger.LOG_QUEUE_TMPL.format(channel=room, date=date)
        mlen = pr.llen(key)

        last = int(self.get_argument("last", mlen)) - 1
        limit = int(self.get_argument("limit", 15 if embedded else mlen))

        start = max(last - limit + 1, 0)

        if self.get_argument("json", False):
            logs = pr.lrange(key, start, last)
            msgs = [json.loads(jmsg.decode("utf-8")) for jmsg in logs]
            for i, m in zip(range(start, last+1), msgs):
                m['id'] = i
                m.pop('opt', None)
                m.pop('receiver', None)
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps(msgs))
            self.finish()
            return

        baseurl = config["baseurl"]
        p = urlparse(baseurl)

        dates = [(get_now() - timedelta(days=i)).strftime("%Y-%m-%d")
                 for i in range(7)]

        self.render(
            "chat_log.html",
            title="#{room} @ {date}".format(
                room=room, date=date),
            next_id=mlen,
            enable_ws=enable_ws,
            room=room,
            rooms=[
                x for x in config["bindings"].keys()
                if x not in config.get("private_rooms", ())
            ],
            date=date,
            dates=dates,
            basepath=p.path,
            embedded=(embedded is not None),
            limit=int(limit),
        )

    def name_style_num(self, text):
        m = hashlib.md5(text.encode('utf-8'))
        return "%d" % (int(m.hexdigest()[:8], 16) & 0x07)


class PostMessageHandler(tornado.web.RequestHandler):

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    def write_json(self, status_code, **kwargs):
        self.set_status(status_code)
        self.write(json.dumps(kwargs))

    def post(self, room):
        if room not in config["bindings"] or \
                room in config.get("private_rooms", []):
            self.set_status(404)
            self.finish("Room not found")
            return
        try:
            self.json_data = json.loads(self.request.body.decode('utf-8'))
        except ValueError:
            message = 'Unable to parse JSON.'
            self.write_json(400, message=message)  # Bad Request
            self.finish()
            return

        content = self.json_data.get("content", None)
        if not content:
            self.write_json(400, msg="Cannot send empty message")
            self.finish()
            return

        sender = str(self.json_data.get("nickname", '').strip())
        if not sender:
            self.write_json(400, msg="Nickname must be set")
            self.finish()
            return
        if not re.match(r'^\w', sender, flags=re.UNICODE):
            self.write_json(
                400, msg="Invalid char found, use a human's nickname instead!")
            self.finish()
            return

        now = get_now()
        date, time = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
        mtype = MessageType.Command \
            if BaseBotInstance.is_cmd(content) \
            else MessageType.Text
        msg = Message(
            ChannelType.Web, sender, room, content=content,
            mtype=mtype, date=date, time=time, room=room
        )

        pr.publish(MessageBus.CHANNEL, msg.dumps())
        self.write_json(200, msg="OK")
        self.finish()


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

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    def write_json(self, status_code=200, **kwargs):
        self.set_status(status_code)
        self.write(json.dumps(kwargs))

    def auth(self):
        token_id = self.request.headers.get(
            "X-TOKEN-ID",
            self.get_argument("id", "")
        )
        token_key = self.request.headers.get(
            "X-TOKEN-KEY",
            self.get_argument("key", "")
        )
        fine = self.mgr.auth(token_id, token_key)
        if not fine:
            self.set_status(403)
            return
        return token_id


class APILongPollingHandler(APIRequestHandler):

    @gen.coroutine
    def get(self):
        token_id = self.auth()
        if token_id is None:
            self.finish("Invalid Token")
            return

        room = self.get_argument("room", None)

        queue = APIClientManager.queue_key.format(token_id=token_id)
        l = yield gen.Task(r.llen, queue)
        msgs = []
        if l > 0:
            msgs = yield gen.Task(r.lrange, queue, 0, -1)
            pr.delete(queue)
            msgs = [json.loads(m) for m in msgs]
        else:
            ret = yield gen.Task(r.blpop, queue, timeout=10)
            if queue in ret:
                msgs = [json.loads(ret[queue])]

        if room:
            msgs = [m for m in msgs if m['room'] == room]

        self.write_json(messages=msgs)
        self.finish()


class APIPostMessageHandler(APIRequestHandler):

    def prepare(self):
        if self.request.body:
            try:
                self.json_data = json.loads(self.request.body.decode('utf-8'))
            except ValueError:
                message = 'Unable to parse JSON.'
                self.write_json(400, message=message)  # Bad Request
                self.finish()
            return

        self.write_json(400, message="Cannot handle empty request")
        self.finish()

    def post(self, room):
        token_id = self.auth()
        if token_id is None:
            self.finish("Invalid Token")
            return

        content = self.json_data.get("content", None)
        if not content:
            self.write_json(400, message="Cannot send empty message")
            self.finish()

        apiname = self.mgr.get_name(token_id)
        sender = self.json_data.get("sender", apiname)
        now = get_now()
        date, time = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
        chantag = "{}-{}".format(ChannelType.API, apiname)
        mtype = MessageType.Command \
            if BaseBotInstance.is_cmd(content) \
            else MessageType.Text
        msg = Message(
            chantag, sender, room, content=content,
            mtype=mtype, date=date, time=time, room=room
        )

        pr.publish(MessageBus.CHANNEL, msg.dumps())
        self.write_json(message="OK")
        self.finish()
