# fishroom
Message forwarding for multiple IM protocols

## Motivation
TUNA needs a chatroom, while each IM protocol/software has its own implementation for chatroom.

Unlike email and mailing list, instant messaging is fragmented and everybody has different preferred software.
As a result, TUNA as a group of people, was splitted into IRC users, wechat users, telegram users, XMPP users, etc.

To reunify TUNA, we created this project to synchronize messages between IM clients, so that people can enjoy a
big party again.

## Supported IMs

- IRC
- XMPP
- Telegram
- Tox (not yet)
- Wechat (maybe)

## TODO

- [x] Implement Telegram protocol using Telegram Bot API
- [x] Plugin system
- [x] Chat with Bots
- [x] Convert `^nickname:` and `@nickname` to `@username`

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
