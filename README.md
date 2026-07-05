# 🛍️ Kapruka AI Shopping Assistant

An intelligent, context-aware personal shopping agent built for the **Kapruka Agent Challenge 2026**. This application connects directly to Kapruka's live Model Context Protocol (MCP) server to help users discover, filter, and view products in a highly visual and conversational interface.

## ✨ Key Features

* **🧠 Context-Aware Memory:** The agent remembers previous turns in the conversation. You can ask for a list of items, and then say "I want the second one," and the AI understands exactly what you mean.
* **🖼️ Unblocked Server-Side Rendering:** Bypasses browser CORS restrictions by securely fetching Kapruka product images server-side via `httpx` and injecting the raw bytes directly into the Chainlit UI.
* **⚡ Dynamic UI Layouts:** Intelligently groups multiple search results into clean text lists to avoid clutter, and only renders rich, large-format image cards when a user isolates a specific product.
* **🎨 Custom Branding:** Features a fully branded dark-mode UI with official Kapruka styling and custom welcome screens.

## 🛠️ Tech Stack

* **Frontend/Framework:** [Chainlit](https://docs.chainlit.io/)
* **AI Model:** Google Gemini 2.5 Flash
* **Database/Tools:** Kapruka Public MCP (`mcp.kapruka.com`)
* **Core Libraries:** `google-genai`, `mcp`, `httpx`
