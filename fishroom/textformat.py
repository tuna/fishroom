"""
This is for text formating

IRC: https://github.com/myano/jenni/wiki/IRC-String-Formatting
"""

import unittest
from .models import TextStyle, RichText, Color


class IRCCtrl(object):
    BOLD = '\x02'
    COLOR = '\x03'
    ITALIC = '\x1d'
    UNDERLINE = '\x1f'
    SWAPCOLOR = '\x16'
    RESET = '\x0f'

    _controls = set([BOLD, COLOR, ITALIC, UNDERLINE, SWAPCOLOR, RESET])
    styles = {
        BOLD: TextStyle.BOLD,
        COLOR: TextStyle.COLOR,
        ITALIC: TextStyle.ITALIC,
        UNDERLINE: TextStyle.UNDERLINE,
    }

    @classmethod
    def is_control(cls, t):
        return t in cls._controls


class TextFormatter(object):

    @classmethod
    def parseIRC(cls, text):
        """
        returns: Text object, with text field set to a list of (style, text)
        """

        if len(text) == 0:
            return [(TextStyle.NORMAL, "")]

        formatted = []
        cur_style = TextStyle()
        cur_str = ""
        color_fg, color_bg = "", None  # ANSI color number

        for (c, cn) in zip(text, list(text[1:])+[None]):
            if IRCCtrl.is_control(c):
                if cur_str:
                    formatted.append((cur_style, cur_str))
                    cur_str = ""
                    cur_style = cur_style.copy()

                if not cn:
                    break

                if c not in (IRCCtrl.COLOR, IRCCtrl.SWAPCOLOR, IRCCtrl.RESET):
                    # use bit xor to toggle style
                    cur_style.toggle(IRCCtrl.styles[c])

                elif c == IRCCtrl.COLOR:
                    # color is set only if valid color option presents
                    if cn.isnumeric():
                        color_fg = cn  # should be expanded later
                        cur_style.set(TextStyle.COLOR)
                    else:
                        color_fg, color_bg = "", None
                        cur_style.clear(TextStyle.COLOR)

                elif c == IRCCtrl.SWAPCOLOR:
                    if cur_style.has_color():
                        cur_style.color.swap()

                elif c == IRCCtrl.RESET:
                    cur_style = TextStyle()

            else:
                if color_fg:
                    # read color number
                    if color_bg is None:
                        # reading color_fg
                        if len(color_fg) == 1:
                            if cn.isnumeric():
                                color_fg += cn
                            elif cn == ',':
                                color_bg = ""
                            else:
                                cur_style.set_color(int(color_fg))
                                color_fg, color_bg = "", None
                        elif len(color_fg) == 2:
                            if cn == ',':
                                color_bg = ""
                            else:
                                cur_style.set_color(int(color_fg))
                                color_fg, color_bg = "", None
                    elif isinstance(color_bg, str):
                        # reading color_bg
                        if len(color_bg) == 0:
                            if cn.isnumeric():
                                color_bg = cn
                            else:
                                # "if the charter after ',' is not number"
                                cur_style.set_color(int(color_fg))
                                color_fg, color_bg = "", None
                                cur_str = ","
                        elif len(color_bg) == 1:
                            if cn.isnumeric():
                                color_bg += cn
                            else:
                                cur_style.set_color(
                                    int(color_fg), int(color_bg))
                                color_fg, color_bg = "", None
                        elif len(color_bg) == 2:
                            cur_style.set_color(int(color_fg), int(color_bg))
                            color_fg, color_bg = "", None
                else:
                    # read normal text
                    cur_str += c
                    if not cn:
                        formatted.append((cur_style, cur_str))

        return RichText(formatted)

    @classmethod
    def parseTelgram(cls, text):
        pass

    @classmethod
    def parseHTML(cls, text):
        pass


class TextTest(unittest.TestCase):

    def test_parse_irc(self):
        test_cases = [
            ("Test1", [(TextStyle(), "Test1")]),
            ("\x03Test2", [(TextStyle(), "Test2")]),
            ("\x03Test2\x03", [(TextStyle(), "Test2")]),
            ("\x03", []),
            ("\x033Test5", [(TextStyle(color=Color(3)), "Test5")]),
            ("\x033Test6\x03", [(TextStyle(color=Color(3)), "Test6")]),
            ("\x033,5Test7", [(TextStyle(color=Color(3, 5)), "Test7")]),
            ("Test9\x03Test9", [(TextStyle(), "Test9"), (TextStyle(), "Test9")]),
            ("\x033,5Test10\x03Test10\x03Test10", [
                (TextStyle(color=Color(3, 5)), "Test10"),
                (TextStyle(), "Test10"),
                (TextStyle(), "Test10"),
            ]),
            ("\x033,5Test11\x0f\x02Test11\x03Test11", [
                (TextStyle(color=Color(3, 5)), "Test11"),
                (TextStyle(bold=1), "Test11"),
                (TextStyle(bold=1), "Test11"),
            ]),
            ("\x033,045Test12", [(TextStyle(color=Color(3, 4)), "5Test12")]),
            ("\x03123,045Test13", [(TextStyle(color=Color(12)), "3,045Test13")]),
            ("Test14\x02\x034Test14\x02\x03Test14", [
                (TextStyle(), "Test14"),
                (TextStyle(bold=1, color=Color(4)), "Test14"),
                (TextStyle(), "Test14")
            ]),
            ("\x1d\x02Test15\x02\x1d", [(TextStyle(bold=1, italic=1), "Test15")]),
            ("\x035,2Test16\x16Test16", [
                (TextStyle(color=Color(5, 2)), "Test16"),
                (TextStyle(color=Color(2, 5)), "Test16"),
            ]),
            ("Test17\x035,2Test17\x16\x02Test17\x0fTest17", [
                (TextStyle(), "Test17"),
                (TextStyle(color=Color(5, 2)), "Test17"),
                (TextStyle(color=Color(2, 5), bold=1), "Test17"),
                (TextStyle(), "Test17"),
            ]),
            (
                ("bigeagle: \x0304errors:\x0f source_file.java:1: error: class,"
                 "interface, or enum expected\x0304\\n\x0f print(1)"
                 "\x0304\\n\x0f ^\x0304\\n\x0f 1 error"),
                [
                    (TextStyle(), "bigeagle: "),
                    (TextStyle(color=Color(4)), "errors:"),
                    (TextStyle(), (
                        " source_file.java:1: error: class,"
                        "interface, or enum expected"
                    )),
                    (TextStyle(color=Color(4)), "\\n"),
                    (TextStyle(), " print(1)"),
                    (TextStyle(color=Color(4)), "\\n"),
                    (TextStyle(), " ^"),
                    (TextStyle(color=Color(4)), "\\n"),
                    (TextStyle(), " 1 error"),
                ]
             ),

        ]
        for (_input, output) in test_cases:
            with self.subTest(_input=_input, output=output):
                self.assertEqual(
                    TextFormatter.parseIRC(_input), RichText(output)
                )


if __name__ == '__main__':
    unittest.main()
