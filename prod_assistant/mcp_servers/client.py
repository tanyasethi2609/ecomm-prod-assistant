import asyncio
import os
import sys
from langchain_mcp_adapters.client import MultiServerMCPClient

PROJECT_ROOT = r"C:\Users\ARSHPARAM\ecomm-prod-assisstant"
SERVER_PATH = r"C:\Users\ARSHPARAM\ecomm-prod-assisstant\prod_assistant\mcp_servers\product_search_server.py"

async def main():
    client = MultiServerMCPClient({
        "hybrid_search": {
            "transport": "stdio",
            "command": sys.executable,          # use the SAME python as your venv
            "args": ["-u", SERVER_PATH],        # unbuffered stdio
            "cwd": PROJECT_ROOT,                # so .env/YAML relative loads work
            "env": os.environ.copy(),           # workaround for env inheritance bug
        }
    })

    tools = await client.get_tools()
    print("Available tools:", [t.name for t in tools])

    # Pick tools by name
    retriever_tool = next(t for t in tools if t.name == "get_product_info")
    web_tool = next(t for t in tools if t.name == "web_search")

    # --- Step 1: Try retriever first ---
    query = "Cooker price"
    # query = "iPhone 15"
    # query = "iPhone 17?"
    retriever_result = await retriever_tool.ainvoke({"query": query})
    print("\nRetriever Result:\n", retriever_result)

    # --- Step 2: Fallback to web search if retriever fails ---
    if not retriever_result.strip() or "No local results found." in retriever_result:
        print("\n No local results, falling back to web search...\n")
        web_result = await web_tool.ainvoke({"query": query})
        print("Web Search Result:\n", web_result)


if __name__ == "__main__":
    asyncio.run(main())
