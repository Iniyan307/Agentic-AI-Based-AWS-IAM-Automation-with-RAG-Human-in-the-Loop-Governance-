# from langchain_community.chat_models import ChatOllama
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

llm = ChatOllama(
    model="qwen2.5:3b",
    # model = "phi3:mini",
    temperature=0
)

response = llm.invoke([
    HumanMessage(content="Explain AWS IAM policy evaluation logic.")
])

print(response.content)