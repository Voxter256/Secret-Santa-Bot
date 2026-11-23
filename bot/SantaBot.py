import datetime
import logging
import os
import pathlib
import random
import uuid
from collections import defaultdict
from copy import deepcopy
from gettext import find, translation
from itertools import permutations
from typing import Callable

from telegram import Chat, ForceReply, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from bot.decorators import rejects_stale_updates
from bot.models.BlockedLink import BlockedLink
from bot.models.Group import Group
from bot.models.Link import Link
from bot.models.Participant import Participant
from bot.repositories.sqlalchemy_repos import (
    SqlBlockedLinkRepository,
    SqlGroupRepository,
    SqlLinkRepository,
    SqlParticipantRepository,
)
from bot.services.exchange_service import ExchangeService

TRANSLATION_DOMAIN = "messages"
LOCALE_DIR = pathlib.Path(__file__).parent / "locale"

# Updates older than this are discarded; override with MESSAGE_MAX_AGE_SECONDS.
DEFAULT_MAX_MESSAGE_AGE_SECONDS = 60
MAX_MESSAGE_AGE_ENV_VAR = "MESSAGE_MAX_AGE_SECONDS"


class SantaBot:
    supported_languages = [
        "de",
        "en",
        "pt-br",
        "fr",
        "it",
        "ru",
    ]

    def __init__(
        self,
        dbConnection,
        exchange: ExchangeService | None = None,
        max_message_age_seconds: int | None = None,
    ):
        # create dummy DB Models so backrefs work
        BlockedLink()
        Group()
        Link()
        Participant()

        self.session = dbConnection.session

        self.token = None
        self.bot_id = None
        self.max_message_age_seconds = self.resolve_max_message_age_seconds(max_message_age_seconds)

        # Wire repositories and service; callers may inject their own service
        self.exchange = exchange or ExchangeService(
            participants=SqlParticipantRepository(self.session),
            groups=SqlGroupRepository(self.session),
            links=SqlLinkRepository(self.session),
            blocked_links=SqlBlockedLinkRepository(self.session),
        )

        # Load every message catalog once instead of re-reading the .mo per update
        self.translations: dict[str, Callable[[str], str]] = self.preload_translations()

        self.handlers = [
            CommandHandler("start", self.start),
            CommandHandler("help", self.help),
            CommandHandler("hello", self.hello),
            CommandHandler("address", self.show_address),
            CommandHandler("join", self.join),
            CommandHandler("not", self.not_command),
            CommandHandler("allow", self.allow),
            CommandHandler("leave", self.leave),
            CommandHandler("status", self.status),
            CommandHandler("start_exchange", self.start_exchange),
            CommandHandler("reset_exchange", self.reset_exchange),
            MessageHandler(filters.REPLY & filters.TEXT, self.address),
        ]

    @staticmethod
    async def send_message(context=None, chat_id=None, text=None, reply_markup=None):
        if context:
            sent_message = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
            logging.info(f"Sent Message {text} with ID {sent_message.message_id} to Chat {chat_id}")
            return

    @staticmethod
    async def reply_message(update=None, text=None):
        if update and text:
            sent_message = await update.effective_message.reply_text(text)
            logging.info(f"Sent Reply {text} with ID {sent_message.message_id} to Chat {update.effective_chat.id}")

    @rejects_stale_updates
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            chat_type = update.effective_chat.type
            _ = self.gettext_translation(update.effective_user)
            if chat_type != "private":
                message = _("You must send me this in a private chat")
                await self.reply_message(update=update, text=message)
                return
            user_id = update.effective_user.id
            user_username = update.effective_user.username

            this_participant = self.exchange.get_participant(user_id)
            address_hint = _("Use /address to share a mailing address, or /wish for wishlists.")  # noqa: E501
            if this_participant is None:
                logging.info(f"Start | New Participant | ID: {user_id} Username: {user_username}")
                this_participant = self.exchange.find_or_create_participant(user_id, user_username)
                message = _("Hello! Lets get you setup!")
                await self.send_message(
                    context=context,
                    chat_id=this_participant.telegram_id,
                    text=message,
                )
            elif this_participant.address is not None:
                already_setup = _("You are already set up. I have your address as:") + "\n"  # noqa: E501
                address_hint = already_setup + this_participant.address + "\n" + address_hint
            await self.send_message(
                context=context,
                chat_id=this_participant.telegram_id,
                text=address_hint,
            )
            logging.info(f"start | This Participant ID: {this_participant.id}")
        except Exception as this_ex:
            logging.exception(this_ex)

    @rejects_stale_updates
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        _ = self.gettext_translation(update.effective_user)
        message = (
            _("Command List:")
            + "\n"
            + "/start \n"
            + _("Sent only in a private message to begin personal setup.")
            + "\n"  # noqa: E501
            + "/hello \n"
            + _("Sent only in a group chat to enable the gift exchange.")
            + "\n"  # noqa: E501
            + "/address \n"
            + _("Sent only in a private message to show and update your address.")
            + "\n"  # noqa: E501
            + "/join \n"
            + _("Joins you in the gift exchange in this chat.")
            + "\n"  # noqa: E501
            + "/status \n"
            + _("Gets the status of this chat's exchange.")
            + "\n"
            + "/not @Mention \n"
            + _("Prevents you from being paired up with this participant.")
            + "\n"  # noqa: E501
            + "/allow @Mention \n"
            + _("Removes block that was preventing you from being paired up with this participant.")
            + "\n"  # noqa: E501
            + "/leave \n"
            + _("You will leave the gift exchange in this chat.")
            + "\n"
            + "/start_exchange \n"
            + _(
                "Begins the gift exchange by assigning a recipient to every participant, "  # noqa: E501
                "then messaging them privately the details."
            )
            + "\n"
            + "/reset_exchange \n"
            + _("Resets the gift exchange by removing every participant's assigned recipient.")  # noqa: E501
        )
        await self.reply_message(update=update, text=message)

    @rejects_stale_updates
    async def show_address(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            logging.info(f"show_address | This Participant's Telegram ID: {update.effective_user.id}")
            chat_type = update.effective_chat.type
            _ = self.gettext_translation(update.effective_user)
            if chat_type != "private":
                message = _("You must send me this in a private chat")
                await self.reply_message(update=update, text=message)
                return
            user_id = update.effective_user.id
            # user_username = update.effective_user.username

            this_participant = self.exchange.get_participant(user_id)
            if this_participant is None:
                message = _("Send me a {command} in a private message, then follow the instructions!").format(
                    command="/start"
                )  # noqa: E501
                await self.reply_message(update=update, text=message)
                return
            else:
                message = (
                    _("I currently have your address as {address}").format(address=str(this_participant.address))
                    + "\n"
                    + _("If that is correct, you can ignore the following message.")  # noqa: E501
                )
                await self.send_message(
                    context=context,
                    chat_id=this_participant.telegram_id,
                    text=message,
                )
                message = _("What is your address? (Reply to this message to change it)")  # noqa: E501
                context.user_data["awaiting_address"] = True
                await self.send_message(
                    context=context,
                    chat_id=this_participant.telegram_id,
                    text=message,
                    reply_markup=ForceReply(),
                )
        except Exception as this_ex:
            logging.exception(this_ex)

    @rejects_stale_updates
    async def address(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            logging.info(
                f"address | Telegram ID: {update.effective_user.id} "
                f"Telegram Name: {update.effective_user.name} "
                f"Text: {update.effective_message.text}"
            )
            _ = self.gettext_translation(update.effective_user)
            new_address = update.effective_message.text
            original_user = update.effective_message.reply_to_message.from_user

            if original_user.id == self.bot_id and context.user_data.get("awaiting_address"):
                this_user = self.exchange.get_participant(update.effective_user.id)
                if this_user is not None:
                    self.exchange.update_address(this_user.id, new_address)
                    context.user_data.pop("awaiting_address", None)

                message = (
                    _("OK, I have added your address as: ")
                    + new_address
                    + "\n"
                    + _("You can now to use {command} in any Telegram Secret Santa group!").format(  # noqa: E501
                        command="/join"
                    )
                    + "\n"
                    + _("A Telegram Secret Santa group only needs to be activated once.")
                    + "\n"  # noqa: E501
                    + _(
                        "To do so, I must be a member of a telegram group and someone needs to activate me with the command {command}"  # noqa: E501
                    ).format(command="/hello")  # noqa: E501
                )
                await self.reply_message(update=update, text=message)
        except Exception as this_ex:
            logging.exception(this_ex)

    @rejects_stale_updates
    async def hello(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            _ = self.gettext_translation(update.effective_user)
            chat_type = update.effective_chat.type
            if chat_type == "private":
                message = _("You must begin from a group chat")
                await self.reply_message(update=update, text=message)
                return

            self.exchange.find_or_create_group(update.effective_chat.id)

            message = (
                _("Hello! ")
                + _("This group chat now has the options of participating in a Secret Santa Exchange!")
                + "\n"  # noqa: E501
                + _("{command} to participate").format(command="/join")
            )
            await self.reply_message(update=update, text=message)
            return
        except Exception as this_ex:
            logging.exception(this_ex)

    @rejects_stale_updates
    async def join(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            _ = self.gettext_translation(update.effective_user)
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            user_username = update.effective_user.username
            chat_type = update.effective_chat.type
            logging.info(f"Chat ID: {chat_id}")
            logging.info(f"User ID: {user_id}")
            if update.effective_user.language_code:
                logging.info(f"User Local: {update.effective_user.language_code}")
            logging.info(f"Type of Chat: {chat_type}")

            if chat_type == "private":
                message = _("You must begin from a group chat")
                await self.reply_message(update=update, text=message)
                return

            this_participant = self.exchange.get_participant(user_id)
            if this_participant is None:
                message = _("Send me a {command} in a private message, then follow the instructions!").format(
                    command="/start"
                )  # noqa: E501
                await self.reply_message(update=update, text=message)
                return

            result = self.exchange.join_group(this_participant.id, chat_id, user_username)
            if result == "no_group":
                message = _("Someone must say {command} first!").format(command="/hello")
                await self.reply_message(update=update, text=message)
            elif result == "joined":
                message = _("OK, you're in!")
                await self.reply_message(update=update, text=message)
            elif result == "already_joined":
                message = _("You have already joined!")
                await self.reply_message(update=update, text=message)
        except Exception as this_ex:
            logging.exception(this_ex)

    @rejects_stale_updates
    async def not_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            logging.info(f"{update.effective_user.name}: not")
            _ = self.gettext_translation(update.effective_user)
            user_id = update.effective_user.id
            p = self.exchange.get_participant(user_id)
            if p is None:
                return
            entities = update.effective_message.parse_entities()
            for entity, entity_text in entities.items():
                entity_type = entity.type
                logging.info(f"not | entity type: {entity_type}")
                if entity_type == "mention":
                    username = entity_text[1:]
                    result = self.exchange.block_by_username(p.id, username)
                    if result == "self_block":
                        message = _("Don't worry, you won't get yourself")
                        await self.reply_message(update=update, text=message)
                    elif result == "blocked":
                        message = _("OK, you can no longer matched with that participant.")
                        await self.reply_message(update=update, text=message)
                    elif result == "already_blocked":
                        message = _("This blocked pairing has already been added.")
                        await self.reply_message(update=update, text=message)
                elif entity_type == "text_mention":
                    mentioned_user = entity.user
                    result = self.exchange.block_by_user_id(p.id, mentioned_user.id)
                    if result == "needs_join_first":
                        message = _("This participant needs to join first")
                        await self.reply_message(update=update, text=message)
                    elif result == "blocked":
                        message = _("OK, you can no longer matched with that participant.")
                        await self.reply_message(update=update, text=message)
                    elif result == "already_blocked":
                        message = _("This blocked pairing has already been added.")
                        await self.reply_message(update=update, text=message)
        except Exception as this_ex:
            logging.exception(this_ex)

    @rejects_stale_updates
    async def allow(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            _ = self.gettext_translation(update.effective_user)

            logging.info(f"allow | request: {update.effective_message.text}")
            p = self.exchange.get_participant(update.effective_user.id)
            if p is None:
                return
            entities = update.effective_message.parse_entities()
            for entity, entity_text in entities.items():
                entity_type = entity.type
                logging.info(f"allow | entity_type: {entity_type}")
                if entity_type == "mention":
                    username = entity_text[1:]
                    target = self.exchange._participants.get_by_username(username)  # noqa: SLF001
                    blocked_id = target.id if target else 0

                    unblocked = self.exchange.unblock(p.id, username, blocked_id)
                    if unblocked:
                        message = _("You can now be assigned to {name}").format(name=entity_text)
                        await self.reply_message(update=update, text=message)
                    else:
                        message = _("{name} was not blocked by you.").format(name=entity_text)
                        await self.reply_message(update=update, text=message)
                elif entity_type == "text_mention":
                    mentioned_user = entity.user
                    unblocked = self.exchange.unblock(p.id, "", mentioned_user.id)
                    if unblocked:
                        message = _("You can now be assigned to {name}").format(name=entity_text)
                        await self.reply_message(update=update, text=message)
                    else:
                        message = _("{name} was not blocked by you.").format(name=entity_text)
                        await self.reply_message(update=update, text=message)
        except Exception as this_ex:
            logging.exception(this_ex)

    @rejects_stale_updates
    async def leave(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            _ = self.gettext_translation(update.effective_user)
            p = self.exchange.get_participant(update.effective_user.id)
            if p is None:
                message = _("You never joined")
            else:
                result = self.exchange.leave_group(p.id, update.effective_chat.id)
                message = _("Done.") if result == "left" else _("You never joined")
            await self.reply_message(update=update, text=message)
        except Exception as this_ex:
            logging.exception(this_ex)

    @rejects_stale_updates
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            _ = self.gettext_translation(update.effective_user)
            chat_id = update.effective_chat.id
            chat_type = update.effective_chat.type
            logging.info(f"Status | Chat ID: {chat_id}")
            logging.info(f"Type of Chat: {chat_type}")

            if chat_type == "private":
                message = _("You must begin from a group chat")
                await self.reply_message(update=update, text=message)
                return

            status_label, group_links = self.exchange.get_exchange_status(chat_id)

            if status_label == "no_group":
                message = _("Someone must say {command} first!").format(command="/hello")
                await self.reply_message(update=update, text=message)
                return

            if status_label == "not_begun":
                message = _("The exchange has not begun") + "\n\n"
            elif status_label == "delivery_pending":
                pending = self.exchange.pending_deliveries(chat_id)
                names = ", ".join(SantaBot.describe_participant(link.santa) for link in pending)
                message = (
                    _("The exchange has finished, but {count} participant(s) were not messaged: {names}").format(
                        count=len(pending),
                        names=names,
                    )
                    + "\n\n"
                )
                message += (
                    _("Ask them to unblock the bot, then run {command} to resend.").format(command="/start_exchange")
                    + "\n\n"
                )
            else:
                message = _("The exchange has finished") + "\n\n"

            message += _("Joined Users:")
            for link in group_links:
                this_participant = link.santa
                chat_member = await update.effective_chat.get_member(user_id=this_participant.telegram_id)
                if not chat_member:
                    continue
                message += f"\n{chat_member.user.name}\n"

                blocked_participants = []

                blocked_links = this_participant.blocked_link
                for blocked_link in blocked_links:
                    blocked_participant = blocked_link.blocker
                    try:
                        chat_member = await update.effective_chat.get_member(user_id=blocked_participant.telegram_id)
                        user_name = chat_member.user.name
                        blocked_participants.append(user_name)
                    except BadRequest as e:
                        logging.warning(f"Got exception {e} for Participant {blocked_participant.id}")
                        continue

                blocker_links = this_participant.blocker_link
                for blocker_link in blocker_links:
                    blocked_participant_by_id = blocker_link.blocked
                    if blocked_participant_by_id:
                        telegram_id = blocked_participant_by_id.telegram_id
                        try:
                            chat_member = await update.effective_chat.get_member(user_id=telegram_id)
                            user_name = chat_member.user.name
                            blocked_participants.append(user_name)
                        except BadRequest:
                            continue
                    else:
                        user_name = blocker_link.blocked_username
                        if user_name:
                            blocked_participants.append(user_name)
                first = True
                if blocked_participants:
                    for blocked_participant in blocked_participants:
                        if first:
                            message += _("Cannot pair with: ")
                            first = False
                        else:
                            message += ", "
                        message += blocked_participant
                    message += "\n"
            message = message.replace("@", "")
            await self.reply_message(update=update, text=message)
        except Exception as this_ex:
            logging.exception(this_ex)

    @rejects_stale_updates
    async def start_exchange(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            _ = self.gettext_translation(update.effective_user)
            chat_id = update.effective_chat.id

            setup_block = self.exchange.is_exchange_setup(chat_id)
            if setup_block == "no_joins":
                message = _("No one has Joined!")
                await self.reply_message(update=update, text=message)
                return
            if setup_block == "already_setup":
                # Assignment is durable; delivery may still be pending for
                # participants who were unreachable on the first attempt.
                if self.exchange.pending_deliveries(chat_id):
                    await self.deliver_pending(chat_id, update, context, _)
                else:
                    message = _("The exchange has already been setup!")
                    await self.reply_message(update=update, text=message)
                return

            # Remove participants that are no longer in the chat
            links = self.exchange._links.get_links_in_group(chat_id)  # noqa: SLF001
            temp_participants_list = []
            for link in links:
                try:
                    await update.effective_chat.get_member(user_id=link.santa.telegram_id)
                    temp_participants_list.append(link.santa)
                except BadRequest:
                    logging.warning(
                        "Participant with telegram id "
                        f"{link.santa.telegram_id} "
                        "is no longer in chat "
                        f"with telegram id {chat_id}"
                    )
                    continue

            group_participants = [x.id for x in temp_participants_list]
            logging.info(group_participants)

            blocked_links = self.exchange._blocked_links.get_by_participant_ids(group_participants)  # noqa: SLF001
            blocked_pairings = [[x.participant_id, x.blocked_id] for x in blocked_links]

            success, selected_combination = self.exchange._pairing.find_combination(  # noqa: SLF001
                group_participants, blocked_pairings
            )

            if not success:
                message = _("Matching Impossible: 0 Permutations")
                await self.reply_message(update=update, text=message)
                return

            await self.save_and_send_exchange_results(selected_combination, update, context, _)

        except Exception as this_ex:
            logging.exception(this_ex)

    async def save_and_send_exchange_results(self, selected_combination, update, context, _):
        chat_id = update.effective_chat.id
        # Persist the pairing before messaging anyone: an unreachable
        # participant must not undo assignments that were already delivered.
        self.exchange.assign_pairing(chat_id, selected_combination)
        await self.deliver_pending(chat_id, update, context, _)

    async def deliver_pending(self, chat_id, update, context, _):
        """Send assignment messages for links that have not been notified yet."""
        links = self.exchange.pending_deliveries(chat_id)
        failures = []
        for link in links:
            delivered, reason = await self.send_individual_result(link, update, context, _)
            if delivered:
                self.exchange.mark_delivered(link)
            else:
                failures.append((link.santa, reason))
                logging.warning(
                    f"Undelivered exchange message for {SantaBot.describe_participant(link.santa)}: {reason}"
                )

        if not failures:
            message = _("Messages have been sent!")
            await self.reply_message(update=update, text=message)
            return

        names = ", ".join(SantaBot.describe_participant(participant) for participant, _reason in failures)
        logging.warning(f"Exchange delivery incomplete, unreachable: {names}")
        message = _("Could not message: {names}. Ask them to unblock the bot, then run {command} again.").format(
            names=names,
            command="/start_exchange",
        )
        await self.reply_message(update=update, text=message)

    @staticmethod
    def describe_participant(participant: Participant) -> str:
        if participant.telegram_username:
            return f"@{participant.telegram_username}"
        return str(participant.telegram_id)

    async def send_individual_result(self, link, update, context, _) -> tuple[bool, str]:
        telegram_chat = update.effective_chat
        santa = link.santa
        receiver = link.receiver
        if santa is None or receiver is None:
            return False, "missing participant"
        try:
            receiver_user = (await telegram_chat.get_member(user_id=int(receiver.telegram_id))).user
            options = self.exchange.group_options(telegram_chat.id)
            message = self.generate_result_message(
                telegram_chat,
                receiver,
                receiver_user.name,
                _,
                requires_address=options["requires_address"],
            )
            await SantaBot.send_message(context=context, chat_id=santa.telegram_id, text=message)
            return True, ""
        except (Forbidden, BadRequest) as this_ex:
            # Blocked bot, deactivated account, or privacy setting — the
            # participant is unreachable, but the rest of the exchange is not.
            return False, str(this_ex)
        except Exception as this_ex:
            exception_id = uuid.uuid4()
            logging.exception(f"Exception {exception_id}: {this_ex} delivering to santa {santa.telegram_id}")
            return False, f"{this_ex} ({exception_id})"

    @staticmethod
    def generate_result_message(
        telegram_chat: Chat,
        receiver: Participant,
        receiver_name: str,
        _,
        *,
        requires_address: bool,
    ) -> str:
        chat_title = str(telegram_chat.title)

        you_got = _("You got {username}!").format(username=receiver_name)
        message = f"{chat_title}| {you_got}"

        if requires_address:
            receiver_address = receiver.address if receiver.address else "?"
            their_address_is = _("Their address is: {address}.").format(address=receiver_address)
            message = f"{message} {their_address_is}"
        return message

    @rejects_stale_updates
    async def reset_exchange(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        _ = self.gettext_translation(update.effective_user)
        self.exchange.reset_exchange(update.effective_chat.id)
        message = _("All pairings have been reset")
        await self.reply_message(update=update, text=message)

    @classmethod
    def find_combination(cls, participants, blocked_pairings):
        #  permutations before removing blocked pairings
        unfiltered_permutations = list(permutations(participants, 2))
        logging.info(f"unfiltered permutations: {len(unfiltered_permutations)}")
        #  permutations after removing blocked pairings
        filtered_permutations = defaultdict(set)
        filtered_permutation_count = 0
        for permutation in unfiltered_permutations:
            blocked = False
            for blocked_pairing in blocked_pairings:
                if permutation[0] in blocked_pairing and permutation[1] in blocked_pairing:
                    blocked = True
                    break
            if not blocked:
                filtered_permutation_count += 1
                filtered_permutations[permutation[0]].add(permutation[1])

        logging.info(f"filtered permutations: {filtered_permutation_count}")

        if not filtered_permutations:
            return False, {}
        #  sort permutations by least number of pairings
        sorted_permutations = sorted(filtered_permutations.items(), key=lambda x: len(x[1]))

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

        while len(participant_pairings) > 0:
            random_receiver = random.sample(list(participant_pairings), 1)[0]
            participant_pairings.remove(random_receiver)
            possible = True
            new_remaining_participants = deepcopy(remaining_participants_copy)
            remaining_pairings_list = [remaining_participant[1] for remaining_participant in new_remaining_participants]
            for remaining_pairings in remaining_pairings_list:
                if len(remaining_pairings) == 1 and random_receiver in remaining_pairings:
                    possible = False
                    break
                remaining_pairings.discard(random_receiver)
            if not possible:
                continue
            success, final_pairings = cls.get_random_pairing(new_remaining_participants, gifting)
            if success:
                final_pairings[this_participant[0]] = random_receiver
                return success, final_pairings
            continue
        #  At this point, no combinations are valid
        return False, {}

    def preload_translations(self) -> dict[str, Callable[[str], str]]:
        """Load every supported message catalog once, keyed by locale directory."""
        translations = {
            language.replace("-", "_"): self.load_translation(language.replace("-", "_"))
            for language in self.supported_languages
        }
        fallback = translations.get("en") or (lambda message: message)
        translations["en"] = fallback
        return {locale_name: loaded or fallback for locale_name, loaded in translations.items()}

    @staticmethod
    def load_translation(locale_name: str) -> Callable[[str], str] | None:
        if find(TRANSLATION_DOMAIN, LOCALE_DIR, languages=[locale_name]) is None:
            logging.warning(f"No message catalog found for locale '{locale_name}'")
            return None
        return translation(
            TRANSLATION_DOMAIN,
            LOCALE_DIR,
            languages=[locale_name],
        ).gettext

    def gettext_translation(self, user) -> Callable[[str], str]:
        return self.translations.get(self.get_locality(user), self.translations["en"])

    @staticmethod
    def get_locality(user) -> str:
        locality = (user.language_code or "").lower()
        if locality not in SantaBot.supported_languages:
            locality = "en"
        return locality.replace("-", "_")

    @staticmethod
    def resolve_max_message_age_seconds(override: int | None = None) -> int:
        """Return the update age limit in seconds: explicit override, env var, then default."""
        if override is not None:
            return override
        raw = os.environ.get(MAX_MESSAGE_AGE_ENV_VAR, "").strip()
        if not raw:
            return DEFAULT_MAX_MESSAGE_AGE_SECONDS
        try:
            value = int(raw)
        except ValueError:
            logging.warning(f"Ignoring {MAX_MESSAGE_AGE_ENV_VAR}={raw!r}: not an integer")
            return DEFAULT_MAX_MESSAGE_AGE_SECONDS
        if value <= 0:
            logging.warning(f"Ignoring {MAX_MESSAGE_AGE_ENV_VAR}={value}: must be positive")
            return DEFAULT_MAX_MESSAGE_AGE_SECONDS
        return value

    def is_update_expired(self, updateObject) -> bool:
        try:
            message = updateObject.effective_message
            currentTime = datetime.datetime.now(datetime.timezone.utc)
            originalDate = message.date.replace(tzinfo=datetime.timezone.utc)
            messageAge = currentTime - originalDate
            if messageAge > datetime.timedelta(seconds=self.max_message_age_seconds):
                logging.warning(
                    f"Discarding Message sent at {originalDate.isoformat()} "
                    f"from user '{updateObject.effective_user}' "
                    f"with text '{message.text}'"
                )
                return True
        except Exception as e:
            logging.exception(e)
            return True
        return False
