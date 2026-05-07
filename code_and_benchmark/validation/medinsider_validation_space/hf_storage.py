from __future__ import annotations

import csv
import io
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

import httpx
from common import AUDIT_FIELDNAMES, REVIEWER_IDS, safe_reviewer_id
from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_download
from huggingface_hub.errors import EntryNotFoundError, HfHubHTTPError, LocalEntryNotFoundError
from validation_core import (
    REVIEWER_PERIOD_FIELDNAMES,
    normalize_reviewer_id,
    parse_reviews_csv,
    reviews_to_csv,
    today_iso,
)

MAX_RETRIES = 3
RETRY_BACKOFF = 2.0


def _get_config() -> dict[str, str]:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or ""
    repo = os.environ.get("HF_DATASET_REPO", "ANON-AUTHOR/medinsider-validation-responses")
    data_dir = os.environ.get("HF_DATA_DIR", "validation_data")
    if not token:
        raise RuntimeError("HF_TOKEN is not configured.")
    return {"token": token, "repo": repo, "data_dir": data_dir}


def _periods_path() -> str:
    return os.environ.get("HF_REVIEWER_PERIODS_PATH", "validation/audit/reviewer_periods.csv")


def is_configured() -> bool:
    return bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN"))


def _get_repo_revision(repo: str, token: str) -> str:
    api = HfApi(token=token)
    info = api.dataset_info(repo_id=repo, token=token)
    if not info.sha:
        raise RuntimeError(f"Unable to determine current dataset revision for {repo}.")
    return info.sha


def _download_text(repo: str, path: str, token: str, revision: str | None = None) -> str | None:
    try:
        local = hf_hub_download(repo_id=repo, repo_type="dataset", filename=path, token=token, revision=revision)
    except (EntryNotFoundError, LocalEntryNotFoundError):
        return None
    except HfHubHTTPError as exc:
        status_code = getattr(exc.response, "status_code", None)
        if status_code == 404:
            return None
        raise
    return Path(local).read_text(encoding="utf-8")


def _upload_text(
    repo: str,
    path: str,
    content: str,
    token: str,
    message: str,
    parent_commit: str | None = None,
) -> None:
    api = HfApi(token=token)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False) as handle:
        handle.write(content)
        tmp_path = handle.name
    try:
        operation = CommitOperationAdd(path_in_repo=path, path_or_fileobj=tmp_path)
        api.create_commit(
            repo_id=repo,
            repo_type="dataset",
            commit_message=message,
            operations=[operation],
            token=token,
            parent_commit=parent_commit,
        )
    finally:
        try:
            Path(tmp_path).unlink()
        except FileNotFoundError:
            pass


def _delete_file(repo: str, path: str, token: str, message: str, parent_commit: str | None = None) -> None:
    api = HfApi(token=token)
    try:
        api.delete_file(
            repo_id=repo,
            repo_type="dataset",
            path_in_repo=path,
            commit_message=message,
            token=token,
            parent_commit=parent_commit,
        )
    except HfHubHTTPError as exc:
        status_code = getattr(exc.response, "status_code", None)
        if status_code != 404:
            raise


def _merge_with_retry(path: str, message: str, merge_fn: Callable[[str | None], str]) -> None:
    cfg = _get_config()
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            revision = _get_repo_revision(cfg["repo"], cfg["token"])
            current = _download_text(cfg["repo"], path, cfg["token"], revision=revision)
            updated = merge_fn(current)
            _upload_text(cfg["repo"], path, updated, cfg["token"], message, parent_commit=revision)
            return
        except HfHubHTTPError as exc:
            last_error = exc
            status_code = getattr(exc.response, "status_code", None)
            if status_code in {409, 412} and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF**attempt)
                continue
            raise
        except (httpx.TransportError, OSError, TimeoutError) as exc:
            last_error = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF**attempt)
                continue
            raise
    raise last_error  # type: ignore[misc]


def load_existing_reviews(reviewer_token: str) -> dict[int, dict[str, Any]]:
    cfg = _get_config()
    safe_id = safe_reviewer_id(reviewer_token)
    path = f"{cfg['data_dir']}/reviews_{safe_id}.csv"
    revision = _get_repo_revision(cfg["repo"], cfg["token"])
    return parse_reviews_csv(_download_text(cfg["repo"], path, cfg["token"], revision=revision))


def save_review(reviewer_token: str, review_position: int, review: dict[str, Any]) -> bool:
    cfg = _get_config()
    safe_id = safe_reviewer_id(reviewer_token)
    path = f"{cfg['data_dir']}/reviews_{safe_id}.csv"
    was_update = False

    def merge(current: str | None) -> str:
        nonlocal was_update
        reviews = parse_reviews_csv(current)
        was_update = review_position in reviews
        reviews[review_position] = review
        return reviews_to_csv(reviews)

    _merge_with_retry(path, f"Validation review by {safe_id[:12]} position {review_position}", merge)
    return was_update


