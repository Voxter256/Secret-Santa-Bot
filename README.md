## Synopsis

This is a bot for Telegram written in Python made to manage a group's Secret Santa Exchange. It is unique from other bots that I found in that it is centrally managed through a group chat, with private messages for addresses and results. When deployed it will be available at @GroupSecretSantaBot

## Code Example

`/join`  
Joins the Secret Santa Exchange in this chat group

`/not @MySO`  
Prevents you from being assigned a Santa to people you're already getting gifts for outside this exchange

`/start_exchange`  
Finds every possible combination that doesn't have you picking yourself or anyone selected with `/not`, randomly selects one, then sends each participant a private message with their username and address

## Motivation

Christmas can be stressful if you have to find gifts for everyone all within your budget. I've been in Secret Santa's where a third party can't participate, instead mediating the event. Odds are good that names will be drawn multiple times because of conflicts. This is meant to simply the process, especially in larger groups.

## Installation

Copy the default_config.ini to config.ini and insert your telegram token from the BotFather

This Bot currently uses SQLite and the following python plugins from pip:
SQLAlchemy
python-telegram-bot

## API Reference

###### All Users

`/help`  
Shows this list of commands.

`/start`  
Sent only in a private message to begin personal setup.

`/hello`  
Sent only in a group chat to enable the gift exchange.

`/settings`  
Sent only in a group chat by an admin to choose what this exchange requires.

`/address`  
Sent only in a private message to show and update your optional mailing address.

`/wish`  
Sent only in a private message to edit your wishlist for an exchange you have joined.

`/join`  
Joins you in the gift exchange in this chat.

`/status`  
Gets the status of this chat's exchange.

`/not @Mention`  
Prevents you from being paired up with this participant.

`/allow @Mention`  
Removes block that was preventing you from being paired up with this participant.

`/leave`  
You will leave the gift exchange in this chat.

`/start_exchange`  
Begins the gift exchange by assigning a recipient to every participant, then messaging them privately the details. When the wishlist is enabled and someone has no items, it names them and stops; `/start_exchange confirm` starts anyway.

`/reset_exchange`  
Resets the gift exchange by removing every participant's assigned recipient.

## Exchange settings

Both options are off by default and are toggled per group with `/settings`, by a group admin:

- **Address required** — when on, the delivery message includes the recipient's mailing address. Groups that existed before this option was added were backfilled to on, so their behaviour did not change; new groups start with it off.
- **Wishlist** — when on, participants can keep a wishlist for this exchange and the delivery message includes the recipient's items.

Wishlists are scoped to a single exchange, so the same person can keep different lists for different groups. They are edited in a private chat with `/wish` and are never posted to the group by the bot. Limits: 1024 characters per item, 20 items, 3500 characters in total — the total is what keeps a list deliverable inside Telegram's 4096-character message limit.

### Sharing a wishlist

Wishlists can be shared through Telegram inline mode: type the bot's username in any chat and pick an exchange. Inline mode has to be enabled once in BotFather:

    /setinline

with a placeholder of `wishlist`. The same value can be set later with `setMySettings` and `inline_query_placeholder`. The share button in `/wish` pre-fills the query with that exchange, so the picker shows a single result.


## Contributors

I'm currently tracking issues here in GitHub. I encourage feature suggestions as well as code improvement! There is plenty of work that needs done

## License

MIT License per LICENSE.txt
