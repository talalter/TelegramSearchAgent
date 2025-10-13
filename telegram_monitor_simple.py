"""
Telegram Channel Monitor
A simple module that connects to Telegram using Telethon API and monitors messages from channels.
"""

import os
import asyncio
import logging
import sys
from datetime import datetime
from typing import List, Set, Optional
from dotenv import load_dotenv
from telethon import TelegramClient, events

from prompts import USER_PROMPT, SYSTEM_PROMPT

# LangChain imports
try:
    from langchain_mistralai import ChatMistralAI
    from langchain_core.messages import HumanMessage
    from langchain_core.prompts import ChatPromptTemplate
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("LangChain not installed. AI processing will be disabled.")

# Load environment variables
load_dotenv()

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MistralAIProcessor:
    """
    A class to process messages using Mistral AI API via LangChain.
    """
    
    def __init__(self, api_key: Optional[str] = None, custom_prompt: Optional[str] = None):
        """Initialize the Mistral AI processor."""
        if not LANGCHAIN_AVAILABLE:
            logger.warning("LangChain not installed. AI processing will be disabled.")
            self.enabled = False
            return
            
        self.api_key = api_key or os.getenv('MISTRAL_API_KEY')
        if not self.api_key:
            logger.warning("Mistral API key not found. AI processing will be disabled.")
            self.enabled = False
            return
        
        self.enabled = True
        
        # Initialize LangChain Mistral AI model
        try:
            self.llm = ChatMistralAI(
                api_key=self.api_key,
                model="mistral-tiny",  # You can change to mistral-small or mistral-medium
                temperature=0.7,
                max_tokens=500
            )
            
            # Default prompt template if none provided
            default_prompt = """You are an intelligent message analyzer. Analyze the following Telegram message and provide insights:

Message Details:
Channel: {channel_name}
Sender: {sender_name}
Date: {message_date}
Text: {message_text}

Please provide:
1. A brief summary
2. Key topics or themes
3. Sentiment analysis
4. Any important entities mentioned
5. Overall assessment

Keep your response concise and informative."""

            self.prompt_template = ChatPromptTemplate.from_template(
                custom_prompt or default_prompt
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize Mistral AI model: {e}")
            self.enabled = False
    
    async def process_message(self, message_data: dict) -> Optional[str]:
        """
        Process a message using Mistral AI via LangChain.
        
        Args:
            message_data: Dictionary containing message information
        
        Returns:
            AI analysis result or None if processing fails
        """
        if not self.enabled:
            return None
        
        try:
            # Create the chain
            chain = self.prompt_template | self.llm
            
            # Invoke the chain with message data
            response = await chain.ainvoke(message_data)
            
            return response.content
                    
        except Exception as e:
            logger.error(f"Error processing message with Mistral AI: {e}")
            return None
    
    async def is_message_relevant(self, message_text: str, user_query: str) -> bool:
        """
        Check if a message is relevant to the user's query using LLM.
        
        Args:
            message_text: The message content to analyze
            user_query: The user's search query
        
        Returns:
            True if message is relevant, False otherwise
        """
        if not self.enabled:
            return True  # If AI is disabled, show all messages
        
        try:
            # Create a simple prompt template for relevance checking
            relevance_prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPT)
            
            # Create the chain
            chain = relevance_prompt | self.llm
            
            # Invoke the chain with the query and message
            response = await chain.ainvoke({
                "user_query": user_query,
                "message_text": message_text
            })
            
            # Parse the response to check if message is relevant
            response_text = str(response.content) if hasattr(response, 'content') else str(response)
            response_text = response_text.strip().upper()
            
            # Log the LLM response for debugging
            logger.info(f"LLM relevance response: {response_text}")
            
            # Return True only if the response starts with "RELEVANT" but not with "NOT RELEVANT"
            if response_text.startswith("NOT RELEVANT"):
                return False
            elif response_text.startswith("RELEVANT"):
                return True
            else:
                # If response doesn't match expected format, log it and default to True
                logger.warning(f"Unexpected LLM response format: {response_text}")
                return True
                    
        except Exception as e:
            logger.error(f"Error checking message relevance: {e}")
            return True  # Default to showing message if error occurs


