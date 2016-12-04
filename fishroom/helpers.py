#!/usr/bin/env python3
import pytz
import requests
import hashlib
import logging

from typing import Tuple
from datetime import datetime
from dateutil import parser
from io import BytesIO
from PIL import Image
from .config import config

tz = pytz.timezone(config.get("timezone", "utc"))


def get_logger(name, level=None) -> logging.Logger:
    logging.basicConfig(format='[%(name)s] [%(levelname)s] %(message)s')
    logger = logging.getLogger(name)
    if level is None:
        level = logging.DEBUG if config.get("debug", False) else logging.INFO
    logger.setLevel(level)
    return logger


def get_now():
    return datetime.now(tz=tz)


def get_now_date_time():
    now = get_now()
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")


def timestamp_date_time(ts):
    d = datetime.fromtimestamp(ts, tz=tz)
    return d.strftime("%Y-%m-%d"), d.strftime("%H:%M:%S")


def string_date_time(dstr):
    d = parser.parse(dstr).astimezone(tz)
    return d.strftime("%Y-%m-%d"), d.strftime("%H:%M:%S")


def webp2png(webp_data):
    with BytesIO(webp_data) as fd:
        im = Image.open(fd)

    with BytesIO() as out:
        im.save(out, "PNG")
        out.seek(0)
        return out.read()


def md5(data):
    m = hashlib.md5()
    m.update(data)
    return m.hexdigest()


def download_file(url) -> Tuple[bytes, str]:
    logger = get_logger(__name__)
    try:
        r = requests.get(url, timeout=10)
    except requests.exceptions.Timeout:
        logger.error("Timeout downloading {}".format(url))
        return None, None
    except:
        logger.exception("Failed to download {}".format(url))
        return None, None

    return (r.content, r.headers.get('content-type'))


def plural(number: int, origin: str, plurals: str=None) -> str:
    # need lots of check, or not?
    if plurals is None:
        plurals = origin + "s"

    if number != 1:
        return "{} {}".format(number, plurals)
    else:
        return "{} {}".format(number, origin)

# vim: ts=4 sw=4 sts=4 expandtab
