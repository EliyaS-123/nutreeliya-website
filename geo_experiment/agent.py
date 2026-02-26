"""Interactive LangChain agent with Azure OpenAI (via LiteLLM) + Tavily web search.

Uses LangGraph's create_react_agent for a tool-calling loop that
searches the web and synthesises answers.  The LLM backend is routed
through LiteLLM so every provider is a single config change.
"""

from langchain_openai import AzureChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.prebuilt import create_react_agent

from geo_experiment.config import (
    AZURE_API_BASE,
    AZURE_API_KEY,
    AZURE_API_VERSION,
    AZURE_DEPLOYMENT_NAME,
)

SYSTEM_PROMPT = (
    "You are a research assistant powered by web search. "
    "Your role is to help users find and synthesize information from the web.\n\n"
    "When answering questions:\n"
    "1. Search the web for relevant and recent information\n"
    "2. Synthesize information from multiple sources\n"
    "3. Always cite your sources with their URLs\n"
    "4. Provide comprehensive, well-structured answers\n"
    "5. Be transparent about the limitations of the information found"
)


def create_geo_agent(verbose: bool = False):
    """Build a LangGraph react agent backed by Azure OpenAI + Tavily.

    Parameters
    ----------
    verbose : bool
        Currently unused; reserved for future debug logging.
    """
    llm = AzureChatOpenAI(
        azure_deployment=AZURE_DEPLOYMENT_NAME,
        azure_endpoint=AZURE_API_BASE,
        api_key=AZURE_API_KEY,
        api_version=AZURE_API_VERSION,
    )

    search_tool = TavilySearch(max_results=10)
    tools = [search_tool]

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )
    return agent


def chat(agent, query: str) -> str:
    """Send a single query to the agent and return the final response text."""
    result = agent.invoke({"messages": [{"role": "user", "content": query}]})
    return result["messages"][-1].content
