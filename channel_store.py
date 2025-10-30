"""Store and manage the list of channels to monitor."""
import json
import os
from typing import List, Set

CHANNELS_FILE = "monitored_channels.json"

def _load_channels() -> Set[str]:
    """Load channels from the JSON file."""
    try:
        if os.path.exists(CHANNELS_FILE):
            with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data.get('channels', _get_default_channels()))
    except Exception:
        pass
    return set(_get_default_channels())

def _save_channels(channels: Set[str]) -> bool:
    """Save channels to the JSON file."""
    try:
        with open(CHANNELS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'channels': sorted(list(channels))}, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def _get_default_channels() -> List[str]:
    """Get the default channels if none are set."""
    return ["TestsTal"]

def get_monitored_channels() -> List[str]:
    """Get the current list of monitored channels."""
    channels = _load_channels()
    return sorted(list(channels))

def add_channel(channel: str) -> bool:
    """Add a channel to monitor. Returns True if added, False if already exists."""
    channels = _load_channels()
    if channel in channels:
        return False
    channels.add(channel)
    return _save_channels(channels)

def remove_channel(channel: str) -> bool:
    """Remove a channel from monitoring. Returns True if removed, False if not found."""
    channels = _load_channels()
    try:
        channels.remove(channel)
        return _save_channels(channels)
    except KeyError:
        return False