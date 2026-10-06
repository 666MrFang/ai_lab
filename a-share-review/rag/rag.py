from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Tuple


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_KNOWLEDGE_DIR = BASE_DIR / "knowledge"

DOCUMENT_TYPE_HISTORICAL_REVIEW = "HISTORICAL_REVIEW"
DOCUMENT_TYPE_RULE = "RULE"
DOCUMENT_TYPE_UNKNOWN = "UNKNOWN"

REVIEW_FILENAME_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2})-review$"
)

RULE_DOCUMENT_IDS = frozenset({"market-rules"})

AS_OF_DATE_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}$"
)


@dataclass
class Document:
    document_id: str
    source: str
    content: str
    document_type: str = DOCUMENT_TYPE_UNKNOWN
    document_date: Optional[str] = None


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    source: str
    heading: str
    content: str
    document_type: str = DOCUMENT_TYPE_UNKNOWN
    document_date: Optional[str] = None


@dataclass
class SearchResult:
    score: float
    chunk: Chunk


def classify_document(
    document_id: str,
) -> Tuple[str, Optional[str]]:
    """
    仅依据文件名解析 metadata，
    不依赖正文中的自然语言日期。

    - YYYY-MM-DD-review -> HISTORICAL_REVIEW + 该日期
    - market-rules      -> RULE + None
    - 其他              -> UNKNOWN + None
    """

    match = REVIEW_FILENAME_PATTERN.match(
        document_id
    )

    if match:
        return (
            DOCUMENT_TYPE_HISTORICAL_REVIEW,
            match.group(1),
        )

    if document_id in RULE_DOCUMENT_IDS:
        return DOCUMENT_TYPE_RULE, None

    return DOCUMENT_TYPE_UNKNOWN, None


def load_documents(knowledge_dir: Path) -> List[Document]:
    documents: List[Document] = []

    for path in sorted(knowledge_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")

        (
            document_type,
            document_date,
        ) = classify_document(path.stem)

        documents.append(
            Document(
                document_id=path.stem,
                source=str(path),
                content=content,
                document_type=document_type,
                document_date=document_date,
            )
        )

    return documents


def split_markdown_document(document: Document) -> List[Chunk]:
    """
    V0.1:
    按 Markdown 标题切 Chunk。

    不使用固定 token 长度，
    目的是先理解 Chunk 的语义边界。
    """

    lines = document.content.splitlines()

    chunks: List[Chunk] = []

    current_heading = "Document"
    current_lines: List[str] = []

    chunk_index = 0

    def flush():
        nonlocal chunk_index
        nonlocal current_lines

        text = "\n".join(current_lines).strip()

        if not text:
            current_lines = []
            return

        chunk_id = f"{document.document_id}::chunk-{chunk_index}"

        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                document_id=document.document_id,
                source=document.source,
                heading=current_heading,
                content=text,
                document_type=document.document_type,
                document_date=document.document_date,
            )
        )

        chunk_index += 1
        current_lines = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("#"):
            flush()

            heading = stripped.lstrip("#").strip()

            if heading:
                current_heading = heading

            continue

        current_lines.append(line)

    flush()

    return chunks


def build_chunks(documents: List[Document]) -> List[Chunk]:
    chunks: List[Chunk] = []

    for document in documents:
        chunks.extend(split_markdown_document(document))

    return chunks


def parse_as_of_date(value: str) -> date:
    """
    严格解析 as_of_date 为 YYYY-MM-DD。

    非法格式或非法日历日期时抛出明确的 ValueError。
    """

    if (
        not isinstance(value, str)
        or not AS_OF_DATE_PATTERN.match(value.strip())
    ):
        raise ValueError(
            "as_of_date must be a string in "
            "YYYY-MM-DD format"
        )

    try:
        return datetime.strptime(
            value.strip(),
            "%Y-%m-%d",
        ).date()

    except ValueError as exc:
        raise ValueError(
            f"invalid as_of_date: {value!r}; "
            "expected a valid YYYY-MM-DD date"
        ) from exc


def filter_chunks_by_as_of_date(
    chunks: List[Chunk],
    as_of_date: str,
) -> List[Chunk]:
    """
    在 retrieval ranking 之前做 temporal filtering。

    规则（strict，不使用 <=）：

    - RULE：始终 eligible，不受日期限制。
    - HISTORICAL_REVIEW：仅当 document_date < as_of_date。
    - UNKNOWN：fail-closed，过滤模式下排除。

    原因：复盘 2026-10-08 时，
    2026-10-08-review.md 通常是当天复盘生成结果，
    不能作为生成 2026-10-08 复盘的输入，
    因此必须使用严格小于。
    """

    as_of = parse_as_of_date(as_of_date)

    eligible: List[Chunk] = []

    for chunk in chunks:

        if (
            chunk.document_type
            == DOCUMENT_TYPE_RULE
        ):
            eligible.append(chunk)
            continue

        if (
            chunk.document_type
            == DOCUMENT_TYPE_HISTORICAL_REVIEW
        ):
            if not chunk.document_date:
                continue

            document_date = datetime.strptime(
                chunk.document_date,
                "%Y-%m-%d",
            ).date()

            if document_date < as_of:
                eligible.append(chunk)

            continue

    return eligible


