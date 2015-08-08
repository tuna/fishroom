#!/usr/bin/env python3
import json
import tornado.web
import tornado.websocket
import tornado.gen as gen
import tornadoredis
from urllib.parse import urlparse
from ..helpers import get_now
from ..models import Message
from ..chatlogger import ChatLogger
from ..config import config


def get_redis():
    r = tornadoredis.Client(
        host=config['redis']['host'], port=config['redis']['port'])
    r.connect()
    return r

r = get_redis()


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

        if date == "today":
            date = get_now().strftime("%Y-%m-%d")
        key = ChatLogger.LOG_QUEUE_TMPL.format(channel=channel, date=date)
        logs = yield gen.Task(r.lrange, key, 0, -1)
        msgs = [Message.loads(msg) for msg in logs]

        baseurl = config["baseurl"]
        p = urlparse(baseurl)
        if p.scheme == "http":
            wsbaseurl = "ws://" + p.netloc + p.path
        elif p.scheme == "https":
            wsbaseurl = "wss://" + p.netloc + p.path

        embedded = self.get_argument("embedded", None)
        limit = self.get_argument("limit", 15)

        self.render(
            "chat_log.html",
            title="Chat Log of #{channel} @ {date}".format(
                channel=channel, date=date),
            msgs=msgs,
            next_id=len(msgs),
            channel=channel,
            wsbaseurl=wsbaseurl,
            embedded=(embedded is not None),
            limit=int(limit),
        )

        # key =


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


