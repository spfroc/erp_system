from db import commit_with_retry, is_lock_conflict, is_lock_conflict_message


class _Orig:
    def __init__(self, code: int, message: str) -> None:
        self.args = (code, message)


class _DBError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.orig = _Orig(code, message)


class _Session:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.commits = 0
        self.rollbacks = 0
        self.writes = 0

    def commit(self) -> None:
        self.commits += 1
        if self.commits <= self.failures:
            raise _DBError(1213, "Deadlock found when trying to get lock")

    def rollback(self) -> None:
        self.rollbacks += 1


def test_detects_deadlock_and_lock_wait():
    assert is_lock_conflict(_DBError(1213, "Deadlock found when trying to get lock"))
    assert is_lock_conflict(_DBError(1205, "Lock wait timeout exceeded"))
    assert not is_lock_conflict(RuntimeError("HTTP 403"))
    assert is_lock_conflict_message("(1213, 'Deadlock found when trying to get lock')")
    assert not is_lock_conflict_message("HTTP 403")


def test_commit_retries_then_succeeds():
    session = _Session(failures=2)
    seen = {"n": 0}

    def write() -> str:
        seen["n"] += 1
        return "ok"

    assert commit_with_retry(session, write, attempts=5) == "ok"
    assert seen["n"] == 3
    assert session.commits == 3
    assert session.rollbacks == 2


def test_commit_does_not_retry_other_errors():
    session = _Session(failures=0)

    def write() -> None:
        raise RuntimeError("parse blew up")

    try:
        commit_with_retry(session, write, attempts=5)
    except RuntimeError as exc:
        assert "parse blew up" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
    assert session.rollbacks == 1
    assert session.commits == 0
