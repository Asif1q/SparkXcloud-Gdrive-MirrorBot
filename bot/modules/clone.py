from random import SystemRandom
from string import ascii_letters, digits
from telegram.ext import CommandHandler
from threading import Thread
from time import sleep

from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, deleteMessage, delete_all_messages, update_all_messages, sendStatusMessage, sendFile, sendMarkup
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.mirror_utils.status_utils.clone_status import CloneStatus
from bot import dispatcher, LOGGER, CLONE_LIMIT, STOP_DUPLICATE, download_dict, download_dict_lock, Interval
from bot.helper.ext_utils.bot_utils import get_readable_file_size, is_gdrive_link, is_gdtot_link, new_thread
from bot.helper.mirror_utils.download_utils.direct_link_generator import gdtot
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException


def _clone(message, bot):
    args = message.text.split()
    reply_to = message.reply_to_message
    link = ''
    multi=1
    if len(args) > 1:
        link = args[1].strip()
        if link.strip().isdigit():
            multi = int(link)
            link = ''
        elif message.from_user.username:
            tag = f"@{message.from_user.username}"
        else:
            tag = message.from_user.mention_html(message.from_user.first_name)
    if reply_to:
        if len(link) == 0:
            link = reply_to.text.split(maxsplit=1)[0].strip()
        if reply_to.from_user.username:
            tag = f"@{reply_to.from_user.username}"
        else:
            tag = reply_to.from_user.mention_html(reply_to.from_user.first_name)
    is_gdtot = is_gdtot_link(link)
    if is_gdtot:
        try:
            msg = sendMessage(f"Processing: <code>{link}</code>", bot, message)
            link = gdtot(link)
            deleteMessage(bot, msg)
        except DirectDownloadLinkException as e:
            deleteMessage(bot, msg)
            return sendMessage(str(e), bot, message)
    if is_gdrive_link(link):
        gd = GoogleDriveHelper()
        res, size, name, files = gd.helper(link)
        if res != "":
            return sendMessage(res, bot, message)
        if STOP_DUPLICATE:
            LOGGER.info('Checking File/Folder if already in Drive...')
            cap, f_name = gd.drive_list(name, True, True)
            if cap:
                cap = f"File/Folder is already available in Drive. Here are the search results:\n\n{cap}"
                sendFile(bot, message, f_name, cap)
                return
        if CLONE_LIMIT is not None:
            LOGGER.info('Checking File/Folder Size...')
            if size > CLONE_LIMIT * 1024**3:
                msg2 = f'𝐅𝐚𝐢𝐥𝐞𝐝, 𝐂𝐥𝐨𝐧𝐞 𝐥𝐢𝐦𝐢𝐭 𝐢𝐬 {CLONE_LIMIT}GB.\n𝐘𝐨𝐮𝐫 𝐅𝐢𝐥𝐞/𝐅𝐨𝐥𝐝𝐞𝐫 𝐬𝐢𝐳𝐞 𝐢𝐬{get_readable_file_size(size)}.'
                return sendMessage(msg2, bot, message)
        if multi > 1:
            sleep(2)
            nextmsg = type('nextmsg', (object, ), {'chat_id': message.chat_id, 'message_id': message.reply_to_message.message_id + 1})
            nextmsg = sendMessage(message.text.replace(str(multi), str(multi - 1), 1), bot, nextmsg)
            nextmsg.from_user.id = message.from_user.id
            sleep(2)
            Thread(target=_clone, args=(nextmsg, bot)).start()
        if files <= 20:
            msg = sendMessage(f"𝐂𝐥𝐨𝐧𝐢𝐧𝐠: <code>{link}</code>", bot, message)
            result, button = gd.clone(link)
            deleteMessage(bot, msg)
        else:
            drive = GoogleDriveHelper(name)
            gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=12))
            clone_status = CloneStatus(drive, size, message, gid)
            with download_dict_lock:
                download_dict[message.message_id] = clone_status
            sendStatusMessage(message, bot)
            result, button = drive.clone(link)
            with download_dict_lock:
                del download_dict[message.message_id]
                count = len(download_dict)
            try:
                if count == 0:
                    Interval[0].cancel()
                    del Interval[0]
                    delete_all_messages()
                else:
                    update_all_messages()
            except IndexError:
                pass
        cc = f'\n\n<b>cc: </b>{tag}'
        if button in ["cancelled", ""]:
            sendMessage(f"{tag} {result}", bot, message)
        else:
            sendMarkup(result + cc, bot, message, button)
            LOGGER.info(f'Cloning Done: {name}')
        if is_gdtot:
            gd.deletefile(link)
    else:
        sendMessage("𝐒𝐞𝐧𝐝 𝐆𝐝𝐫𝐢𝐯𝐞 𝐨𝐫 𝐠𝐝𝐭𝐨𝐭 𝐥𝐢𝐧𝐤 𝐚𝐥𝐨𝐧𝐠 𝐰𝐢𝐭𝐡 𝐜𝐨𝐦𝐦𝐚𝐧𝐝 𝐨𝐫 𝐛𝐲 𝐫𝐞𝐩𝐥𝐲𝐢𝐧𝐠 𝐭𝐨 𝐭𝐡𝐞 𝐥𝐢𝐧𝐤 𝐛𝐲 𝐜𝐨𝐦𝐦𝐚𝐧𝐝\n\n<b>𝐌𝐮𝐥𝐭𝐢 𝐥𝐢𝐧𝐤𝐬 𝐨𝐧𝐥𝐲 𝐛𝐲 𝐫𝐞𝐩𝐥𝐲𝐢𝐧𝐠 𝐭𝐨 𝐟𝐢𝐫𝐬𝐭 𝐥𝐢𝐧𝐤/𝐟𝐢𝐥𝐞:</b>\n<code>/cmd</code> 10(number of links/files)", bot, message)

@new_thread
def cloneNode(update, context):
    _clone(update.message, context.bot)

clone_handler = CommandHandler(BotCommands.CloneCommand, cloneNode, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
dispatcher.add_handler(clone_handler)