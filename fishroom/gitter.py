#!/usr/bin/env python3
import re
import json
import asyncio
import aiohttp
import requests
import requests.exceptions
from .base import BaseBotInstance, EmptyBot
from .models import MessageType, Message, ChannelType
from .helpers import string_date_time


class Gitter(BaseBotInstance):

    ChanTag = ChannelType.Gitter
    SupportMultiline = True

    _stream_api = "https://stream.gitter.im/v1/rooms/{room}/chatMessages"
    _post_api = "https://api.gitter.im/v1/rooms/{room}/chatMessages"

    def __init__(self, token, rooms, me):
        self.token = token
        self.rooms = rooms
        self.me = me

    @property
    def headers(self):
        return {
            'Accept': 'application/json',
            'Authorization': 'Bearer %s' % self.token,
        }

    def _must_post(self, api, data=None, json=None, timeout=10, **kwargs):
        if data is not None:
            kwargs['data'] = data
        elif json is not None:
            kwargs['json'] = json
        else:
            kwargs['data'] = {}
        kwargs['timeout'] = timeout

        try:
            r = requests.post(api, **kwargs)
            return r
        except requests.exceptions.Timeout:
            print("Error: Timeout requesting Telegram")
        except KeyboardInterrupt:
            raise
        except:
            import traceback
            traceback.print_exc()
        return None

    async def fetch(self, session, room, id_blacklist):
        url = self._stream_api.format(room=room)
        while True:
            # print("polling on url %s" % url)
            try:
                with aiohttp.Timeout(300):
                    async with session.get(url, headers=self.headers) as resp:
                        while True:
                            line = await resp.content.readline()
                            line = bytes.decode(line, 'utf-8').strip()
                            if not line:
                                continue
                            msg = self.parse_jmsg(room, json.loads(line))
                            if msg.sender in id_blacklist:
                                continue
                            self.send_to_bus(msg)
            except asyncio.TimeoutError:
                pass
            except:
                raise

    def parse_jmsg(self, room, jmsg):
        from_user = jmsg['fromUser']['username']
        content = jmsg['text']
        date, time = string_date_time(jmsg['sent'])

        mtype = MessageType.Command \
            if self.is_cmd(content) \
            else MessageType.Text

        return Message(
            ChannelType.Gitter,
            from_user, room, content, mtype,
            date=date, time=time, media_url=None, opt={}
        )

    def send_msg(self, target, content, sender=None, raw=None, **kwargs):
        url = self._post_api.format(room=target)
        if sender:
            sender = re.sub(r'([\[\*_#])', r'\\\1', sender)

        reply = ""
        if 'reply_text' in kwargs:
            reply_to = kwargs['reply_to']
            reply_text_lines = kwargs['reply_text'].splitlines()
            if len(reply_text_lines) > 0:
                for line in reply_text_lines:
                    if not line.startswith(">"):
                        reply_text = line
                        break
                else:
                    reply_text = reply_text_lines[0]

                reply = "> [{reply_to}] {reply_text}\n\n".format(
                    reply_to=reply_to, reply_text=reply_text,
                )

        text = "**[{sender}]** {content}" if sender else "{content}"

        if raw is not None:
            if raw.mtype in (MessageType.Photo, MessageType.Sticker):
                content = "%s\n![](%s)" % (raw.mtype, raw.media_url)

        j = {
            'text': reply + text.format(sender=sender, content=content)
        }

        self._must_post(url, json=j, headers=self.headers)


    def send_to_bus(self, msg):
        raise NotImplementedError()

    def listen_message_stream(self, id_blacklist=None):
        id_blacklist = set(id_blacklist or [self.me, ])

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with aiohttp.ClientSession(loop=loop) as session:
            self.aioclient_session = session

            tasks = [
                asyncio.ensure_future(self.fetch(session, room, id_blacklist))
                for room in self.rooms
            ]
            done, _ = loop.run_until_complete(
                asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
            )
            for d in done:
                if d.exception():
                    raise d.exception()


def GitterThread(gt, bus, ):
    if gt is None or isinstance(gt, EmptyBot):
        return
    def send_to_bus(msg):
        bus.publish(msg)
    gt.send_to_bus = send_to_bus
    gt.listen_message_stream()


if __name__ == "__main__":

    gitter = Gitter(
        token="",
        rooms=(
            "57397795c43b8c60197322b9",
            "5739b957c43b8c6019732c0b",
        ),
        me=''
    )

    def response(msg):
        print(msg)
        gitter.send_msg(
            target=msg.receiver, content=msg.content, sender="fishroom")

    gitter.send_to_bus = response

    try:
        gitter.listen_message_stream(id_blacklist=("master_tuna_twitter", ))
    except Exception:
        import traceback
        traceback.print_exc()




# vim: ts=4 sw=4 sts=4 expandtab
