from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, List

from mcp.server import MCPServer


# ============================================================
# Reuse existing Mini RAG code (no RAG re-implementation)
# ============================================================

REPO_ROOT = Path(__file__).resolve().parent.parent

RAG_DIR = REPO_ROOT / "rag"

if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from rag import (  # noqa: E402
    Chunk,
    TfidfRetriever,
    build_chunks,
    filter_chunks_by_as_of_date,
    load_documents,
)


KNOWLEDGE_DIR = RAG_DIR / "knowledge"

DEFAULT_RETRIEVER = "tfidf"

SUPPORTED_RETRIEVERS = (
    "tfidf",
    "embedding",
    "hybrid",
)


# ============================================================
# MCP Server
# ============================================================

mcp = MCPServer("A-Share Knowledge MCP")


def _build_retriever(
    retriever: str,
    chunks: List[Chunk],
):
    """
    在 eligible chunks 上构建 Retriever。

    tfidf 为默认，仅依赖标准库；
    embedding / hybrid 采用惰性 import，
    因此默认路径没有 embedding runtime dependency。
    """

    if retriever == "tfidf":
        return TfidfRetriever(chunks)

    if retriever == "embedding":
        from embedding_rag import (
            EmbeddingRetriever,
        )

        return EmbeddingRetriever(chunks=chunks)

    if retriever == "hybrid":
        from embedding_rag import (
            EmbeddingRetriever,
        )
        from hybrid_rag import HybridRetriever

        return HybridRetriever(
            chunks=chunks,
            tfidf_retriever=TfidfRetriever(chunks),
            embedding_retriever=EmbeddingRetriever(
                chunks=chunks,
            ),
        )

    raise ValueError(
        f"unsupported retriever: {retriever!r}"
    )


# ============================================================
# Tools
# ============================================================

@mcp.tool()
def search_review_knowledge(
    query: str,
    as_of_date: str,
    top_k: int = 5,
    retriever: str = DEFAULT_RETRIEVER,
) -> dict[str, Any]:
    """
    检索历史复盘与市场规则知识库，返回截至某日可用的历史文本上下文。

    适用场景：
        - 检索历史复盘记录（document_type = HISTORICAL_REVIEW）
        - 检索市场规则知识（document_type = RULE）
        - 获取历史上下文，用于比较过去市场状态、板块表现、赚钱效应、
          市场判断的文字记录
        - 为当前复盘提供「历史上是怎么描述的」这类文字 Evidence 素材

    不适用场景（本 Tool 不做这些）：
        - 获取当前实时行情或当日数据（请使用 market MCP）
        - 获取精确历史价格统计或量化指标
        - 计算上涨概率或任何统计概率
        - 获取当前新闻
        - 判断当前 market_regime
        - 判断当前 main theme
        - 判断因果关系
        - 给出看多/看空结论或交易建议

    重要边界：
        如果用户询问「过去 20 次涨停后次日上涨概率」这类需要
        Structured Historical Market Data 的问题，本 Tool 无法回答，
        不应假装回答；应说明这属于未来的 Historical Structured
        Market Data Tool。本 Tool 只返回 Retrieved Historical Context，
        不生成任何结论。

    时间安全（Future Leakage 防护）：
        - as_of_date 必填，格式 YYYY-MM-DD。
        - HISTORICAL_REVIEW 仅当 document_date < as_of_date 时可用（严格小于）：
          复盘 as_of_date 当天的 review 文档通常由当天复盘生成，
          不能作为生成当天复盘的输入。
        - RULE 文档不受日期限制。
        - filtering 在 retrieval ranking 之前执行，
          future chunks 不会进入 candidate 集合。
        - as_of_date 非法时返回 success=false 与明确 error。

    Args:
        query: 检索查询文本，非空字符串。
        as_of_date: 截止日期，格式 YYYY-MM-DD。
        top_k: 返回结果数量上限，正整数，默认 5。
        retriever: 检索器，默认 "tfidf"；
            可选 "tfidf" / "embedding" / "hybrid"。
            当前固定 Eval Set 上 TF-IDF 是最佳 baseline，
            且无 embedding runtime dependency，因此作为默认。
    """

    if (
        not isinstance(query, str)
        or not query.strip()
    ):
        return {
            "success": False,
            "query": query,
            "as_of_date": as_of_date,
            "retriever": retriever,
            "error": "query must be a non-empty string",
        }

    if (
        isinstance(top_k, bool)
        or not isinstance(top_k, int)
        or top_k < 1
    ):
        return {
            "success": False,
            "query": query,
            "as_of_date": as_of_date,
            "retriever": retriever,
            "error": "top_k must be a positive integer",
            "top_k": top_k,
        }

    if retriever not in SUPPORTED_RETRIEVERS:
        return {
            "success": False,
            "query": query,
            "as_of_date": as_of_date,
            "retriever": retriever,
            "error": (
                "retriever must be one of "
                f"{sorted(SUPPORTED_RETRIEVERS)}"
            ),
        }

    documents = load_documents(KNOWLEDGE_DIR)

    chunks = build_chunks(documents)

    try:
        eligible_chunks = filter_chunks_by_as_of_date(
            chunks,
            as_of_date,
        )

    except ValueError as exc:
        return {
            "success": False,
            "query": query,
            "as_of_date": as_of_date,
            "retriever": retriever,
            "error": str(exc),
        }

    try:
        engine = _build_retriever(
            retriever,
            eligible_chunks,
        )

    except ImportError as exc:
        return {
            "success": False,
            "query": query,
            "as_of_date": as_of_date,
            "retriever": retriever,
            "error": (
                f"retriever {retriever!r} is unavailable "
                f"in this environment: {exc}"
            ),
        }

    results = engine.search(
        query=query,
        top_k=top_k,
    )

    return {
        "success": True,
        "query": query,
        "as_of_date": as_of_date,
        "retriever": retriever,
        "eligible_chunk_count": len(eligible_chunks),
        "result_count": len(results),
        "results": [
            {
                "rank": rank,
                "score": round(result.score, 6),
                "chunk_id": result.chunk.chunk_id,
                "document_id": result.chunk.document_id,
                "document_type": result.chunk.document_type,
                "document_date": result.chunk.document_date,
                "source": result.chunk.source,
                "heading": result.chunk.heading,
                "content": result.chunk.content,
            }
            for rank, result in enumerate(
                results,
                start=1,
            )
        ],
    }


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    mcp.run()
