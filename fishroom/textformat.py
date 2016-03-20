import unittest


class Text(object):
    def __init__(self, text):
        self.text = text

    @classmethod
    def fromIRC(cls, text):
        formatted = []
        controls = ['\x02', '\x03', '\x1d', '\x1f', '\x16', '\x0f']
        current_str = ""
        current_state = "normal"
        if len(text) > 0:
            c = text[0]
            if c in controls:
                current_state = "controls"
        current_color_num = 0

        def text_iter(text):
            for index in range(len(text)):
                if index == len(text) - 1:
                    yield text[index], None
                else:
                    yield text[index], text[index + 1]

        for (c, cn) in text_iter(text):
            if current_state == "controls":
                if not cn:
                    continue
                if cn in controls:
                    current_state = "controls"
                    continue
                if c == '\x03':
                    if cn.isnumeric():
                        current_state = "color"
                        current_color_num = 1
                    else:
                        current_state = "normal"
                elif c == "\x02":
                    current_str = ""
                    current_state = "bold"
                continue

            if current_state == "bold":
                if c == '\x02':
                    formatted.append((current_state, current_str))
                    if cn in controls:
                        current_str = ""
                        current_state = "controls"
                    else:
                        current_str = ""
                        current_state = "normal"
                if c not in controls:
                    current_str += c
                continue

            if current_state == "color":
                if c == '\x03':
                    formatted.append((current_state, current_str))
                    current_str = ""
                    if not cn:
                        continue
                    elif cn.isnumeric():
                        current_color_num = 1
                    elif cn in controls:
                        current_state = "controls"
                    else:
                        current_state = "normal"
                    continue
                # xx,xx xxx
                if current_color_num > 5 or current_color_num == 0:
                    current_color_num = 0
                    current_str += c
                    if not cn:
                        formatted.append((current_state, current_str))
                elif current_color_num == 1:
                    if cn and cn == ",":
                        current_color_num = 3
                    elif cn and not cn.isnumeric():
                        current_color_num = 6
                    else:
                        current_color_num += 1
                elif current_color_num == 2:
                    if cn == ",":
                        current_color_num += 1
                    else:
                        current_color_num = 6
                elif current_color_num == 3:
                    if cn and not cn.isnumeric():
                        current_color_num = 6
                    else:
                        current_color_num += 1
                elif current_color_num == 4:
                    if cn and not cn.isnumeric():
                        current_color_num = 6
                    else:
                        current_color_num += 1
                elif current_color_num == 5:
                    current_color_num += 1
                continue
            if current_state == "normal":
                current_str += c
                if not cn:
                    formatted.append((current_state, current_str))
                    continue
                if cn in controls:
                    formatted.append((current_state, current_str))
                    current_str = ""
                    current_state = "controls"
                    continue

        return Text(formatted)

    @classmethod
    def fromTelgram(cls, text):
        pass

    @classmethod
    def fromHTML(cls, text):
        pass

    def toIRC(self):
        pass

    def toTelegram(self):
        pass

    def toHTML(self):
        pass

    def toPlain(self):
        return ''.join(i[1] for i in self.text)

    def __eq__(self, other):
        # print(self.text)
        # print(other.text)
        return (isinstance(other, self.__class__) and
                self.text == other.text)

    def __ne__(self, other):
        return not self.__eq__(other)


class TextTest(unittest.TestCase):
    def test_eq(self):
        self.assertEqual(Text([("normal", "Normal")]),
                         Text([("normal", "Normal")]),
                         "Class equal function")

    def test_to_plain(self):
        self.assertEqual(Text([
            ("color", "Test1"), ("color", "Test2"), ("normal", "Test3")
        ]).toPlain(), "Test1Test2Test3")

    def test_paser_irc(self):
        test_cases = [
            ("Test1", [("normal", "Test1")]),
            ("\x03Test2", [("normal", "Test2")]),
            ("\x03Test3\x03", [("normal", "Test3")]),
            ("\x033", []),
            ("\x033Test5", [("color", "Test5")]),
            ("\x033Test6\x03", [("color", "Test6")]),
            ("\x033,5Test7", [("color", "Test7")]),
            ("\x033,5Test8\x03", [("color", "Test8")]),
            ("\x033,05Test8\x03", [("color", "Test8")]),
            ("\x0303,05Test8\x03", [("color", "Test8")]),
            ("Test9\x03Test9", [("normal", "Test9"), ("normal", "Test9")]),
            ("\x033,5Test10\x03Test10\x03Test10", [
                ("color", "Test10"), ("normal", "Test10"), ("normal", "Test10")
            ]),
            ("\x033,5Test11\x034,5Test11\x03Test11", [
                ("color", "Test11"), ("color", "Test11"), ("normal", "Test11")
            ]),
            ("\x033,045Test12", [("color", "5Test12")]),
            ("\x03123,045Test12", [("color", "3,045Test12")]),
            ("\x02Test13\x02", [("bold", "Test13")]),
            ("Test14\x02Test14\x02Test14", [
                ("normal", "Test14"), ("bold", "Test14"), ("normal", "Test14")
            ]),
            ("\x1d\x02Test15\x02", [("bold", "Test15")]),
            ("\x1d\x02Test16\x02\x1d", [("bold", "Test16")]),
        ]
        for (_input, output) in test_cases:
            with self.subTest(_input=_input, output=output):
                self.assertEqual(Text.fromIRC(_input), Text(output))


if __name__ == '__main__':
    unittest.main()
