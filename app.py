import os
import re
import httpx
import chainlit as cl
from google import genai
from google.genai import errors
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

# Load the API key from environment variables safely
os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", "YOUR_PLACEHOLDER_KEY")

VISUAL_SYSTEM_PROMPT = (
    "You are a premium, highly helpful shopping assistant for Kapruka Sri Lanka.\n"
    "You have a perfect memory of this conversation. If a user refers to 'the 2nd item' or 'that cake', look back at your previous responses to see what it was.\n\n"
    "When presenting product search results, you MUST format each item exactly like this so the UI can parse it:\n"
    "PRODUCT_START\n"
    "Title: [Product Name]\n"
    "Image: [Exact Image URL from tool]\n"
    "Price: [Price]\n"
    "Description: [One sentence description]\n"
    "PRODUCT_END\n\n"
    "For standard chat conversation, placing orders, or collecting details, speak completely normally without using the PRODUCT blocks."
)


def clean_mcp_schema(schema_dict):
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
    if not raw_text:
        return

    product_pattern = re.compile(
        r"PRODUCT_START\s*Title:\s*(.*?)\s*Image:\s*(.*?)\s*Price:\s*(.*?)\s*Description:\s*(.*?)\s*PRODUCT_END",
        re.DOTALL)
    products = product_pattern.findall(raw_text)

    if not products:
        await cl.Message(content=raw_text).send()
        return

    clean_text = product_pattern.sub("", raw_text).strip()

    # Case 1: Multiple products found (Search results list)
    if len(products) > 1:
        list_content = clean_text + "\n\n" if clean_text else ""
        for i, (title, img_url, price, desc) in enumerate(products, 1):
            list_content += f"{i}. **{title.strip()}** — {price.strip()}\n   *{desc.strip()}*\n\n"

        await cl.Message(content=list_content.strip()).send()
        return

    # Case 2: Exactly ONE product isolated
    if len(products) == 1:
        title, img_url, price, desc = products[0]
        title = title.strip()
        img_url = img_url.strip()
        price = price.strip()
        desc = desc.strip()

        content_markdown = f"{clean_text}\n\n### 🎁 {title}\n**Price:** {price}\n\n* {desc}" if clean_text else f"### 🎁 {title}\n**Price:** {price}\n\n* {desc}"
        elements = []
        image_rendered_via_element = False

        if img_url.startswith("http"):
            async with httpx.AsyncClient() as client:
                try:
                    # Increased timeout to 15 seconds for slower cloud routing environments
                    response = await client.get(img_url, timeout=15.0)
                    if response.status_code == 200:
                        elements.append(
                            cl.Image(name=title, content=response.content, display="inline", size="large")
                        )
                        image_rendered_via_element = True
                except Exception as e:
                    print(f"Server-side image fetch failed: {e}. Falling back to standard markdown formatting.")

        # Fallback: If server-side download fails or times out, embed a standard markdown image link
        if not image_rendered_via_element and img_url.startswith("http"):
            content_markdown += f"\n\n![{title}]({img_url})"

        await cl.Message(content=content_markdown.strip(), elements=elements).send()


@cl.on_chat_start
async def start():
    cl.user_session.set("history", [])


@cl.on_message
async def handle_message(message: cl.Message):
    gemini_client = genai.Client()

    history = cl.user_session.get("history", [])
    history.append(f"User: {message.content}")

    status_message = cl.Message(content="Connecting to Kapruka database...")
    await status_message.send()

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "mcp-remote", "https://mcp.kapruka.com/mcp"]
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            kapruka_tools = await session.list_tools()
            for t in kapruka_tools.tools:
                t.inputSchema = clean_mcp_schema(t.inputSchema)

            status_message.content = "Analyzing request history..."
            await status_message.update()

            prompt_context = "\n".join(history)

            try:
                response = gemini_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt_context,
                    config={
                        'tools': kapruka_tools.tools,
                        'system_instruction': VISUAL_SYSTEM_PROMPT
                    }
                )
            except errors.APIError:
                status_message.content = "⚠️ Server busy. Please try sending that again."
                await status_message.update()
                return

            final_text = ""
            if response.function_calls:
                for call in response.function_calls:
                    status_message.content = f"🔄 Executing Kapruka system lookups..."
                    await status_message.update()

                    tool_result = await session.call_tool(call.name, arguments=call.args)

                    try:
                        final_response = gemini_client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=[
                                prompt_context,
                                response.text if response.text else "",
                                f"System Tool Feedback ({call.name}): {tool_result.content}"
                            ],
                            config={'system_instruction': VISUAL_SYSTEM_PROMPT}
                        )
                        final_text = final_response.text
                    except errors.APIError:
                        status_message.content = "⚠️ Compilation failed. Please retry."
                        await status_message.update()
                        return
            else:
                final_text = response.text

            await status_message.remove()
            await render_response(final_text)

            if final_text:
                history.append(f"Assistant: {final_text}")
                cl.user_session.set("history", history)