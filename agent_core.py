import os
import asyncio
from google import genai
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

# Initialize your Gemini Client
os.environ["GEMINI_API_KEY"] = "YOUR_ACTUAL_API_KEY_HERE"
gemini_client = genai.Client()


async def run_shopping_agent():
    url = "https://mcp.kapruka.com/sse"

    async with sse_client(url) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()

            # 1. Fetch available tools from Kapruka
            kapruka_tools = await session.list_tools()

            # Try a prompt that requires a tool
            user_message = "Show me some trending items on Kapruka right now."
            print(f"User: {user_message}\n")

            # 2. First turn: Send the message and the available tools to Gemini
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_message,
                config={
                    'tools': kapruka_tools.tools,
                    'system_instruction': "You are an expert shopping assistant for Kapruka Sri Lanka. Format responses cleanly."
                }
            )

            # 3. If Gemini decides to call a tool, execute it!
            if response.function_calls:
                for call in response.function_calls:
                    print(f"🤖 AI called tool: '{call.name}' with args: {call.args}")

                    # Call the actual tool on Kapruka's server using your session
                    tool_result = await session.call_tool(call.name, arguments=call.args)
                    print(f"📦 Live Data fetched from Kapruka!\n")

                    # 4. Second turn: Send the live store data back to Gemini so it can write a friendly reply
                    final_response = gemini_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[
                            user_message,  # The original question
                            response.text if response.text else "",  # Gemini's initial thought
                            f"Tool Result from {call.name}: {tool_result.content}"  # The raw store data
                        ],
                        config={
                            'system_instruction': "You are an expert shopping assistant for Kapruka Sri Lanka. Present the products beautifully with names and prices."
                        }
                    )

                    print(f"Assistant: {final_response.text}")
            else:
                print(f"Assistant: {response.text}")


if __name__ == "__main__":
    asyncio.run(run_shopping_agent())