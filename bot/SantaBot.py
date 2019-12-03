import random
import re
import traceback
from collections import defaultdict
from copy import deepcopy
from itertools import permutations

from sqlalchemy import or_
from telegram import ForceReply, Update
from telegram.ext import CallbackContext, CommandHandler, MessageHandler
from telegram.ext.filters import Filters

from bot.models.BlockedLinks import BlockedLink
from bot.models.Group import Group
from bot.models.Link import Link
from bot.models.Participant import Participant


class SantaBot:
    def __init__(self, dbConnection):

        # create dummy DB Models so backrefs work
        BlockedLink()
        Group()
        Link()
        Participant()

        self.session = dbConnection.session

        address_regex_string = r"""
            \d+[ ](?:[A-Za-z0-9.#-]+[ ]?)+,?[ ](?:[A-Za-z-]+[ ]?)+,[ ]
            (?:{Alabama|Alaska|Arizona|Arkansas|California|Colorado|
            Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|
            Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|
            Nebraska|Nevada|New[ ]Hampshire|New[ ]Jersey|New[ ]Mexico|New[ ]York|North[ ]Carolina|
            North[ ]Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode[ ]Island|South[ ]Carolina|
            South[ ]Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West[ ]Virginia|Wisconsin|
            Wyoming}|AL|AK|AS|AZ|AR|CA|CO|CT|DE|DC|FM|FL|GA|GU|HI|ID|IL|IN|IA|KS|KY|LA|ME|MH|MD|MA|MI|MN|
            MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|MP|OH|OK|OR|PW|PA|PR|RI|SC|SD|TN|TX|UT|VT|VI|VA|WA|WV|WI|
            WY)[ ]\d{5}(?:-\d{4})?"
            """

        self.address_re = re.compile(address_regex_string, re.IGNORECASE)

        self.message_strings = {"en": {
            "private_error": "You must send me this in a private chat",
            "hello": "Hello! Lets get you setup!",
            "address?": "What is your address? (Reply to this message to change it)",
            "already_setup": "You are already set up. I have your address as: \n",
            "help": "Command List: \n" +
                "/start \n" +
                    "Sent only in a private message to begin personal setup. \n" +
                "/hello \n" +
                    "Sent only in a group chat to enable the gift exchange. \n" +
                "/address \n" +
                    "Sent only in a private message to show and update your address. \n" +
                "/join \n" +
                    "Joins you in the gift exchange in this chat. \n" +
                "/not @Mention \n" +
                    "Prevents you from being paired up with this participant. \n" +
                "/allow @Mention \n" +
                    "Removes block that was preventing you from being paired up with this participant. \n" +
                "/leave \n" +
                    "You will leave the gift exchange in this chat. \n" +
                "/start_exchange \n" +
                    "Begins the gift exchange by assigning a recipient to every participant, "
                    "then messaging them privately the details. \n" +
                "/reset_exchange \n" +
                    "Resets the gift exchange by removing every participant's assigned recipient.",
            "send_start": "Send me a /start in a private message, then follow the instructions!",
            "current_address_1": "I currently have your address as: \n",
            "current_address_2": "If that is correct, you can ignore the following message.",
            "address_confirmation": "OK, I have added your address as: ",
            "post_confirm_instructions": "You can now to use the /join command in any Telegram Secret Santa group!\n" +
                "A Telegram Secret Santa group only needs to be activated once.\n" +
                "To do so, I must be a member of a telegram group " +
                "and someone needs to activate me with the command /hello",
            "address_error": "This is not a valid Address. An example is: 350 Fifth Ave. New York, NY 10118",
            "group_error": "You must begin from a group chat",
            "hello_done": "Hello! This group chat now has the options of participating in a " +
                        "Secret Santa Exchange! \n /join to participate",
            "start_private": "Send me a /start in a private message, then follow the instructions!",
            "need_address": "I need your address first! I am sending you a private message now.",
            "say_hello": "Someone must /hello first!",
            "in": "OK, you're in!",
            "already_joined": "You have already joined!",
            "already_blocked_pairing": "This blocked pairing has already been added.",
            "not_yourself": "Don't worry, you won't get yourself",
            "block_successful": "OK, you can no longer matched with that participant.",
            "allow_successful": "You can now be assigned to ",
            "not_blocked": " was not blocked by you.",
            "never_joined": "You never joined",
            "done": "Done.",
            "no_one_joined": "No one has Joined!",
            "exchange_already_setup": "The exchange has already been setup!",
            "pairing_impossible": "Pairing is impossible",
            "you_got": "You got ",
            "their_address_is": "! Their address is: ",
            "messages_sent": "Messages have been sent!",
            "potential_combinations": " potential combinations",
            "pairings_reset": "All pairings have been reset",
            "user_hasnt_joined": "This participant needs to join first",

                }, "pt-br": {
            "private_error": "Você deve me enviar isso em um bate-papo privado",
            "hello": "Olá! Vamos pegar sua configuração!",
            "address?": "Qual é o seu endereço? (Responda a esta mensagem para alterá-la)",
            "already_setup": "Você já está configurado. Eu tenho seu endereço como: \n",
            "help": "Command List: \n" +
                "/start \n" +
                    "Enviado apenas em uma mensagem privada para iniciar a configuração pessoal. \n" +
                "/hello \n" +
                    "Enviado somente em um bate-papo em grupo para ativar a troca de presentes. \n" +
                "/address \n" +
                    "Enviou apenas uma mensagem privada para mostrar e atualizar seu endereço. \n" +
                "/join \n" +
                    "Junta-te a ti na troca de presentes neste chat. \n" +
                "/not @Mention \n" +
                    "Impede que você seja emparelhado com este participante. \n" +
                "/allow @Mention \n" +
                    "Remove o bloqueio que estava impedindo você de ser emparelhado com este participante. \n" +
                "/leave \n" +
                    "Você vai deixar a troca de presentes neste chat. \n" +
                "/start_exchange \n" +
                    "Começa a troca de presentes atribuindo um destinatário a cada participante, "
                    "depois enviando os detalhes em particular. \n" +
                "/reset_exchange \n" +
                "Redefine a troca de presentes removendo o destinatário atribuído de cada participante.",
            "send_start": "Envie - me um / start em uma mensagem privada e siga as instruções!",
            "current_address_1": "Atualmente tenho seu endereço como: \n",
            "current_address_2": "Se isso estiver correto, você pode ignorar a seguinte mensagem.",
            "address_confirmation": "Eu adicionei seu endereço como: ",
            "post_confirm_instructions":
                "Agora você pode usar o comando /join em qualquer grupo Telegram Secret Santa!\n" +
                "Um grupo Telegram Secret Santa só precisa ser ativado uma vez.\n" +
                "Para fazer isso, eu devo ser um membro de um grupo de telegramas " +
                "e alguém precisa me ativar com o comando /hello",
            "address_error": "Este não é um endereço válido. Um exemplo é: 350 Fifth Ave. New York, NY 10118",
            "group_error": "Você deve começar de um bate-papo em grupo",
            "hello_done": "Olá! Este bate-papo em grupo agora tem a opção de participar de um " +
                          "Secret Santa Exchange! \n /join para participar",
            "start_private": "Envie-me um /start em uma mensagem privada e siga as instruções!",
            "need_address": "Eu preciso do seu endereço primeiro! Estou enviando uma mensagem particular agora.",
            "say_hello": "Alguém deve /hello primeiro!",
            "in": "Você está dentro!",
            "already_joined": "Você já se juntou!",
            "already_blocked_pairing": "Este par bloqueado já foi adicionado.",
            "not_yourself": "Não se preocupe, você não vai conseguir",
            "block_successful": "OK, você não pode mais corresponder a esse participante.",
            "allow_successful": "Agora você pode ser atribuído a ",
            "not_blocked": " não foi bloqueado por você.",
            "never_joined": "Você nunca se juntou",
            "done": "Feito.",
            "no_one_joined": "Ninguém se juntou!",
            "exchange_already_setup": "A troca já foi configurada!",
            "pairing_impossible": "O emparelhamento é impossível",
            "you_got": "Você tem ",
            "their_address_is": "! Seu endereço é: ",
            "messages_sent": "Mensagens foram enviadas!",
            "potential_combinations": " combinações potenciais",
            "pairings_reset": "Todos os pares foram redefinidos",
            "user_hasnt_joined": "Este participante precisa participar primeiro",

        }}

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
            CommandHandler('start_exchange', self.start_exchange),
            CommandHandler('reset_exchange', self.reset_exchange),
            MessageHandler(Filters.reply & Filters.text, self.address)
        ]

    def start(self, update: Update, context: CallbackContext):
        try:
            chat_type = update.effective_message.chat.type
            user_locality = self.get_locality(update.effective_user)
            if chat_type != "private":
                message = self.message_strings[user_locality]["private_error"]
                update.effective_message.reply_text(message)
                return
            user_id = update.effective_user.id
            user_username = update.effective_user.username

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
        user_locality = self.get_locality(update.effective_user)
        message = self.message_strings[user_locality]["help"]
        update.effective_message.reply_text(message)

    def show_address(self, update: Update, context: CallbackContext):
        try:
            chat_type = update.effective_message.chat.type
            user_locality = self.get_locality(update.effective_user)
            if chat_type != "private":
                message = self.message_strings[user_locality]["private_error"]
                update.effective_message.reply_text(message)
                return
            user_id = update.effective_user.id
            # user_username = update.effective_user.username

            this_participant = self.session.query(Participant).filter(Participant.telegram_id == user_id).first()
            if this_participant is None:
                message = self.message_strings[user_locality]["send_start"]
                update.effective_message.reply_text(message)
                return
            else:
                message = self.message_strings[user_locality]["current_address_1"] + str(this_participant.address) + "\n" + \
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
            print("address | {}".format(update))
            user_locality = self.get_locality(update.effective_user)
            new_address = update.effective_message.text
            original_user = update.effective_message.reply_to_message.from_user
            original_text = update.effective_message.reply_to_message.text
            if original_user.id == self.bot_id and \
                    original_text == self.message_strings[user_locality]["address?"]:
                user_language_code = update.effective_user.language_code
                address_match_object = self.address_re.match(new_address)
                if user_language_code is not "en":
                    this_user = self.session.query(Participant).filter(
                        Participant.telegram_id == update.effective_user.id).first()
                    this_user.address = new_address
                    self.session.commit()

                    message = self.message_strings[user_locality]["address_confirmation"] + new_address + "\n" + \
                              self.message_strings[user_locality]["post_confirm_instructions"]
                    update.effective_message.reply_text(message)
                elif address_match_object is not None:
                    this_user = self.session.query(Participant).filter(
                        Participant.telegram_id == update.effective_user.id).first()
                    address_filtered = address_match_object.group()
                    this_user.address = address_filtered
                    self.session.commit()

                    message = self.message_strings[user_locality]["address_confirmation"] + address_filtered + "\n" + \
                        self.message_strings[user_locality]["post_confirm_instructions"]
                    update.effective_message.reply_text(message)
                else:
                    message = self.message_strings[user_locality]["address_error"]
                    update.effective_message.reply_text(message)
                    context.bot.send_message(chat_id=update.effective_user.id,
                                     text=self.message_strings[user_locality]["address?"],
                                     reply_markup=ForceReply())
        except Exception as this_ex:
            print(this_ex)
            print(traceback.format_exc())

    def hello(self, update: Update, context: CallbackContext):
        try:
            user_locality = self.get_locality(update.effective_user)
            chat_type = update.effective_message.chat.type
            if chat_type == "private":
                message = self.message_strings[user_locality]["group_error"]
                update.effective_message.reply_text(message)
                return

            chat_id = update.effective_message.chat.id
            group_exists = self.session.query(Group).filter(Group.telegram_id == chat_id).first() 
            if not group_exists:
                print("hello | new group")
                new_group = Group(telegram_id=chat_id)
                self.session.add(new_group)
                self.session.commit()
            else:
                print("hello | group_exists.id: " + group_exists.id)

            message = self.message_strings[user_locality]["hello_done"]
            update.effective_message.reply_text(message)
            return
        except Exception as this_ex:
            print(this_ex)
            print(traceback.format_exc())

    def join(self, update: Update, context: CallbackContext):
        try:
            user_locality = self.get_locality(update.effective_user)
            chat_id = update.effective_message.chat.id
            user_id = update.effective_user.id
            user_username = update.effective_user.username
            chat_type = update.effective_message.chat.type
            print("Chat ID: " + str(chat_id))
            print("User ID: " + str(user_id))
            if update.effective_user.language_code:
                print("User Local: " + update.effective_user.language_code)
            print("Type of Chat: " + chat_type)

            if chat_type == "private":
                message = self.message_strings[user_locality]["group_error"]
                update.effective_message.reply_text(message)
                return

            this_participant = self.session.query(Participant).filter(Participant.telegram_id == user_id).first()
            if this_participant is None:
                message = self.message_strings[user_locality]["start_private"]
                update.effective_message.reply_text(message)
                return

            if this_participant.address is None:
                message = self.message_strings[user_locality]["need_address"]
                update.effective_message.reply_text(message)
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
                    update.effective_message.reply_text(message)
                    return
                self.session.add(Link(santa_id=this_participant.id, group_id=this_group.id))
                self.session.commit()
                message = self.message_strings[user_locality]["in"]
                update.effective_message.reply_text(message)
            else:
                message = self.message_strings[user_locality]["already_joined"]
                update.effective_message.reply_text(message)
        except Exception as this_ex:
            print(this_ex)
            print(traceback.format_exc())

    def not_command(self, update: Update, context: CallbackContext):
        try:
            print("{}: not".format(update.effective_user.name))
            user_locality = self.get_locality(update.effective_user)
            entities = update.effective_message.parse_entities()
            for entity, entity_text in entities.items():
                entity_type = entity.type
                print("not | entity type: {}".format(str(entity_type)))
                if entity_type == "mention":
                    this_participant = self.session.query(Participant).filter(
                        Participant.telegram_id == update.effective_user.id).first()

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
                            update.effective_message.reply_text(message)
                    elif participant_by_username.id == this_participant.id:
                        message = self.message_strings[user_locality]["not_yourself"]
                        update.effective_message.reply_text(message)
                    else:
                        id_list = [this_participant.id, participant_by_username.id]
                        in_blocked_list = self.session.query(BlockedLink).filter(
                            BlockedLink.participant_id.in_(id_list), BlockedLink.blocked_id.in_(id_list)).first()
                        if in_blocked_list is None:
                            self.session.add(
                                BlockedLink(participant_id=this_participant.id, blocked_id=participant_by_username.id))
                            message = self.message_strings[user_locality]["block_successful"]
                            update.effective_message.reply_text(message)
                        else:
                            message = self.message_strings[user_locality]["already_blocked_pairing"]
                            update.effective_message.reply_text(message)
                elif entity_type == "text_mention":
                    this_participant = self.session.query(Participant).filter(
                        Participant.telegram_id == update.effective_user.id).first()

                    mentioned_user = entity.user
                    mentioned_participant = self.session.query(Participant).filter(
                        Participant.telegram_id == mentioned_user.id).first()
                    if mentioned_participant is None:
                        message = self.message_strings[user_locality]["user_hasnt_joined"]
                        update.effective_message.reply_text(message)
                    else:
                        id_list = [this_participant.id, mentioned_participant.id]
                        in_blocked_list = self.session.query(BlockedLink).filter(
                            BlockedLink.participant_id.in_(id_list), BlockedLink.blocked_id.in_(id_list)).first()
                        if in_blocked_list is None:
                            self.session.add(
                                BlockedLink(participant_id=this_participant.id, blocked_id=mentioned_participant.id))
                            message = self.message_strings[user_locality]["block_successful"]
                            update.effective_message.reply_text(message)
                        else:
                            message = self.message_strings[user_locality]["already_blocked_pairing"]
                            update.effective_message.reply_text(message)
                    
            self.session.commit()
        except Exception as this_ex:
            print(this_ex)
            print(traceback.format_exc())

    def allow(self, update: Update, context: CallbackContext):
        try:
            user_locality = self.get_locality(update.effective_user)
            entities = update.effective_message.parse_entities()
            for entity, entity_text in entities.items():
                entity_type = entity.type
                print("allow | entity_type: " + str(entity_type))
                if entity_type == "mention":
                    this_participant = self.session.query(Participant).filter(
                        Participant.telegram_id == update.effective_user.id).first()

                    mentioned_participant = entity_text[1:]

                    mentioned_participant = self.session.query(Participant).filter(
                        Participant.telegram_username == mentioned_participant).first()
                    if mentioned_participant is None:
                        blocked_id = 0
                    else:
                        blocked_id = mentioned_participant.id

                    blocked_link = self.session.query(BlockedLink).join(BlockedLink.blocked, isouter=True)\
                        .filter(BlockedLink.participant_id == this_participant.id)\
                        .filter(or_(
                            BlockedLink.blocked_username == mentioned_participant,
                            BlockedLink.blocked_id == blocked_id)).first()
                    if blocked_link is not None:
                        self.session.delete(blocked_link)
                        self.session.commit()
                        message = self.message_strings[user_locality]["allow_successful"] + entity_text
                        update.effective_message.reply_text(message)
                    else:
                        message = entity_text + self.message_strings[user_locality]["not_blocked"]
                        update.effective_message.reply_text(message)
                elif entity_type == "text_mention":
                    this_participant = self.session.query(Participant).filter(
                        Participant.telegram_id == update.effective_user.id).first()

                    mentioned_user = entity.user
                    mentioned_participant = self.session.query(Participant).filter(
                        Participant.telegram_id == mentioned_user.id).first()
                    if mentioned_participant is None:
                        blocked_link = None
                    else:
                        blocked_link = self.session.query(BlockedLink).join(BlockedLink.blocked, isouter=True)\
                            .filter(BlockedLink.participant_id == this_participant.id)\
                            .filter(BlockedLink.blocked_id == mentioned_participant.id).first()

                    if blocked_link is not None:
                        self.session.delete(blocked_link)
                        self.session.commit()
                        message = self.message_strings[user_locality]["allow_successful"] + entity_text
                        update.effective_message.reply_text(message)
                    else:
                        message = entity_text + self.message_strings[user_locality]["not_blocked"]
                        update.effective_message.reply_text(message)
        except Exception as this_ex:
            print(this_ex)
            print(traceback.format_exc())

    def leave(self, update: Update, context: CallbackContext):
        try:
            user_locality = self.get_locality(update.effective_user)
            # delete in memberships
            this_link = self.session.query(Link).join(Link.santa).join(Group)\
                .filter(Participant.telegram_id == update.effective_user.id,
                        Group.telegram_id == update.effective_message.chat.id).first()
            if this_link is None:
                message = self.message_strings[user_locality]["never_joined"]
                update.effective_message.reply_text(message)
            else:
                self.session.query()
                self.session.delete(this_link)
                self.session.commit()
                message = self.message_strings[user_locality]["done"]
                update.effective_message.reply_text(message)
        except Exception as this_ex:
            print(this_ex)

    def start_exchange(self, update: Update, context: CallbackContext):
        try:
            user_locality = self.get_locality(update.effective_user)
            link_record_to_check = self.session.query(Link).join(Group).filter(
                Group.telegram_id == update.effective_message.chat.id).first()
            if link_record_to_check is None:
                message = self.message_strings[user_locality]["no_one_joined"]
                update.effective_message.reply_text(message)
                return
            if link_record_to_check.receiver_id is not None:
                message = self.message_strings[user_locality]["exchange_already_setup"]
                update.effective_message.reply_text(message)
                return

            this_group_id = update.effective_message.chat.id
            group_participants_objects = self.session.query(Participant).join(Participant.link_santa).join(Group)\
                .filter(Group.telegram_id == this_group_id).all()
            group_participants = [x.id for x in group_participants_objects]
            print(group_participants)

            blocked_participants_objects = self.session.query(BlockedLink).filter(BlockedLink.participant_id.in_(group_participants)).all()
            blocked_participants = [[x.participant_id, x.blocked_id] for x in blocked_participants_objects]

            success, selected_combination = self.find_combination(group_participants, blocked_participants)

            #  TODO Deal with failure
            if not success:
                print("Matching Impossible")
                return

            chatInfo = update.effective_message.chat
            chatTitle = str(chatInfo.title)

            for santa_id, receiver_id in selected_combination.items():
                santa = self.session.query(Participant).get(santa_id)
                receiver = self.session.query(Participant).get(receiver_id)
                
                santa_link = self.session.query(Link).join(Group)\
                    .filter(Link.santa_id == santa.id, Group.telegram_id == chatInfo.id).first()
                santa_link.receiver_id = receiver.id
                receiverUser = chatInfo.get_member(user_id=receiver.telegram_id).user
                youGotUsername = "{}| {}{}".format(chatTitle, self.message_strings[user_locality]["you_got"],receiverUser.name)
                if receiver.address:
                    receiverAddress = receiver.address
                else:
                    receiverAddress = "empty"
                youGotAddress = self.message_strings[user_locality]["their_address_is"] + receiverAddress
                message =  youGotUsername + youGotAddress
                context.bot.send_message(chat_id=santa.telegram_id, text=message)
            self.session.commit()
            message = self.message_strings[user_locality]["messages_sent"]
            update.effective_message.reply_text(message)
        except Exception as this_ex:
            print(this_ex)
            print(traceback.format_exc())

    def reset_exchange(self, update: Update, context: CallbackContext):
        user_locality = self.get_locality(update.effective_user)
        this_group_id = update.effective_message.chat.id
        group_links = self.session.query(Link).join(Group).filter(Group.telegram_id == this_group_id)
        for group_link in group_links:
            group_link.receiver_id = None
        self.session.commit()
        message = self.message_strings[user_locality]["pairings_reset"]
        update.effective_message.reply_text(message)

    def find_combination(self, participants, blocked_pairings):      
        #  permutations before removing blocked pairings
        unfiltered_permutations = list(permutations(participants, 2))    
        print("unfiltered permutations: {}".format(len(unfiltered_permutations)))
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
        
        print("filtered permutations: {}".format(filtered_permutation_count))

        if not filtered_permutations:
            return False, {}
        #  sort permutations by least number of pairings
        sorted_permutations = sorted(filtered_permutations.items(), key=lambda x: len(x[1]))

        #  get random set of pairings if possible
        success, result_set = self.get_random_pairing(sorted_permutations)
 
        return success, result_set
        
    def get_random_pairing(self, remaining_participants, gifting=[]):
        remaining_participants_copy = deepcopy(remaining_participants)
        this_participant = remaining_participants_copy.pop(0)
        print(this_participant)
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
            for remaining_participant, remaining_pairings in new_remaining_participants:
                if len(remaining_pairings) == 1 and random_receiver in remaining_pairings:
                    possible = False
                    break
                remaining_pairings.discard(random_receiver)      
            if not possible:
                continue
            success, final_pairings = self.get_random_pairing(new_remaining_participants, gifting)
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
