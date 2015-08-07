#!/usr/bin/env python3
import json
import tornado.web
import tornado.gen as gen
import tornadoredis
from ..config import config
from ..textstore import RedisStore


def get_redis():
    r = tornadoredis.Client(
        host=config['redis']['host'], port=config['redis']['port'])
    r.connect()
    return r

r = get_redis()


class TextStoreHandler(tornado.web.RequestHandler):

    @gen.coroutine
    def get(self, text_id):
        key = RedisStore.KEY_TMPL.format(id=text_id)
        val = yield gen.Task(r.get, key)
        if val is None:
            self.clear()
            self.set_status(404)
            self.finish("text not found")
            return
        val = json.loads(val)
        self.set_header('Content-Type', 'text/html')
        self.render(
            "text_store.html",
            title=val["title"],
            content=val["content"],
            time=val.get("time"),
        )
