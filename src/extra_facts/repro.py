from __future__ import annotations

import os
from datetime import UTC, datetime

_FALLBACK_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)


def deterministic_utc_datetime() -> datetime:
    """Return a reproducible UTC datetime for generated artifact metadata."""
    source_date_epoch = os.getenv("SOURCE_DATE_EPOCH", "").strip()
    if source_date_epoch:
        try:
            return datetime.fromtimestamp(int(source_date_epoch), tz=UTC)
        except ValueError:
            pass
    return _FALLBACK_EPOCH
