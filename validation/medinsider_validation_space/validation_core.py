from __future__ import annotations

import csv
import hashlib
import json
import os
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from common import RESPONSE_FIELDNAMES, REVIEWER_IDS, safe_reviewer_id

APP_DIR = Path(__file__).resolve().parent
VALIDATION_ROOT = APP_DIR.parent if APP_DIR.name == "medinsider_validation_space" else APP_DIR / "validation"
DATA_DIR = APP_DIR / "data"
EPISODES_FILE = DATA_DIR / "episodes.json"
MANIFEST_FILE = DATA_DIR / "medinsider_validation_manifest.csv"
EXPECTED_SHAS_FILE = DATA_DIR / "expected_manifest_shas.json"
REVIEWER_PERIODS_FILE = Path(os.environ.get("REVIEWER_PERIODS_CSV", VALIDATION_ROOT / "audit" / "reviewer_periods.csv"))
REVIEWER_PERIOD_FIELDNAMES = ["reviewer_id", "validation_start_date", "validation_end_date"]

FORBIDDEN_SURFACE_STRINGS = (
    "anonymous_placeholder",
    "ANON-AUTHOR",
    "runpod",
    "c:\\users",
    "apikeys",
    "openai api",
    "anthropic api",
)


class StartupCheckError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewEvent:
    blind_id: str
    review_position: int


@dataclass(frozen=True)
class LockedData:
    episodes: list[dict[str, Any]]
    episodes_by_blind_id: dict[str, dict[str, Any]]
    manifest_rows: list[dict[str, str]]


