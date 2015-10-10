#!/usr/bin/env python3
from marshmallow import Schema, fields, validate


class ChannelType(object):
    """\
    Channel Types
    """
    XMPP = "xmpp"
    IRC = "irc"
    Telegram = "telegram"
    Web = "web"
    API = "api"


class MessageType(object):
    """\
    Message Types
    """
    Text = "text"
    Photo = "photo"
    Sticker = "sticker"
    Location = "location"
    Event = "event"
    Command = "command"


class MessageSchema(Schema):
    """\
    Json Schema for Message
    """

    # Where is this message from
    channel = fields.String(validate=validate.OneOf(
        (ChannelType.IRC, ChannelType.XMPP, ChannelType.Telegram,
         ChannelType.Web, ChannelType.API, ),
    ))
    # message sender
    sender = fields.String()
    # message receiver (usually group id)
    receiver = fields.String()
    # message type
    mtype = fields.String(validate=validate.OneOf(
        (MessageType.Photo, MessageType.Text, MessageType.Sticker,
         MessageType.Location, MessageType.Command, MessageType.Event),
    ))
    # if message is photo or sticker, this contains url
    media_url = fields.String()
    # message text
    content = fields.String()
    # date and time
    date = fields.String()
    time = fields.String()
    # is this message from fishroom bot?
    botmsg = fields.Boolean()
    # room
    room = fields.String()
    # channel specific options (passed to send_msg method)
    opt = fields.Dict()


class Message(object):
    """\
    Message instance

    Attributes:
        channel: one in ChannelType.{XMPP, Telegram, IRC}
        sender: sender name
        receiver: receiver name
        content: message content
        mtype: text or photo or sticker
        media_url: URL to media if mtype is sticker or photo
        date, time: message date and time
        room: which room to deliver
        botmsg: msg is from fishroom bot
        opt: channel specific options
    """

    _schema = MessageSchema()

    def __init__(self, channel, sender, receiver, content,
                 mtype=MessageType.Text, date=None, time=None,
                 media_url=None, botmsg=False, room=None, opt=None):
        self.channel = channel
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.mtype = mtype
        self.date = date
        self.time = time
        self.media_url = media_url
        self.botmsg = botmsg
        self.room = room
        self.opt = opt or {}

    def __repr__(self):
        return (
            "[{channel}] {mtype} from: {sender}, to: {receiver}, {content}"
            .format(
                channel=self.channel, mtype=self.mtype, sender=self.sender,
                receiver=self.receiver, content=self.content,
            ))

    def dumps(self):
        return self._schema.dumps(self).data

    @classmethod
    def loads(cls, jstr):
        if isinstance(jstr, bytes):
            jstr = jstr.decode('utf-8')

        try:
            m = Message(**cls._schema.loads(jstr).data)
            return m
        except:
            return None


# vim: ts=4 sw=4 sts=4 expandtab
