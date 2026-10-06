import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deepseek_agent import _decode_review_content


def test_decode_exact_json():
    assert _decode_review_content('{"date":"2026-09-30"}')["date"] == "2026-09-30"


def test_decode_single_json_markdown_fence():
    assert _decode_review_content('```json\n{"date":"2026-09-30"}\n```')["date"] == "2026-09-30"


def test_decode_prose_wrapped_single_object():
    value = _decode_review_content('Result follows:\n{"date":"2026-09-30"}')
    assert value["date"] == "2026-09-30"


def test_reject_trailing_prose_after_object():
    with pytest.raises(json.JSONDecodeError):
        _decode_review_content('{"date":"2026-09-30"} extra')


def test_reject_non_object_root():
    with pytest.raises(ValueError):
        _decode_review_content('[]')
