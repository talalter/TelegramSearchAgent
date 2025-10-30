"""Command-line utilities for running the Telegram monitor."""

import asyncio
import os
from typing import List, Sequence

from prompts import SYSTEM_PROMPT, USER_PROMPT

from ai import LANGCHAIN_AVAILABLE
from config import get_logger
from monitor import TelegramChannelMonitor

logger = get_logger(__name__)


def _get_channels_to_monitor() -> List[str]:
    """Return the list of channels to monitor from the channel store."""
    from channel_store import get_monitored_channels
    return get_monitored_channels()


def _print_ai_status() -> None:
    """Display the status of AI integrations for the CLI."""
    if LANGCHAIN_AVAILABLE:
        mistral_key = os.getenv("MISTRAL_API_KEY")
        if mistral_key:
            print("✅ LangChain + Mistral AI integration enabled")
        else:
            print("⚠️  Mistral API key not found - AI analysis disabled")
            print("   Add MISTRAL_API_KEY to your .env file to enable AI features")
    else:
        print("⚠️  LangChain not installed - AI analysis disabled")
        print("   Install with: pip install langchain-mistralai langchain-core")


async def run_monitor() -> None:
    """Run the interactive monitor with optional channel overrides."""
    
    channels_to_monitor = _get_channels_to_monitor()
    print(f'channels_to_monitor: {channels_to_monitor} ')
    print("🤖 Telegram Channel Monitor with AI Filtering")
    print("=" * 60)
    print("This bot will monitor Telegram channels and filter")
    print("messages using Mistral AI for relevance to your query.")
    print(f"🎯 Current Query: {USER_PROMPT}")
    print()

    _print_ai_status()
    print()

    monitor = TelegramChannelMonitor()
    await monitor.run_monitor()


async def main() -> None:
    """Entry point for the CLI script."""
    await run_monitor()


def run() -> None:
    """Synchronous wrapper that executes the CLI."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as exc:
        logger.error("Error running monitor: %s", exc)
        print(f"Error: {exc}")