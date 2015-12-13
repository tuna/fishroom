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
        auth = qiniu.Auth(access_key, secret_key)
        self.qiniu = qiniu
        self.token = auth.upload_token(bucket_name)
        self.counter = counter
        self.base_url = base_url

    def upload_image(self, filename=None, filedata=None):
        if filedata is None:
            with open(filename, 'rb') as f:
                filedata = f.read()

        with BytesIO(filedata) as f:
            ext = imghdr.what(f)

        name = "img/%02x.%s" % (self.counter.incr(), ext)

        ret, info = self.qiniu.put_data(self.token, name, filedata)
        if ret is None:
            return

        return self.base_url + name

    def upload_file(self, filedata, filetype="audio", filename=None):
        return


# vim: ts=4 sw=4 sts=4 expandtab
