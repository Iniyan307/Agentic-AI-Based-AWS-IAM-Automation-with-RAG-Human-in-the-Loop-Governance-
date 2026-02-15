from langgraph.graph import StateGraph, MessagesState, START, END
from langchain.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from typing import Literal
from langchain.tools import tool
from dotenv import load_dotenv
import os
from awsRAG import retrival_argumented_generation
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from prompts import RAG_planner_prompt1, RAG_agent_prompt1, OPERATOR_agent_prompt1, FINAL_reponse_prompt1
from langgraph.types import Command, interrupt

load_dotenv()



# ================= MODEL =================
try:
    # model = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
# gemini-2.5-flash-lite, gemini-2.5-flash, gemini-2.5-pro , gemini-3-flash, gemini-2.0-flash
    model = ChatOllama(model="qwen2.5:7b", temperature=0)
    # qwen2.5:3b, qwen2.5:7b, llama3.2:3b

except Exception as e:
    raise ValueError(f"❌ Failed to initialize Gemini LLM: {e}")

# ================= TOOLS =================

@tool
def RAG(query: str) -> str:
    """ 
        Get similar documents from the vector store
        Args:
            query: str
    """
    docs = retrival_argumented_generation(query)

    # Ensure output is always plain string
    if isinstance(docs, list):
        if isinstance(docs[0], dict) and "text" in docs[0]:
            return "\n".join(d["text"] for d in docs)
        return "\n".join(str(d) for d in docs)

    return str(docs)

@tool
def AWSTool(service: str, configuration_item: str, action: str, reversible: bool, highImpact: bool ) -> str:
    """
        Take action based on the AWS service and configuration item
        Args: 
            service: str (AWS services like IAM, lambda, S3)
            configuration_item: str 
            action: str 
            Reversible: bool 
            HighImpact: bool 
    """
    print("Reversible, HighImpact: ", reversible, highImpact)

    # Irreversible block
    if not reversible:
        return (
            f"❌ Action '{action}' NOT executed.\n"
            f"Reason: Action is irreversible."
        )

    if highImpact:
        response = interrupt({"action": "high_impact"})
        if response.get("decision") != "approve":
            return (
                f"❌ Action '{action}' was NOT executed.\n"
                f"Reason: High impact action rejected by human."
            )

    return (
        f"✅ Action '{action}' executed for "
        f"Service '{service}' on CI '{configuration_item}'."
    )

rag_model = model.bind_tools([RAG])
operator_model = model.bind_tools([AWSTool])

tools_by_name = {
    "RAG": RAG,
    "AWSTool": AWSTool
}

def append_if_valid(state, response):
    if response.content or response.tool_calls:
        return {"messages": state["messages"] + [response]}
    return {"messages": state["messages"]}

# ================= TOOL NODE =================

def rag_tool_node(state: MessagesState):
    last = state["messages"][-1]
    results = []

    for tool_call in last.tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])

        if isinstance(observation, list):
            observation = str(observation)

        results.append(
            ToolMessage(
                content=str(observation),
                tool_call_id=tool_call["id"]
            )
        )

    return {"messages": state["messages"] + results}

def operator_tool_node(state: MessagesState):
    last = state["messages"][-1]
    results = []

    for tool_call in last.tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])

        if isinstance(observation, list):
            observation = str(observation)

        results.append(
            ToolMessage(
                content=str(observation),
                tool_call_id=tool_call["id"]
            )
        )

    return {"messages": state["messages"] + results}

# ================= NODES =================

# 1. RAG Planner (must call RAG)
def rag_planner(state: MessagesState):
    system_prompt = SystemMessage(content=RAG_planner_prompt1)
    response = rag_model.invoke([system_prompt] + state["messages"])
    return append_if_valid(state, response)

# 2. Rerank Agent
def rerank_agent(state: MessagesState):
    system_prompt = SystemMessage(content=RAG_agent_prompt1)

    response = model.invoke([system_prompt] + state["messages"])
    return append_if_valid(state, response)

# 3. Operator Agent (must call AWStool)
def operator_agent(state: MessagesState):
    system_prompt = SystemMessage(content=OPERATOR_agent_prompt1)

    response = operator_model.invoke([system_prompt] + state["messages"])
    return append_if_valid(state, response)

# 4. Final Response Agent
def final_response(state: MessagesState):
    system_prompt = SystemMessage(content=FINAL_reponse_prompt1)
    response = model.invoke([system_prompt] + state["messages"])
    return append_if_valid(state, response)

# ================= ROUTING =================

def should_call_rag_tool(state: MessagesState) -> Literal["rag_tool_node", "rerank_agent"]:
    last = state["messages"][-1]

    if getattr(last, "tool_calls", None):
        return "rag_tool_node"

    return "rerank_agent"


def should_call_operator_tool(state: MessagesState) -> Literal["operator_tool_node", "final_response"]:
    last = state["messages"][-1]

    if getattr(last, "tool_calls", None):
        return "operator_tool_node"

    return "final_response"

# ================= GRAPH =================

graph = StateGraph(MessagesState)

graph.add_node("rag_planner", rag_planner)
graph.add_node("rerank_agent", rerank_agent)
graph.add_node("operator_agent", operator_agent)
graph.add_node("rag_tool_node", rag_tool_node)
graph.add_node("operator_tool_node", operator_tool_node)
graph.add_node("final_response", final_response)

graph.add_edge(START, "rag_planner")

# RAG phase
graph.add_conditional_edges(
    "rag_planner",
    should_call_rag_tool,
    ["rag_tool_node", "rerank_agent"]
)

graph.add_edge("rag_tool_node", "rerank_agent")

# Diagnosis → operator
graph.add_edge("rerank_agent", "operator_agent")

# Operator phase
graph.add_conditional_edges(
    "operator_agent",
    should_call_operator_tool,
    ["operator_tool_node", "final_response"]
)

graph.add_edge("operator_tool_node", "final_response")

graph.add_edge("final_response", END)

# checkpointer = MemorySaver()
# agent = graph.compile(checkpointer=checkpointer)

from functools import lru_cache
@lru_cache
def get_agent():
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)

agent = get_agent()

# ================= TEST =================

# messages = [
#     HumanMessage(content="Users are getting AccessDenied when trying to assume an IAM role from EC2. The error mentions sts:AssumeRole. How do I fix this?")
# ]

# messages = [
#     HumanMessage(content="We no longer need the IAM role Finance-Prod-Access. Permanently delete this role and all attached policies.")
# ]

# ============================= Without streamlit =======================

# config = {"configurable": {"thread_id": "12345"}}
# messages = [
#     HumanMessage(content="Remove the AdministratorAccess policy from the IAM role Prod-Admin-Role.")
# ]
# initial = agent.invoke({"messages": messages}, config=config)

# resumed = agent.invoke(
#     Command(resume={"decision": "approve"}),
#     config=config,
# )

# for m in resumed["messages"]:
#     if getattr(m, "content", None) or getattr(m, "tool_calls", None):
#         m.pretty_print()

# ==============================================================================



# ================== TEST CASES =========================

# 1. Reversible = True, HighImpact = False
# Attach the policy AmazonS3ReadOnlyAccess to IAM role Dev-App-Role.

# 2. Reversible = True, HighImpact = True 
# Remove the AdministratorAccess policy from IAM role Prod-Admin-Role.

# 3. Reversible = False, HighImpact = False
# Permanently delete IAM user contractor-temp-user.

# 4. Reversible = False, HighImpact = True
# Permanently delete IAM role Prod-App-Role used by production EC2 instances.

# ==============================================================