class TelegramChannelMonitor:
    """
    A class to monitor Telegram channels for new messages.
    """
    
    def __init__(self, mistral_api_key: Optional[str] = None, custom_prompt: Optional[str] = None):
        """Initialize the Telegram client with API credentials from .env file."""
        self.api_id = os.getenv('api_id')
        self.api_hash = os.getenv('api_hash')
        
        if not self.api_id or not self.api_hash:
            raise ValueError("API credentials not found in .env file")
        
        # Initialize Telegram client
        self.client = TelegramClient('telegram_session', int(self.api_id), self.api_hash)
        self.monitored_channels: Set[int] = set()
        
        # Initialize Mistral AI processor
        self.ai_processor = MistralAIProcessor(mistral_api_key, custom_prompt)
        
        # Store user info for forwarding messages
        self.user_entity = None
        
    async def start(self):
        """Start the Telegram client and authenticate."""
        try:
            # Connect to Telegram
            await self.client.connect()
            
            # Check if we're already authorized
            if not await self.client.is_user_authorized():
                print("First time login - you'll need to enter your phone number and verification code")
                phone = input("Enter your phone number: ")
                await self.client.send_code_request(phone)
                code = input("Enter the verification code: ")
                await self.client.sign_in(phone, code)
            
            logger.info("Successfully connected to Telegram")
            
            # Get current user info
            me = await self.client.get_me()
            self.user_entity = me  # Store for message forwarding
            if hasattr(me, 'first_name'):
                username = getattr(me, 'username', 'N/A')
                logger.info(f"Logged in as: {me.first_name} (@{username})")
            else:
                logger.info("Successfully logged in")
            
        except Exception as e:
            logger.error(f"Failed to start Telegram client: {e}")
            raise
    
    async def forward_message_to_self(self, message, source_chat_name: str) -> bool:
        """
        Forward a relevant message to the user's own Telegram account.
        
        Args:
            message: The Telegram message object to forward
            source_chat_name: Name of the source channel for context
        
        Returns:
            bool: True if forwarding succeeded, False otherwise
        """
        if not self.user_entity:
            logger.error("User entity not available for message forwarding")
            return False
        
        try:
            # Create a context message
            # context_text = f"🎯 RELEVANT MESSAGE from {source_chat_name}\nQuery: {USER_PROMPT}\n\n--- Original Message ---"
            
            # Send context message first
            # await self.client.send_message(self.user_entity, context_text)
            
            # Forward the actual message
            await self.client.forward_messages(
                entity=self.user_entity,
                messages=message,
                from_peer=message.peer_id
            )
            
            logger.info(f"Successfully forwarded message to self from {source_chat_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to forward message to self: {e}")
            return False
    
    async def add_channel_to_monitor(self, channel_username: str) -> bool:
        """
        Add a channel to monitoring list.
        
        Args:
            channel_username: Channel username (with or without @)
        
        Returns:
            bool: True if successfully added, False otherwise
        """
        try:
            # Remove @ if present
            if channel_username.startswith('@'):
                channel_username = channel_username[1:]
            
            # Get the channel entity
            channel = await self.client.get_entity(channel_username)
            
            # Add to monitored channels
            self.monitored_channels.add(channel.id)
            logger.info(f"Successfully added channel to monitoring: @{channel_username} (ID: {channel.id})")
            return True
                
        except Exception as e:
            logger.error(f"Failed to add channel @{channel_username} to monitoring: {e}")
            return False
    
    async def add_channels_to_monitor(self, channel_list: List[str]) -> List[str]:
        """
        Add multiple channels to monitoring.
        
        Args:
            channel_list: List of channel usernames
        
        Returns:
            List of successfully added channels
        """
        added_channels = []
        
        for channel in channel_list:
            if await self.add_channel_to_monitor(channel):
                added_channels.append(channel)
                # Add a small delay to avoid rate limiting
                await asyncio.sleep(0.5)
        
        return added_channels
    
    def setup_message_handler(self):
        """Set up event handler for new messages."""
        
        @self.client.on(events.NewMessage())
        async def message_handler(event):
            """Handle new messages from monitored channels."""
            try:
                # Get message details
                message = event.message
                chat = await event.get_chat()
                
                # Debug logging
                chat_name = getattr(chat, 'title', getattr(chat, 'username', 'Unknown'))
                try:
                    logger.info(f"Received message from chat: '{chat_name}' (ID: {getattr(chat, 'id', 'Unknown')})")
                except UnicodeEncodeError:
                    safe_chat_name = str(chat_name).encode('ascii', 'replace').decode('ascii')
                    logger.info(f"Received message from chat: '{safe_chat_name}' (ID: {getattr(chat, 'id', 'Unknown')})")
                logger.info(f"Monitored channels: {self.monitored_channels}")
                
                # Only process messages from channels we're monitoring
                if hasattr(chat, 'id') and chat.id in self.monitored_channels:
                    logger.info(f"Processing message from monitored channel: {chat.id}")
                    
                    # Extract message text for relevance checking
                    message_text = message.text or ''
                    if not message_text:
                        message_text = '[Non-text content]'
                    
                    # Check if message is relevant using AI
                    is_relevant = await self.ai_processor.is_message_relevant(message_text, USER_PROMPT)
                    
                    if is_relevant:
                        logger.info(f"Message is relevant to query, processing...")
                        await self.process_new_message(message, chat)
                        
                        # Forward the relevant message to self
                        forwarded = await self.forward_message_to_self(message, chat_name)
                        if forwarded:
                            print("📤 Message forwarded to your Telegram account!")
                        else:
                            print("❌ Failed to forward message to your account")
                    else:
                        logger.info(f"Message not relevant to query, skipping...")
                else:
                    logger.info(f"Ignoring message from unmonitored chat: {getattr(chat, 'id', 'Unknown')}")
                    
            except Exception as e:
                logger.error(f"Error processing message: {e}")
    
    async def process_new_message(self, message, chat):
        """
        Process and print new messages from monitored channels.
        
        Args:
            message: The Telegram message object
            chat: The chat/channel object
        """
        try:
            # Extract message information
            channel_name = getattr(chat, 'title', 'Unknown Channel')
            username = getattr(chat, 'username', 'N/A')
            message_text = message.text or '[Media/File/Sticker/Other content]'
            message_date = message.date.strftime('%Y-%m-%d %H:%M:%S')
            message_id = message.id
            
            # Sender information
            sender = await message.get_sender()
            sender_name = 'Unknown'
            if sender:
                if hasattr(sender, 'first_name') and sender.first_name:
                    sender_name = sender.first_name
                    if hasattr(sender, 'last_name') and sender.last_name:
                        sender_name += f" {sender.last_name}"
                elif hasattr(sender, 'title') and sender.title:
                    sender_name = sender.title
                elif hasattr(sender, 'username') and sender.username:
                    sender_name = f"@{sender.username}"
            
            # Print message details
            print("\n" + "="*70)
            print(f"📢 NEW MESSAGE FROM CHANNEL")
            print("="*70)
            print(f"Channel: {channel_name}")
            if username and username != 'N/A':
                print(f"Username: @{username}")
            print(f"Sender: {sender_name}")
            print(f"Date: {message_date}")
            print(f"Message ID: {message_id}")
            print(f"Text: {message_text}")
            
            # Check for media
            if message.media:
                media_type = type(message.media).__name__
                print(f"Media Type: {media_type}")
                
                # Try to get media info
                if hasattr(message.media, 'document'):
                    doc = message.media.document
                    if hasattr(doc, 'attributes'):
                        for attr in doc.attributes:
                            if hasattr(attr, 'file_name'):
                                print(f"File Name: {attr.file_name}")
                            elif hasattr(attr, 'alt'):
                                print(f"Sticker: {attr.alt}")
            
            # Check for forward information
            if message.forward:
                print(f"Forwarded from: {getattr(message.forward, 'from_name', 'Unknown')}")
            
            print("="*70)
            
            # Show that this message passed the AI relevance filter
            if self.ai_processor.enabled:
                print(f"\n🎯 AI FILTER RESULT:")
                print("-" * 50)
                print(f"Query: {USER_PROMPT}")
                print(f"Status: ✅ RELEVANT - Message passed AI filter")
                print("-" * 50)
            
            print("="*70)
            
            # Log the message (truncated for log file)
            log_text = message_text[:100] + "..." if len(message_text) > 100 else message_text
            try:
                logger.info(f"New message from {channel_name} (@{username}): {log_text}")
            except UnicodeEncodeError:
                # Fallback for console encoding issues
                safe_channel_name = channel_name.encode('ascii', 'replace').decode('ascii')
                safe_username = username.encode('ascii', 'replace').decode('ascii') if username != 'N/A' else username
                safe_log_text = log_text.encode('ascii', 'replace').decode('ascii')
                logger.info(f"New message from {safe_channel_name} (@{safe_username}): {safe_log_text}")
            
        except Exception as e:
            logger.error(f"Error processing message details: {e}")
    
    async def get_channel_info(self, channel_username: str):
        """
        Get and display information about a channel.
        
        Args:
            channel_username: Channel username
        """
        try:
            if channel_username.startswith('@'):
                channel_username = channel_username[1:]
            
            channel = await self.client.get_entity(channel_username)
            
            print(f"\n📊 CHANNEL INFO: @{channel_username}")
            print(f"Title: {getattr(channel, 'title', 'N/A')}")
            print(f"ID: {getattr(channel, 'id', 'N/A')}")
            print(f"Username: @{getattr(channel, 'username', 'N/A')}")
            print(f"Participants: {getattr(channel, 'participants_count', 'N/A')}")
            
            # Get full channel info for description
            full_channel = await self.client.get_entity(channel)
            if hasattr(full_channel, 'about'):
                print(f"Description: {full_channel.about}")
                
        except Exception as e:
            logger.error(f"Failed to get channel info for @{channel_username}: {e}")
    
    async def run_monitor(self, channels: List[str]):
        """
        Main method to run the channel monitor.
        
        Args:
            channels: List of channel usernames to monitor
        """
        try:
            # Start the client
            await self.start()
            
            # Add channels to monitoring
            print(f"\n🔗 Adding {len(channels)} channels to monitoring...")
            added = await self.add_channels_to_monitor(channels)
            print(f"✅ Successfully added {len(added)} channels to monitoring")
            
            if not added:
                print("❌ No channels added to monitoring. Exiting...")
                return
            
            # Display channel info
            for channel in added:
                await self.get_channel_info(channel)
                await asyncio.sleep(0.5)
            
            # Set up message handler
            self.setup_message_handler()
            
            print(f"\n👂 Monitoring {len(added)} channels for new messages...")
            print("Press Ctrl+C to stop monitoring\n")
            
            # Keep the client running to receive messages
            try:
                # Use the non-awaitable version in an async context
                while self.client.is_connected():
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error in event loop: {e}")
            
        except KeyboardInterrupt:
            print("\n\n🛑 Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Error in monitor: {e}")
            raise
        finally:
            if self.client.is_connected():
                await self.client.disconnect()
            logger.info("Telegram client disconnected")