def tokenize(text: str) -> List[str]:
    """
    一个故意保持简单的 tokenizer。

    英文：
        提取 word token。

    中文：
        V0.1 使用连续中文字符的 unigram + bigram。

    这不是生产级中文分词。
    """

    text = text.lower()

    tokens: List[str] = []

    english_words = re.findall(r"[a-z0-9_]+", text)

    tokens.extend(english_words)

    chinese_groups = re.findall(r"[\u4e00-\u9fff]+", text)

    for group in chinese_groups:
        chars = list(group)

        tokens.extend(chars)

        for i in range(len(chars) - 1):
            tokens.append(chars[i] + chars[i + 1])

    return tokens


class TfidfRetriever:
    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks

        self.chunk_term_freq: List[Counter] = []

        self.document_frequency: Counter = Counter()

        self._build_index()

    def _build_index(self) -> None:
        for chunk in self.chunks:
            searchable_text = (
                chunk.heading
                + "\n"
                + chunk.content
            )

            tokens = tokenize(searchable_text)

            tf = Counter(tokens)

            self.chunk_term_freq.append(tf)

            for token in tf.keys():
                self.document_frequency[token] += 1

    def _idf(self, token: str) -> float:
        total = len(self.chunks)

        df = self.document_frequency.get(token, 0)

        return math.log(
            (total + 1) / (df + 1)
        ) + 1.0

    def _vector(self, tf: Counter) -> dict[str, float]:
        vector: dict[str, float] = {}

        for token, count in tf.items():
            vector[token] = (
                (1.0 + math.log(count))
                * self._idf(token)
            )

        return vector

    @staticmethod
    def _cosine_similarity(
        left: dict[str, float],
        right: dict[str, float],
    ) -> float:

        common_tokens = (
            set(left.keys())
            & set(right.keys())
        )

        dot = sum(
            left[token] * right[token]
            for token in common_tokens
        )

        left_norm = math.sqrt(
            sum(value * value for value in left.values())
        )

        right_norm = math.sqrt(
            sum(value * value for value in right.values())
        )

        if left_norm == 0 or right_norm == 0:
            return 0.0

        return dot / (left_norm * right_norm)

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[SearchResult]:

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        query_tf = Counter(tokenize(query))
        query_vector = self._vector(query_tf)

        results: List[SearchResult] = []

        for chunk, chunk_tf in zip(
            self.chunks,
            self.chunk_term_freq,
        ):
            chunk_vector = self._vector(chunk_tf)

            score = self._cosine_similarity(
                query_vector,
                chunk_vector,
            )

            if score <= 0:
                continue

            results.append(
                SearchResult(
                    score=score,
                    chunk=chunk,
                )
            )

        results.sort(
            key=lambda item: item.score,
            reverse=True,
        )

        return results[:top_k]


def build_context(
    results: List[SearchResult],
) -> str:

    context_blocks: List[str] = []

    for index, result in enumerate(results, start=1):
        block = f"""
[CONTEXT-{index}]

source:
{result.chunk.source}

document_id:
{result.chunk.document_id}

heading:
{result.chunk.heading}

retrieval_score:
{result.score:.4f}

content:
{result.chunk.content}
""".strip()

        context_blocks.append(block)

    return "\n\n".join(context_blocks)


def search_knowledge(
    query: str,
    top_k: int = 5,
    knowledge_dir: Path = DEFAULT_KNOWLEDGE_DIR,
) -> dict:

    documents = load_documents(knowledge_dir)

    chunks = build_chunks(documents)

    retriever = TfidfRetriever(chunks)

    results = retriever.search(
        query=query,
        top_k=top_k,
    )

    return {
        "query": query,
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "result_count": len(results),
        "results": [
            {
                "score": round(result.score, 6),
                "chunk": asdict(result.chunk),
            }
            for result in results
        ],
        "context": build_context(results),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mini RAG V0.1 for A-Share review"
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
        "--json",
        action="store_true",
        help="print full JSON result",
    )

    args = parser.parse_args()

    result = search_knowledge(
        query=args.query,
        top_k=args.top_k,
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

    print("Query:")
    print(result["query"])

    print()
    print(
        f'Documents: {result["document_count"]}, '
        f'Chunks: {result["chunk_count"]}'
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

        print(chunk["content"])

        print("-" * 70)


if __name__ == "__main__":
    main()