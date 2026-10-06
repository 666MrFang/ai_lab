"""Date normalization.

Internal canonical date format is ``YYYY-MM-DD``. Providers use a compact
``YYYYMMDD`` at their boundary (Tushare ``trade_date``, AkShare query params);
conversion happens only at the provider boundary.
"""

from __future__ import annotations

import datetime as _datetime
import re
from datetime import date as _date
from datetime import timedelta

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_COMPACT_RE = re.compile(r"^\d{8}$")


def is_valid_iso_date(value: object) -> bool:
    """Return True only for a real calendar date in ``YYYY-MM-DD`` form."""

    if not isinstance(value, str) or not _ISO_RE.match(value):
        return False
    try:
        _date.fromisoformat(value)
    except ValueError:
        return False
    return True


def normalize_iso_date(value: str) -> str:
    """Validate and return a canonical ``YYYY-MM-DD`` string."""

    if not is_valid_iso_date(value):
        raise ValueError(f"invalid ISO date: {value!r}")
    return value


def to_provider_date(iso_date: str) -> str:
    """``YYYY-MM-DD`` -> ``YYYYMMDD`` (compact provider form)."""

    return iso_date.replace("-", "")


def from_provider_date(compact: object) -> str | None:
    """``YYYYMMDD`` -> ``YYYY-MM-DD``; ``None`` when malformed."""

    if not isinstance(compact, str) or not _COMPACT_RE.match(compact):
        return None
    candidate = f"{compact[0:4]}-{compact[4:6]}-{compact[6:8]}"
    return candidate if is_valid_iso_date(candidate) else None


def shift_calendar_days(iso_date: str, days: int) -> str:
    """Shift a date by calendar days (not trading days)."""

    shifted = _date.fromisoformat(iso_date) + timedelta(days=days)
    return shifted.isoformat()


def coerce_to_iso_date(value: object) -> str | None:
    """Coerce a provider date value to canonical ``YYYY-MM-DD``.

    Handles ``datetime.date`` / ``datetime.datetime`` objects (Sina calendar)
    and ``YYYY-MM-DD`` or ``YYYYMMDD`` strings. Anything else, or an invalid
    calendar date, returns ``None``.
    """

    if isinstance(value, _datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, _datetime.date):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        if is_valid_iso_date(text):
            return text
        return from_provider_date(text)
    return None
