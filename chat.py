import os
from google import genai

import os
api_key = os.environ.get("GEMINI_API_KEY", "YOUR_PLACEHOLDER_KEY")
client = genai.Client()

# 1. Define a regular Python function
def get_item_price(item_name: str) -> str:
    """Get the price of an item in our store."""
    if "shirt" in item_name.lower():
        return "2500 LKR"
    return "Price not found"

# 2. Tell Gemini it is allowed to use this function
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents='How much is that blue shirt?',
    config={'tools': [get_item_price]} # This passes your function as a tool
)

# Gemini will notice the word "shirt", realize it has a tool for it,
# and ask your code to execute get_item_price(item_name="blue shirt")
print(response.function_calls)