import streamlit as st
from langgraph.types import Command
from AWSagent import agent   # import your compiled agent

st.set_page_config(page_title="AWS AI Operator", layout="wide")

st.title("🔐 AWS AI Operator")

# Session state
if "thread_id" not in st.session_state:
    st.session_state.thread_id = "streamlit-thread"

if "waiting_for_approval" not in st.session_state:
    st.session_state.waiting_for_approval = False

if "last_state" not in st.session_state:
    st.session_state.last_state = None


user_input = st.chat_input("Enter your AWS request")

config = {"configurable": {"thread_id": st.session_state.thread_id}}

# ================= INITIAL INVOCATION =================
if user_input:
    with st.spinner("Processing..."):
        result = agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config=config
        )

    st.session_state.last_state = result

    # 🔴 CHECK FOR INTERRUPT
    if "__interrupt__" in result:
        st.session_state.waiting_for_approval = True
    else:
        # Show final message
        final_msg = result["messages"][-1]
        st.chat_message("assistant").write(final_msg.content)


# ================= APPROVAL UI =================
if st.session_state.waiting_for_approval:
    with st.chat_message("assistant"):
        st.markdown("⚠️ This is a high-impact production change. Do you approve?")

    approve = st.button("✅ Approve")
    reject = st.button("❌ Reject")

    if approve:
        with st.spinner("Executing action..."):
            resumed = agent.invoke(
                Command(resume={"decision": "approve"}),
                config=config
            )
        st.session_state.waiting_for_approval = False

        for msg in resumed["messages"]:
            if msg.type == "human":
                with st.chat_message("user"):
                    st.markdown(msg.content)

            elif msg.type == "ai":
                with st.chat_message("assistant"):
                    st.markdown(msg.content)

            elif msg.type == "tool":
                with st.chat_message("assistant"):
                    st.markdown(f"🔧 Tool Output:\n\n{msg.content}")

    if reject:
        with st.spinner("Rejecting action..."):
            resumed = agent.invoke(
                Command(resume={"decision": "reject"}),
                config=config
            )
        st.session_state.waiting_for_approval = False

        for msg in resumed["messages"]:
            if msg.type == "human":
                with st.chat_message("user"):
                    st.markdown(msg.content)

            elif msg.type == "ai":
                with st.chat_message("assistant"):
                    st.markdown(msg.content)

            elif msg.type == "tool":
                with st.chat_message("assistant"):
                    st.markdown(f"🔧 Tool Output:\n\n{msg.content}")