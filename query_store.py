"""Store and manage the user's search query."""
import json
import os
from typing import Optional

QUERY_FILE = "user_query.json"

def get_current_query() -> str:
    """Get the current user query."""
    try:
        if os.path.exists(QUERY_FILE):
            with open(QUERY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('query', get_default_query())
    except Exception:
        pass
    return get_default_query()

def set_current_query(query: str) -> bool:
    """Set the current user query. Returns True if successful."""
    try:
        with open(QUERY_FILE, 'w', encoding='utf-8') as f:
            json.dump({'query': query}, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def get_default_query() -> str:
    """Get the default query if none is set."""
    return "Find all messages that have words on it."