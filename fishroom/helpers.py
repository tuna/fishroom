#!/usr/bin/env python3
import pytz
from datetime import datetime
from io import BytesIO
from PIL import Image
from .config import config

tz = pytz.timezone(config.get("timezone", "utc"))


def get_now():
    return datetime.now(tz=tz)


def get_now_date_time():
    now = get_now()
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")


def timestamp_date_time(ts):
    d = datetime.fromtimestamp(ts, tz=tz)
    return d.strftime("%Y-%m-%d"), d.strftime("%H:%M:%S")


def webp2png(webp_data):
    with BytesIO(webp_data) as fd:
        im = Image.open(fd)

    with BytesIO() as out:
        im.save(out, "PNG")
        out.seek(0)
        return out.read()

# vim: ts=4 sw=4 sts=4 expandtab
