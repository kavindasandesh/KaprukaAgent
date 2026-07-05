import os
import re
import httpx
import chainlit as cl
from google import genai
from google.genai import errors
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

# Initialize your Gemini Client (Ensure your real key is set in your environment variables!)
os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", "YOUR_PLACEHOLDER_KEY")
gemini_client = genai.Client()

# System prompt optimized to return structured format for parsing
VISUAL_SYSTEM_PROMPT = (
    "You are a premium, highly helpful shopping assistant for Kapruka Sri Lanka.\n"
    "When displaying a product, you MUST format the details exactly as follows so the interface can render it natively:\n\n"
    "PRODUCT_START\n"
    "Title: [Product Name]\n"
    "Image: [Exact Image URL from tool]\n"
    "Price: [Price]\n"
    "Description: [One sentence description]\n"
    "PRODUCT_END\n\n"
    "If you are replying with conversational text or an error, just type normally without using the PRODUCT blocks."
)


def clean_mcp_schema(schema_dict):
    """Recursively removes boolean values from JSON schemas to prevent SDK crashes."""
    if not isinstance(schema_dict, dict):
        return schema_dict
    cleaned = {}
    for k, v in schema_dict.items():
        if isinstance(v, bool):
            continue
        elif isinstance(v, dict):
            cleaned[k] = clean_mcp_schema(v)
        elif isinstance(v, list):
            cleaned[k] = [clean_mcp_schema(i) for i in v]
        else:
            cleaned[k] = v
    return cleaned


async def render_response(raw_text: str):
    """Parses custom product blocks and renders them using native Chainlit UI elements."""
    if not raw_text:
        return

    # Regex pattern to find product blocks
    product_pattern = re.compile(
        r"PRODUCT_START\s*Title:\s*(.*?)\s*Image:\s*(.*?)\s*Price:\s*(.*?)\s*Description:\s*(.*?)\s*PRODUCT_END",
        re.DOTALL)
    products = product_pattern.findall(raw_text)

    if not products:
        # Standard chat message if no structured products are found
        await cl.Message(content=raw_text).send()
        return

    # Clean up standard text surrounding product blocks if any
    clean_text = product_pattern.sub("", raw_text).strip()
    if clean_text:
        await cl.Message(content=clean_text).send()

    # Download images server-side using httpx to bypass browser security restrictions
    async with httpx.AsyncClient() as client:
        for title, img_url, price, desc in products:
            title = title.strip()
            img_url = img_url.strip()
            price = price.strip()
            desc = desc.strip()

            # Build a beautiful text card layout
            content_markdown = f"### 🎁 {title}\n**Price:** {price}\n\n* {desc}"

            elements = []
            if img_url.startswith("http"):
                try:
                    # Fetch the actual image data bytes behind the scenes
                    response = await client.get(img_url, timeout=10.0)
                    if response.status_code == 200:
                        image_bytes = response.content

                        # Pass raw bytes (content) instead of the blocked URL
                        elements.append(
                            cl.Image(name=title, content=image_bytes, display="inline", size="large")
                        )
                except Exception as e:
                    print(f"Server-side image fetch failed for {title}: {e}")

            await cl.Message(content=content_markdown, elements=elements).send()


@cl.on_message
async def handle_message(message: cl.Message):
    status_message = cl.Message(content="Connecting to Kapruka via secure tunnel...")
    await status_message.send()

    server_params = StdioServerParameters(
        command="npx.cmd",
        args=["-y", "mcp-remote", "https://mcp.kapruka.com/mcp"]
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            kapruka_tools = await session.list_tools()
            for t in kapruka_tools.tools:
                t.inputSchema = clean_mcp_schema(t.inputSchema)

            status_message.content = "Thinking..."
            await status_message.update()

            try:
                response = gemini_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=message.content,
                    config={
                        'tools': kapruka_tools.tools,
                        'system_instruction': VISUAL_SYSTEM_PROMPT
                    }
                )
            except errors.APIError:
                status_message.content = "⚠️ Google's servers are experiencing heavy traffic. Please try again in a moment."
                await status_message.update()
                return

            if response.function_calls:
                for call in response.function_calls:
                    status_message.content = f"🔄 Fetching data from Kapruka using tool: `{call.name}`..."
                    await status_message.update()

                    tool_result = await session.call_tool(call.name, arguments=call.args)

                    try:
                        final_response = gemini_client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=[
                                message.content,
                                response.text if response.text else "",
                                f"Tool Result from {call.name}: {tool_result.content}"
                            ],
                            config={
                                'system_instruction': VISUAL_SYSTEM_PROMPT
                            }
                        )
                        # Remove processing status message and render components natively
                        await status_message.remove()
                        await render_response(final_response.text)
                    except errors.APIError:
                        status_message.content = "⚠️ Google's API limit hit during final compilation. Please retry."
                        await status_message.update()
            else:
                await status_message.remove()
                await render_response(response.text)