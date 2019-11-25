import json
import os.path
import re
import random
import traceback

from configparser import ConfigParser
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext, Dispatcher
from telegram.ext.filters import Filters
from telegram import ForceReply
from sqlalchemy import or_
from collections import OrderedDict
from copy import deepcopy

from bot.Base import Session
from bot.SantaBot import SantaBot
from bot.models.BlockedLinks import BlockedLink
from bot.models.Group import Group
from bot.models.Link import Link
from bot.models.Participant import Participant


class LambdaSantaBot(SantaBot):
    def __init__(self):
        super().__init__(self)
        self.read_config()  # TODO Replace with Environment Variables
        try:
            self.bot_id = int(self.token.split(":")[0])
        except:
           self.bot_id = None

        self.bot = Bot(self.token)
        self.dispatcher = Dispatcher(self.bot, None, workers=0, use_context=True)

        for handler in self.handlers:
            self.dispatcher.add_handler(handler)

    def read_config(self):  # TODO Replace with Environment Variables
        config = ConfigParser()
        configPath = os.path.normpath('config/config.ini')
        config.read(configPath)
        self.token = config.get('auth', 'token')

    def process_message(self, updateText):
        print('incoming message')
        print(updateText)
        decodedUpdate = Update.de_json(updateText, self.bot)
        self.dispatcher.process_update(decodedUpdate)
        self.session.close()

    def start(self, update: Update, context: CallbackContext):
        try:
            chat_type = update.message.chat.type
            user_locality = self.get_locality(update.message.from_user)
            if chat_type != "private":
                message = self.message_strings[user_locality]["private_error"]
                update.message.reply_text(message)
                return
            user_id = update.message.from_user.id
            user_username = update.message.from_user.username

            this_participant = self.session.query(Participant).filter(Participant.telegram_id == user_id).first()
            if this_participant is None:
                print("New Participant. ID:" + str(user_id) + " Username:" + str(user_username))
                this_participant = Participant(telegram_id=user_id, telegram_username=user_username)
                self.session.add(this_participant)
                self.session.commit()
                message = self.message_strings[user_locality]["hello"]
                context.bot.send_message(chat_id=this_participant.telegram_id, text=message)
                message = self.message_strings[user_locality]["address?"]
                context.bot.send_message(chat_id=this_participant.telegram_id, text=message, reply_markup=ForceReply())
            elif this_participant.address is None:
                message = self.message_strings[user_locality]["address?"]
                context.bot.send_message(chat_id=this_participant.telegram_id, text=message, reply_markup=ForceReply())
            else:
                message = self.message_strings[user_locality]["already_setup"] + this_participant.address
                context.bot.send_message(chat_id=this_participant.telegram_id, text=message)
            print("start | This Participant id: " + str(this_participant.id))
        except Exception as this_ex:
            print(this_ex)
            print(traceback.format_exc())

    def help(self, update: Update, context: CallbackContext):
        user_locality = self.get_locality(update.message.from_user)
        message = self.message_strings[user_locality]["help"]
        update.message.reply_text(message)

    def show_address(self, update: Update, context: CallbackContext):
        try:
            chat_type = update.message.chat.type
            user_locality = self.get_locality(update.message.from_user)
            if chat_type != "private":
                message = self.message_strings[user_locality]["private_error"]
                update.message.reply_text(message)
                return
            user_id = update.message.from_user.id
            # user_username = update.message.from_user.username

            this_participant = self.session.query(Participant).filter(Participant.telegram_id == user_id).first()
            if this_participant is None:
                message = self.message_strings[user_locality]["send_start"]
                update.message.reply_text(message)
                return
            else:
                message = self.message_strings[user_locality]["current_address_1"] + this_participant.address + "\n" + \
                    self.message_strings[user_locality]["current_address_2"]
                context.bot.send_message(chat_id=this_participant.telegram_id, text=message)
                message = self.message_strings[user_locality]["address?"]
                context.bot.send_message(chat_id=this_participant.telegram_id, text=message, reply_markup=ForceReply())
            print("show_address | This Participant id: " + str(this_participant.id))
        except Exception as this_ex:
            print(this_ex)
            print(traceback.format_exc())

    def address(self, update: Update, context: CallbackContext):
        try:
            user_locality = self.get_locality(update.message.from_user)
            new_address = update.message.text
            original_user = update.message.reply_to_message.from_user
            original_text = update.message.reply_to_message.text
            if original_user.id == self.bot_id and \
                    original_text == self.message_strings[user_locality]["address?"]:
                user_language_code = update.message.from_user.language_code
                address_match_object = self.address_re.match(new_address)
                if user_language_code is not "en":
                    this_user = self.session.query(Participant).filter(
                        Participant.telegram_id == update.message.from_user.id).first()
                    this_user.address = new_address
                    self.session.commit()

                    message = self.message_strings[user_locality]["address_confirmation"] + new_address + "\n" + \
                              self.message_strings[user_locality]["post_confirm_instructions"]
                    update.message.reply_text(message)
                elif address_match_object is not None:
                    this_user = self.session.query(Participant).filter(
                        Participant.telegram_id == update.message.from_user.id).first()
                    address_filtered = address_match_object.group()
                    this_user.address = address_filtered
                    self.session.commit()

                    message = self.message_strings[user_locality]["address_confirmation"] + address_filtered + "\n" + \
                        self.message_strings[user_locality]["post_confirm_instructions"]
                    update.message.reply_text(message)
                else:
                    message = self.message_strings[user_locality]["address_error"]
                    update.message.reply_text(message)
                    context.bot.send_message(chat_id=update.message.from_user.id,
                                     text=self.message_strings[user_locality]["address?"],
                                     reply_markup=ForceReply())
        except Exception as this_ex:
            print(this_ex)
            print(traceback.format_exc())

    def hello(self, update: Update, context: CallbackContext):
        try:
            user_locality = self.get_locality(update.message.from_user)
            chat_type = update.message.chat.type
            if chat_type == "private":
                message = self.message_strings[user_locality]["group_error"]
                update.message.reply_text(message)
                return

            chat_id = update.message.chat.id
            group_exists = self.session.query(Group).filter(Group.telegram_id == chat_id).first()
            print("hello | group_exists: " + str(group_exists))
            if not group_exists:
                new_group = Group(telegram_id=chat_id)
                self.session.add(new_group)
                self.session.commit()

            message = self.message_strings[user_locality]["hello_done"]
            update.message.reply_text(message)
            return
        except Exception as this_ex:
            print(this_ex)
            print(traceback.format_exc())

    def join(self, update: Update, context: CallbackContext):
        try:
            user_locality = self.get_locality(update.message.from_user)
            chat_id = update.message.chat.id
            user_id = update.message.from_user.id
            user_username = update.message.from_user.username
            chat_type = update.message.chat.type
            print("Chat ID: " + str(chat_id))
            print("User ID: " + str(user_id))
            print("User Local: " + update.message.from_user.language_code)
            print("Type of Chat: " + chat_type)

            if chat_type == "private":
                message = self.message_strings[user_locality]["group_error"]
                update.message.reply_text(message)
                return

            this_participant = self.session.query(Participant).filter(Participant.telegram_id == user_id).first()
            if this_participant is None:
                message = self.message_strings[user_locality]["start_private"]
                update.message.reply_text(message)
                return

            if this_participant.address is None:
                message = self.message_strings[user_locality]["need_address"]
                update.message.reply_text(message)
                message = self.message_strings[user_locality]["address?"]
                context.bot.send_message(chat_id=this_participant.telegram_id, text=message, reply_markup=ForceReply())
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
            if this_link is None:
                this_group = self.session.query(Group).filter(Group.telegram_id == chat_id).first()
                if this_group is None:
                    message = self.message_strings[user_locality]["say_hello"]
                    update.message.reply_text(message)
                    return
                self.session.add(Link(santa_id=this_participant.id, group_id=this_group.id))
                self.session.commit()
                message = self.message_strings[user_locality]["in"]
                update.message.reply_text(message)
            else:
                message = self.message_strings[user_locality]["already_joined"]
                update.message.reply_text(message)
        except Exception as this_ex:
            print(this_ex)
            print(traceback.format_exc())

    def not_command(self, update: Update, context: CallbackContext):
        try:
            user_locality = self.get_locality(update.message.from_user)
            entities = update.message.parse_entities()
            for entity, entity_text in entities.items():
                entity_type = entity.type
                print("not | entity type: " + str(entity_type))
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
                            message = self.message_strings[user_locality]["already_blocked_pairing"]
                            update.message.reply_text(message)
                    elif participant_by_username.id == this_participant.id:
                        message = self.message_strings[user_locality]["not_yourself"]
                        update.message.reply_text(message)
                    else:
                        id_list = [this_participant.id, participant_by_username.id]
                        in_blocked_list = self.session.query(BlockedLink).filter(
                            BlockedLink.participant_id.in_(id_list), BlockedLink.blocked_id.in_(id_list)).first()
                        if in_blocked_list is None:
                            self.session.add(
                                BlockedLink(participant_id=this_participant.id, blocked_id=participant_by_username.id))
                            message = self.message_strings[user_locality]["block_successful"]
                            update.message.reply_text(message)
                        else:
                            message = self.message_strings[user_locality]["already_blocked_pairing"]
                            update.message.reply_text(message)

            self.session.commit()
        except Exception as this_ex:
            print(this_ex)
            print(traceback.format_exc())

    def allow(self, update: Update, context: CallbackContext):
        try:
            user_locality = self.get_locality(update.message.from_user)
            entities = update.message.parse_entities()
            for entity, entity_text in entities.items():
                entity_type = entity.type
                print("allow | entity_type: " + str(entity_type))
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
                        message = self.message_strings[user_locality]["allow_successful"] + entity_text
                        update.message.reply_text(message)
                    else:
                        message = entity_text + self.message_strings[user_locality]["not_blocked"]
                        update.message.reply_text(message)
        except Exception as this_ex:
            print(this_ex)
            print(traceback.format_exc())

    def leave(self, update: Update, context: CallbackContext):
        try:
            user_locality = self.get_locality(update.message.from_user)
            # delete in memberships
            this_link = self.session.query(Link).join(Link.santa).join(Group)\
                .filter(Participant.telegram_id == update.message.from_user.id,
                        Group.telegram_id == update.message.chat.id).first()
            if this_link is None:
                message = self.message_strings[user_locality]["never_joined"]
                update.message.reply_text(message)
            else:
                self.session.query()
                self.session.delete(this_link)
                self.session.commit()
                message = self.message_strings[user_locality]["done"]
                update.message.reply_text(message)
        except Exception as this_ex:
            print(this_ex)

    def start_exchange(self, update: Update, context: CallbackContext):
        try:
            user_locality = self.get_locality(update.message.from_user)
            link_record_to_check = self.session.query(Link).join(Group).filter(
                Group.telegram_id == update.message.chat.id).first()
            if link_record_to_check is None:
                message = self.message_strings[user_locality]["no_one_joined"]
                update.message.reply_text(message)
                return
            if link_record_to_check.receiver_id is not None:
                message = self.message_strings[user_locality]["exchange_already_setup"]
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
                message = self.message_strings[user_locality]["pairing_impossible"]
                update.message.reply_text(message)
                return
            participant_dictionary = OrderedDict(participant_dictionary)
            print(participant_dictionary)

            combinations = self.find_combinations(group_participants, participant_dictionary, [])
            print("totals")
            print(len(combinations))
            print(combinations)
            choice = random.choice(combinations)
            print("choice")
            print(choice)

            for santa in group_participants_objects:
                receiver = None
                for potential_receiver in group_participants_objects:
                    if potential_receiver.id == choice[santa.id]:
                        receiver = potential_receiver

                santa_link = self.session.query(Link).join(Group)\
                    .filter(Link.santa_id == santa.id, Group.telegram_id == update.message.chat.id).first()
                santa_link.receiver_id = receiver.id
                message = self.message_strings[user_locality]["you_got"] + receiver.telegram_username + \
                    self.message_strings[user_locality]["their_address_is"] + receiver.address
                context.bot.send_message(chat_id=santa.telegram_id, text=message)
            self.session.commit()
            message = self.message_strings[user_locality]["messages_sent"] + str(len(combinations)) + \
                self.message_strings[user_locality]["potential_combinations"]
            update.message.reply_text(message)
        except Exception as this_ex:
            print(this_ex)
            print(traceback.format_exc())

    def reset_exchange(self, update: Update, context: CallbackContext):
        user_locality = self.get_locality(update.message.from_user)
        this_group_id = update.message.chat.id
        group_links = self.session.query(Link).join(Group).filter(Group.telegram_id == this_group_id)
        for group_link in group_links:
            group_link.receiver_id = None
        self.session.commit()
        message = self.message_strings[user_locality]["pairings_reset"]
        update.message.reply_text(message)

    def find_combinations(self, remaining_participants, participant_dictionary, taken):
        remaining_participants_copy = deepcopy(remaining_participants)
        this_participant = remaining_participants_copy.pop(0)
        these_combinations = []
        for option in participant_dictionary[this_participant]:
            if option in taken:
                continue
            if len(remaining_participants_copy) > 0:
                taken_copy = deepcopy(taken)
                taken_copy.append(option)
                child_combinations = self.find_combinations(
                    remaining_participants_copy, participant_dictionary, taken_copy)
                if len(child_combinations) > 0:
                    for new_combination_dictionary in child_combinations:
                        new_combination_dictionary[this_participant] = option
                        these_combinations.append(new_combination_dictionary)
            else:
                return [{this_participant: option}]
        return these_combinations

    @staticmethod
    def get_locality(user):
        locality = user.language_code
        if locality not in ["en", "pt-br"]:
            locality = "en"
        return locality
