import os
import time
import wget
from datetime import datetime
from pytz import timezone
from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from PIL import Image

# Import your helper functions and database access here
from helper.utils import progress_for_pyrogram, convert, humanbytes
from helper.database import db

# Initialize your Pyrogram Client
app = Client("my_bot")

# Helper function to handle filename renaming
@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def rename_start(client, message):
    file = getattr(message, message.media.value)
    filename = file.file_name
    if file.file_size > 2000 * 1024 * 1024:
        return await message.reply_text("Sorry, this bot does not support uploading files bigger than 2GB")

    try:
        await message.reply_text(
            text=f"**Please enter new filename...**\n\n**Old Filename**: `{filename}`",
            reply_to_message_id=message.message_id,
            reply_markup=ForceReply(True)
        )
        await app.sleep(30)
    except FloodWait as e:
        await app.sleep(e.x)
        await message.reply_text(
            text=f"**Please enter new filename...**\n\n**Old Filename**: `{filename}`",
            reply_to_message_id=message.message_id,
            reply_markup=ForceReply(True)
        )
    except Exception as e:
        print(f"Error in rename_start: {e}")

# Handle the renamed file and processing
@Client.on_message(filters.private & filters.reply)
async def handle_rename(client, message):
    reply_message = message.reply_to_message
    if isinstance(reply_message.reply_markup, ForceReply):
        new_name = message.text
        await message.delete()
        msg = await client.get_messages(message.chat.id, reply_message.message_id)
        file = msg.reply_to_message
        media = getattr(file, file.media.value)
        
        if not "." in new_name:
            extn = file.file_name.rsplit('.', 1)[-1] if "." in media.file_name else "mkv"
            new_name = f"{new_name}.{extn}"
        
        await reply_message.delete()

        buttons = [[InlineKeyboardButton("📁 Document", callback_data="upload_document")]]
        if file.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
            buttons.append([InlineKeyboardButton("🎥 Video", callback_data="upload_video")])
        elif file.media == MessageMediaType.AUDIO:
            buttons.append([InlineKeyboardButton("🎵 Audio", callback_data="upload_audio")])

        await message.reply(
            text=f"**Select the output file type**\n**• Filename:**```{new_name}```",
            reply_to_message_id=file.message_id,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

# Callback to handle different types of uploads
@Client.on_callback_query(filters.regex("upload"))
async def upload_callback(bot, update):
    new_name = update.message.text
    new_filename = new_name.split(":-")[1].strip()
    file_path = f"downloads/{new_filename}"
    file = update.message.reply_to_message

    ms = await update.message.edit("Trying to download...")
    try:
        path = await bot.download_media(message=file, file_name=file_path, progress=progress_for_pyrogram, progress_args=("Download started...", ms, time.time()))
    except Exception as e:
        return await ms.edit(f"Error downloading file: {e}")

    duration = 0
    try:
        metadata = extractMetadata(createParser(file_path))
        if metadata.has("duration"):
            duration = metadata.get('duration').seconds
    except Exception as e:
        print(f"Error extracting metadata: {e}")

    ph_path = None
    user_id = int(update.message.chat.id)
    media = getattr(file, file.media.value)
    c_caption = await db.get_caption(update.message.chat.id)
    c_thumb = await db.get_thumbnail(update.message.chat.id)

    try:
        caption = c_caption.format(filename=new_filename, filesize=humanbytes(media.file_size), duration=convert(duration)) if c_caption else f"**{new_filename}**"
    except Exception as e:
        return await ms.edit(f"Error formatting caption: {e}")

    if media.thumbs or c_thumb:
        ph_path = await bot.download_media(c_thumb) if c_thumb else await bot.download_media(media.thumbs[0].file_id)
        Image.open(ph_path).convert("RGB").save(ph_path)
        Image.open(ph_path).resize((320, 320)).save(ph_path, "JPEG")

    ending_image_url = "https://telegra.ph/file/fb69b8524027808ab86c8.jpg"
    ending_image_path = "downloads/ending_image.jpg"
    wget.download(ending_image_url, ending_image_path)

    final_video_path = f"downloads/final_{new_filename}"

    try:
        if file.media == MessageMediaType.DOCUMENT:
            await bot.send_document(
                update.message.chat.id,
                document=final_video_path,
                thumb=ph_path,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=("Upload started...", ms, time.time()))
        elif file.media == MessageMediaType.VIDEO:
            await bot.send_video(
                update.message.chat.id,
                video=final_video_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("Upload started...", ms, time.time()))
        elif file.media == MessageMediaType.AUDIO:
            await bot.send_audio(
                update.message.chat.id,
                audio=final_video_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("Upload started...", ms, time.time()))
    except Exception as e:
        os.remove(final_video_path)
        if ph_path:
            os.remove(ph_path)
        return await ms.edit(f"Error uploading file: {e}")

    await ms.delete()
    os.remove(final_video_path)
    if ph_path:
        os.remove(ph_path)
    os.remove(file_path)
    os.remove(ending_image_path)

# Run the client
app.run()