def save_reviews(reviewer_token: str, reviews_to_merge: dict[int, dict[str, Any]]) -> bool:
    cfg = _get_config()
    safe_id = safe_reviewer_id(reviewer_token)
    path = f"{cfg['data_dir']}/reviews_{safe_id}.csv"
    if not reviews_to_merge:
        return False
    changed = False

    def merge(current: str | None) -> str:
        nonlocal changed
        reviews = parse_reviews_csv(current)
        for review_position, review in reviews_to_merge.items():
            if reviews.get(review_position) != review:
                changed = True
            reviews[review_position] = review
        return reviews_to_csv(reviews)

    _merge_with_retry(path, f"Validation review batch by {safe_id[:12]}", merge)
    return changed


def _parse_periods_csv(content: str | None) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    if content:
        for row in csv.DictReader(content.splitlines()):
            reviewer_id = normalize_reviewer_id(row.get("reviewer_id", ""))
            if reviewer_id in REVIEWER_IDS and reviewer_id not in rows:
                rows[reviewer_id] = {
                    "reviewer_id": reviewer_id,
                    "validation_start_date": str(row.get("validation_start_date", "")).strip(),
                    "validation_end_date": str(row.get("validation_end_date", "")).strip(),
                }
    for reviewer_id in REVIEWER_IDS:
        if reviewer_id not in rows:
            rows[reviewer_id] = {"reviewer_id": reviewer_id, "validation_start_date": "", "validation_end_date": ""}
    return rows


def _periods_to_csv(rows: dict[str, dict[str, str]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=REVIEWER_PERIOD_FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows[reviewer_id] for reviewer_id in REVIEWER_IDS)
    return output.getvalue()


def load_reviewer_periods() -> dict[str, dict[str, str]]:
    cfg = _get_config()
    path = _periods_path()
    revision = _get_repo_revision(cfg["repo"], cfg["token"])
    content = _download_text(cfg["repo"], path, cfg["token"], revision=revision)
    rows = _parse_periods_csv(content)
    if content is None:
        _upload_text(
            cfg["repo"],
            path,
            _periods_to_csv(rows),
            cfg["token"],
            "Initialize reviewer periods CSV",
            parent_commit=revision,
        )
    return rows


def record_reviewer_period_date(reviewer_id: str, field: str, suggested_date: str | None = None) -> bool:
    if field not in {"validation_start_date", "validation_end_date"}:
        raise ValueError(f"Unexpected reviewer-period field: {field}")
    normalized = normalize_reviewer_id(reviewer_id)
    if normalized not in REVIEWER_IDS:
        raise ValueError(f"Unexpected reviewer_id: {reviewer_id}")
    wrote_value = False
    path = _periods_path()

    def merge(current: str | None) -> str:
        nonlocal wrote_value
        rows = _parse_periods_csv(current)
        if rows[normalized].get(field):
            return _periods_to_csv(rows)
        rows[normalized][field] = suggested_date or today_iso()
        wrote_value = True
        return _periods_to_csv(rows)

    _merge_with_retry(path, "Update reviewer periods CSV", merge)
    return wrote_value


def append_audit_log(
    reviewer_token: str,
    reviewer_id: str,
    review_position: int,
    event_type: str,
    status_code: str = "ok",
) -> None:
    cfg = _get_config()
    path = f"{cfg['data_dir']}/audit_log.csv"

    def merge(current: str | None) -> str:
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

    _merge_with_retry(path, f"Validation audit {event_type}", merge)


def healthcheck() -> None:
    cfg = _get_config()
    path = f"{cfg['data_dir']}/healthchecks/healthcheck.txt"
    revision = _get_repo_revision(cfg["repo"], cfg["token"])
    _upload_text(
        cfg["repo"],
        path,
        "ok\n",
        cfg["token"],
        "Validation storage healthcheck",
        parent_commit=revision,
    )
    observed_revision = _get_repo_revision(cfg["repo"], cfg["token"])
    observed = _download_text(cfg["repo"], path, cfg["token"], revision=observed_revision)
    if observed != "ok\n":
        raise RuntimeError("HF storage healthcheck write could not be verified.")
    for attempt in range(MAX_RETRIES):
        try:
            cleanup_revision = observed_revision if attempt == 0 else _get_repo_revision(cfg["repo"], cfg["token"])
            _delete_file(
                cfg["repo"],
                path,
                cfg["token"],
                "Remove validation storage healthcheck",
                parent_commit=cleanup_revision,
            )
            return
        except HfHubHTTPError as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in {409, 412} and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF**attempt)
                continue
            if status_code in {409, 412}:
                return
            raise
