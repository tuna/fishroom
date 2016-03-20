import unittest


class Text(object):
    def __init__(self, msg):
        self.msg = msg

    @classmethod
    def fromIRC(cls, msg):
        pass

    @classmethod
    def fromTelgram(cls, msg):
        pass

    @classmethod
    def fromHTML(cls, msg):
        pass

    def toIRC(self):
        pass

    def toTelegram(self):
        pass

    def toHTML(self):
        pass


class TextTest(unittest.TestCase):
    def test_paser_irc(self):
        self.assertEqual(Text.fromIRC("Normal"),
                         Text([("normal", "Normal")]))


if __name__ == '__main__':
    unittest.main()
