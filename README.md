# 🚀 Agentic AI-Based AWS IAM Automation with RAG & Human-in-the-Loop Governance

An AI-powered AWS automation system that combines **Retrieval-Augmented Generation (RAG)**, **tool-integrated agents**, and **human-in-the-loop approval workflows** to safely automate AWS IAM troubleshooting and remediation actions.

---

## 📌 Overview

This project implements a production-style **Agentic AI system** that:

- Retrieves contextual knowledge from AWS IAM documentation using RAG
- Decides remediation steps using LLM-based reasoning
- Classifies actions as reversible / irreversible and high / low impact
- Enforces approval gating for high-impact production actions
- Maintains persistent conversational state and audit-ready execution flow

The system is designed to simulate enterprise-grade cloud change management automation.

---

## 🧠 Architecture

User (Streamlit UI) -> LangGraph Agent -> RAG (Vector DB + Metadata Filtering) -> AWS Action Tool -> High-Impact Detection -> Interrupt -> Human Approval -> Resume Execution

---

## ⚙️ Core Components

- **LLM-based Agent** for reasoning and decision-making  
- **RAG pipeline** over AWS IAM User Guides  
- **Hybrid retrieval** (vector similarity + metadata filtering)  
- **Tool-integrated AWS action execution layer**  
- **Human-in-the-loop approval system using LangGraph interrupts**  
- **Persistent state management via checkpointing**

---

## 🛠 Tech Stack

- Python  
- LangGraph  
- LangChain  
- Vector Database (for embeddings storage)  
- Streamlit  

---

## 🔄 Human-in-the-Loop Workflow

1. User submits AWS-related query.
2. Agent retrieves relevant IAM documentation via RAG.
3. Agent determines required AWS action.
4. Tool classifies action:
   - Reversible
   - High Impact
5. If High Impact:
   - Execution pauses using `interrupt()`
   - User approval is requested from UI
   - Workflow resumes only after approval
6. Action is executed or safely rejected.

This ensures **production-safe automation with governance controls**.

---

## Screenshots

<img width="1919" height="925" alt="image" src="https://github.com/user-attachments/assets/19a114c4-cb23-4c38-836f-2151ef55e59b" />

<img width="1919" height="927" alt="image" src="https://github.com/user-attachments/assets/9ef9cab5-96ea-498e-850b-3ce56160d917" />

<img width="1919" height="924" alt="image" src="https://github.com/user-attachments/assets/4365f981-f53d-45fd-954a-8cf0a8a98f28" />

<img width="1918" height="922" alt="image" src="https://github.com/user-attachments/assets/0315e02a-7016-4be2-866d-9d55c792cf39" />



