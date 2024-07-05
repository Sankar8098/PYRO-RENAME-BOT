# Import necessary modules
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserNotParticipant
from config import Config  # Assuming Config contains your bot configuration
from helper.database import db  # Assuming db handles database operations

# Define a function to check if user is subscribed
async def not_subscribed(_, client, message):
    # Add user to database
    await db.add_user(client, message)
    
    # Check if forced subscription is required
    if not Config.FORCE_SUB:
        return False
    
    try:
        # Check if user is a member of the required channel or group
        user = await client.get_chat_member(Config.FORCE_SUB, message.from_user.id)
        
        # If user is banned, return True
        if user.status == enums.ChatMemberStatus.BANNED:
            return True
        else:
            return False
    
    except UserNotParticipant:
        pass
    
    # Return True if user is not a participant
    return True

# Define handler for private messages that are not subscribed
@Client.on_message(filters.private & filters.create(not_subscribed))
async def forces_sub(client, message):
    # Prepare message and buttons for non-subscribed users
    buttons = [[InlineKeyboardButton(text="📢 Join Update Channel 📢", url=f"https://t.me/{Config.FORCE_SUB}")]]
    text = "**Sorry, you're not joined my channel 😐. Please join our update channel to continue**"
    
    try:
        # Check if user is banned from using the bot
        user = await client.get_chat_member(Config.FORCE_SUB, message.from_user.id)
        
        if user.status == enums.ChatMemberStatus.BANNED:
            return await client.send_message(message.from_user.id, text="Sorry, you're banned to use me")
    
    except UserNotParticipant:
        # If user is not a participant, send subscription message with buttons
        return await message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))
    
    # Send subscription message with buttons
    return await message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))
