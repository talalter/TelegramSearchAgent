"""Store and manage the list of channels to monitor."""
from typing import List, Set

# Store channels in memory (you could extend this to use a file or database)
_monitored_channels: Set[str] = set([
    "TestsTal",
    "Gaza Now - בעברית 🇮🇱",
    "אבו עלי אקספרס", 
    "הרגע הזמנתי", 
])

def get_monitored_channels() -> List[str]:
    """Get the current list of monitored channels."""
    return sorted(list(_monitored_channels))

def add_channel(channel: str) -> bool:
    """Add a channel to monitor. Returns True if added, False if already exists."""
    if channel in _monitored_channels:
        return False
    _monitored_channels.add(channel)
    return True

def remove_channel(channel: str) -> bool:
    """Remove a channel from monitoring. Returns True if removed, False if not found."""
    try:
        _monitored_channels.remove(channel)
        return True
    except KeyError:
        return False