import os
import sys
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters,
)

import prompts
from monitor import generate_response
from config import get_logger
from channel_store import add_channel, remove_channel, get_monitored_channels
from query_store import get_current_query, set_current_query

logger = get_logger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
# User's personal API credentials (required for accessing their channels)
API_ID = os.getenv("api_id")
API_HASH = os.getenv("api_hash")

# Use a separate session for bot operations to avoid conflicts with monitor.py
telethon_client = None  # Will be initialized when needed

async def start(update, context):
    """Send welcome message with current search query and available commands."""
    welcome_text = (
        "הייייייייייי\n\n"
        "Available commands:\n"
        "/start - Show this help message\n"
        "/getmyid - Get your Telegram user ID for configuration\n"
        "/listchannels - List all your Telegram channels\n"
        "/setquery <text> - Set a new search query for filtering messages\n"
        "/showquery - Show current search query\n"
        "/addchannel <name> - Add a channel to monitor\n"
        "/removechannel <name> - Remove a channel from monitoring\n"
        "/listmonitored - Show currently monitored channels\n\n"
        f"Current search query: {get_current_query()}"
    )
    await update.message.reply_text(welcome_text)

async def set_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update the search query used for filtering messages."""
    # Get the text after the command
    query = update.message.text.removeprefix("/setquery").strip()
    
    if not query:
        await update.message.reply_text(
            "❌ Please provide a search query after /setquery\n"
            "Example: /setquery find messages about tech news"
        )
        return

    # Update the query using the query store (persists across processes)
    if set_current_query(query):
        await update.message.reply_text(
            f"✅ Search query updated!\n\n"
            f"New query: {query}\n\n"
            f"The monitor will now filter messages based on this query."
        )
        logger.info(f"Search query updated to: {query}")
    else:
        await update.message.reply_text(
            "❌ Failed to update search query. Please try again."
        )
        logger.error(f"Failed to save query: {query}")


async def show_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the current search query."""
    await update.message.reply_text(
        f"Current search query:\n{get_current_query()}"
    )

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show your Telegram user ID."""
    user = update.effective_user
    await update.message.reply_text(
        f"Your Telegram user ID is: `{user.id}`\n\n"
        f"Add this to your .env file as:\n"
        f"`USER_CHAT_ID={user.id}`",
        parse_mode="Markdown"
    )

async def add_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a channel to the monitoring list."""
    channel = update.message.text.removeprefix("/addchannel").strip()
    
    if not channel:
        await update.message.reply_text(
            "❌ Please provide a channel name or ID after /addchannel\n"
            "Example: /addchannel @channelname or /addchannel channelname"
        )
        return

    # Remove @ if provided
    channel = channel.lstrip("@")
    
    if add_channel(channel):
        await update.message.reply_text(
            f"✅ Channel '{channel}' added to monitoring list.\n\n"
            f"Current monitored channels:\n{', '.join(get_monitored_channels())}"
        )
        logger.info(f"Added channel to monitoring: {channel}")
    else:
        await update.message.reply_text(
            f"ℹ️ Channel '{channel}' is already being monitored."
        )

