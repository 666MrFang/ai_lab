from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from rag import (
    Chunk,
    SearchResult,
    build_chunks,
    build_context,
    load_documents,
)


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_KNOWLEDGE_DIR = BASE_DIR / "knowledge"

DEFAULT_MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)


class EmbeddingRetriever:
    def __init__(
        self,
        chunks: List[Chunk],
        model_name: str = DEFAULT_MODEL_NAME,
    ):
        self.chunks = chunks

        print(f"Loading embedding model: {model_name}")

        self.model = SentenceTransformer(model_name)

        self.chunk_texts = [
            self._build_chunk_text(chunk)
            for chunk in chunks
        ]

        print(
            f"Encoding {len(self.chunk_texts)} chunks..."
        )

        self.chunk_embeddings = self.model.encode(
            self.chunk_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    @staticmethod
    def _build_chunk_text(chunk: Chunk) -> str:
        """
        Embedding 时不仅编码 content，
        同时把 heading 放进去。

        heading 本身也是重要语义信息。
        """

        return (
            f"标题：{chunk.heading}\n"
            f"内容：{chunk.content}"
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[SearchResult]:

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than 0"
            )

        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]

        # 因为 embedding 已 normalize：
        #
        # cosine_similarity(a, b)
        # =
        # dot(a, b)
        #
        scores = np.dot(
            self.chunk_embeddings,
            query_embedding,
        )

        ranked_indices = np.argsort(scores)[::-1]

        results: List[SearchResult] = []

        for index in ranked_indices[:top_k]:
            score = float(scores[index])

            results.append(
                SearchResult(
                    score=score,
                    chunk=self.chunks[index],
                )
            )

        return results


def create_retriever(
    knowledge_dir: Path = DEFAULT_KNOWLEDGE_DIR,
    model_name: str = DEFAULT_MODEL_NAME,
) -> EmbeddingRetriever:

    documents = load_documents(
        knowledge_dir
    )

    chunks = build_chunks(
        documents
    )

    return EmbeddingRetriever(
        chunks=chunks,
        model_name=model_name,
    )


def search_knowledge(
    query: str,
    top_k: int = 5,
    knowledge_dir: Path = DEFAULT_KNOWLEDGE_DIR,
    model_name: str = DEFAULT_MODEL_NAME,
) -> dict:

    documents = load_documents(
        knowledge_dir
    )

    chunks = build_chunks(
        documents
    )

    retriever = EmbeddingRetriever(
        chunks=chunks,
        model_name=model_name,
    )

    results = retriever.search(
        query=query,
        top_k=top_k,
    )

    return {
        "retriever": "embedding",
        "model": model_name,
        "query": query,
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "result_count": len(results),

        "results": [
            {
                "score": round(
                    result.score,
                    6,
                ),
                "chunk": asdict(
                    result.chunk
                ),
            }
            for result in results
        ],

        "context": build_context(
            results
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Mini RAG V0.2 "
            "Embedding Retriever"
        )
    )

    parser.add_argument(
        "query",
        help="knowledge retrieval query",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_NAME,
    )

    parser.add_argument(
        "--json",
        action="store_true",
    )

    args = parser.parse_args()

    result = search_knowledge(
        query=args.query,
        top_k=args.top_k,
        model_name=args.model,
    )

    if args.json:
        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print()
    print("Retriever: Embedding")
    print(f'Model: {result["model"]}')
    print(f'Query: {result["query"]}')

    print()
    print(
        f'Documents: '
        f'{result["document_count"]}, '
        f'Chunks: '
        f'{result["chunk_count"]}'
    )

    print()

    for index, item in enumerate(
        result["results"],
        start=1,
    ):
        chunk = item["chunk"]

        print(
            f'[{index}] '
            f'score={item["score"]:.4f} '
            f'document={chunk["document_id"]} '
            f'heading={chunk["heading"]}'
        )

        print(
            chunk["content"]
        )

        print("-" * 70)


if __name__ == "__main__":
    main()