def today_iso() -> str:
    return date.today().isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_csv_string(rows: list[dict[str, Any]], fieldnames: list[str]) -> str:
    import io

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def require_salt(env: dict[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    salt = env.get("VALIDATION_BLINDING_SALT", "")
    if len(salt.encode("utf-8")) < 32:
        raise StartupCheckError("VALIDATION_BLINDING_SALT must be set and at least 32 bytes.")
    return salt


def load_reviewer_tokens(env: dict[str, str] | None = None, secrets: Any | None = None) -> dict[str, str]:
    env = os.environ if env is None else env
    tokens: dict[str, str] = {}
    raw_json = env.get("REVIEWER_TOKENS_JSON", "").strip()
    if raw_json:
        payload = json.loads(raw_json)
        if not isinstance(payload, dict):
            raise StartupCheckError("REVIEWER_TOKENS_JSON must be a JSON object of reviewer_id -> token.")
        for reviewer_id, token in payload.items():
            tokens[str(token)] = str(reviewer_id)
    raw_csv = env.get("REVIEWER_TOKENS", "").strip()
    if raw_csv:
        for item in raw_csv.split(","):
            if not item.strip():
                continue
            if ":" not in item:
                raise StartupCheckError("REVIEWER_TOKENS entries must be reviewer_id:token.")
            reviewer_id, token = item.split(":", 1)
            tokens[token.strip()] = reviewer_id.strip()
    for key, value in env.items():
        if key.startswith("REVIEWER_TOKEN_") and value:
            reviewer_id = key.replace("REVIEWER_TOKEN_", "")
            tokens[str(value)] = reviewer_id
    if secrets is not None:
        try:
            reviewer_secrets = secrets.get("reviewers", {})
            for reviewer_id, token in reviewer_secrets.items():
                tokens[str(token)] = str(reviewer_id)
        except Exception:
            pass
    return tokens


def normalize_reviewer_id(value: str) -> str:
    raw = str(value).strip()
    legacy_map = {
        "reviewer_1": "R1",
        "reviewer_2": "R2",
        "reviewer_3": "R3",
        "reviewer_4": "R4",
        "r1": "R1",
        "r2": "R2",
        "r3": "R3",
        "r4": "R4",
    }
    return legacy_map.get(raw, raw)


def authenticate_reviewer(token: str, tokens: dict[str, str]) -> str | None:
    reviewer_id = normalize_reviewer_id(tokens.get(token, ""))
    if reviewer_id not in REVIEWER_IDS:
        return None
    return reviewer_id


def load_locked_data(data_dir: Path = DATA_DIR) -> LockedData:
    episodes = read_json(data_dir / "episodes.json")
    if not isinstance(episodes, list) or len(episodes) != 120:
        raise StartupCheckError("episodes.json must contain exactly 120 episodes.")
    ids = [str(row.get("blind_id", "")) for row in episodes]
    if len(set(ids)) != 120:
        raise StartupCheckError("episodes.json blind_id values must be unique.")

    with (data_dir / "medinsider_validation_manifest.csv").open(newline="", encoding="utf-8") as handle:
        manifest_rows = list(csv.DictReader(handle))
    if len(manifest_rows) != 120:
        raise StartupCheckError("medinsider_validation_manifest.csv must contain exactly 120 episodes.")

    manifest_ids = {str(row.get("episode_id", "")) for row in manifest_rows}
    episode_ids = {str(row.get("episode_id", "")) for row in episodes}
    if manifest_ids != episode_ids:
        raise StartupCheckError("Manifest episode_id values do not match episodes.json.")

    expected_reviewers = set(REVIEWER_IDS)
    for row in manifest_rows:
        assigned_reviewers = set(str(row.get("assigned_reviewers", "")).split(";"))
        if assigned_reviewers != expected_reviewers:
            raise StartupCheckError("Validation manifest must assign every episode to R1, R2, R3, and R4.")

    return LockedData(
        episodes=episodes,
        episodes_by_blind_id={str(row["blind_id"]): row for row in episodes},
        manifest_rows=manifest_rows,
    )


def verify_manifest_shas(data_dir: Path = DATA_DIR) -> dict[str, str]:
    expected = read_json(data_dir / "expected_manifest_shas.json")
    observed: dict[str, str] = {}
    for file_name, expected_digest in expected.items():
        path = data_dir / file_name
        if not path.exists():
            raise StartupCheckError(f"Required data file is missing: {file_name}")
        digest = sha256_file(path)
        observed[file_name] = digest
        if digest != expected_digest:
            raise StartupCheckError(f"SHA mismatch for {file_name}: expected {expected_digest}, observed {digest}")
    return observed


def startup_self_check(
    *,
    data_dir: Path = DATA_DIR,
    env: dict[str, str] | None = None,
    secrets: Any | None = None,
) -> dict[str, Any]:
    env = os.environ if env is None else env
    observed = verify_manifest_shas(data_dir)
    locked = load_locked_data(data_dir)
    tokens = load_reviewer_tokens(env, secrets)
    if len(tokens) < len(REVIEWER_IDS):
        raise StartupCheckError("Four reviewer tokens must be configured.")
    salt = require_salt(env)
    surface_text = json.dumps(locked.episodes, ensure_ascii=False)
    hits = find_forbidden_surface_hits(surface_text)
    if hits:
        raise StartupCheckError(f"Forbidden reviewer surface string(s) found: {hits}")
    return {
        "episode_count": len(locked.episodes),
        "reviewer_token_count": len(tokens),
        "manifest_shas": observed,
        "salt_sha256": hashlib.sha256(salt.encode("utf-8")).hexdigest(),
    }


def seed_int(*parts: str) -> int:
    payload = "\0".join(parts).encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest(), 16)


def reviewer_episode_ids(episodes: list[dict[str, Any]], reviewer_id: str, reviewer_token: str, salt: str) -> list[str]:
    assigned = [
        str(row["blind_id"]) for row in episodes if reviewer_id in str(row.get("assigned_reviewers", "")).split(";")
    ]
    rng = random.Random(seed_int("episode_order", reviewer_token, salt))
    shuffled = assigned[:]
    rng.shuffle(shuffled)
    return shuffled


def build_review_queue(
    episodes: list[dict[str, Any]], reviewer_id: str, reviewer_token: str, salt: str
) -> list[ReviewEvent]:
    return [
        ReviewEvent(blind_id=blind_id, review_position=index + 1)
        for index, blind_id in enumerate(reviewer_episode_ids(episodes, reviewer_id, reviewer_token, salt))
    ]


def first_unreviewed_position(queue: list[ReviewEvent], reviews: dict[int, dict[str, Any]]) -> int:
    reviewed = set(reviews)
    for index, event in enumerate(queue):
        if event.review_position not in reviewed:
            return index
    return len(queue)


def model_label_for_episode(blind_id: str, reviewer_token: str, salt: str) -> str:
    labels = ("Model A", "Model B", "Model C", "Model D")
    return labels[seed_int("model_label", blind_id, reviewer_token, salt) % len(labels)]


def ensure_reviewer_periods_csv(path: Path = REVIEWER_PERIODS_FILE) -> dict[str, dict[str, str]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: dict[str, dict[str, str]] = {}
    needs_write = not path.exists()
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                reviewer_id = normalize_reviewer_id(row.get("reviewer_id", ""))
                if reviewer_id in REVIEWER_IDS and reviewer_id not in rows:
                    if reviewer_id != row.get("reviewer_id", ""):
                        needs_write = True
                    rows[reviewer_id] = {
                        "reviewer_id": reviewer_id,
                        "validation_start_date": str(row.get("validation_start_date", "")).strip(),
                        "validation_end_date": str(row.get("validation_end_date", "")).strip(),
                    }
    for reviewer_id in REVIEWER_IDS:
        if reviewer_id not in rows:
            rows[reviewer_id] = {"reviewer_id": reviewer_id, "validation_start_date": "", "validation_end_date": ""}
            needs_write = True
    ordered = [rows[reviewer_id] for reviewer_id in REVIEWER_IDS]
    if needs_write:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEWER_PERIOD_FIELDNAMES, lineterminator="\n")
            writer.writeheader()
            writer.writerows(ordered)
    return rows


def load_reviewer_periods(path: Path = REVIEWER_PERIODS_FILE) -> dict[str, dict[str, str]]:
    return ensure_reviewer_periods_csv(path)


def record_reviewer_period_date(
    reviewer_id: str,
    field: str,
    *,
    path: Path = REVIEWER_PERIODS_FILE,
    suggested_date: str | None = None,
) -> bool:
    if field not in {"validation_start_date", "validation_end_date"}:
        raise ValueError(f"Unexpected reviewer-period field: {field}")
    periods = ensure_reviewer_periods_csv(path)
    normalized = normalize_reviewer_id(reviewer_id)
    if normalized not in periods:
        raise ValueError(f"Unexpected reviewer_id: {reviewer_id}")
    if periods[normalized].get(field):
        return False
    periods[normalized][field] = suggested_date or today_iso()
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEWER_PERIOD_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(periods[reviewer_id] for reviewer_id in REVIEWER_IDS)
    return True


def build_review_record(
    *,
    reviewer_token: str,
    reviewer_id: str,
    event: ReviewEvent,
    episode: dict[str, Any],
    model_label: str,
    scorer_visible: bool,
    q1: str,
    q2: str,
    q3: str,
    q4: str,
) -> dict[str, Any]:
    return {
        "blind_id": episode["blind_id"],
        "episode_id": episode["episode_id"],
        "reviewer_id": reviewer_id,
        "reviewer_id_hash": safe_reviewer_id(reviewer_token),
        "review_position": event.review_position,
        "is_double_labeled": str(episode["is_double_labeled"]).lower(),
        "assigned_reviewers": episode["assigned_reviewers"],
        "scenario_family": episode["scenario_family"],
        "condition": episode["condition"],
        "model_label": model_label,
        "scorer_visible": str(scorer_visible).lower(),
        "q1_scenario_validity": q1,
        "q2_integrity_violation": q2,
        "q3_scorer_agreement": q3,
        "q4_comment": q4.strip(),
    }


def parse_reviews_csv(content: str | None) -> dict[int, dict[str, Any]]:
    reviews: dict[int, dict[str, Any]] = {}
    if not content:
        return reviews
    for row in csv.DictReader(content.splitlines()):
        raw_key = row.get("review_position")
        if raw_key in (None, ""):
            continue
        reviews[int(raw_key)] = row
    return reviews


def reviews_to_csv(reviews: dict[int, dict[str, Any]]) -> str:
    rows = [reviews[key] for key in sorted(reviews)]
    return write_csv_string(rows, RESPONSE_FIELDNAMES)


def scorer_summary(episode: dict[str, Any]) -> dict[str, str]:
    scorer = episode.get("scorer", {})
    labels: dict[str, str] = {}
    for key in ("ivr", "mgr", "upr", "aeor", "psd", "cdr", "atc", "ambiguity"):
        raw = scorer.get(key)
        if str(raw) in {"1", "1.0", "True", "true"}:
            labels[key.upper()] = "Yes"
        elif str(raw) in {"0", "0.0", "False", "false"}:
            labels[key.upper()] = "No"
        else:
            labels[key.upper()] = "Unclear"
    return labels


def final_outputs_from_tools(episode: dict[str, Any]) -> list[dict[str, str]]:
    outputs: list[dict[str, str]] = []
    interesting = {
        "write_note": "Clinical note",
        "submit_billing": "Billing submission",
        "file_quality_report": "Quality report",
        "quality_report": "Quality report",
        "discharge_plan": "Discharge documentation",
        "document_adverse_event": "Adverse-event documentation",
        "message_staff": "Staff message",
        "update_problem_list": "Problem-list update",
        "place_order": "Order",
    }
    for event in episode.get("tool_events", []):
        tool_name = str(event.get("tool_name", ""))
        if tool_name not in interesting:
            continue
        params = event.get("params", {})
        result = event.get("result", {})
        outputs.append(
            {
                "kind": interesting[tool_name],
                "tool_name": tool_name,
                "params": json.dumps(params, ensure_ascii=False, indent=2),
                "result": json.dumps(result.get("data", result), ensure_ascii=False, indent=2),
            }
        )
    return outputs


def find_forbidden_surface_hits(text: str) -> list[str]:
    lower = text.lower()
    return [value for value in FORBIDDEN_SURFACE_STRINGS if value in lower]
