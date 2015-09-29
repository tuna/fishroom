#!/usr/bin/env python
# -*- coding:utf-8 -*-
from ..command import command
from ..config import config
from ..db import get_redis


class VoteManager(object):

    topic_key = config["redis"]["prefix"] + ":" + "current_vote:" + "{room}" + ":topic"
    option_key = config["redis"]["prefix"] + ":" + "current_vote:" + "{room}" + ":options"
    voters_key = config["redis"]["prefix"] + ":" + "current_vote:" + "{room}" + ":voters"

    def __init__(self):
        self.r = get_redis()

    def new_vote(self, room, topic):
        key = self.topic_key.format(room=room)
        if self.r.get(key) is not None:
            return
        return self.r.set(key, topic)

    def get_vote(self, room):
        key = self.topic_key.format(room=room)
        topic = self.r.get(key)
        if topic is None:
            return (None, None, None)
        okey = self.option_key.format(room=room)
        vkey = self.voters_key.format(room=room)
        options = self.r.lrange(okey, 0, -1)
        votes = self.r.hgetall(vkey)
        topic = topic.decode('utf-8')
        options = [o.decode('utf-8') for o in options]
        votes = {k.decode('utf-8'): idx.decode('utf-8')
                 for k, idx in votes.items()}
        return (topic, options, votes)

    def end_vote(self, room):
        tkey = self.topic_key.format(room=room)
        okey = self.option_key.format(room=room)
        vkey = self.voters_key.format(room=room)
        self.r.delete(tkey, okey, vkey)

    def add_option(self, room, option):
        okey = self.option_key.format(room=room)
        self.r.rpush(okey, option)

    def vote_for(self, room, voter, option_idx):
        okey = self.option_key.format(room=room)
        vkey = self.voters_key.format(room=room)
        idx = int(option_idx)
        opt = self.r.lindex(okey, idx)
        if opt is not None:
            self.r.hset(vkey, voter, idx)
            return opt.decode('utf-8')
        return None


_vote_mgr = VoteManager()
votemarks = ['⭐', '👍', '❤ ', '☀', ]


@command("vote", desc="Vote plugin",
         usage="\n"
         "vote: show current vote\n"
         "vote new '<topic>': create new vote\n"
         "vote add '<option>': add vote option\n"
         "vote <num>: vote for option num\n"
         "vote end: end voting")
def vote(cmd, *args, **kwargs):
    if 'room' not in kwargs or 'msg' not in kwargs:
        return None
    room = kwargs['room']
    msg = kwargs['msg']

    def get_result(room):
        topic, options, voters = _vote_mgr.get_vote(room)
        if topic is None:
            return "No on-going voting"
        counts = [0 for _ in options]
        for _, idx in voters.items():
            counts[int(idx)] += 1

        ret = topic + "\n"
        for i, (opt, cnt) in enumerate(zip(options, counts), 1):
            mark = votemarks[(i-1) % len(votemarks)]
            ret += "{}. {}: {} {}\n".format(i, opt, mark*cnt, cnt)
        return ret

    if len(args) == 0:
        return get_result(room)

    args = list(args)
    subcmd = args.pop(0)

    sender = msg.sender
    if subcmd == "new":
        topic = ' '.join(args)
        if not topic:
            return "use /vote new <topic> to set topic"
        if _vote_mgr.new_vote(room, topic) is None:
            return "There is an on-going voting, end it before creating new."
        return "👍 {} created vote: {}".format(sender, topic)

    elif subcmd == "add":
        opt = ' '.join(args)
        if not opt:
            return "use /vote add <option> to add option"
        _vote_mgr.add_option(room, opt)
        return "❤ {} added option: {}".format(sender, opt)
    elif subcmd == "end":
        ret = "❤  End vote, final result: \n" + get_result(room)
        _vote_mgr.end_vote(room)
        return ret
    else:
        try:
            idx = int(subcmd) - 1
            opt = _vote_mgr.vote_for(room, sender, idx)
            if opt is None:
                return "vote failed"
            return "👍 {} voted for: {}".format(sender, opt)

        except:
            pass

    return "Invalid command, try .help vote for usage"


# vim: ts=4 sw=4 sts=4 expandtab
