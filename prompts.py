# Import the query store to get dynamic queries
from query_store import get_current_query

# Legacy variable - use get_current_query() for dynamic queries
# This is kept for backward compatibility, but prefer get_current_query()
USER_PROMPT = get_current_query()

def get_user_prompt():
    """Get the current user prompt dynamically from the query store."""
    return get_current_query()

SYSTEM_PROMPT = """
You are an expert at analyzing Telegram channel messages. Your task is to identify and extract messages that are related to a user's query.
Given the user's query and a message, determine if the message is relevant to the query.
Respond with "RELEVANT" if the message is related to the query, otherwise respond with "NOT RELEVANT".
The user's query is: {user_query}
The message to analyze is: {message_text}
"""