import asyncio
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession


async def test_kapruka_connection():
    # The public Kapruka MCP endpoint
    url = "https://mcp.kapruka.com/sse"

    print(f"Connecting to {url}...")

    # 1. Open the SSE pipeline to the server
    async with sse_client(url) as streams:
        # 2. Start a session using the read/write streams
        async with ClientSession(streams[0], streams[1]) as session:
            # 3. Perform the mandatory MCP handshake
            await session.initialize()
            print("Connection successful! \n")

            # 4. Ask the server for its list of tools
            response = await session.list_tools()

            print("--- Available Kapruka Tools ---")
            for tool in response.tools:
                print(f"🔹 {tool.name}")
                print(f"   Description: {tool.description}\n")


# Run the asynchronous function
if __name__ == "__main__":
    asyncio.run(test_kapruka_connection())