from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Set

from embedding_rag import (
    EmbeddingRetriever,
    DEFAULT_MODEL_NAME,
)
from hybrid_rag import (
    HybridRetriever,
    DEFAULT_RRF_K,
    DEFAULT_CANDIDATE_K,
)
from rag import (
    Chunk,
    SearchResult,
    TfidfRetriever,
    build_chunks,
    load_documents,
)


BASE_DIR = Path(__file__).resolve().parent

DEFAULT_KNOWLEDGE_DIR = (
    BASE_DIR / "knowledge"
)

DEFAULT_EVAL_FILE = (
    BASE_DIR / "eval_cases.json"
)


def semantic_chunk_id(
    chunk: Chunk,
) -> str:

    return (
        f"{chunk.document_id}"
        f"::{chunk.heading}"
    )


def load_eval_cases(
    path: Path,
) -> list[dict]:

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def evaluate_result(
    results: List[SearchResult],
    relevant_chunks: Set[str],
    top_k: int,
) -> dict:

    retrieved_ids = [
        semantic_chunk_id(
            result.chunk
        )
        for result in results[:top_k]
    ]

    retrieved_set = set(
        retrieved_ids
    )

    hits = (
        retrieved_set
        & relevant_chunks
    )

    hit_at_k = (
        1
        if len(hits) > 0
        else 0
    )

    recall_at_k = (
        len(hits)
        / len(relevant_chunks)
        if relevant_chunks
        else 0.0
    )

    precision_at_k = (
        len(hits)
        / len(retrieved_ids)
        if retrieved_ids
        else 0.0
    )

    return {
        "retrieved": retrieved_ids,
        "hits": sorted(hits),
        "hit_at_k": hit_at_k,
        "recall_at_k": recall_at_k,
        "precision_at_k": precision_at_k,
    }


def evaluate_retriever(
    retriever_name: str,
    retriever,
    eval_cases: list[dict],
    top_k: int,
) -> dict:

    case_results = []

    total_hit = 0
    total_recall = 0.0
    total_precision = 0.0

    for case in eval_cases:
        query = case["query"]

        relevant_chunks = set(
            case["relevant_chunks"]
        )

        results = retriever.search(
            query=query,
            top_k=top_k,
        )

        metrics = evaluate_result(
            results=results,
            relevant_chunks=relevant_chunks,
            top_k=top_k,
        )

        total_hit += (
            metrics["hit_at_k"]
        )

        total_recall += (
            metrics["recall_at_k"]
        )

        total_precision += (
            metrics["precision_at_k"]
        )

        case_results.append(
            {
                "id": case["id"],
                "query": query,
                "relevant": sorted(
                    relevant_chunks
                ),
                **metrics,
            }
        )

    count = len(eval_cases)

    return {
        "retriever": retriever_name,
        "top_k": top_k,
        "case_count": count,

        "mean_hit_at_k": (
            total_hit / count
            if count
            else 0.0
        ),

        "mean_recall_at_k": (
            total_recall / count
            if count
            else 0.0
        ),

        "mean_precision_at_k": (
            total_precision / count
            if count
            else 0.0
        ),

        "cases": case_results,
    }


def print_report(
    results: List[dict],
) -> None:

    print()
    print("=" * 90)

    print(
        f'{"Case":<8}'
        f'{"Retriever":<14}'
        f'{"Hit@K":<10}'
        f'{"Recall@K":<12}'
        f'{"Precision@K":<14}'
    )

    print("-" * 90)

    cases_by_retriever = [
        {
            case["id"]: case
            for case in result["cases"]
        }
        for result in results
    ]

    case_ids = list(
        cases_by_retriever[0].keys()
    )

    for case_id in case_ids:
        for result, cases in zip(
            results,
            cases_by_retriever,
        ):
            case = cases[case_id]

            print(
                f'{case_id:<8}'
                f'{result["retriever"]:<14}'
                f'{case["hit_at_k"]:<10}'
                f'{case["recall_at_k"]:<12.3f}'
                f'{case["precision_at_k"]:<14.3f}'
            )

        print("-" * 90)

    print()
    print("Overall")
    print("-" * 90)

    for result in results:
        print(
            f'{result["retriever"]:<12} '
            f'Hit@K='
            f'{result["mean_hit_at_k"]:.3f} '
            f'Recall@K='
            f'{result["mean_recall_at_k"]:.3f} '
            f'Precision@K='
            f'{result["mean_precision_at_k"]:.3f}'
        )

    print("=" * 90)


def print_case_details(
    result: dict,
) -> None:

    print()
    print(
        f'### {result["retriever"]}'
    )

    for case in result["cases"]:
        print()
        print(
            f'{case["id"]}: '
            f'{case["query"]}'
        )

        print("Relevant:")

        for item in case["relevant"]:
            print(
                f"  R  {item}"
            )

        print("Retrieved:")

        hit_set = set(
            case["hits"]
        )

        for item in case["retrieved"]:
            marker = (
                "✓"
                if item in hit_set
                else "✗"
            )

            print(
                f"  {marker}  {item}"
            )


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Compare TF-IDF, Embedding "
            "and Hybrid Retrieval"
        )
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--details",
        action="store_true",
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

    args = parser.parse_args()

    documents = load_documents(
        DEFAULT_KNOWLEDGE_DIR
    )

    chunks = build_chunks(
        documents
    )

    eval_cases = load_eval_cases(
        DEFAULT_EVAL_FILE
    )

    print(
        f"Documents: {len(documents)}"
    )

    print(
        f"Chunks: {len(chunks)}"
    )

    print(
        f"Eval Cases: {len(eval_cases)}"
    )

    print()

    print(
        "Building TF-IDF Retriever..."
    )

    tfidf_retriever = (
        TfidfRetriever(chunks)
    )

    print(
        "Building Embedding Retriever..."
    )

    embedding_retriever = (
        EmbeddingRetriever(
            chunks=chunks,
            model_name=args.model,
        )
    )

    print(
        "Building Hybrid Retriever..."
    )

    hybrid_retriever = (
        HybridRetriever(
            chunks=chunks,
            tfidf_retriever=tfidf_retriever,
            embedding_retriever=embedding_retriever,
            rrf_k=args.rrf_k,
            candidate_k=args.candidate_k,
        )
    )

    results = [
        evaluate_retriever(
            retriever_name="TF-IDF",
            retriever=tfidf_retriever,
            eval_cases=eval_cases,
            top_k=args.top_k,
        ),
        evaluate_retriever(
            retriever_name="Embedding",
            retriever=embedding_retriever,
            eval_cases=eval_cases,
            top_k=args.top_k,
        ),
        evaluate_retriever(
            retriever_name="Hybrid",
            retriever=hybrid_retriever,
            eval_cases=eval_cases,
            top_k=args.top_k,
        ),
    ]

    print_report(results)

    if args.details:
        for result in results:
            print_case_details(
                result
            )


if __name__ == "__main__":
    main()