from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from clients.http_session import request_with_retries


@patch("clients.http_session.time.sleep", return_value=None)
def test_retries_on_502_then_succeeds(_sleep):
    session = MagicMock()
    bad = MagicMock()
    bad.status_code = 502
    good = MagicMock()
    good.status_code = 200
    session.request.side_effect = [bad, bad, good]
    retries: list[tuple] = []

    resp = request_with_retries(
        session,
        "POST",
        "https://example.test/list",
        retries=5,
        backoff=2.0,
        timeout=1,
        on_retry=lambda attempt, attempts, reason, wait: retries.append((attempt, reason, wait)),
    )

    assert resp is good
    assert session.request.call_count == 3
    assert len(retries) == 2
    assert retries[0][1] == "HTTP 502"


@patch("clients.http_session.time.sleep", return_value=None)
def test_raises_connection_error_after_retries(_sleep):
    session = MagicMock()
    session.request.side_effect = requests.ConnectionError("boom")
    try:
        request_with_retries(session, "GET", "https://example.test/x", retries=2, backoff=2.0, timeout=1)
        assert False, "expected ConnectionError"
    except requests.ConnectionError:
        pass
    assert session.request.call_count == 2
