#!/usr/bin/env python
# -*- coding:utf-8 -*-
from ..command import command
from ..config import config
from ..db import get_redis


class NoVote(Exception):
    pass


class NoOptions(Exception):
    pass


class VoteExisted(Exception):
    pass


class VoteStarted(Exception):
    pass


class VoteNotStarted(Exception):
    pass


class VoteManager(object):

    topic_key = config["redis"]["prefix"] + ":" + "current_vote:" + "{room}" + ":topic"
    status_key = config["redis"]["prefix"] + ":" + "current_vote:" + "{room}" + ":status"
    option_key = config["redis"]["prefix"] + ":" + "current_vote:" + "{room}" + ":options"
    voters_key = config["redis"]["prefix"] + ":" + "current_vote:" + "{room}" + ":voters"

    STAT_NEW = b"new"
    STAT_VOTING = b"voting"

    def __init__(self):
        self.r = get_redis()

    def new_vote(self, room, topic):
        key = self.topic_key.format(room=room)
        if self.r.get(key) is not None:
            raise VoteExisted()
        self.r.set(key, topic)
        key = self.status_key.format(room=room)
        self.r.set(key, self.STAT_NEW)

    def get_vote_topic(self, room):
        key = self.topic_key.format(room=room)
        topic = self.r.get(key)
        if topic is None:
            raise NoVote()
        return topic

    def get_vote(self, room):
        key = self.topic_key.format(room=room)
        topic = self.r.get(key)
        if topic is None:
            raise NoVote()
        skey = self.status_key.format(room=room)
        okey = self.option_key.format(room=room)
        vkey = self.voters_key.format(room=room)
        status = self.r.get(skey)
        options = self.r.lrange(okey, 0, -1)
        votes = self.r.hgetall(vkey)
        topic = topic.decode('utf-8')
        options = [o.decode('utf-8') for o in options]
        votes = {k.decode('utf-8'): idx.decode('utf-8')
                 for k, idx in votes.items()}
        return (topic, status, options, votes)

    def start_vote(self, room):
        key = self.topic_key.format(room=room)
        topic = self.r.get(key)
        if topic is None:
            raise NoVote()
        okey = self.option_key.format(room=room)
        if self.r.llen(okey) == 0:
            raise NoOptions()
        skey = self.status_key.format(room=room)
        if self.r.get(skey) == self.STAT_VOTING:
            raise VoteStarted()
        self.r.set(skey, self.STAT_VOTING)

    def end_vote(self, room):
        tkey = self.topic_key.format(room=room)
        okey = self.option_key.format(room=room)
        vkey = self.voters_key.format(room=room)
        self.r.delete(tkey, okey, vkey)

    def add_option(self, room, option):
        tkey = self.topic_key.format(room=room)
        if self.r.get(tkey) is None:
            raise NoVote()
        skey = self.status_key.format(room=room)
        if self.r.get(skey) != self.STAT_NEW:
            raise VoteStarted()
        okey = self.option_key.format(room=room)
        self.r.rpush(okey, option)

    def vote_for(self, room, voter, option_idx):
        skey = self.status_key.format(room=room)
        if self.r.get(skey) != self.STAT_VOTING:
            raise VoteNotStarted()
        okey = self.option_key.format(room=room)
        vkey = self.voters_key.format(room=room)
        idx = int(option_idx)
        opt = self.r.lindex(okey, idx)
        if opt is not None:
            self.r.hset(vkey, voter, idx)
            return opt.decode('utf-8')
        raise NoOptions()

    def vote_for_opt(self, room, voter, option_str):
        skey = self.status_key.format(room=room)
        if self.r.get(skey) != self.STAT_VOTING:
            raise VoteNotStarted()
        okey = self.option_key.format(room=room)
        vkey = self.voters_key.format(room=room)
        for idx, opt in enumerate(self.r.lrange(okey, 0, -1)):
            if opt.decode('utf-8') == option_str:
                self.r.hset(vkey, voter, idx)
                return idx
        raise NoOptions()


_vote_mgr = VoteManager()
votemarks = ['⭐', '👍', '❤ ', '☀', ]


@command("vote", desc="Vote plugin",
         usage="\n"
         "vote: show current vote\n"
         "vote new '<topic>': create new vote\n"
         "vote add '<option>': add vote option\n"
         "vote start: start voting\n"
         "vote <num>: vote for option num\n"
         "vote end: end voting")
def vote(cmd, *args, **kwargs):
    if 'room' not in kwargs or 'msg' not in kwargs:
        return None
    room = kwargs['room']
    msg = kwargs['msg']

    def get_result(room, end=False, start=False):
        try:
            topic, status, options, voters = _vote_mgr.get_vote(room)
        except NoVote:
            return "No on-going voting"

        counts = [0 for _ in options]
        for _, idx in voters.items():
            counts[int(idx)] += 1

        ret = topic + "\n"
        for i, (opt, cnt) in enumerate(zip(options, counts), 1):
            mark = votemarks[(i-1) % len(votemarks)]
            ret += "{}. {}: {} {}\n".format(i, opt, mark*cnt, cnt)

        if status == VoteManager.STAT_NEW:
            ret += "voting not started yet"
        else:
            if not end:
                ret += "use /vote <number> to vote for your option\n"
            if start:
                ret += "use /vote to show vote status\n"
        return ret.strip()

    if len(args) == 0:
        return get_result(room)

    args = list(args)
    subcmd = args.pop(0)

    sender = msg.sender
    if subcmd == "new":
        topic = ' '.join(args)
        if not topic:
            return "use /vote new <topic> to set topic"
        try:
            _vote_mgr.new_vote(room, topic)
        except VoteExisted:
            return "There is an on-going voting, end it before creating new."

        return (
            "👍 {} created vote: {}\n"
            "use /vote add <option> to add options\n"
            "and /vote start to start voting"
        ).format(sender, topic)

    elif subcmd == "add":
        opt = ' '.join(args)
        if not opt:
            return "use /vote add <option> to add option"
        try:
            _vote_mgr.add_option(room, opt)
        except NoVote:
            return "no ongoing votes"
        except VoteStarted:
            return "vote started, cannot add options now"

        return "👍"

    elif subcmd == "start":
        try:
            _vote_mgr.start_vote(room)
        except NoVote:
            return "no ongoing votes"
        except NoOptions:
            return "no options for the vote, cannot start"
        except VoteStarted:
            return "cannot start a vote twice"

        topic, _, options, _ = _vote_mgr.get_vote(room)
        return get_result(room, start=True)

    elif subcmd == "end":
        ret = "❤  End vote, final result: \n" + get_result(room, end=True)
        _vote_mgr.end_vote(room)
        return ret

    else:
        try:
            if subcmd == "for":
                opt = ' '.join(args)
                if not opt:
                    return "use /vote for <str> to vote"
                idx = _vote_mgr.vote_for_opt(room, sender, opt)
            else:
                idx = int(subcmd) - 1
                opt = _vote_mgr.vote_for(room, sender, idx)

        except NoOptions:
            return "invalid option"
        except VoteNotStarted:
            return "vote not started"
        except:
            return None

        return votemarks[idx % len(votemarks)]

    return "Invalid command, try .help vote for usage"


# vim: ts=4 sw=4 sts=4 expandtab
