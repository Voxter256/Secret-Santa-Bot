import json
from pathlib import Path


class Scraper:
    def __init__(self):
        self.patch_version = None
        self.patch_notes = ""
        self.notes_link = ""

    @staticmethod
    def open_version_file(file_name):
        if Path(file_name).is_file():
            with open(file_name, 'r') as file:
                file_contents = file.read()
                if file_contents == '':
                    version_dictionary = {}
                else:
                    version_dictionary = json.loads(file_contents)
        else:
            file = open(file_name, 'w+')
            file.close()
            version_dictionary = {}
        return version_dictionary

    def update_version_file(self, file_name):
        patch_data = {
            "patch_version": self.patch_version,
            "patch_notes": self.patch_notes,
            "notes_link": self.notes_link
        }
        if hasattr(self, 'build_version'):
            patch_data['build_version'] = self.build_version
        if hasattr(self, 'patch_date'):
            patch_data['patch_date'] = self.patch_date

        with open(file_name, 'w') as file:
            json.dump(patch_data, file)

    def reply_current_version(self, bot, update):
        message = "The current version is " + self.patch_version + ". " + \
                  self.patch_notes + " notes can be found here: " + self.notes_link
        update.message.reply_text(message)

    @staticmethod
    def bot_send_message(bot, subscription_list, message):
        for chat_id in subscription_list:
            bot.send_message(chat_id=chat_id, text=message)
