from langchain_core.documents import Document
from typing import List, Dict, Any, Optional
from langchain_huggingface import HuggingFaceEmbeddings
import fitz  # PyMuPDF
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
import numpy as np
from pinecone import Pinecone
import os

load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

# --------------------------------------------------
# PDF SECTION CHUNKER
# --------------------------------------------------
class PDFSectionChunker:
    def __init__(
        self,
        chunk_size=1000,
        chunk_overlap=150,
        heading_min_size=14,
        heading_max_size=18,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.heading_min_size = heading_min_size
        self.heading_max_size = heading_max_size

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". "]
        )

    def _flush_buffer(self, text: str, metadata: dict, documents: List[Document]):
        """Split buffered text and attach metadata to every chunk"""
        for chunk in self.splitter.split_text(text):
            header = ""

            if metadata.get("section"):
                header += f"Section: {metadata['section']}\n"
            if metadata.get("subsection"):
                header += f"Subsection: {metadata['subsection']}\n"

            if header:
                header += "\n"

            documents.append(
                Document(
                    page_content=header + chunk,
                    metadata=metadata.copy()
                )
            )

    def process_pdf(self, pdf_path: str) -> List[Document]:
        doc = fitz.open(pdf_path)

        pages = []
        all_heading_sizes = set()

        # --------------------------------------------------
        # 1️⃣ Extract headings + text blocks
        # --------------------------------------------------
        for page_no, page in enumerate(doc, 1):
            headings = []
            blocks = []

            for block in page.get_text("dict")["blocks"]:
                if "lines" not in block:
                    continue

                block_text = []
                block_y = block["bbox"][1]

                for line in block["lines"]:
                    line_text = " ".join(
                        span["text"] for span in line["spans"]
                    ).strip()

                    if not line_text:
                        continue

                    sizes = [round(span["size"]) for span in line["spans"]]
                    max_size = max(sizes)

                    if self.heading_min_size <= max_size <= self.heading_max_size:
                        headings.append({
                            "text": line_text,
                            "size": max_size,
                            "y": line["bbox"][1]
                        })
                        all_heading_sizes.add(max_size)
                    else:
                        block_text.append(line_text)

                if block_text:
                    blocks.append({
                        "text": " ".join(block_text),
                        "y": block_y
                    })

            pages.append({
                "page": page_no,
                "headings": sorted(headings, key=lambda x: x["y"]),
                "blocks": sorted(blocks, key=lambda x: x["y"])
            })

        # --------------------------------------------------
        # 2️⃣ Detect heading hierarchy
        # --------------------------------------------------
        sizes = sorted(all_heading_sizes, reverse=True)
        h1_size = sizes[0] if len(sizes) > 0 else None
        h2_size = sizes[1] if len(sizes) > 1 else None

        # print("Detected heading sizes:", {"H1": h1_size, "H2": h2_size})

        # --------------------------------------------------
        # 3️⃣ Section-aware chunking
        # --------------------------------------------------
        documents = []
        current_h1, current_h2 = None, None
        section_buffer = ""

        for page in pages:
            heads = page["headings"]
            blocks = page["blocks"]
            head_idx = 0

            for block in blocks:
                # Update section on heading transition
                while head_idx < len(heads) and heads[head_idx]["y"] < block["y"]:
                    if section_buffer.strip():
                        self._flush_buffer(
                            section_buffer,
                            {
                                "page": page["page"],
                                "section": current_h1,
                                "subsection": current_h2,
                                "source": pdf_path
                            },
                            documents
                        )
                        section_buffer = ""

                    h = heads[head_idx]
                    if h["size"] == h1_size:
                        current_h1 = h["text"]
                        current_h2 = None
                    elif h["size"] == h2_size:
                        current_h2 = h["text"]

                    head_idx += 1

                # Always keep metadata updated
                section_meta = {
                    "page": page["page"],
                    "section": current_h1,
                    "subsection": current_h2,
                    "source": pdf_path
                }

                section_buffer += block["text"] + "\n\n"

                if len(section_buffer) >= self.chunk_size:
                    self._flush_buffer(section_buffer, section_meta, documents)
                    section_buffer = ""

        # Flush remaining text
        if section_buffer.strip():
            self._flush_buffer(
                section_buffer,
                {
                    "page": page["page"],
                    "section": current_h1,
                    "subsection": current_h2,
                    "source": pdf_path
                },
                documents
            )

        return documents
    
def clean_metadata(metadata: dict) -> dict:
    return {k: v for k, v in metadata.items() if v is not None}


# MAIN Embedding Function
# --------------------------------------------------
def embedder(file_path):

    chunker = PDFSectionChunker(
        chunk_size=1000,
        chunk_overlap=150
    )

    docs = chunker.process_pdf(f"data\pdf\{file_path}")

    print("Total chunks:", len(docs))
    # print("Sample document:\n", docs[0])
    # print("Sample metadata:\n", docs[0].metadata)

    # EMBEDDINGS
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-mpnet-base-v2"
    )

    vectors = [
        embeddings.embed_query(doc.page_content)
        for doc in docs
    ]
    # for vector in vectors:  
    #     print(vector)
    # print("Sample Vector-----", vectors[0])

    # # --------------------------------------------------
    # # PINECONE-READY VECTORS
    # # --------------------------------------------------

    index = []
    for i, doc in enumerate(docs):
        metadata = {
            "text": doc.page_content,
            **doc.metadata
        }
        # remove None values
        metadata = clean_metadata(metadata)

        index.append({
            "id": f"user_guide_doc_{i+1}",
            "values": vectors[i],  # must be List[float], NOT string
            "metadata": metadata
        })

    # print("Sample records:\n", index[0:3])

    pc = Pinecone(api_key = f"{PINECONE_API_KEY}")
    pinecone_index = pc.Index("rag")
    pinecone_index.upsert(
    vectors=index,
    namespace="user_guide_docs"
    )
    print("Inserted Vectors into Pinecone")

embedder("AWSiamUserGuide_modified.pdf")