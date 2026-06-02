import argparse
import json
from pathlib import Path

from medinsider.phaseB_validation import (
    run_inter_rater_agreement,
    run_metric_validation,
    run_scorer_error_audit,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase B metric validation reports from expert labels.")
    parser.add_argument("--labels-csv", default="docs/validation/blinded_gold_label_set.csv")
    parser.add_argument("--predictions-csv", default="docs/validation/internal_validation_predictions.csv")
    parser.add_argument("--metric-results-md", default="docs/validation/metric_validation_results.md")
    parser.add_argument("--metric-results-json", default="docs/validation/metric_validation_results.json")
    parser.add_argument("--agreement-md", default="docs/validation/inter_rater_agreement.md")
    parser.add_argument("--error-audit-md", default="docs/validation/scorer_error_audit.md")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    Path(args.metric_results_md).parent.mkdir(parents=True, exist_ok=True)

    metric_summary = run_metric_validation(
        labels_csv=args.labels_csv,
        output_markdown=args.metric_results_md,
        output_json=args.metric_results_json,
        predictions_csv=args.predictions_csv,
    )

    agreement_summary = run_inter_rater_agreement(
        labels_csv=args.labels_csv,
        output_markdown=args.agreement_md,
    )

    audit_summary = run_scorer_error_audit(
        labels_csv=args.labels_csv,
        output_markdown=args.error_audit_md,
        top_k=args.top_k,
        predictions_csv=args.predictions_csv,
    )

    summary = {
        "metric_validation": metric_summary,
        "inter_rater_agreement": agreement_summary,
        "scorer_error_audit": audit_summary,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
