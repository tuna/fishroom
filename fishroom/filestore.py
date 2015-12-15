#!/usr/bin/env python3
from .photostore import BasePhotoStore
from io import BytesIO
import imghdr


class BaseFileStore(object):

    def upload_file(self, filename):
        raise Exception("Not Implemented")


class QiniuStore(BaseFileStore, BasePhotoStore):

    def __init__(self, access_key, secret_key, bucket_name, counter, base_url):
        try:
            import qiniu
        except ImportError:
            raise Exception("qiniu sdk is not installed")
        self.qiniu = qiniu

        self.auth = qiniu.Auth(access_key, secret_key)
        self.bucket = bucket_name
        self.counter = counter
        self.base_url = base_url

    def upload_image(self, filename=None, filedata=None, tag=None):
        token = self.auth.upload_token(self.bucket)
        if filedata is None:
            with open(filename, 'rb') as f:
                filedata = f.read()

        with BytesIO(filedata) as f:
            ext = imghdr.what(f)

        prefix = tag or "img"
        name = "%s/%02x.%s" % (prefix, self.counter.incr(), ext)

        ret, info = self.qiniu.put_data(token, name, filedata)
        if ret is None:
            return

        return self.base_url + name

    def upload_file(self, filedata, filename, filetype="file"):
        token = self.auth.upload_token(self.bucket)

        name = "%s/%02x-%s" % (filetype, self.counter.incr(), filename)
        ret, info = self.qiniu.put_data(token, name, filedata)
        if ret is None:
            return
        return self.base_url + name


# vim: ts=4 sw=4 sts=4 expandtab
