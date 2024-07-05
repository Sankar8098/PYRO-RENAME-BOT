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
from helper.utils import progress_for_pyrogram, convert, humanbytes
from helper.database import db
from asyncio import sleep

# Function to handle renaming start
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
        await sleep(30)
    except FloodWait as e:
        await sleep(e.value)
        await message.reply_text(
            text=f"**Please enter new filename...**\n\n**Old Filename**: `{filename}`",
            reply_to_message_id=message.message_id,  
            reply_markup=ForceReply(True)
        )
    except Exception as e:
        print(f"Error in rename_start: {e}")

# Function to handle reply with new filename
@Client.on_message(filters.private & filters.reply)
async def refunc(client, message):
    reply_message = message.reply_to_message
    if (reply_message.reply_markup) and isinstance(reply_message.reply_markup, ForceReply):
        new_name = message.text 
        await message.delete() 
        try:
            msg = await client.get_messages(message.chat.id, reply_message.message_id)
            file = msg.reply_to_message
            media = getattr(file, file.media.value)
            if not "." in new_name:
                if "." in media.file_name:
                    extn = media.file_name.rsplit('.', 1)[-1]
                else:
                    extn = "mkv"
                new_name = new_name + "." + extn
            await reply_message.delete()

            button = [[InlineKeyboardButton("📁 Document", callback_data="upload_document")]]
            if file.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
                button.append([InlineKeyboardButton("🎥 Video", callback_data="upload_video")])
            elif file.media == MessageMediaType.AUDIO:
                button.append([InlineKeyboardButton("🎵 Audio", callback_data="upload_audio")])
            await message.reply(
                text=f"**Select the output file type**\n**• Filename:**```{new_name}```",
                reply_to_message_id=file.message_id,
                reply_markup=InlineKeyboardMarkup(button)
            )
        except Exception as e:
            print(f"Error in refunc: {e}")

# Callback function to handle document uploads
@Client.on_callback_query(filters.regex("upload"))
async def doc(bot, update):
    try:
        new_name = update.message.text
        new_filename = new_name.split(":-")[1].strip()
        file_path = f"downloads/{new_filename}"
        file = update.message.reply_to_message

        ms = await update.message.edit("Trying to download...")

        # Downloading the file
        try:
            path = await bot.download_media(message=file, file_name=file_path, progress=progress_for_pyrogram, progress_args=("Download started...", ms, time.time()))                    
        except Exception as e:
            return await ms.edit(f"Error downloading file: {e}")

        # Extracting metadata
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

        # Generating caption
        if c_caption:
            try:
                caption = c_caption.format(filename=new_filename, filesize=humanbytes(media.file_size), duration=convert(duration))
            except Exception as e:
                return await ms.edit(f"Error generating caption: {e}")
        else:
            caption = f"**{new_filename}**"

        # Processing thumbnail
        if media.thumbs or c_thumb:
            try:
                if c_thumb:
                    ph_path = await bot.download_media(c_thumb)
                else:
                    ph_path = await bot.download_media(media.thumbs[0].file_id)
                Image.open(ph_path).convert("RGB").save(ph_path)
                img = Image.open(ph_path)
                img.resize((320, 320))
                img.save(ph_path, "JPEG")
            except Exception as e:
                print(f"Error processing thumbnail: {e}")

        # Downloading ending image
        ending_image_url = "https://telegra.ph/file/fb69b8524027808ab86c8.jpg"
        ending_image_path = "downloads/ending_image.jpg"
        wget.download(ending_image_url, ending_image_path)

        final_video_path = f"downloads/final_{new_filename}"

        # Uploading the final file
        try:
            if media == MessageMediaType.DOCUMENT:
                await bot.send_document(
                    update.message.chat.id,
                    document=final_video_path,
                    thumb=ph_path,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload started...", ms, time.time()))
            elif media == MessageMediaType.VIDEO:
                await bot.send_video(
                    update.message.chat.id,
                    video=final_video_path,
                    caption=caption,
                    thumb=ph_path,
                    duration=duration,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload started...", ms, time.time()))
            elif media == MessageMediaType.AUDIO:
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

        # Cleanup
        await ms.delete()
        os.remove(final_video_path)
        if ph_path:
            os.remove(ph_path)
        os.remove(file_path)
        os.remove(ending_image_path)

    except Exception as e:
        print(f"Error in doc callback: {e}")

