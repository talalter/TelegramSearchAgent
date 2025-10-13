# Telegram Channel Monitor

A Python application that monitors Telegram channels for new messages using the Telethon API.

## Features

- Connect to Telegram using API credentials
- Monitor multiple public channels simultaneously
- Display new messages in real-time with detailed information
- Log messages to file
- Get channel information and statistics
- Handle media messages and forwards

## Setup

### 1. Prerequisites

- Python 3.7 or higher
- Telegram API credentials (api_id and api_hash)

### 2. Get Telegram API Credentials

1. Go to https://my.telegram.org/auth
2. Log in with your phone number
3. Go to "API Development Tools"
4. Create a new application
5. Copy the `api_id` and `api_hash`

### 3. Configuration

Your `.env` file should contain:
```
api_id=your_api_id_here
api_hash=your_api_hash_here
```

### 4. Installation

The required packages are already installed in your virtual environment:
- telethon
- python-dotenv

## Usage

### Basic Usage

Run the simple monitor:
```powershell
python telegram_monitor_simple.py
```

This will:
1. Connect to Telegram using your credentials
2. Add the default channels to monitoring (durov, telegram)
3. Display channel information
4. Start monitoring for new messages

### Custom Usage

Use the example script for more options:
```powershell
python example_usage.py
```

### Programmatic Usage

```python
import asyncio
from telegram_monitor_simple import TelegramChannelMonitor

async def main():
    # List of channels to monitor (without @ symbol)
    channels = [
        "durov",
        "telegram", 
        "your_channel_here"
    ]
    
    monitor = TelegramChannelMonitor()
    await monitor.run_monitor(channels)

asyncio.run(main())
```

## File Structure

- `telegram_monitor_simple.py` - Main monitoring module
- `example_usage.py` - Usage examples
- `requirements.txt` - Python dependencies
- `.env` - API credentials (keep this secure!)
- `telegram_session.session` - Telegram session file (auto-generated)
- `telegram_monitor.log` - Log file for messages

## Output Example

When a new message is received, you'll see:
```
======================================================================
📢 NEW MESSAGE FROM CHANNEL
======================================================================
Channel: Telegram
Username: @telegram
Sender: Telegram
Date: 2025-10-13 14:30:45
Message ID: 12345
Text: Welcome to Telegram!
Media Type: MessageMediaPhoto
======================================================================
```

## Important Notes

1. **First Run**: On the first run, Telegram will send you a verification code to your phone. Enter it when prompted.

2. **Session File**: The `telegram_session.session` file stores your login session. Keep this file secure and don't delete it unnecessarily.

3. **Rate Limits**: The script includes delays to avoid hitting Telegram's rate limits.

4. **Channel Access**: You can only monitor public channels or channels you're already a member of.

5. **Privacy**: This tool only monitors channels, not private messages.

## Troubleshooting

### Common Issues

1. **"API credentials not found"**
   - Check your `.env` file has the correct `api_id` and `api_hash`

2. **"Channel does not exist"**
   - Make sure the channel username is correct
   - Check if the channel is public

3. **"Channel is private"**
   - You need to join private channels manually first
   - Or use public channels only

4. **Authentication issues**
   - Delete the `telegram_session.session` file and run again
   - Make sure your API credentials are correct

### Logs

Check `telegram_monitor.log` for detailed error messages and debugging information.

## Customization

### Adding More Channels

Edit the `channels_to_monitor` list in the main function:

```python
channels_to_monitor = [
    "durov",
    "telegram",
    "your_channel1",
    "your_channel2",
]
```

### Filtering Messages

You can modify the `process_new_message` method to filter messages based on:
- Keywords
- Sender
- Message type
- Time

### Custom Actions

Extend the `process_new_message` method to:
- Save messages to database
- Send notifications
- Forward to other channels
- Analyze message content

## Security

- Keep your `.env` file secure and never commit it to version control
- The session file contains authentication tokens - keep it safe
- Use this tool responsibly and respect Telegram's Terms of Service

## License

This project is for educational purposes. Make sure to comply with Telegram's API Terms of Service.