async def main():
    """Main function to run the Telegram channel monitor."""
    # Example channel list - modify as needed
    channels_to_monitor = [
        "TestChannelTalGayBatahat",  # Example channel
        # Add more channels here
        # "python_telegram_bot_updates",
        # "telethon_updates",
    ]
    
    # Custom AI prompt (optional)
    custom_ai_prompt = SYSTEM_PROMPT
    
    print("🤖 Telegram Channel Monitor with AI Filtering")
    print("=" * 60)
    print("This bot will monitor Telegram channels and filter")
    print("messages using Mistral AI for relevance to your query.")
    print(f"🎯 Current Query: {USER_PROMPT}")
    print()
    
    # Check dependencies and API key
    if LANGCHAIN_AVAILABLE:
        mistral_key = os.getenv('MISTRAL_API_KEY')
        if mistral_key:
            print("✅ LangChain + Mistral AI integration enabled")
        else:
            print("⚠️  Mistral API key not found - AI analysis disabled")
            print("   Add MISTRAL_API_KEY to your .env file to enable AI features")
    else:
        print("⚠️  LangChain not installed - AI analysis disabled")
        print("   Install with: pip install langchain-mistralai langchain-core")
    
    print()
    
    monitor = TelegramChannelMonitor(custom_prompt=custom_ai_prompt)
    await monitor.run_monitor(channels_to_monitor)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")