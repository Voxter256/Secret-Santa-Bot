from bot.SantaBot import SantaBot
from bot.Base import Base, engine


if __name__ == '__main__':

    bot = SantaBot()
    Base.metadata.create_all(engine)
    bot.main()

    # TODO Unit Tests

    # class User:
    #     id = "user_id"
    #
    # class Chat:
    #     id = "chat_id"
    #     type="public"
    #
    # class Message:
    #     chat = Chat()
    #     from_user = User()
    #
    #     @staticmethod
    #     def reply_text(text):
    #         print("text");
    #
    # class TestUpdate:
    #     message = Message()
    #
    # test_update = TestUpdate()
    #
    # bot.join("",test_update)


