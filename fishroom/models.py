#!/usr/bin/env python3
import unittest
from marshmallow import Schema, fields, validate, ValidationError


class ChannelType(object):
    """\
    Channel Types
    """
    XMPP = "xmpp"
    IRC = "irc"
    Telegram = "telegram"
    Gitter = "gitter"
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
    Audio = "audio"
    Video = "video"
    Animation = "animation"
    File = "file"
    Event = "event"
    Command = "command"


class Color(object):
    """\
    Text color option
    """

    def __init__(self, fg: int, bg: int=None):
        self.fg = fg
        self.bg = bg

    def __repr__(self):
        return "<color: {}/{}>".format(self.fg, self.bg)

    def __nonzero__(self):
        return (self.fg is not None) or (self.bg is not None)

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__) and
            self.fg == other.fg and
            self.bg == other.bg
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def swap(self):
        self.fg, self.bg = self.bg, self.fg


class ColorField(fields.Field):

    def _serialize(self, value, attr, obj):
        if value is None:
            return ''
        return (value.fg, value.bg)

    def _deserialize(self, value, attr, obj):
        if not value:
            return None
        elif isinstance(value, int):
            return Color(value)
        else:
            try:
                fg, bg = map(int, value)
            except:
                raise ValidationError(
                    "Color field should only contain fg and bg")
            return Color(fg, bg)
    # def __str__(self):
    #     return json.dumps({'fg': self.fg, 'bg': self.bg})


class TextStyle(object):
    """\
    TextStyle option, including normal, color, italic, bold and underline
    """

    # TODO: Add newline support

    NORMAL = 0
    COLOR = 1
    ITALIC = 2
    BOLD = 4
    UNDERLINE = 8

    _schema = None  # should be set later

    def __init__(self, color: Color=None, italic: int=0,
                 bold: int=0, underline: int=0, style: int=0):
        self.style = style
        self.color = color
        if color:
            self.style |= self.COLOR
        self.style |= self.ITALIC if italic else 0
        self.style |= self.BOLD if bold else 0
        self.style |= self.UNDERLINE if underline else 0

    @classmethod
    def style_list(cls, style):
        styles = []
        if style & cls.ITALIC:
            styles.append('italic')
        if style & cls.BOLD:
            styles.append('bold')
        if style & cls.UNDERLINE:
            styles.append('underline')
        return styles

    def toggle(self, mask: int=0):
        """\
        mask should be one of COLOR, ITALIC, BOLD, UNDERLINE
        """
        if mask not in (self.COLOR, self.ITALIC, self.BOLD, self.UNDERLINE):
            return
        self.style ^= mask

    def set(self, mask: int=0):
        """
        set style of a mask
        """
        if mask not in (self.COLOR, self.ITALIC, self.BOLD, self.UNDERLINE):
            return
        self.style |= mask

    def clear(self, mask: int=0):
        """
        clear style of a mask
        """
        self.style &= ~mask
        if mask == self.COLOR:
            self.color = None

    def set_color(self, fg: int, bg: int=None):
        self.set(self.COLOR)
        self.color = Color(fg, bg)

    def has_color(self):
        return self.style & self.COLOR

    def is_normal(self):
        return self.style == 0

    def is_italic(self):
        return self.style & self.ITALIC

    def is_bold(self):
        return self.style & self.BOLD

    def is_underline(self):
        return self.style & self.UNDERLINE

    def copy(self):
        return TextStyle(
            color=Color(self.color.fg, self.color.bg),
            style=self.style,
        ) if self.has_color() else TextStyle(style=self.style)

    def dump(self):
        return self._schema.dump(self).data

    def dumps(self):
        return self._schema.dumps(self).data

    @classmethod
    def loads(cls, jstr):
        if isinstance(jstr, bytes):
            jstr = jstr.decode('utf-8')

        ts = TextStyle(**cls._schema.loads(jstr).data)
        return ts

    @classmethod
    def load(cls, data):
        return TextStyle(**cls._schema.load(data).data)

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__) and
            self.style == other.style and
            self.color == other.color
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        styles = self.style_list(self.style)
        color = None
        if self.style & self.COLOR:
            color = self.color

        if color is None:
            if not styles:
                return "<normal>"
            return "<{}>".format(",".join(styles))

        if not styles:
            return "{}".format(self.color)
        return "<{}, [{}]>".format(self.color, ",".join(styles))


