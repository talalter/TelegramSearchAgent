"""
Example usage script for the Telegram Channel Monitor
"""

import asyncio
from telegram_monitor_simple import TelegramChannelMonitor


async def monitor_specific_channels():
    """Example: Monitor specific channels."""
    channels = [
        "durov",          # Pavel Durov's official channel
        "telegram",       # Telegram official updates
        "tginfo",         # Telegram Info channel (if exists)
    ]
    
    monitor = TelegramChannelMonitor()
    await monitor.run_monitor(channels)


async def get_channel_info_example():
    """Example: Get information about channels before monitoring."""
    monitor = TelegramChannelMonitor()
    await monitor.start()
    
    channels_to_check = ["durov", "telegram"]
    
    print("Getting channel information...")
    for channel in channels_to_check:
        await monitor.get_channel_info(channel)
        await asyncio.sleep(1)
    
    await monitor.client.disconnect()


if __name__ == "__main__":
    print("Choose an option:")
    print("1. Monitor channels for new messages")
    print("2. Get channel information only")
    
    choice = input("Enter your choice (1 or 2): ").strip()
    
    if choice == "1":
        asyncio.run(monitor_specific_channels())
    elif choice == "2":
        asyncio.run(get_channel_info_example())
    else:
        print("Invalid choice. Please run the script again.")