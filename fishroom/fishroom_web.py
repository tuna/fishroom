#!/usr/bin/env python3
import tornado.ioloop
import tornado.web
from .web.handlers import TextStoreHandler
from .config import config


def main():
    debug = config.get("debug", False)
    application = tornado.web.Application([
        (r"/text/([a-z0-9]+)", TextStoreHandler),
    ], debug=debug, autoreload=debug)
    application.listen(8000)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()

# vim: ts=4 sw=4 sts=4 expandtab