class TextStyleField(fields.Field):
    """\
    Serialization of TextStyle, color is not included
    """

    def _serialize(self, value, attr, obj):
        if value is None:
            return []
        return TextStyle.style_list(value)

    def _deserialize(self, value, attr, obj):
        style = TextStyle.NORMAL
        try:
            styles = set(value)
        except:
            raise ValidationError("Invalid style list")
        if "italic" in styles:
            style |= TextStyle.ITALIC
        if "bold" in styles:
            style |= TextStyle.BOLD
        if "underline" in styles:
            style |= TextStyle.UNDERLINE
        return style


class TextStyleSchema(Schema):
    """\
    Schema of Styled Text
    """

    color = ColorField(missing=None)
    style = TextStyleField(missing=[])


TextStyle._schema = TextStyleSchema()


class RichText(object):

    def __init__(self, text: list):
        """\
        text should be list of (style, text) tuple
        """
        self.text = list(text)

    def __repr__(self):
        return "%s" % self.text

    def __eq__(self, other):
        return (isinstance(other, self.__class__) and
                self.text == other.text)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __getitem__(self, i):
        return self.text[i]

    def __len__(self):
        return len(self.text)

    def __iter__(self):
        yield from self.text

    def toPlain(self):
        return ''.join(i[1] for i in self.text)


class RichTextField(fields.Field):
    """\
    RichText field serialization.
    rich_text is a list of (style, text) tuple
    """

    def _serialize(self, value, attr, obj):
        if value is None:
            return None

        try:
            for style, text in value.text:
                if not isinstance(style, TextStyle) or \
                        not isinstance(text, str):
                    raise
        except:
            raise ValidationError(
                "RichText should be a list of style and content")

        return [(s.dump(), t) for s, t in value.text]

    def _deserialize(self, value, attr, obj):
        if value is None:
            return None
        try:
            return RichText([(TextStyle.load(s), t) for s, t in value])
        except:
            raise ValidationError(
                "RichText should be a list of style and content")


class MessageSchema(Schema):
    """\
    Json Schema for Message
    """

    # Where is this message from
    channel = fields.String()
    # message sender
    sender = fields.String()
    # message receiver (usually group id)
    receiver = fields.String()
    # message type
    mtype = fields.String(validate=validate.OneOf(
        (MessageType.Photo, MessageType.Text, MessageType.Sticker,
         MessageType.Location, MessageType.Audio, MessageType.Command,
         MessageType.Event, MessageType.File, MessageType.Animation,
         MessageType.Video),
    ))
    # if message is photo or sticker, this contains url
    media_url = fields.String()
    # message text
    content = fields.String()
    # formated rich text
    rich_text = RichTextField()
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
                 media_url=None, botmsg=False, room=None, opt=None,
                 rich_text=None):
        self.channel = channel
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.rich_text = rich_text
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
            return Message("fishroom", "fishroom", "None", "Error")


class TestRichText(unittest.TestCase):

    def test_eq(self):
        self.assertEqual(RichText([("normal", "Normal")]),
                         RichText([("normal", "Normal")]),
                         "RichText equal function")
        self.assertEqual(
            RichText([
                (TextStyle(color=Color(3, 5)), "Test11"),
                (TextStyle(color=Color(4, 5)), "Test11"),
                (TextStyle(), "Test11"),
            ]),
            RichText([
                (TextStyle(color=Color(3, 5)), "Test11"),
                (TextStyle(color=Color(4, 5)), "Test11"),
                (TextStyle(), "Test11"),
            ]),
            "RichText equal function",
        )

        self.assertEqual(
            TextStyle(italic=1, color=Color(58, 12)),
            TextStyle(italic=1, color=Color(58, 12)),
            "TextStyle equal"
        )

    def test_to_plain(self):
        self.assertEqual(RichText([
            (TextStyle(italic=1), "Test1"),
            (TextStyle(), "Test2"),
            (TextStyle(), "Test3")
        ]).toPlain(), "Test1Test2Test3")

    def test_serialization_deserialization(self):
        c = Color(fg=5, bg=6)
        ts = TextStyle(color=c, italic=1)
        self.assertEqual(
            TextStyle.loads(ts.dumps()),
            ts,
            "TextStyle loads the same value from its dump"
        )
        m = Message(
            channel=ChannelType.Telegram, content="test", sender="tester",
            receiver="tester2", rich_text=RichText([(ts, "test")]),
        )
        self.assertEqual(
            Message.loads(m.dumps()).rich_text,
            RichText([(ts, "test")]),
            "Rich Text should be dumpable and loadable",
        )
        print(m, m.rich_text)


if __name__ == '__main__':

    unittest.main()

# vim: ts=4 sw=4 sts=4 expandtab
