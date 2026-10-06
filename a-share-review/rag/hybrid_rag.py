from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

from rag import (
    Chunk,
    SearchResult,
    TfidfRetriever,
    build_chunks,
    build_context,
    load_documents,
)

from embedding_rag import (
    EmbeddingRetriever,
    DEFAULT_MODEL_NAME,
)


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_KNOWLEDGE_DIR = BASE_DIR / "knowledge"

DEFAULT_RRF_K = 60
DEFAULT_CANDIDATE_K = 10


class HybridRetriever:
    """
    TF-IDF + Embedding 的 Hybrid Retriever。

    TF-IDF 与 Embedding 的原始 score 不在同一尺度，
    因此禁止使用：

        alpha * tfidf_score + beta * embedding_score

    本实现只使用 rank-based Reciprocal Rank Fusion：

        rrf_score(chunk) += 1 / (rrf_k + rank)

    rank 从 1 开始。

    合并时使用 Chunk.chunk_id 作为稳定 identity，
    不依赖 Python object identity，也不使用 content 文本。

    candidate_k 处理：
        两个子 Retriever 各取 max(candidate_k, top_k) 个候选。
        当 candidate_k < top_k 时自动提升到 top_k，
        保证最终一定能返回 top_k 个结果（不抛错）。
    """

    def __init__(
        self,
        chunks: List[Chunk],
        tfidf_retriever: TfidfRetriever,
        embedding_retriever: EmbeddingRetriever,
        rrf_k: int = DEFAULT_RRF_K,
        candidate_k: int = DEFAULT_CANDIDATE_K,
    ):
        if rrf_k <= 0:
            raise ValueError("rrf_k must be greater than 0")

        if candidate_k <= 0:
            raise ValueError("candidate_k must be greater than 0")

        self.chunks = chunks

        self.tfidf_retriever = tfidf_retriever
        self.embedding_retriever = embedding_retriever

        self.rrf_k = rrf_k
        self.candidate_k = candidate_k

        self.chunk_by_id: Dict[str, Chunk] = {
            chunk.chunk_id: chunk
            for chunk in chunks
        }

        if len(self.chunk_by_id) != len(chunks):
            raise ValueError(
                "chunk_id is not unique; "
                "cannot be used as identity"
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

        effective_candidate_k = max(
            self.candidate_k,
            top_k,
        )

        tfidf_results = self.tfidf_retriever.search(
            query=query,
            top_k=effective_candidate_k,
        )

        embedding_results = (
            self.embedding_retriever.search(
                query=query,
                top_k=effective_candidate_k,
            )
        )

        rrf_scores: Dict[str, float] = {}

        best_rank: Dict[str, int] = {}

        def fuse(
            results: List[SearchResult],
        ) -> None:

            for rank, result in enumerate(
                results,
                start=1,
            ):
                key = result.chunk.chunk_id

                rrf_scores[key] = (
                    rrf_scores.get(key, 0.0)
                    + 1.0 / (self.rrf_k + rank)
                )

                previous = best_rank.get(key)

                if previous is None or rank < previous:
                    best_rank[key] = rank

        fuse(tfidf_results)

        fuse(embedding_results)

        ranked_keys = sorted(
            rrf_scores.keys(),
            key=lambda key: (
                -rrf_scores[key],
                best_rank[key],
                key,
            ),
        )

        results: List[SearchResult] = []

        for key in ranked_keys[:top_k]:
            results.append(
                SearchResult(
                    score=rrf_scores[key],
                    chunk=self.chunk_by_id[key],
                )
            )

        return results


def create_retriever(
    knowledge_dir: Path = DEFAULT_KNOWLEDGE_DIR,
    model_name: str = DEFAULT_MODEL_NAME,
    rrf_k: int = DEFAULT_RRF_K,
    candidate_k: int = DEFAULT_CANDIDATE_K,
) -> HybridRetriever:

    documents = load_documents(
        knowledge_dir
    )

    chunks = build_chunks(
        documents
    )

    tfidf_retriever = TfidfRetriever(chunks)

    embedding_retriever = EmbeddingRetriever(
        chunks=chunks,
        model_name=model_name,
    )

    return HybridRetriever(
        chunks=chunks,
        tfidf_retriever=tfidf_retriever,
        embedding_retriever=embedding_retriever,
        rrf_k=rrf_k,
        candidate_k=candidate_k,
    )


def search_knowledge(
    query: str,
    top_k: int = 5,
    knowledge_dir: Path = DEFAULT_KNOWLEDGE_DIR,
    model_name: str = DEFAULT_MODEL_NAME,
    rrf_k: int = DEFAULT_RRF_K,
    candidate_k: int = DEFAULT_CANDIDATE_K,
) -> dict:

    documents = load_documents(
        knowledge_dir
    )

    chunks = build_chunks(
        documents
    )

    tfidf_retriever = TfidfRetriever(chunks)

    embedding_retriever = EmbeddingRetriever(
        chunks=chunks,
        model_name=model_name,
    )

    retriever = HybridRetriever(
        chunks=chunks,
        tfidf_retriever=tfidf_retriever,
        embedding_retriever=embedding_retriever,
        rrf_k=rrf_k,
        candidate_k=candidate_k,
    )

    results = retriever.search(
        query=query,
        top_k=top_k,
    )

    return {
        "retriever": "Hybrid RRF",
        "model": model_name,
        "query": query,
        "rrf_k": rrf_k,
        "candidate_k": candidate_k,
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
            "Mini RAG V0.3 "
            "Hybrid Retriever (RRF)"
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
        "--rrf-k",
        type=int,
        default=DEFAULT_RRF_K,
    )

    parser.add_argument(
        "--candidate-k",
        type=int,
        default=DEFAULT_CANDIDATE_K,
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
        rrf_k=args.rrf_k,
        candidate_k=args.candidate_k,
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
    print("Retriever: Hybrid RRF")
    print(f'Model: {result["model"]}')
    print(f'Query: {result["query"]}')
    print(f'RRF k: {result["rrf_k"]}')
    print(f'Candidate k: {result["candidate_k"]}')

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
            f'rank={index} '
            f'rrf_score={item["score"]:.6f} '
            f'document={chunk["document_id"]} '
            f'heading={chunk["heading"]}'
        )

        print(
            chunk["content"]
        )

        print("-" * 70)


if __name__ == "__main__":
    main()
