#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import shlex
from collections import namedtuple
from .config import config

LEADING_CHARS = ('/', '.')

CmdHandler = namedtuple(
    'CmdHandler',
    ('func', 'desc', 'usage')
)
CmdMe = config.get("cmd_me", "")

command_handlers = {}


def register_command(cmd, func, **options):
    if cmd in command_handlers:
        raise Exception("Command '%s' already registered" % cmd)
    print("[Fishroom] command `%s` registered" % cmd)
    command_handlers[cmd] = CmdHandler(
        func, options.get("desc", ""), options.get("usage", ""))


def command(cmd, **options):
    def wrapper(func):
        register_command(cmd, func, **options)
    return wrapper


def parse_command(content):
    tokens = shlex.split(content)
    if len(tokens) < 1:
        return None, None
    cmd = tokens.pop(0)
    assert cmd[0] in LEADING_CHARS and len(cmd) > 2
    cmd, *botname = cmd.split('@')
    if len(botname) == 1 and CmdMe not in botname:
        return None, None
    args = tokens
    return cmd[1:], args


def get_command_handler(cmd):
    return command_handlers.get(cmd, None)


@command("help", desc="list commands or usage", usage="help [cmd]")
def list_commands(cmd, *args, **kwargs):
    if len(args) == 0:
        return "\n".join([
            "{}: {}".format(c, h.desc)
            for c, h in command_handlers.items()
        ])

    if len(args) == 1:
        h = get_command_handler(args[0])
        if h is None:
            return
        return "{}: {}\nUsage: {}".format(args[0], h.desc, h.usage)


if __name__ == "__main__":

    @command("test")
    def test(cmd, *args, **kwargs):
        print("Command: ", cmd)
        print("Arguments: ", args)

    print(command_handlers)
    cmd = "/test a b c 'd'"
    cmd, args = parse_command(cmd)
    func = command_handlers[cmd]
    func(cmd, *args)


# vim: ts=4 sw=4 sts=4 expandtab
