# fishroom
![](https://img.shields.io/badge/license-AGPL-blue.svg)
![Proudly Powered by Python3](https://img.shields.io/badge/python-3.4%2C3.5-blue.svg)
[![](https://img.shields.io/badge/%23chat-fishroom-brightgreen.svg)](https://fishroom.tuna.moe/)

Message forwarding for multiple IM protocols

## Motivation
TUNA needs a chatroom, while each IM protocol/software has its own implementation for chatroom.

Unlike email and mailing list, instant messaging is fragmented: everyone prefers different softwares.
As a result, people of TUNA are divided by the IM they use, be it IRC, wechat, telegram, or XMPP.

To reunify TUNA, we created this project to relay messages between IM clients, so that people can enjoy a
big party again.

## Supported IMs

- IRC
- XMPP
- [Matrix](https://matrix.org) (depends on [matrix-python-sdk](https://github.com/matrix-org/matrix-python-sdk))
- Telegram
- Gitter
- Actor (not yet)
- Tox (not yet)
- Wechat (maybe)

## Basic Architecture

Fishroom consists of a *fishroom core* process, which routes messages among IMs and process commands, 
and several IM handler processes to deal with different IMs. These components are connected via Redis pub/sub.

```
+----------+
| IRC      |<-+
+----------+  |
+----------+  |
| XMPP     |<-+
+----------+  |
+----------+  |    +-------+       +---------------+
| Telegram |<-+--> | Redis | <---> | Fishroom Core |
+----------+  |    +-------+       +---------------+
+----------+  |
| Gitter   |<-+
+----------+  |
+----------+  |
| Web      |<-+
+----------+
```

## How to Use

Clone me first
```
git clone https://github.com/tuna/fishroom
cd fishroom
```

### Docker Rocks!

Get a redis docker and run it:

```
docker pull redis:alpine
docker run --name redis -v /var/lib/redis:/data -d redis:alpine
```

Modify the config file, and remember the redis hostname you specified in `config.py`.
I suggest that just use `redis` as the hostname.

```bash
mv fishroom/config.py.example fishroom/config.py
vim fishroom/config.py
```

Modify `Dockerfile`, you may want to change the `sources.list` content.
Build the docker for fishroom:

```
docker build --tag fishroom:dev .
```

Since the code of fishroom often changes, we mount the code as a volume, and link redis to it.

You can test it using
```
# this is fishroom core
docker run -it --rm --link redis:redis -v /path/to/fishroom/fishroom:/data/fishroom fishroom:dev python3 -u -m fishroom.fishroom

# these are fishroom IM interfaces, not all of them are needed
docker run -it --rm --link redis:redis -v /path/to/fishroom/fishroom:/data/fishroom fishroom:dev python3 -u -m fishroom.telegram
docker run -it --rm --link redis:redis -v /path/to/fishroom/fishroom:/data/fishroom fishroom:dev python3 -u -m fishroom.IRC
docker run -it --rm --link redis:redis -v /path/to/fishroom/fishroom:/data/fishroom fishroom:dev python3 -u -m fishroom.gitter
docker run -it --rm --link redis:redis -v /path/to/fishroom/fishroom:/data/fishroom fishroom:dev python3 -u -m fishroom.xmpp
```
You may need `tmux` or simply multiple terminals to run the aforementioned foreground commands.

If everything works, we run it as daemon.
```
docker run -d --name fishroom --link redis:redis -v /path/to/fishroom/fishroom:/data/fishroom fishroom:dev python3 -u -m fishroom.fishroom
docker run -d --name fishroom --link redis:redis -v /path/to/fishroom/fishroom:/data/fishroom fishroom:dev python3 -u -m fishroom.telegram
```

To view the logs, use
```
docker logs fishroom
```

Next we run the web interface, if you have configured the `chat_logger` part in `config.py`.
```
docker run -d --name fishroom-web --link redis:redis -p 127.0.0.1:8000:8000 -v /path/to/fishroom/fishroom:/data/fishroom fishroom:dev python3 -u -m fishroom.web
```
Open your browser, and visit <http://127.0.0.1:8000/>, you should be able to view the web UI of fishoom.


### Docker Sucks!

Install and run redis first, assuming you use ubuntu or debian.

```
apt-get install redis
```

Modify the config file, the redis server should be on addr `127.0.0.1` and port `6379`.

```bash
mv fishroom/config.py.example fishroom/config.py
vim fishroom/config.py
```

Ensure your python version is at least 3.4, next, we install the dependencies for fishroom.

```
apt-get install -y python3-dev python3-pip libmagic1 libjpeg-dev libpng-dev libwebp-dev zlib1g-dev gcc
pip3 install --upgrade pip setuptools
pip3 install -r requirements.txt
```

Run fishroom and fishroom web.
```
# run fishroom core
python3 -m fishroom.fishroom

# start IM interfaces, select not all of them are needed
python3 -m fishroom.telegram
python3 -m fishroom.IRC
python3 -m fishroom.gitter
python3 -m fishroom.xmpp

python3 -m fishroom.web
```
Open your browser, and visit <http://127.0.0.1:8000/>, you should be able to view the web UI of fishoom.

Good Luck!

## Related Projects

- [Telegram2IRC](https://github.com/tuna/telegram2irc)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [IRCBindXMPP](https://github.com/lilydjwg/ircbindxmpp)
- [SleekXMPP](https://pypi.python.org/pypi/sleekxmpp)
	- Multi-User Chat Supported (http://sleekxmpp.com/getting_started/muc.html)
- [Tox-Sync](https://github.com/aitjcize/tox-irc-sync)
- [qwx](https://github.com/xiangzhai/qwx)

## LICENSE

```
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
```
