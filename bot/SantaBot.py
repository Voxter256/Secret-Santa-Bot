import re
import random

from configparser import ConfigParser
from telegram.ext import Updater, CommandHandler, MessageHandler
from telegram.ext.filters import Filters
from telegram import ForceReply
from sqlalchemy import or_
from collections import OrderedDict
from copy import deepcopy

from .Base import Session
from .models.BlockedLinks import BlockedLink
from .models.Group import Group
from .models.Link import Link
from .models.Participant import Participant


class SantaBot:
    def __init__(self):
        self.token = None
        self.bot_id = None
        self.read_config()

        # create dummy DB Models so backrefs work
        BlockedLink()
        Group()
        Link()
        Participant()

        address_regex_string = \
            "\d+[ ](?:[A-Za-z0-9.#-]+[ ]?)+,?[ ](?:[A-Za-z-]+[ ]?)+,[ ]" \
            "(?:{Alabama|Alaska|Arizona|Arkansas|California|Colorado|" \
            "Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|" \
            "Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|" \
            "Nebraska|Nevada|New[ ]Hampshire|New[ ]Jersey|New[ ]Mexico|New[ ]York|North[ ]Carolina|" \
            "North[ ]Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode[ ]Island|South[ ]Carolina|" \
            "South[ ]Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West[ ]Virginia|Wisconsin|" \
            "Wyoming}|AL|AK|AS|AZ|AR|CA|CO|CT|DE|DC|FM|FL|GA|GU|HI|ID|IL|IN|IA|KS|KY|LA|ME|MH|MD|MA|MI|MN|" \
            "MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|MP|OH|OK|OR|PW|PA|PR|RI|SC|SD|TN|TX|UT|VT|VI|VA|WA|WV|WI|" \
            "WY)[ ]\d{5}(?:-\d{4})?"

        self.address_re = re.compile(address_regex_string, re.IGNORECASE)

        self.session = Session()

    def read_config(self):
        config = ConfigParser()
        config.read('config\\config.ini')
        self.token = config.get('auth', 'token')

    def main(self):
        updater = Updater(token=self.token)
        self.bot_id = updater.bot.get_me().id
        print("Initialized with id: " + str(self.bot_id))

        # /begin : begins secret santa based on chat room; output instructions
        # /join : join secret santa based on chat room
        # private message to ask details
        # /leave : leave secret santa
        # /start : randomize participants and message individually

        dispatcher = updater.dispatcher

        handlers = [
            CommandHandler('start', self.start),
            CommandHandler('help', self.help),
            CommandHandler('hello', self.hello),
            CommandHandler('join', self.join),
            CommandHandler('not', self.not_command),
            CommandHandler('allow', self.allow),
            CommandHandler('leave', self.leave),
            CommandHandler('start_exchange', self.start_exchange),
            CommandHandler('reset_exchange', self.reset_exchange),
            MessageHandler(Filters.reply & Filters.text, self.address)
        ]

        for handler in handlers:
            dispatcher.add_handler(handler)

        updater.start_polling()

    def start(self, bot, update):
        try:
            chat_type = update.message.chat.type
            if chat_type != "private":
                message = "You must send me this in a private chat"
                update.message.reply_text(message)
                return
            user_id = update.message.from_user.id
            user_username = update.message.from_user.username

            this_participant = self.session.query(Participant).filter(Participant.telegram_id == user_id).first()
            print("This Participant: " + str(this_participant))
            if this_participant is None:
                print("New Participant: " + str(user_id) + " " + str(user_username))
                this_participant = Participant(telegram_id=user_id, telegram_username=user_username)
                self.session.add(this_participant)
                self.session.commit()

            message = "Hello! What is your address? (Reply to this message to change it)"
            bot.send_message(chat_id=this_participant.telegram_id, text=message, reply_markup=ForceReply())
        except Exception as this_ex:
            print(this_ex)

    @staticmethod
    def help(bot, update):
        message = "Command List: \n" \
                  "/start \n" \
                  "Sent only in a private message to begin personal setup. \n" \
                  "/hello \n" \
                  "Sent only in a group chat to enable the gift exchange. \n" \
                  "/join \n" \
                  "Joins you in the gift exchange in this chat. \n" \
                  "/not @Mention \n" \
                  "Prevents you from being paired up with this participant. \n" \
                  "/allow @Mention \n" \
                  "Removes block that was preventing you from being paired up with this participant. \n" \
                  "/leave \n" \
                  "You will leave the gift exchange in this chat. \n" \
                  "/start_exchange \n" \
                  "Begins the gift exchange by assigning a recipient to every participant, then " \
                  "messaging them privately the details. \n" \
                  "/reset_exchange \n" \
                  "Resets the gift exchange by removing every participant's assigned recipient."
        update.message.reply_text(message)

    def address(self, bot, update):
        try:
            new_address = update.message.text
            original_user = update.message.reply_to_message.from_user
            original_text = update.message.reply_to_message.text
            # print(original_user)
            # print(original_text)
            # print(new_address)
            if original_user.id == self.bot_id and \
                    original_text == "Hello! What is your address? (Reply to this message to change it)":
                address_match_object = self.address_re.match(new_address)
                if address_match_object is not None:
                    # print(address_match_object)
                    this_user = self.session.query(Participant).filter(
                        Participant.telegram_id == update.message.from_user.id).first()
                    # print(this_user)
                    # print(this_user.id)
                    address_filtered = address_match_object.group()
                    # print(address_filtered)
                    this_user.address = address_filtered
                    self.session.commit()
                    message = "OK, I have added your address as: " + address_filtered + "\n" \
                        "You can now to use the /join command in any Telegram Secret Santa group!\n" \
                        "A Telegram Secret Santa group only needs to be activated once.\n" \
                        "To do so, I must be a member of a telegram group " \
                        "and someone needs to activate me with the command /hello" \

                    update.message.reply_text(message)
                else:
                    message = "This is not a valid Address. An example is: 350 Fifth Ave. New York, NY 10118"
                    update.message.reply_text(message)
                    bot.send_message(chat_id=update.message.from_user.id, text="Hello! What is your address? (Reply to this message to change it)",
                                     reply_markup=ForceReply())
        except Exception as this_ex:
            print(this_ex)

    def hello(self, bot, update):
        try:
            chat_type = update.message.chat.type
            if chat_type == "private":
                message = "You must begin from a group chat"
                update.message.reply_text(message)
                return

            chat_id = update.message.chat.id
            group_exists = self.session.query(Group).filter(Group.telegram_id == chat_id).first()
            print(group_exists)
            if group_exists:
                message = "Hello! This group chat has the options of participating in a Secret Santa Exchange! \n" \
                      "/join to participate"
                update.message.reply_text(message)
                return

            new_group = Group(telegram_id=chat_id)
            self.session.add(new_group)
            self.session.commit()

            message = "Hello! This group chat now has the options of participating in a Secret Santa Exchange! \n" \
                      "/join to participate"
            update.message.reply_text(message)
            return
        except Exception as this_ex:
            print(this_ex)

    def join(self, bot, update):
        try:
            chat_id = update.message.chat.id
            user_id = update.message.from_user.id
            user_username = update.message.from_user.username
            chat_type = update.message.chat.type
            print("Chat ID: " + str(chat_id))
            print("User ID: " + str(user_id))
            print("Type of Chat: " + chat_type)

            if chat_type == "private":
                message = "You must join from a group chat"
                update.message.reply_text(message)
                return

            this_participant = self.session.query(Participant).filter(Participant.telegram_id == user_id).first()
            # print("This Participant: " + str(this_participant))
            if this_participant is None:
                message = "Send me a /start in a private message, then follow the instructions!"
                update.message.reply_text(message)
                return

            if this_participant.address is None:
                message = "I need your address first! I am sending you a private message now."
                update.message.reply_text(message)
                message = "Hello! What is your address? (Reply to this message to change it)"
                bot.send_message(chat_id=this_participant.telegram_id, text=message, reply_markup=ForceReply())
                return

            # Check to see if there is a BlockedLink waiting, if so update it
            this_participant_blocked_link = self.session.query(BlockedLink).filter(
                BlockedLink.blocked_username == user_username)
            if this_participant_blocked_link is not None:
                this_participant_blocked_link.blocked_id = this_participant.id
                this_participant_blocked_link.blocked_username = None
                self.session.commit()

            this_link = self.session.query(Link).join(Group).filter(Group.telegram_id == chat_id,
                                                                    Link.santa_id == this_participant.id).first()
            # print("This Link: " + str(this_link))
            if this_link is None:
                this_group = self.session.query(Group).filter(Group.telegram_id == chat_id).first()
                if this_group is None:
                    message = "Someone must /hello first!"
                    update.message.reply_text(message)
                    return
                # print("This Group: " + str(this_group))
                self.session.add(Link(santa_id=this_participant.id, group_id=this_group.id))
                self.session.commit()
                message = "OK, you're in!"
                update.message.reply_text(message)
            else:
                message = "You have already joined!"
                update.message.reply_text(message)
        except Exception as this_ex:
            print(this_ex)

    def not_command(self, bot, update):
        try:
            entities = update.message.parse_entities()
            # print(entities)
            for entity, entity_text in entities.items():
                entity_type = entity.type
                print(entity_type)
                if entity_type == "mention":
                    this_participant = self.session.query(Participant).filter(
                        Participant.telegram_id == update.message.from_user.id).first()

                    mentioned_participant = entity_text[1:]
                    participant_by_username = self.session.query(Participant).filter(
                        Participant.telegram_username == mentioned_participant).first()
                    if participant_by_username is None:
                        already_blocked = self.session.query(BlockedLink)\
                            .filter(BlockedLink.participant_id == this_participant.id,
                                    BlockedLink.blocked_username == mentioned_participant).first()
                        if already_blocked is None:
                            self.session.add(
                                BlockedLink(participant_id=this_participant.id, blocked_username=mentioned_participant))
                        else:
                            message = "This blocked pairing has already been added."
                            update.message.reply_text(message)
                    elif participant_by_username.id == this_participant.id:
                        message = "Don't worry, you won't get yourself"
                        update.message.reply_text(message)
                    else:
                        id_list = [this_participant.id, participant_by_username.id]
                        in_blocked_list = self.session.query(BlockedLink).filter(
                            BlockedLink.participant_id.in_(id_list), BlockedLink.blocked_id.in_(id_list)).first()
                        if in_blocked_list is None:
                            self.session.add(
                                BlockedLink(participant_id=this_participant.id, blocked_id=participant_by_username.id))
                            message = "OK, you can't be matched with that participant."
                            update.message.reply_text(message)
                        else:
                            message = "This blocked pairing has already been added."
                            update.message.reply_text(message)

            self.session.commit()
        except Exception as this_ex:
            print(this_ex)

    def allow(self, bot, update):
        try:
            entities = update.message.parse_entities()
            # print(entities)
            for entity, entity_text in entities.items():
                entity_type = entity.type
                print(entity_type)
                if entity_type == "mention":
                    this_participant = self.session.query(Participant).filter(
                        Participant.telegram_id == update.message.from_user.id).first()

                    mentioned_participant = entity_text[1:]

                    participant_by_username = self.session.query(Participant).filter(
                        Participant.telegram_username == mentioned_participant).first()
                    if participant_by_username is None:
                        blocked_id = 0
                    else:
                        blocked_id = participant_by_username.id

                    blocked_link = self.session.query(BlockedLink).join(BlockedLink.blocked, isouter=True)\
                        .filter(BlockedLink.participant_id == this_participant.id)\
                        .filter(or_(
                            BlockedLink.blocked_username == mentioned_participant,
                            BlockedLink.blocked_id == blocked_id)).first()
                    if blocked_link is not None:
                        self.session.delete(blocked_link)
                        self.session.commit()
                        message = "You can now be assigned to " + entity_text
                        update.message.reply_text(message)
                    else:
                        message = "You did not have " + entity_text + " blocked."
                        update.message.reply_text(message)
        except Exception as this_ex:
            print(this_ex)

    def leave(self, bot, update):
        try:
            # delete in memberships
            this_link = self.session.query(Link).join(Link.santa).join(Group)\
                .filter(Participant.telegram_id == update.message.from_user.id,
                        Group.telegram_id == update.message.chat.id).first()
            if this_link is None:
                message = "You never joined"
                update.message.reply_text(message)
            else:
                self.session.query()
                self.session.delete(this_link)
                self.session.commit()
                message = "Done."
                update.message.reply_text(message)
        except Exception as this_ex:
            print(this_ex)

    def start_exchange(self, bot, update):
        try:
            link_record_to_check = self.session.query(Link).join(Group).filter(
                Group.telegram_id == update.message.chat.id).first()
            if link_record_to_check is None:
                message = "No one has Joined!"
                update.message.reply_text(message)
                return
            if link_record_to_check.receiver_id is not None:
                message = "The exchange has already been setup!"
                update.message.reply_text(message)
                return

            this_group_id = update.message.chat.id
            group_participants_objects = self.session.query(Participant).join(Participant.link_santa).join(Group)\
                .filter(Group.telegram_id == this_group_id).all()
            group_participants = [x.id for x in group_participants_objects]
            print(group_participants)
            group_blocked_exchange = self.session.query(BlockedLink).filter(
                or_(BlockedLink.participant_id.in_(group_participants),
                    BlockedLink.blocked_id.in_(group_participants))).all()

            participant_dictionary = {}
            for this_participant in group_participants:
                participant_dictionary[this_participant] = deepcopy(group_participants)
                participant_dictionary[this_participant].remove(this_participant)

            for blocked_exchange in group_blocked_exchange:
                participant_id = blocked_exchange.participant_id
                blocked_id = blocked_exchange.blocked_id
                participant_dictionary[participant_id].remove(blocked_id)
                participant_dictionary[blocked_id].remove(participant_id)

            if [] in participant_dictionary.values():
                message = "Pairing is impossible"
                update.message.reply_text(message)
                return
            participant_dictionary = OrderedDict(participant_dictionary)
            print(participant_dictionary)

            combinations = self.find_combinations(group_participants, participant_dictionary, [])
            print(len(combinations))
            print(combinations)
            choice = random.choice(combinations)
            print(choice)

            for santa in group_participants_objects:
                receiver = None
                for potential_receiver in group_participants_objects:
                    if potential_receiver.id == choice[santa.id]:
                        receiver = potential_receiver

                santa_link = self.session.query(Link).join(Group)\
                    .filter(Link.santa_id == santa.id, Group.telegram_id == update.message.chat.id).first()
                santa_link.receiver_id = receiver.id
                message = "You got " + receiver.telegram_username + "! Their address is: " + receiver.address
                # print("send message to " + str(santa.telegram_id))
                bot.send_message(chat_id=santa.telegram_id, text=message)
            self.session.commit()
            message = "Messages have been sent! There were " + str(len(combinations)) + " potential combinations"
            update.message.reply_text(message)
        except Exception as this_ex:
            print(this_ex)

    def reset_exchange(self, bot, update):
        this_group_id = update.message.chat.id
        group_links = self.session.query(Link).join(Group).filter(Group.telegram_id == this_group_id)
        for group_link in group_links:
            group_link.receiver_id = None
        self.session.commit()
        message = "All pairings have been reset"
        update.message.reply_text(message)

    def find_combinations(self, remaining_participants, participant_dictionary, taken):
        remaining_participants_copy = deepcopy(remaining_participants)
        this_participant = remaining_participants_copy.pop(0)
        these_combinations = []
        # print("This Participant: " + str(this_participant))
        for option in participant_dictionary[this_participant]:
            # print("This Option: " + str(option))
            if option in taken:
                # print("Taken")
                continue
            if len(remaining_participants_copy) > 0:
                taken_copy = deepcopy(taken)
                taken_copy.append(option)
                child_combinations = self.find_combinations(
                    remaining_participants_copy, participant_dictionary, taken_copy)
                # print("Up Level to: " + str(this_participant))
                if len(child_combinations) > 0:
                    for new_combination_dictionary in child_combinations:
                        new_combination_dictionary[this_participant] = option
                        these_combinations.append(new_combination_dictionary)
            else:
                return [{this_participant: option}]
        return these_combinations
