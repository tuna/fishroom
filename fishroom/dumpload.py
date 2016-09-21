#!/usr/bin/env python3
import json
import base64
from .api_client import APIClientManager
from .telegram import RedisNickStore, RedisStickerURLStore
from .counter import Counter


def dump_meta(r, tofilename):
    backup = {}

    rkeys = [
        APIClientManager.clients_name_key,
        RedisNickStore.NICKNAME_KEY, RedisNickStore.USERNAME_KEY,
        RedisStickerURLStore.STICKER_KEY,
    ]

    for rk in rkeys:
        b = {}
        for k, v in r.hgetall(rk).items():
            try:
                k, v = k.decode('utf-8'), v.decode('utf-8')
            except:
                continue
            b[k] = v
        backup[rk] = b

    backup[APIClientManager.clients_key] = {
        k.decode('utf-8'): base64.b64encode(v).decode('utf-8')
        for k, v in r.hgetall(APIClientManager.clients_key).items()
    }

    counters = [Counter(r, name) for name in ('qiniu', )]
    for c in counters:
        backup[c.key] = c.incr()

    with open(tofilename, 'w') as f:
        json.dump(backup, f, indent=4)


def load_meta(r, fromfile):
    with open(fromfile, 'r') as f:
        backup = json.load(f)

    for rk, b in backup.items():
        if rk == APIClientManager.clients_key:
            for token_id, b64token in b.items():
                r.hset(rk, token_id, base64.b64decode(b64token))
        elif isinstance(b, int):
            r.set(rk, b)
        elif isinstance(b, dict):
            for k, v in b.items():
                r.hset(rk, k, v)


if __name__ == "__main__":
    import os
    import argparse
    import sys
    from .db import get_redis

    parser = argparse.ArgumentParser("Import/Export data from/to json")
    subparsers = parser.add_subparsers(dest="command", help="valid subcommands")
    dp = subparsers.add_parser('dump', aliases=['d'], help="dump data")
    dp.add_argument('-d', '--dump-dir', help="where to store the backup json")
    lp = subparsers.add_parser('load', aliases=['l'], help="load data")
    lp.add_argument('--meta-file', help='json is metadata (nicks, cache, etc.)')
    subparsers.add_parser('help', help="print help")

    args = parser.parse_args()

    if args.command == "help":
        parser.print_help()
        sys.exit(0)

    r = get_redis()
    mgr = APIClientManager(r)

    if args.command in ('dump', 'd'):
        dump_meta(r, os.path.join(args.dump_dir, "meta.json"))
    elif args.command in ('load', 'l'):
        load_meta(r, args.meta_file)


# vim: ts=4 sw=4 sts=4 expandtab
