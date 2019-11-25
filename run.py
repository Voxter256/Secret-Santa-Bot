import json

from bot.SantaBot import SantaBot
from bot.Base import Base, engine


if __name__ == '__main__':

    bot = SantaBot()
    Base.metadata.create_all(engine)
    bot.main()

def lambda_handler(event, context):
    
    bot = SantaBot()
    Base.metadata.create_all(engine)
    
    bot.process_message(event)

    return {
        'statusCode': 200,
    }

