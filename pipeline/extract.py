"""Extract: download exchange rates from the NBP public API and save the raw JSON."""
import json
import logging
import time
from datetime import timedelta
from pathlib import Path

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://api.nbp.pl/api/exchangerates/rates/a/{code}/{start}/{end}/"
MAX_DAYS = 367  # the API allows at most 367 days per request
RAW_DIR = Path("data/raw")


def date_chunks(start, end, max_days=MAX_DAYS):
    """Split the range [start, end] into consecutive ranges of at most max_days days."""
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=max_days - 1), end)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def fetch_chunk(code, start, end, retries=3, timeout=30):
    """Download one date range for one currency. Retries on network errors.

    Returns the parsed JSON, or None if the API has no data for the range
    (the API answers 404, for example for a range with only weekends).
    """
    url = BASE_URL.format(code=code.lower(), start=start.isoformat(), end=end.isoformat())
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params={"format": "json"}, timeout=timeout)
            if response.status_code == 404:
                log.info("%s %s..%s: no data for this range", code, start, end)
                return None
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            log.warning("%s %s..%s: attempt %d of %d failed: %s",
                        code, start, end, attempt, retries, exc)
            if attempt == retries:
                raise
            time.sleep(2 ** attempt)


def extract(code, start, end, raw_dir=RAW_DIR):
    """Download all chunks for one currency and save each raw response as a JSON file."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    payloads = []
    for chunk_start, chunk_end in date_chunks(start, end):
        payload = fetch_chunk(code, chunk_start, chunk_end)
        if payload is None:
            continue
        path = raw_dir / f"{code.upper()}_{chunk_start}_{chunk_end}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        payloads.append(payload)
    log.info("%s: downloaded %d file(s)", code, len(payloads))
    return payloads
