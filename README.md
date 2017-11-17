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
`/start`  
Sent only in a private message to begin personal setup. 

`/hello`  
Sent only in a group chat to enable the gift exchange. 

`/join`  
Joins you in the gift exchange in this chat.  

`/not @Mention`  
Prevents you from being paired up with this participant. 

`/allow @Mention`  
Removes block that was preventing you from being paired up with this participant. 
 
`/leave`  
You will leave the gift exchange in this chat. 

`/start_exchange`  
Begins the gift exchange by assigning a recipient to every participant, then messaging them privately the details.
  
`/reset_exchange`   
Resets the gift exchange by removing every participant's assigned recipient.

## Contributors

I'm currently tracking issues here in GitHub. I encourage feature suggestions as well as code improvement! There is plenty of work that needs done

## License

MIT License per LICENSE.txt