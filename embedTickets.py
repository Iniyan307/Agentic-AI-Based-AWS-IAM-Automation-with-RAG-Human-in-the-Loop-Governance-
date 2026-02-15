from langchain_core.documents import Document
from typing import List
import json
from typing import List, Dict, Any, Optional
from langchain_huggingface import HuggingFaceEmbeddings
import numpy as np
from pinecone import Pinecone
import os

from dotenv import load_dotenv
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

def serialize_record(record: Dict[str, Any]) -> str:
    """
    Convert a dict into a readable plain-text block for embedding/search.
    Preserves the keys as anchors for retrieval.
    """
    lines = []
    for key, value in record.items():
        lines.append(f"{key}: {value}")
    return "\n".join(lines)

def to_documents_per_object(records: List[Dict[str, Any]], *, source: str = "tickets.json", extra_metadata: Optional[Dict[str, Any]] = None
) -> List[Document]:
    """
    Create one LangChain Document per JSON object.
    - page_content: serialized text of the object
    - metadata: includes source, page (incremented), plus any fields you want to carry over
    """
    docs: List[Document] = []
    for i, rec in enumerate(records):
        text = serialize_record(rec)

        base_meta = {
            "source": source
        }
        if extra_metadata:
            base_meta.update(extra_metadata)

        # You can also include a few helpful fields from the object itself as metadata:
        # for k in ("configuration_item"):
        if "configuration_item" in rec:
            base_meta["configuration_item"] = rec["configuration_item"]

        docs.append(Document(page_content=text, metadata=base_meta))
    return docs


# Main embedding function
def embedder(file_name):
    with open(f"data/text_files/{file_name}", "r", encoding="utf-8") as f:
        records = json.load(f)
    # print(records)

    #Convert JSON to doc obj
    docs = to_documents_per_object(
        records,
        source=f"{file_name}",
        # You can pass any extra metadata you want applied to all docs:
        extra_metadata=None
    )

    # for doc in docs:
    #     print("CONTENT:   \n", doc.page_content)
    #     print("Metadata:   \n", doc.metadata)
    #     print(f"Length: {len(doc.page_content)}\n\n")
    # print("\n")
    # print(doc)

    print("Sample Doc-----", docs[0])
    # Load HuggingFace Embedding Model
    embeddings = HuggingFaceEmbeddings(
        model_name = "sentence-transformers/all-mpnet-base-v2",
    )

    #Converting the Docs into vectors
    vectors = [
        embeddings.embed_query(doc.page_content)
        for doc in docs
    ]
    # for vector in vectors:  
    #     print(vector)
    print("Sample Vector-----", vectors[0])

    #Adding MetaData and id for storing in VectorDB (Pinecone)
    index = []
    for i in range(len(vectors)):
        index.append({
            "id": f"ticket_doc_{i+1}",
            "values": vectors[i],  # good practice to cast to float32 for storage
            "metadata": {
                "text": docs[i].page_content,
                **docs[i].metadata
            }
        })

    pc = Pinecone(api_key = f"{PINECONE_API_KEY}")
    pinecone_index = pc.Index("rag")
    pinecone_index.upsert(
    vectors=index,
    namespace="ticket_docs"
    )
    print("Inserted Vectors into Pinecone")

# embedder("IAMtickets.json")