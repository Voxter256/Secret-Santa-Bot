import json

from bot.LambdaSantaBot import LambdaSantaBot
from bot.LocalSantaBot import LocalSantaBot
from bot.Base import Base, engine


if __name__ == '__main__':

    bot = LocalSantaBot()
    Base.metadata.create_all(engine)
    bot.main()

def lambda_handler(event, context):
    
    bot = LambdaSantaBot()
    Base.metadata.create_all(engine)
    
    bot.process_message(event)

    return {
        'statusCode': 200,
    }

