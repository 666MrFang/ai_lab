from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import List


REPO_ROOT = Path(__file__).resolve().parent.parent

RAG_DIR = REPO_ROOT / "rag"

if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from rag import (  # noqa: E402
    DOCUMENT_TYPE_HISTORICAL_REVIEW,
    DOCUMENT_TYPE_RULE,
    TfidfRetriever,
    build_chunks,
    filter_chunks_by_as_of_date,
    load_documents,
)


FIXTURE_FILES = {
    "2026-09-30-review.md": (
        "# 板块\n"
        "半导体板块表现较强。\n"
    ),
    "2026-10-08-review.md": (
        "# 板块\n"
        "当天复盘生成的板块记录。\n"
    ),
    "2026-10-09-review.md": (
        "# 板块\n"
        "未来的板块记录。\n"
    ),
    "market-rules.md": (
        "# 主线\n"
        "涨幅第一不等于市场主线。\n"
    ),
}


def build_fixture(root: Path) -> None:

    for name, content in FIXTURE_FILES.items():
        (root / name).write_text(
            content,
            encoding="utf-8",
        )


def test_metadata_parsing(root: Path) -> None:

    documents = load_documents(root)

    by_id = {
        document.document_id: document
        for document in documents
    }

    assert (
        by_id["2026-09-30-review"].document_type
        == DOCUMENT_TYPE_HISTORICAL_REVIEW
    ), by_id["2026-09-30-review"]

    assert (
        by_id["2026-09-30-review"].document_date
        == "2026-09-30"
    ), by_id["2026-09-30-review"]

    assert (
        by_id["market-rules"].document_type
        == DOCUMENT_TYPE_RULE
    ), by_id["market-rules"]

    assert (
        by_id["market-rules"].document_date is None
    ), by_id["market-rules"]

    print("[PASS] metadata parsing")


def test_filter_before_retrieval(root: Path) -> None:

    documents = load_documents(root)

    chunks = build_chunks(documents)

    eligible = filter_chunks_by_as_of_date(
        chunks,
        "2026-10-08",
    )

    eligible_ids = {
        chunk.document_id
        for chunk in eligible
    }

    assert eligible_ids == {
        "2026-09-30-review",
        "market-rules",
    }, eligible_ids

    assert "2026-10-08-review" not in eligible_ids

    assert "2026-10-09-review" not in eligible_ids

    print(
        "[PASS] eligible chunk set excludes "
        "current-date and future documents"
    )

    for chunk in eligible:
        if (
            chunk.document_type
            == DOCUMENT_TYPE_HISTORICAL_REVIEW
        ):
            assert (
                chunk.document_date < "2026-10-08"
            ), chunk

    chunk_ids = {
        chunk.chunk_id
        for chunk in eligible
    }

    assert all(
        chunk.document_id not in {
            "2026-10-08-review",
            "2026-10-09-review",
        }
        for chunk in eligible
    ), "future/current date document leaked into eligible chunks"

    assert len(chunk_ids) == len(eligible)

    print(
        "[PASS] strict '<' boundary: "
        "2026-10-08-review excluded"
    )


def test_retrieval_has_no_future_document(
    root: Path,
) -> None:

    documents = load_documents(root)

    chunks = build_chunks(documents)

    eligible = filter_chunks_by_as_of_date(
        chunks,
        "2026-10-08",
    )

    retriever = TfidfRetriever(eligible)

    results = retriever.search(
        query="板块 主线",
        top_k=10,
    )

    for result in results:
        assert result.chunk.document_id in {
            "2026-09-30-review",
            "market-rules",
        }, result.chunk.document_id

    print(
        "[PASS] retrieval results contain no "
        "future/current-date document"
    )


def test_invalid_as_of_date(root: Path) -> None:

    documents = load_documents(root)

    chunks = build_chunks(documents)

    invalid_values: List[str] = [
        "2026/10/08",
        "2026-10-8",
        "20261008",
        "2026-13-01",
        "not-a-date",
        "",
    ]

    for value in invalid_values:
        try:
            filter_chunks_by_as_of_date(
                chunks,
                value,
            )
        except ValueError as exc:
            assert str(exc), value
            continue

        raise AssertionError(
            "expected ValueError for "
            f"as_of_date={value!r}"
        )

    print(
        "[PASS] invalid as_of_date raises ValueError"
    )


def main() -> None:

    with tempfile.TemporaryDirectory() as tmp:

        root = Path(tmp)

        build_fixture(root)

        test_metadata_parsing(root)

        test_filter_before_retrieval(root)

        test_retrieval_has_no_future_document(
            root
        )

        test_invalid_as_of_date(root)

    print()
    print("ALL FUTURE-LEAKAGE TESTS PASSED")


if __name__ == "__main__":
    main()
