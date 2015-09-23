#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import shlex

command_handlers = {}

LEADING_CHARS = ('/', '.')


def register_command(cmd, func):
    if cmd in command_handlers:
        raise Exception("Command '%s' already registed" % cmd)
    print("[Fishroom] command `%s` registerred" % cmd)
    command_handlers[cmd] = func


def command(*cmds, **options):
    def wrapper(func):
        for cmd in cmds:
            register_command(cmd, func)
    return wrapper


class InvalidCommand(Exception):
    pass


def parse_command(content):
    tokens = shlex.split(content)
    if len(tokens) < 1:
        raise InvalidCommand()
    cmd = tokens.pop(0)
    assert cmd[0] in LEADING_CHARS and len(cmd) > 2
    args = tokens
    return cmd[1:], args


def get_command_handler(cmd):
    return command_handlers.get(cmd, None)


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
