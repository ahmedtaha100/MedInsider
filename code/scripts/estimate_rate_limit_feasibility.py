import argparse
import json
from typing import Any


def _positive(name: str, value: float | None) -> float | None:
    if value is None:
        return None
    if value <= 0:
        raise ValueError(f"{name} must be > 0, got {value}")
    return value


def _non_negative(name: str, value: float) -> float:
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value}")
    return value


def estimate_feasibility(
    *,
    calls: int,
    rpm: float | None = None,
    input_tokens_per_call: float = 0.0,
    output_tokens_per_call: float = 0.0,
    tpm: float | None = None,
    input_tpm: float | None = None,
    output_tpm: float | None = None,
    label: str = "run",
) -> dict[str, Any]:
    if calls <= 0:
        raise ValueError(f"calls must be > 0, got {calls}")

    rpm = _positive("rpm", rpm)
    tpm = _positive("tpm", tpm)
    input_tpm = _positive("input_tpm", input_tpm)
    output_tpm = _positive("output_tpm", output_tpm)
    input_tokens_per_call = _non_negative("input_tokens_per_call", input_tokens_per_call)
    output_tokens_per_call = _non_negative("output_tokens_per_call", output_tokens_per_call)

    if rpm is None and tpm is None and input_tpm is None and output_tpm is None:
        raise ValueError("at least one limit must be provided")

    total_input_tokens = calls * input_tokens_per_call
    total_output_tokens = calls * output_tokens_per_call
    total_tokens = total_input_tokens + total_output_tokens

    constraints: list[dict[str, Any]] = []
    if rpm is not None:
        constraints.append(
            {
                "name": "requests_per_minute",
                "minutes": calls / rpm,
            }
        )
    if tpm is not None:
        constraints.append(
            {
                "name": "tokens_per_minute",
                "minutes": total_tokens / tpm,
            }
        )
    if input_tpm is not None:
        constraints.append(
            {
                "name": "input_tokens_per_minute",
                "minutes": total_input_tokens / input_tpm,
            }
        )
    if output_tpm is not None:
        constraints.append(
            {
                "name": "output_tokens_per_minute",
                "minutes": total_output_tokens / output_tpm,
            }
        )

    bottleneck = max(constraints, key=lambda item: item["minutes"])
    return {
        "label": label,
        "calls": calls,
        "input_tokens_per_call": input_tokens_per_call,
        "output_tokens_per_call": output_tokens_per_call,
        "total_input_tokens": round(total_input_tokens, 4),
        "total_output_tokens": round(total_output_tokens, 4),
        "total_tokens": round(total_tokens, 4),
        "constraints": [
            {
                "name": item["name"],
                "minutes": round(item["minutes"], 4),
                "hours": round(item["minutes"] / 60, 4),
            }
            for item in constraints
        ],
        "bottleneck": {
            "name": bottleneck["name"],
            "minutes": round(bottleneck["minutes"], 4),
            "hours": round(bottleneck["minutes"] / 60, 4),
        },
        "projected_wall_clock_minutes": round(bottleneck["minutes"], 4),
        "projected_wall_clock_hours": round(bottleneck["minutes"] / 60, 4),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate phase-4 API run wall clock from dashboard rate limits.")
    parser.add_argument("--label", default="run")
    parser.add_argument("--calls", type=int, required=True)
    parser.add_argument("--rpm", type=float, default=None)
    parser.add_argument("--input-tokens-per-call", type=float, default=0.0)
    parser.add_argument("--output-tokens-per-call", type=float, default=0.0)
    parser.add_argument(
        "--tpm", type=float, default=None, help="Combined tokens-per-minute limit if provider reports one."
    )
    parser.add_argument("--input-tpm", type=float, default=None, help="Input tokens-per-minute limit.")
    parser.add_argument("--output-tpm", type=float, default=None, help="Output tokens-per-minute limit.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = estimate_feasibility(
            label=args.label,
            calls=args.calls,
            rpm=args.rpm,
            input_tokens_per_call=args.input_tokens_per_call,
            output_tokens_per_call=args.output_tokens_per_call,
            tpm=args.tpm,
            input_tpm=args.input_tpm,
            output_tpm=args.output_tpm,
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
