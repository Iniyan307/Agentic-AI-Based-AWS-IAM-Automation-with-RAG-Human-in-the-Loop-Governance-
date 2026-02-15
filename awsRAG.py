from typing import List, Dict, Any, Optional
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv
import numpy as np
from pinecone import Pinecone
import os
from google import genai

load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


# llm calling
def llmout(query, user_guides, tickets):
    content =   f"""Rank the given user guides data and tickets data from the similarity algorithm which will be the most suitable for the given query.
                    Query: {query},
                    User_guides: {user_guides},
                    tickets: {tickets}.
                """

    client = genai.Client(api_key = GOOGLE_API_KEY)
    response = client.models.generate_content(
        model = "gemini-2.5-flash-lite",
        contents = content
    )
    ranking = response.text
    # print(ranking)

    content =   f"""Based on the context: {ranking}
                    Suggest a solution for the query.
                    query: {query}
                """

    response = client.models.generate_content(
        model = "gemini-2.5-flash-lite",
        contents = content
    )
    # print(response.text)

    return response.text


## Approx ~15-20secs for retrival
def retrival_argumented_generation(query):
    embeddings = HuggingFaceEmbeddings(
        model_name = "sentence-transformers/all-mpnet-base-v2",
    )

    q_emb =  embeddings.embed_query(query)
    query_vector = np.array(q_emb, dtype=np.float32).tolist()
    # print(query_vector)

    pc = Pinecone(api_key = f"{PINECONE_API_KEY}")
    pinecone_index = pc.Index("rag")
    user_guide_response = pinecone_index.query(
        vector=query_vector,
        top_k=3,
        namespace="user_guide_docs",
        include_metadata=True,
        include_values=False
    )
    ticket_response = pinecone_index.query(
        vector=query_vector,
        top_k=3,
        namespace="ticket_docs",
        include_metadata=True,
        include_values=False
    )
    # print(user_guide_response["matches"], ticket_response["matches"])

    user_guides=[]
    tickets=[]
    for match in user_guide_response["matches"]:
        user_guides.append(match["metadata"])
    for match in ticket_response["matches"]:
        tickets.append(match["metadata"])

    #Uncomment if running alone for RAG
    # llm_output = llmout(query, user_guides, tickets)

    return user_guides+tickets

# retrival_argumented_generation("Why is AssumeRole failing?")