async def remove_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a channel from the monitoring list."""
    channel = update.message.text.removeprefix("/removechannel").strip()
    
    if not channel:
        await update.message.reply_text(
            "❌ Please provide a channel name or ID after /removechannel\n"
            "Example: /removechannel @channelname or /removechannel channelname"
        )
        return

    # Remove @ if provided
    channel = channel.lstrip("@")
    
    if remove_channel(channel):
        await update.message.reply_text(
            f"✅ Channel '{channel}' removed from monitoring list.\n\n"
            f"Current monitored channels:\n{', '.join(get_monitored_channels())}"
        )
        logger.info(f"Removed channel from monitoring: {channel}")
    else:
        await update.message.reply_text(
            f"❌ Channel '{channel}' was not in the monitoring list."
        )

async def list_monitored_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the list of channels being monitored."""
    channels = get_monitored_channels()
    if channels:
        await update.message.reply_text(
            "📺 Currently monitored channels:\n\n" +
            "\n".join(f"- {channel}" for channel in channels)
        )
    else:
        await update.message.reply_text(
            "ℹ️ No channels are currently being monitored.\n"
            "Use /addchannel to start monitoring a channel."
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular chat messages by generating AI responses."""
    if not update.message or not update.message.text:
        await update.message.reply_text("Sorry, I can only process text messages.")
        return
        
    user = update.effective_user
    user_name = getattr(user, "username", None) or getattr(user, "first_name", "Anonymous")
    logger.info(f"Message from @{user_name}: {update.message.text[:100]}")

    # Show typing indicator while generating response
    async with update.message.chat.action("typing"):
        try:
            response = await generate_response(update.message.text)
            await update.message.reply_text(response)
            logger.info(f"Response sent to @{user_name}")
        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            await update.message.reply_text(error_msg)
            logger.error(f"Error responding to @{user_name}: {e}")

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List channels from your user account using a separate session."""
    global telethon_client
    user = update.effective_user
    requester = f"@{user.username}" if getattr(user, "username", None) else getattr(user, "first_name", "You")
    
    try:
        # Create a separate client instance to avoid session conflicts
        if not API_ID or not API_HASH:
            await update.message.reply_text(
                "❌ API credentials not configured.\n"
                "Please add api_id and api_hash to your .env file."
            )
            return
            
        # Use a different session name to avoid conflicts with monitor.py
        client = TelegramClient("bot_user_session", int(API_ID), API_HASH)
        
        await client.connect()
        
        if not await client.is_user_authorized():
            await update.message.reply_text(
                "� **First Time Setup Required**\n\n"
                "You need to authenticate your Telegram account.\n"
                "Check the terminal where the bot is running for instructions."
            )
            print(f"\n🔐 User {requester} needs authentication:")
            print("Enter your phone number (international format, e.g. +1234567890): ")
            phone = input("> ")
            await client.send_code_request(phone)
            print("Enter the verification code from Telegram: ")
            code = input("> ")
            try:
                await client.sign_in(phone, code)
                await update.message.reply_text("✅ Successfully authenticated! Try /listchannels again.")
            except SessionPasswordNeededError:
                print("Enter your 2FA password: ")
                password = input("> ")
                await client.sign_in(password=password)
                await update.message.reply_text("✅ Successfully authenticated with 2FA! Try /listchannels again.")
            except Exception as e:
                await update.message.reply_text(f"❌ Authentication failed: {str(e)}")
            finally:
                await client.disconnect()
            return

        dialogs = await client.get_dialogs(limit=500)
        channels = []
        
        for d in dialogs:
            ent = getattr(d, "entity", None)
            if not ent:
                continue
                
            # Include both broadcast channels and supergroups (like original code)
            is_channel = getattr(ent, "broadcast", False) or getattr(ent, "megagroup", False)
            if is_channel:
                title = getattr(ent, "title", None) or getattr(ent, "username", None) or str(getattr(ent, "id", ""))
                username = getattr(ent, "username", None)
                
                if username:
                    channels.append(f"{title} (@{username}) — ID: {ent.id}")
                else:
                    channels.append(f"{title} — ID: {ent.id}")

        await client.disconnect()
        
        if not channels:
            await update.message.reply_text(f"{requester}: No channels found in your account.")
            return

        await update.message.reply_text(f"{requester}: Found {len(channels)} channels. Sending list...")

        # Send results in chunks to avoid message size limits
        chunk = []
        current_len = 0
        for line in channels:
            if current_len + len(line) + 1 > 3500:
                await update.message.reply_text("\n".join(chunk))
                chunk = []
                current_len = 0
            chunk.append(line)
            current_len += len(line) + 1
        if chunk:
            await update.message.reply_text("\n".join(chunk))

        await update.message.reply_text(
            "💡 **Tip:** Use `/addchannel channelname` to monitor any of these channels!"
        )

    except Exception as exc:
        await update.message.reply_text(f"❌ Failed to list channels: {exc}")
        logger.error(f"Error in list_channels: {exc}")


def main():
    """Initialize and run the bot."""
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN not found in .env file")
        return
    if not API_ID or not API_HASH:
        print("❌ Error: api_id or api_hash not found in .env file")
        print("💡 These are needed for the /listchannels command")
        return

    print("\n🤖 Starting Telegram Bot...")
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("listchannels", list_channels))
    application.add_handler(CommandHandler("setquery", set_query))
    application.add_handler(CommandHandler("showquery", show_query))
    application.add_handler(CommandHandler("getmyid", get_my_id))
    application.add_handler(CommandHandler("addchannel", add_channel_handler))
    application.add_handler(CommandHandler("removechannel", remove_channel_handler))
    application.add_handler(CommandHandler("listmonitored", list_monitored_channels))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✨ Bot started! Available commands:")
    print("  /start - Show help message")
    print("  /listchannels - List your Telegram channels")
    print("  /setquery <text> - Set a new search query")
    print("  /showquery - Show current search query")
    print("  /addchannel <name> - Add a channel to monitor")
    print("  /removechannel <name> - Remove a channel from monitoring")
    print("  /listmonitored - Show currently monitored channels")
    print(f"\nCurrent search query: {get_current_query()}")
    print("\nPress Ctrl+C to stop the bot")

    application.run_polling()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}")
        sys.exit(1)