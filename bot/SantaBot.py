import datetime
import logging
import random
from collections import defaultdict
from copy import deepcopy
# from gettext import gettext as _
from itertools import permutations

from sqlalchemy import or_
from telegram import ForceReply, Update
from telegram.error import BadRequest
from telegram.ext import CallbackContext, CommandHandler, MessageHandler
from telegram.ext.filters import Filters

from bot.models.BlockedLinks import BlockedLink
from bot.models.Group import Group
from bot.models.Link import Link
from bot.models.Participant import Participant
from bot.TextTranslations import message_strings


class SantaBot:

    def __init__(self, dbConnection):

        # create dummy DB Models so backrefs work
        BlockedLink()
        Group()
        Link()
        Participant()

        self.session = dbConnection.session

        logging.basicConfig(
            filename='santabot.log',
            level=logging.INFO,
            format='%(asctime)s %(message)s'
        )

        self.message_strings = message_strings

        self.token = None
        self.bot_id = None

        self.handlers = [
            CommandHandler('start', self.start),
            CommandHandler('help', self.help),
            CommandHandler('hello', self.hello),
            CommandHandler('address', self.show_address),
            CommandHandler('join', self.join),
            CommandHandler('not', self.not_command),
            CommandHandler('allow', self.allow),
            CommandHandler('leave', self.leave),
            CommandHandler('status', self.status),
            CommandHandler('start_exchange', self.start_exchange),
            CommandHandler('reset_exchange', self.reset_exchange),
            MessageHandler(Filters.reply & Filters.text, self.address)
        ]

    @staticmethod
    def send_message(context=None, chat_id=None,
                     text=None, reply_markup=None):
        if context:
            sent_message = context.bot.send_message(
                chat_id=chat_id, text=text, reply_markup=reply_markup)
            logging.info(
                f"Sent Message {text} with ID {sent_message.message_id} "
                f"to Chat {chat_id}")
            return

    @staticmethod
    def reply_message(update=None, text=None):
        if update and text:
            sent_message = update.effective_message.reply_text(text)
            logging.info(
                f"Sent Reply {text} with ID {sent_message.message_id}"
                f" to Chat {update.effective_chat.id}")

    def start(self, update: Update, context: CallbackContext):
        try:
            if self.checkUpdateAgeExpired(update):
                return
            chat_type = update.effective_chat.type
            user_locality = self.get_locality(update.effective_user)
            if chat_type != "private":
                message = self.message_strings[user_locality]["private_error"]
                self.reply_message(update=update, text=message)
                return
            user_id = update.effective_user.id
            user_username = update.effective_user.username

            this_participant = self.session.query(Participant).filter(
                Participant.telegram_id == user_id).first()
            if this_participant is None:
                logging.info(
                    f"Start | New Participant | ID: {user_id} "
                    f"Username: {user_username}")
                this_participant = Participant(
                    telegram_id=user_id, telegram_username=user_username)
                self.session.add(this_participant)
                self.session.commit()
                message = self.message_strings[user_locality]["hello"]
                self.send_message(
                    context=context,
                    chat_id=this_participant.telegram_id,
                    text=message,
                )
                message = self.message_strings[user_locality]["address?"]
                self.send_message(
                    context=context,
                    chat_id=this_participant.telegram_id,
                    text=message,
                    reply_markup=ForceReply(),
                )
            elif this_participant.address is None:
                message = self.message_strings[user_locality]["address?"]
                self.send_message(
                    context=context,
                    chat_id=this_participant.telegram_id,
                    text=message,
                    reply_markup=ForceReply(),
                )
            else:
                already_setup = (
                    self.message_strings[user_locality]["already_setup"]
                )
                message = already_setup + this_participant.address
                self.send_message(
                    context=context,
                    chat_id=this_participant.telegram_id,
                    text=message,
                )
            logging.info(f"start | This Participant ID: {this_participant.id}")
        except Exception as this_ex:
            logging.exception(this_ex)

    def help(self, update: Update, context: CallbackContext):
        if self.checkUpdateAgeExpired(update):
            return
        user_locality = self.get_locality(update.effective_user)
        message = self.message_strings[user_locality]["help"]
        self.reply_message(update=update, text=message)

    def show_address(self, update: Update, context: CallbackContext):
        try:
            if self.checkUpdateAgeExpired(update):
                return
            logging.info(
                f"show_address | "
                f"This Participant's Telegram ID: {update.effective_user.id}")
            chat_type = update.effective_chat.type
            user_locality = self.get_locality(update.effective_user)
            if chat_type != "private":
                message = self.message_strings[user_locality]["private_error"]
                self.reply_message(update=update, text=message)
                return
            user_id = update.effective_user.id
            # user_username = update.effective_user.username

            this_participant = self.session.query(Participant).filter(
                Participant.telegram_id == user_id).first()
            if this_participant is None:
                message = self.message_strings[user_locality]["send_start"]
                self.reply_message(update=update, text=message)
                return
            else:
                message = (
                    self.message_strings[user_locality]["current_address_1"] +
                    str(this_participant.address) + "\n" +
                    self.message_strings[user_locality]["current_address_2"]
                )
                self.send_message(
                    context=context,
                    chat_id=this_participant.telegram_id,
                    text=message,
                )
                message = self.message_strings[user_locality]["address?"]
                self.send_message(
                    context=context,
                    chat_id=this_participant.telegram_id,
                    text=message,
                    reply_markup=ForceReply(),
                )
        except Exception as this_ex:
            logging.exception(this_ex)

    def address(self, update: Update, context: CallbackContext):
        try:
            if self.checkUpdateAgeExpired(update):
                return
            logging.info(
                f"address | Telegram ID: {update.effective_user.id} "
                f"Telegram Name: {update.effective_user.name} "
                f"Text: {update.effective_message.text}"
            )
            user_locality = self.get_locality(update.effective_user)
            messageDict = self.message_strings[user_locality]
            new_address = update.effective_message.text
            original_user = update.effective_message.reply_to_message.from_user
            original_text = update.effective_message.reply_to_message.text

            if (
                original_user.id == self.bot_id and
                original_text == messageDict["address?"]
            ):
                this_user = (
                    self.session
                    .query(Participant)
                    .filter(
                        Participant.telegram_id == update.effective_user.id
                    ).first()
                )
                this_user.address = new_address
                self.session.commit()

                message = (
                    messageDict["address_confirmation"] +
                    new_address + "\n" +
                    messageDict["post_confirm_instructions"]
                )
                self.reply_message(update=update, text=message)
        except Exception as this_ex:
            logging.exception(this_ex)

    def hello(self, update: Update, context: CallbackContext):
        try:
            if self.checkUpdateAgeExpired(update):
                return
            user_locality = self.get_locality(update.effective_user)
            chat_type = update.effective_chat.type
            if chat_type == "private":
                message = self.message_strings[user_locality]["group_error"]
                self.reply_message(update=update, text=message)
                return

            chat_id = update.effective_chat.id
            group_exists = self.session.query(Group).filter(
                Group.telegram_id == chat_id).first()
            if not group_exists:
                logging.info("hello | new group")
                new_group = Group(telegram_id=chat_id)
                self.session.add(new_group)
                self.session.commit()
            else:
                logging.info(f"hello | group_exists.id: {group_exists.id}")

            message = self.message_strings[user_locality]["hello_done"]
            self.reply_message(update=update, text=message)
            return
        except Exception as this_ex:
            logging.exception(this_ex)

    def join(self, update: Update, context: CallbackContext):
        try:
            if self.checkUpdateAgeExpired(update):
                return
            user_locality = self.get_locality(update.effective_user)
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            user_username = update.effective_user.username
            chat_type = update.effective_chat.type
            logging.info(f"Chat ID: {chat_id}")
            logging.info(f"User ID: {user_id}")
            if update.effective_user.language_code:
                logging.info(
                    f"User Local: {update.effective_user.language_code}")
            logging.info(f"Type of Chat: {chat_type}")

            if chat_type == "private":
                message = self.message_strings[user_locality]["group_error"]
                self.reply_message(update=update, text=message)
                return

            this_participant = self.session.query(Participant).filter(
                Participant.telegram_id == user_id).first()
            if this_participant is None:
                message = self.message_strings[user_locality]["start_private"]
                self.reply_message(update=update, text=message)
                return

            if this_participant.address is None:
                message = self.message_strings[user_locality]["need_address"]
                self.reply_message(update=update, text=message)
                message = self.message_strings[user_locality]["address?"]
                self.send_message(
                    context=context,
                    chat_id=this_participant.telegram_id,
                    text=message,
                    reply_markup=ForceReply(),
                    )
                return

            # Check to see if there is a BlockedLink waiting, if so update it
            this_participant_blocked_link = (
                self.session
                .query(BlockedLink)
                .filter(
                    BlockedLink.blocked_username == user_username
                )
            )
            if this_participant_blocked_link is not None:
                this_participant_blocked_link.blocked_id = this_participant.id
                this_participant_blocked_link.blocked_username = None
                self.session.commit()

            this_link = (
                self.session
                .query(Link)
                .join(Group)
                .filter(
                    Group.telegram_id == chat_id,
                    Link.santa_id == this_participant.id
                ).first()
            )
            if this_link is None:
                this_group = self.session.query(Group).filter(
                    Group.telegram_id == chat_id).first()
                if this_group is None:
                    message = self.message_strings[user_locality]["say_hello"]
                    self.reply_message(update=update, text=message)
                    return
                self.session.add(
                    Link(santa_id=this_participant.id, group_id=this_group.id))
                self.session.commit()
                message = self.message_strings[user_locality]["in"]
                self.reply_message(update=update, text=message)
            else:
                message = self.message_strings[user_locality]["already_joined"]
                self.reply_message(update=update, text=message)
        except Exception as this_ex:
            logging.exception(this_ex)

    def not_command(self, update: Update, context: CallbackContext):
        try:
            if self.checkUpdateAgeExpired(update):
                return
            logging.info(f"{update.effective_user.name}: not")
            user_locality = self.get_locality(update.effective_user)
            messageDict = self.message_strings[user_locality]
            entities = update.effective_message.parse_entities()
            for entity, entity_text in entities.items():
                entity_type = entity.type
                logging.info(f"not | entity type: {entity_type}")
                if entity_type == "mention":
                    this_participant = (
                        self.session
                        .query(Participant)
                        .filter(
                            Participant.telegram_id == update.effective_user.id
                        ).first()
                    )

                    mentioned_participant = entity_text[1:]
                    participant_by_username = (
                        self.session
                        .query(Participant)
                        .filter(
                            Participant.telegram_username ==
                            mentioned_participant
                        ).first()
                    )
                    if participant_by_username is None:
                        already_blocked = (
                            self.session
                            .query(BlockedLink)
                            .filter(
                                BlockedLink.participant_id ==
                                this_participant.id,

                                BlockedLink.blocked_username ==
                                mentioned_participant
                            ).first()
                        )
                        if already_blocked is None:
                            self.session.add(
                                BlockedLink(
                                    participant_id=this_participant.id,
                                    blocked_username=mentioned_participant
                                )
                            )
                        else:
                            message = messageDict["already_blocked_pairing"]
                            self.reply_message(update=update, text=message)
                    elif participant_by_username.id == this_participant.id:
                        message = messageDict["not_yourself"]
                        self.reply_message(update=update, text=message)
                    else:
                        id_list = [this_participant.id,
                                   participant_by_username.id]
                        in_blocked_list = (
                            self.session
                            .query(BlockedLink)
                            .filter(
                                BlockedLink.participant_id.in_(id_list),
                                BlockedLink.blocked_id.in_(id_list)
                            ).first()
                        )
                        if in_blocked_list is None:
                            self.session.add(
                                BlockedLink(
                                    participant_id=this_participant.id,
                                    blocked_id=participant_by_username.id
                                    )
                                )
                            message = messageDict["block_successful"]
                            self.reply_message(update=update, text=message)
                        else:
                            message = messageDict["already_blocked_pairing"]
                            self.reply_message(update=update, text=message)
                elif entity_type == "text_mention":
                    this_participant = (
                        self.session
                        .query(Participant)
                        .filter(
                            Participant.telegram_id == update.effective_user.id
                        ).first()
                    )

                    mentioned_user = entity.user
                    mentioned_participant = (
                        self.session
                        .query(Participant)
                        .filter(
                            Participant.telegram_id == mentioned_user.id
                        ).first()
                    )
                    if mentioned_participant is None:
                        message = messageDict["user_hasnt_joined"]
                        self.reply_message(update=update, text=message)
                    else:
                        id_list = [this_participant.id,
                                   mentioned_participant.id]
                        in_blocked_list = (
                            self.session
                            .query(BlockedLink)
                            .filter(
                                BlockedLink.participant_id.in_(id_list),
                                BlockedLink.blocked_id.in_(id_list)
                            ).first()
                        )
                        if in_blocked_list is None:
                            self.session.add(
                                BlockedLink(
                                    participant_id=this_participant.id,
                                    blocked_id=mentioned_participant.id
                                )
                            )
                            message = messageDict["block_successful"]
                            self.reply_message(update=update, text=message)
                        else:
                            message = messageDict["already_blocked_pairing"]
                            self.reply_message(update=update, text=message)

            self.session.commit()
        except Exception as this_ex:
            logging.exception(this_ex)

    def allow(self, update: Update, context: CallbackContext):
        try:
            if self.checkUpdateAgeExpired(update):
                return
            user_locality = self.get_locality(update.effective_user)
            messageDict = self.message_strings[user_locality]
            entities = update.effective_message.parse_entities()
            for entity, entity_text in entities.items():
                entity_type = entity.type
                logging.info(f"allow | entity_type: {entity_type}")
                if entity_type == "mention":
                    this_participant = (
                        self.session
                        .query(Participant)
                        .filter(
                            Participant.telegram_id == update.effective_user.id
                        ).first()
                    )

                    mentioned_participant = entity_text[1:]

                    mentioned_participant = (
                        self.session
                        .query(Participant)
                        .filter(
                            Participant.telegram_username ==
                            mentioned_participant
                        ).first()
                    )
                    if mentioned_participant is None:
                        blocked_id = 0
                    else:
                        blocked_id = mentioned_participant.id

                    blocked_link = (
                        self.session
                        .query(BlockedLink)
                        .join(BlockedLink.blocked, isouter=True)
                        .filter(
                            BlockedLink.participant_id ==
                            this_participant.id
                        )
                        .filter(or_(
                            BlockedLink.blocked_username ==
                            mentioned_participant,

                            BlockedLink.blocked_id == blocked_id)
                        ).first()
                    )
                    if blocked_link is not None:
                        self.session.delete(blocked_link)
                        self.session.commit()
                        message = messageDict["allow_successful"] + entity_text
                        self.reply_message(update=update, text=message)
                    else:
                        message = entity_text + \
                            messageDict["not_blocked"]
                        self.reply_message(update=update, text=message)
                elif entity_type == "text_mention":
                    this_participant = (
                        self.session
                        .query(Participant)
                        .filter(
                            Participant.telegram_id == update.effective_user.id
                        ).first()
                    )

                    mentioned_user = entity.user
                    mentioned_participant = (
                        self.session
                        .query(Participant)
                        .filter(
                            Participant.telegram_id == mentioned_user.id
                        ).first()
                    )
                    if mentioned_participant is None:
                        blocked_link = None
                    else:
                        blocked_link = (
                            self.session
                            .query(BlockedLink)
                            .join(BlockedLink.blocked, isouter=True)
                            .filter(
                                BlockedLink.participant_id ==
                                this_participant.id
                            )
                            .filter(
                                BlockedLink.blocked_id ==
                                mentioned_participant.id
                            )
                            .first()
                        )

                    if blocked_link is not None:
                        self.session.delete(blocked_link)
                        self.session.commit()
                        message = messageDict["allow_successful"] + entity_text
                        self.reply_message(update=update, text=message)
                    else:
                        message = entity_text + \
                            messageDict["not_blocked"]
                        self.reply_message(update=update, text=message)
        except Exception as this_ex:
            logging.exception(this_ex)

    def leave(self, update: Update, context: CallbackContext):
        try:
            if self.checkUpdateAgeExpired(update):
                return
            user_locality = self.get_locality(update.effective_user)
            # delete in memberships
            this_link = self.session.query(Link).join(Link.santa).join(Group)\
                .filter(Participant.telegram_id == update.effective_user.id,
                        Group.telegram_id == update.effective_chat.id).first()
            if this_link is None:
                message = self.message_strings[user_locality]["never_joined"]
                self.reply_message(update=update, text=message)
            else:
                self.session.query()
                self.session.delete(this_link)
                self.session.commit()
                message = self.message_strings[user_locality]["done"]
                self.reply_message(update=update, text=message)
        except Exception as this_ex:
            logging.exception(this_ex)

    def status(self, update: Update, context: CallbackContext):
        try:
            if self.checkUpdateAgeExpired(update):
                return
            user_locality = self.get_locality(update.effective_user)
            messageDict = self.message_strings[user_locality]
            chat_id = update.effective_chat.id
            chat_type = update.effective_chat.type
            logging.info(f"Status | Chat ID: {chat_id}")
            logging.info(f"Type of Chat: {chat_type}")

            if chat_type == "private":
                message = messageDict["group_error"]
                self.reply_message(update=update, text=message)
                return

            this_group = self.session.query(Group).filter(
                Group.telegram_id == chat_id).first()

            if this_group is None:
                message = messageDict["say_hello"]
                self.reply_message(update=update, text=message)
                return

            link_record_to_check = self.session.query(Link).join(Group).filter(
                Group.telegram_id == update.effective_chat.id).first()
            if link_record_to_check.receiver_id is not None:
                message = (
                    f'{messageDict["exchange_finished"]}\n\n')
            else:
                message = (
                    f'{messageDict["exchange_waiting"]}\n\n')

            # Get all Group Members
            group_links = this_group.links

            message += (
                f'{messageDict["joined_users"]}:\n')
            for link in group_links:
                this_participant = link.santa
                chat_member = update.effective_chat.get_member(
                    user_id=this_participant.telegram_id)
                if not chat_member:
                    continue
                message += (f'\n{chat_member.user.name}\n')

                blocked_participants = []
                blocked_links = this_participant.blocked_link
                for blocked_link in blocked_links:
                    blocked_participants.append(blocked_link.blocker)
                blocker_links = this_participant.blocker_link
                for blocker_link in blocker_links:
                    blocked_participants.append(blocker_link.blocked)

                first = True
                if blocked_participants:

                    for blocked_participant in blocked_participants:
                        try:
                            chat_member = update.effective_chat.get_member(
                                user_id=blocked_participant.telegram_id)
                        except BadRequest:
                            # TODO Remove participant from chat
                            continue
                        if first:
                            message += (
                                f'{messageDict["cannot_pair_with"]}: ')
                            first = False
                        message += (f'{chat_member.user.name}, ')
                    message = message[:-2] + '\n'
                    message = message.replace('@', '')
            self.reply_message(update=update, text=message)
        except Exception as this_ex:
            logging.exception(this_ex)

    def start_exchange(self, update: Update, context: CallbackContext):
        try:
            if self.checkUpdateAgeExpired(update):
                return
            user_locality = self.get_locality(update.effective_user)
            messageDict = self.message_strings[user_locality]
            link_record_to_check = (
                self.session
                .query(Link)
                .join(Group)
                .filter(
                    Group.telegram_id == update.effective_chat.id
                ).first()
            )
            if link_record_to_check is None:
                message = messageDict["no_one_joined"]
                self.reply_message(update=update, text=message)
                return
            if link_record_to_check.receiver_id is not None:
                message = messageDict["exchange_already_setup"]
                self.reply_message(update=update, text=message)
                return

            this_group_id = update.effective_chat.id
            group_participants_objects = (
                self.session
                .query(Participant)
                .join(Participant.link_santa)
                .join(Group)
                .filter(Group.telegram_id == this_group_id)
                .all()
            )

            # Remove participants that are no longer in the chat
            temp_participants_list = []
            for group_participant in group_participants_objects:
                try:
                    update.effective_chat.get_member(
                        user_id=group_participant.telegram_id)
                    temp_participants_list.append(group_participant)
                except BadRequest:
                    logging.warning(
                        "Participant with telegram id "
                        f"{group_participant.telegram_id} "
                        "is no longer in chat "
                        f"with telegram id {this_group_id}"
                    )
                    # TODO Remove participant from chat
                    continue

            group_participants = [x.id for x in temp_participants_list]
            logging.info(group_participants)

            blocked_participants_objects = (
                self.session
                .query(BlockedLink)
                .filter(
                    BlockedLink.participant_id.in_(group_participants)
                ).all()
            )
            blocked_participants = [[x.participant_id, x.blocked_id]
                                    for x in blocked_participants_objects]

            success, selected_combination = self.find_combination(
                group_participants, blocked_participants)

            #  TODO Deal with failure
            if not success:
                message = "Matching Impossible: 0 Permutations"
                self.reply_message(update=update, text=message)
                return

            chatInfo = update.effective_chat
            chatTitle = str(chatInfo.title)

            for santa_id, receiver_id in selected_combination.items():
                receiverUser = None
                try:
                    santa = self.session.query(Participant).get(santa_id)
                    receiver = self.session.query(Participant).get(receiver_id)

                    santa_link = (
                        self.session
                        .query(Link)
                        .join(Group)
                        .filter(
                            Link.santa_id == santa.id,
                            Group.telegram_id == chatInfo.id
                        ).first()
                    )
                    santa_link.receiver_id = receiver.id
                    receiverUser = chatInfo.get_member(
                        user_id=receiver.telegram_id).user
                    youGotUsername = (
                        f"{chatTitle}| "
                        f"{messageDict['you_got']}{receiverUser.name}"
                    )
                    if receiver.address:
                        receiverAddress = receiver.address
                    else:
                        receiverAddress = "empty"
                    youGotAddress = (
                        messageDict["their_address_is"] + receiverAddress)
                    message = youGotUsername + youGotAddress
                    self.send_message(
                        context=context,
                        chat_id=santa.telegram_id,
                        text=message,
                        )
                except Exception as this_ex:
                    if santa_id and receiverUser:
                        santaName = chatInfo.get_member(
                            user_id=santa_id).user.name
                        logging.exception(
                            f"Exception: {this_ex}. Santa ID: {santa_id} "
                            f"Santa Name: {santaName} got "
                            f"Receiver ID: {receiverUser.id} "
                            f"Receiver Name: {receiverUser.name}"
                        )
                    else:
                        logging.exception(f"Exception: {this_ex}.")
            self.session.commit()
            message = messageDict["messages_sent"]
            self.reply_message(update=update, text=message)
        except Exception as this_ex:
            logging.exception(this_ex)

    def reset_exchange(self, update: Update, context: CallbackContext):
        if self.checkUpdateAgeExpired(update):
            return
        user_locality = self.get_locality(update.effective_user)
        this_group_id = update.effective_chat.id
        group_links = self.session.query(Link).join(
            Group).filter(Group.telegram_id == this_group_id)
        for group_link in group_links:
            group_link.receiver_id = None
        self.session.commit()
        message = self.message_strings[user_locality]["pairings_reset"]
        self.reply_message(update=update, text=message)

    @classmethod
    def find_combination(cls, participants, blocked_pairings):
        #  permutations before removing blocked pairings
        unfiltered_permutations = list(permutations(participants, 2))
        logging.info(
            f"unfiltered permutations: {len(unfiltered_permutations)}")
        #  permutations after removing blocked pairings
        filtered_permutations = defaultdict(set)
        filtered_permutation_count = 0
        for permutation in unfiltered_permutations:
            blocked = False
            for blocked_pairing in blocked_pairings:
                if (
                    permutation[0] in blocked_pairing and
                    permutation[1] in blocked_pairing
                ):
                    blocked = True
                    break
            if not blocked:
                filtered_permutation_count += 1
                filtered_permutations[permutation[0]].add(permutation[1])

        logging.info(f"filtered permutations: {filtered_permutation_count}")

        if not filtered_permutations:
            return False, {}
        #  sort permutations by least number of pairings
        sorted_permutations = sorted(
            filtered_permutations.items(), key=lambda x: len(x[1]))

        #  get random set of pairings if possible
        success, result_set = cls.get_random_pairing(sorted_permutations)

        return success, result_set

    @classmethod
    def get_random_pairing(cls, remaining_participants, gifting=[]):
        remaining_participants_copy = deepcopy(remaining_participants)
        this_participant = remaining_participants_copy.pop(0)
        logging.info(this_participant)
        gifting.append(this_participant[0])
        participant_pairings = this_participant[1]
        if len(remaining_participants_copy) == 0:
            final_pairings = {this_participant[0]: participant_pairings.pop()}
            return True, final_pairings

        while(len(participant_pairings) > 0):
            random_receiver = random.sample(participant_pairings, 1)[0]
            participant_pairings.remove(random_receiver)
            possible = True
            new_remaining_participants = deepcopy(remaining_participants_copy)
            remaining_pairings_list = [
                remaining_participant[1]
                for remaining_participant in new_remaining_participants
            ]
            for remaining_pairings in remaining_pairings_list:
                if (
                    len(remaining_pairings) == 1 and
                    random_receiver in remaining_pairings
                ):
                    possible = False
                    break
                remaining_pairings.discard(random_receiver)
            if not possible:
                continue
            success, final_pairings = cls.get_random_pairing(
                new_remaining_participants, gifting)
            if success:
                final_pairings[this_participant[0]] = random_receiver
                return success, final_pairings
            continue
        #  At this point, no combinations are valid
        return False, {}

    @staticmethod
    def get_locality(user):
        locality = user.language_code
        if locality not in ["en", "pt-br"]:
            locality = "en"
        return locality

    @staticmethod
    def checkUpdateAgeExpired(updateObject) -> bool:
        try:
            message = updateObject.effective_message
            currentTime = datetime.datetime.now(datetime.timezone.utc)
            originalDate = message.date.replace(tzinfo=datetime.timezone.utc)
            messageAge = currentTime - originalDate
            if messageAge > datetime.timedelta(minutes=1):
                logging.warn(
                    f"Discarding Message sent at {originalDate.isoformat()} "
                    f"from user '{updateObject.effective_user}' "
                    f"with text '{message.text}'"
                )
                return True
        except Exception as e:
            logging.exception(e)
            return True
        return False
