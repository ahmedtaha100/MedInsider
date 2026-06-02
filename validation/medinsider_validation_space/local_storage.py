from __future__ import annotations

import csv
import io
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from common import AUDIT_FIELDNAMES, safe_reviewer_id
from validation_core import parse_reviews_csv, reviews_to_csv

RESULTS_DIR = Path("results")
LOCK_TIMEOUT_SECONDS = 15.0
LOCK_POLL_SECONDS = 0.05


def _lock_is_stale(lock_path: Path) -> bool:
    try:
        if os.name != "nt":
            raw_pid = lock_path.read_text(encoding="ascii", errors="ignore").strip()
            if raw_pid:
                try:
                    os.kill(int(raw_pid), 0)
                except OSError:
                    return True
    except FileNotFoundError:
        return False
    except ValueError:
        return True
    return False


@contextmanager
def _file_lock(path: Path, timeout_seconds: float = LOCK_TIMEOUT_SECONDS) -> Iterator[None]:
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    wait_limit = time.monotonic() + timeout_seconds
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(fd, str(os.getpid()).encode("ascii"))
        except FileExistsError:
            if _lock_is_stale(lock_path):
                try:
                    lock_path.unlink()
                    continue
                except FileNotFoundError:
                    continue
            if time.monotonic() >= wait_limit:
                raise TimeoutError(f"Timed out waiting for storage lock: {lock_path}") from None
            time.sleep(LOCK_POLL_SECONDS)
    try:
        yield
    finally:
        os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _locked_update(path: Path, merge_fn: Callable[[str], str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _file_lock(path):
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        updated = merge_fn(current)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent) as handle:
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
            tmp_path = Path(handle.name)
        tmp_path.replace(path)


def get_results_path(reviewer_token: str, results_dir: Path = RESULTS_DIR) -> Path:
    return results_dir / f"reviews_{safe_reviewer_id(reviewer_token)}.csv"


def load_existing_reviews(reviewer_token: str, results_dir: Path = RESULTS_DIR) -> dict[int, dict[str, Any]]:
    path = get_results_path(reviewer_token, results_dir)
    if not path.exists():
        return {}
    return parse_reviews_csv(path.read_text(encoding="utf-8"))


def save_review(
    reviewer_token: str, review_position: int, review: dict[str, Any], results_dir: Path = RESULTS_DIR
) -> bool:
    path = get_results_path(reviewer_token, results_dir)
    was_update = False

    def merge(current: str) -> str:
        nonlocal was_update
        reviews = parse_reviews_csv(current)
        was_update = review_position in reviews
        reviews[review_position] = review
        return reviews_to_csv(reviews)

    _locked_update(path, merge)
    return was_update


def append_audit_log(
    reviewer_token: str,
    reviewer_id: str,
    review_position: int,
    event_type: str,
    status_code: str = "ok",
    results_dir: Path = RESULTS_DIR,
) -> None:
    path = results_dir / "audit_log.csv"

    def merge(current: str) -> str:
        output = io.StringIO()
        if current:
            output.write(current)
            if not current.endswith("\n"):
                output.write("\n")
        else:
            csv.writer(output, lineterminator="\n").writerow(AUDIT_FIELDNAMES)
        csv.writer(output, lineterminator="\n").writerow(
            [reviewer_id, safe_reviewer_id(reviewer_token), review_position, event_type, status_code]
        )
        return output.getvalue()

    _locked_update(path, merge)


def healthcheck(results_dir: Path = RESULTS_DIR) -> None:
    health_dir = results_dir / "healthchecks"
    health_dir.mkdir(parents=True, exist_ok=True)
    sentinel = health_dir / "healthcheck.txt"
    sentinel.write_text("ok\n", encoding="utf-8")
    sentinel.unlink()
