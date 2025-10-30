"""Telegram channel monitoring utilities."""


import asyncio
import os
import json
from datetime import datetime
from typing import List, Optional, Sequence, Set

import httpx
from telethon import TelegramClient, events

from query_store import get_current_query
from channel_store import get_monitored_channels
from ai import MistralAIProcessor
from config import get_logger

logger = get_logger(__name__)


async def generate_response(message_text: str) -> str:
    """Generate an AI response to a message using MistralAI.
    
    Args:
        message_text: The text message to analyze
        
    Returns:
        str: The AI-generated response
    """
    ai_processor = MistralAIProcessor()
    try:
        # Prepare message data for the AI processor
        message_data = {
            "message_text": message_text,
            "channel_name": "Direct Message",
            "sender_name": "User",
            "message_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Process the message with AI
        response = await ai_processor.process_message(message_data)
        if response:
            return response
        return "Sorry, I couldn't analyze that message."
    except Exception as exc:
        logger.error("Error generating response: %s", exc)
        return f"Error generating response: {str(exc)}"


class TelegramChannelMonitor:
    """Monitor Telegram channels for new messages."""

    def __init__(self) -> None:
        self.api_id = os.getenv("api_id")
        self.api_hash = os.getenv("api_hash")
        self.bot_token = os.getenv("BOT_TOKEN")
        self.user_chat_id = os.getenv("USER_CHAT_ID")  # Your Telegram user ID

        if not self.api_id or not self.api_hash:
            raise ValueError("API credentials not found in .env file")

        self.client = TelegramClient("telegram_session", int(self.api_id), self.api_hash)
        self.ai_processor = MistralAIProcessor()
        self.user_entity = None

    async def start(self) -> None:
        """Start the Telegram client and authenticate."""
        try:
            await self.client.connect()

            if not await self.client.is_user_authorized():
                print("First time login - you'll need to enter your phone number and verification code")
                phone = input("Enter your phone number: ")
                await self.client.send_code_request(phone)
                code = input("Enter the verification code: ")
                await self.client.sign_in(phone, code)

            logger.info("Successfully connected to Telegram")

            me = await self.client.get_me()
            self.user_entity = me
            if hasattr(me, "first_name"):
                username = getattr(me, "username", "N/A")
                logger.info("Logged in as: %s (@%s)", me.first_name, username)
            else:
                logger.info("Successfully logged in")

        except Exception as exc:  # pragma: no cover - network failures etc.
            logger.error("Failed to start Telegram client: %s", exc)
            raise

    async def send_message_via_bot(self, message, chat, source_chat_name: str) -> bool:
        """Send relevant message info via bot to the user."""
        if not self.bot_token or not self.user_chat_id:
            logger.error("Bot token or user chat ID not configured. Cannot send messages.")
            return False

        try:
            # Format the message content
            channel_name = getattr(chat, "title", "Unknown Channel")
            username = getattr(chat, "username", "N/A")
            message_text = message.text or "[Media/File/Sticker/Other content]"
            message_date = message.date.strftime("%Y-%m-%d %H:%M:%S")
            
            # Get sender info
            sender = await message.get_sender()
            sender_name = "Unknown"
            if sender:
                if hasattr(sender, "first_name") and sender.first_name:
                    sender_name = sender.first_name
                    if hasattr(sender, "last_name") and sender.last_name:
                        sender_name += f" {sender.last_name}"
                elif hasattr(sender, "title") and sender.title:
                    sender_name = sender.title
                elif hasattr(sender, "username") and sender.username:
                    sender_name = f"@{sender.username}"

            # Create message link for direct access
            message_link = None
            if hasattr(chat, 'username') and chat.username:
                # Public channel with username
                message_link = f"https://t.me/{chat.username}/{message.id}"
            elif hasattr(chat, 'id'):
                # Private channel or group (works if user has access)
                chat_id_str = str(chat.id).replace('-100', '')  # Remove -100 prefix for supergroups
                message_link = f"https://t.me/c/{chat_id_str}/{message.id}"

            # Format message for bot
            bot_message = f"🎯 **RELEVANT MESSAGE FOUND**\n\n"
            bot_message += f"**Channel:** {channel_name}\n"
            if username and username != "N/A":
                bot_message += f"**Username:** @{username}\n"
            bot_message += f"**Sender:** {sender_name}\n"
            bot_message += f"**Date:** {message_date}\n"
            bot_message += f"**Query:** {get_current_query()}\n\n"
            
            # Add clickable link to original message
            if message_link:
                bot_message += f"🔗 **[Click to view original message]({message_link})**\n\n"
            
            bot_message += f"**Message:**\n{message_text}"

            # Send via Bot API
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.user_chat_id,
                "text": bot_message,
                "parse_mode": "Markdown"
            }
            
            # Add inline keyboard with link button if we have a message link
            if message_link:
                payload["reply_markup"] = {
                    "inline_keyboard": [[
                        {
                            "text": "🔗 Open Original Message",
                            "url": message_link
                        }
                    ]]
                }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    logger.info("Successfully sent message via bot from %s", source_chat_name)
                    return True
                else:
                    logger.error("Bot API error: %s", response.text)
                    return False

        except Exception as exc:
            logger.error("Failed to send message via bot: %s", exc)
            return False

    async def validate_channels_from_store(self) -> Set[str]:
        """Validate that channels from store exist and are accessible."""
        channels = get_monitored_channels()
        print(f"📂 Loading channels from channel store: {channels}")
        
        validated_channels = set()
        for channel in channels:
            try:
                print(f"🔍 Validating channel: {channel}")
                entity = await self.client.get_entity(channel)
                if entity:
                    print(f"✅ Channel '{channel}' validated (ID: {entity.id})")
                    validated_channels.add(channel)
            except ValueError as e:
                print(f"❌ Channel '{channel}' not found or not accessible: {e}")
            except Exception as e:
                print(f"❌ Error validating channel '{channel}': {type(e).__name__}: {e}")
        
        return validated_channels

    def setup_message_handler(self) -> None:
        """Set up the event handler for new messages."""

        @self.client.on(events.NewMessage())
        async def message_handler(event):  # pragma: no cover - relies on Telegram events
            try:
                message = event.message
                chat = await event.get_chat()
                chat_name = getattr(chat, "title", getattr(chat, "username", "Unknown"))
                print(f'chat_name: {chat_name}')
                try:
                    logger.info(
                        "Received message from chat: '%s' (ID: %s)",
                        chat_name,
                        getattr(chat, "id", "Unknown"),
                    )
                except UnicodeEncodeError:
                    safe_chat_name = str(chat_name).encode("ascii", "replace").decode("ascii")
                    logger.info(
                        "Received message from chat: '%s' (ID: %s)",
                        safe_chat_name,
                        getattr(chat, "id", "Unknown"),
                    )
                monitored_channels = get_monitored_channels()
                logger.info("Monitored channels: %s", monitored_channels)
                print(f'chat_name: {chat_name}, monitored_channels: {monitored_channels}')
                if chat_name in monitored_channels:

                    logger.info("Processing message from monitored channel: %s", chat.id)
                    message_text = message.text or ""
                    if not message_text:
                        message_text = "[Non-text content]"

           
                    # Get the current query dynamically from the query store
                    current_query = get_current_query()

                    # Use the dynamic query from the query store
                    is_relevant = await self.ai_processor.is_message_relevant(
                        message_text, current_query
                    )
                    # is_relevant = True # TEMP OVERRIDE FOR TESTING

                    if is_relevant:
                        logger.info("Message is relevant to query, processing...")
                        await self.process_new_message(message, chat)

                        # Send summary with clickable link (current implementation)
                        sent = await self.send_message_via_bot(message, chat, chat_name)
                             
                        if sent:
                            print("📤 Message sent to your bot!")
                        else:
                            print("❌ Failed to send message to bot")
                    else:
                        logger.info("Message not relevant to query, skipping...")
                else:
                    logger.info(
                        "Ignoring message from unmonitored chat: %s",
                        getattr(chat, "id", "Unknown"),
                    )
            except Exception as exc:  # pragma: no cover - event loop runtime issues
                logger.error("Error processing message: %s", exc)

    async def process_new_message(self, message, chat) -> None:
        """Process and print new messages from monitored channels."""
        try:
            channel_name = getattr(chat, "title", "Unknown Channel")
            username = getattr(chat, "username", "N/A")
            message_text = message.text or "[Media/File/Sticker/Other content]"
            message_date = message.date.strftime("%Y-%m-%d %H:%M:%S")
            message_id = message.id

            sender = await message.get_sender()
            sender_name = "Unknown"
            if sender:
                if hasattr(sender, "first_name") and sender.first_name:
                    sender_name = sender.first_name
                    if hasattr(sender, "last_name") and sender.last_name:
                        sender_name += f" {sender.last_name}"
                elif hasattr(sender, "title") and sender.title:
                    sender_name = sender.title
                elif hasattr(sender, "username") and sender.username:
                    sender_name = f"@{sender.username}"

            print("\n" + "=" * 70)
            print("📢 NEW MESSAGE FROM CHANNEL")
            print("=" * 70)
            print(f"Channel: {channel_name}")
            if username and username != "N/A":
                print(f"Username: @{username}")
            print(f"Sender: {sender_name}")
            print(f"Date: {message_date}")
            print(f"Message ID: {message_id}")
            print(f"Text: {message_text}")

            if message.media:
                media_type = type(message.media).__name__
                print(f"Media Type: {media_type}")

                if hasattr(message.media, "document"):
                    doc = message.media.document
                    if hasattr(doc, "attributes"):
                        for attr in doc.attributes:
                            if hasattr(attr, "file_name"):
                                print(f"File Name: {attr.file_name}")
                            elif hasattr(attr, "alt"):
                                print(f"Sticker: {attr.alt}")

            if message.forward:
                print(f"Forwarded from: {getattr(message.forward, 'from_name', 'Unknown')}")

            print("=" * 70)

            if self.ai_processor.enabled:
                print("\n🎯 AI FILTER RESULT:")
                print("-" * 50)
                print(f"Query: {get_current_query()}")
                print("Status: ✅ RELEVANT - Message passed AI filter")
                print("-" * 50)

            print("=" * 70)

            log_text = message_text[:100] + "..." if len(message_text) > 100 else message_text
            try:
                logger.info("New message from %s (@%s): %s", channel_name, username, log_text)
            except UnicodeEncodeError:
                safe_channel_name = channel_name.encode("ascii", "replace").decode("ascii")
                safe_username = (
                    username.encode("ascii", "replace").decode("ascii")
                    if username != "N/A"
                    else username
                )
                safe_log_text = log_text.encode("ascii", "replace").decode("ascii")
                logger.info("New message from %s (@%s): %s", safe_channel_name, safe_username, safe_log_text)

        except Exception as exc:  # pragma: no cover - runtime errors from API
            logger.error("Error processing message details: %s", exc)


    async def get_channel_info(self, channel_username: str) -> None:
        """Get and display information about a channel."""
        try:
            username = channel_username[1:] if channel_username.startswith("@") else channel_username
            channel = await self.client.get_entity(username)

            print(f"\n📊 CHANNEL INFO: @{username}")
            print(f"Title: {getattr(channel, 'title', 'N/A')}")
            print(f"ID: {getattr(channel, 'id', 'N/A')}")
            print(f"Username: @{getattr(channel, 'username', 'N/A')}")
            print(f"Participants: {getattr(channel, 'participants_count', 'N/A')}")

            full_channel = await self.client.get_entity(channel)
            if hasattr(full_channel, "about"):
                print(f"Description: {full_channel.about}")

        except Exception as exc:  # pragma: no cover - network failures etc.
            logger.error("Failed to get channel info for @%s: %s", channel_username, exc)


    async def run_monitor(self) -> None:
        """Run the channel monitor end-to-end. Loads channels from channel store."""
        try:
            await self.start()

            # Validate channels from persistent store
            validated_channels = await self.validate_channels_from_store()
            print(f"\n✅ Successfully loaded {len(validated_channels)} channels from store")
            print(f"📋 Active channels: {validated_channels}")

            if not validated_channels:
                print("❌ No valid channels found in store. Add channels via bot first!")
                print("💡 Use the bot commands: /addchannel <channelname>")
                return

            # Get info for each validated channel
            for channel in validated_channels:
                await self.get_channel_info(channel)
                await asyncio.sleep(0.5)

            self.setup_message_handler()

            print(f"\n👂 Monitoring {len(validated_channels)} channels for new messages...")
            print("Press Ctrl+C to stop monitoring\n")

            try:
                while self.client.is_connected():
                    await asyncio.sleep(1)
            except Exception as exc:  # pragma: no cover - event loop runtime issues
                logger.error("Error in event loop: %s", exc)

        except KeyboardInterrupt:
            print("\n\n🛑 Monitoring stopped by user")
        except Exception as exc:  # pragma: no cover - network failures etc.
            logger.error("Error in monitor: %s", exc)
            raise
        finally:
            if self.client.is_connected():
                await self.client.disconnect()
            logger.info("Telegram client disconnected")