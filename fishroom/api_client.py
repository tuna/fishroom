#!/usr/bin/env python
# -*- coding:utf-8 -*-
import hashlib
from .config import config


class TokenException(Exception):
    pass


class APIClientManager(object):

    clients_key = config["redis"]["prefix"] + ":api_clients"
    clients_name_key = config["redis"]["prefix"] + ":api_clients_name"
    queue_key = config["redis"]["prefix"] + ":api:{token_id}"
    max_buffer = 15

    def __init__(self, r):
        self.r = r

    def publish(self, msg):
        clients = self.r.hgetall(self.clients_key)
        p = self.r.pipeline(transaction=False)
        for token_id in clients:
            k = self.queue_key.format(token_id=token_id.decode('utf-8'))
            p.rpush(k, msg.dumps())
            p.ltrim(k, -self.max_buffer, -1)
            p.expire(k, 60)
        p.execute()

    def auth(self, token_id, token_key):
        saved = self.r.hget(self.clients_key, token_id)
        if not saved:
            return False

        m = hashlib.sha1()
        m.update(token_key.encode('utf-8'))
        return m.digest() == saved

    def list_clients(self):
        tokens = self.r.hgetall(self.clients_key)
        names_map = self.r.hgetall(self.clients_name_key)
        ids = [_id.decode('utf-8') for _id in tokens]
        names = [names_map.get(_id, b"nobot").decode('utf-8') for _id in tokens]
        return zip(ids, names)

    def add(self, token_id, token_key, name):
        if self.r.hexists(self.clients_key, token_id):
            raise TokenException("Token Id Existed!")

        m = hashlib.sha1()
        m.update(token_key.encode('utf-8'))
        self.r.hset(self.clients_key, token_id, m.digest())
        self.r.hset(self.clients_name_key, token_id, name)

    def get_name(self, token_id):
        n = self.r.hget(self.clients_name_key, token_id)
        return n.decode('utf-8') if isinstance(n, bytes) else None

    def revoke(self, token_id):
        self.r.hdel(self.clients_key, args.token_id)
        queue = self.queue_key.format(token_id=token_id)
        self.r.delete(queue)

    def exists(self, token_id):
        return self.r.hexists(self.clients_key, args.token_id)


if __name__ == "__main__":
    import sys
    import argparse
    import string
    import random
    from .db import get_redis

    def token_id_gen(N):
        return ''.join(
            random.choice(string.digits)
            for _ in range(N)
        )

    def token_key_gen(N):
        return ''.join(
            random.choice(string.ascii_letters + string.digits)
            for _ in range(N)
        )

    parser = argparse.ArgumentParser("API tokens management")
    subparsers = parser.add_subparsers(dest="command", help="valid subcommands")
    subparsers.add_parser('list', aliases=['l'], help="list tokens")
    sp = subparsers.add_parser('add', aliases=['a'], help="add a token")
    sp.add_argument('-n', '--name', required=True, help='bot name')
    sp.add_argument('token_id', nargs='?', default='',
                    help='token id (auto generate if unspecified)')
    sp.add_argument('token_key', nargs='?', default='',
                    help='token key (auto generate if unspecified)')
    sp = subparsers.add_parser('revoke', aliases=['r'], help="revoke a token")
    sp.add_argument('token_id', help='token_id')
    sp = subparsers.add_parser('test', help="test authenticating a token")
    sp.add_argument('token_id', help='token id')
    sp.add_argument('token_key', help='token key')
    subparsers.add_parser('help', help="print help")

    args = parser.parse_args()

    if args.command == "help":
        parser.print_help()
        sys.exit(0)

    r = get_redis()
    mgr = APIClientManager(r)

    if args.command in ("list", "l"):
        print("\n".join(["{}: {}".format(_id, n)
                         for _id, n in mgr.list_clients()]))

    elif args.command in ("add", "a"):
        if args.token_id and args.token_key:
            token_id, token_key = args.token_id, args.token_key
        elif not (args.token_id or args.token_key):
            token_id, token_key = token_id_gen(8), token_key_gen(16)
            while mgr.exists(token_id):
                token_id = token_id_gen(8)
        else:
            print('Please specify both or neither of token_id and token_key')
            sys.exit(-1)
        try:
            mgr.add(token_id, token_key, args.name)
        except TokenException as e:
            print(e)
        else:
            print(token_id, token_key, args.name)

    elif args.command in ("revoke", "r"):
        yn = input("Revoke token_id: {}? Y/[N]:".format(args.token_id))
        if yn.lower() == "y":
            mgr.revoke(args.token_id)
        else:
            print("Cancelled")

    elif args.command == "test":
        print(mgr.auth(args.token_id, args.token_key))


# vim: ts=4 sw=4 sts=4 expandtab
