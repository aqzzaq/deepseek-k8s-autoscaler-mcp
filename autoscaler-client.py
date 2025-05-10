import os
import asyncio
from langchain_deepseek import ChatDeepSeek
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent


server_params = StdioServerParameters(command="python", args=["autoscaler-server.py"])

if not os.getenv("DEEPSEEK_API_KEY"):
    os.environ["DEEPSEEK_API_KEY"] = "" # Input Deepseek api key.

llm = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)


async def run(query):
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await load_mcp_tools(session)
            print(f"Available tools: {tools}")
            agent = create_react_agent(llm, tools)
            result = await agent.ainvoke({"messages": [("human", query)]})
            print(result)

if __name__ == "__main__":
    query = "You are a helpful DevOps specialist.\n \
             Choose the appropriate tool based on user's question and execute them.\n \
             If no tool is needed, reply directly and do not call any tool. \n \
             User's question: Monitor and manage the Kuberenetes cluster. Scale the cluster in a cost-effective manner."
    asyncio.run(run(query))