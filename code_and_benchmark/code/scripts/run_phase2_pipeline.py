import json
from pathlib import Path

from medinsider.fhir.paired_scenario import generate_v2_dataset
from medinsider.fhir.review_sampling import generate_clinician_review_sample
from medinsider.phase2_validation import validate_dataset


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    dataset_dir = project_root / "scenarios/phase2"
    generation = generate_v2_dataset(str(dataset_dir), seed=42)
    validation = validate_dataset(str(dataset_dir))
    clinician = generate_clinician_review_sample(
        dataset_dir=str(dataset_dir),
        output_path=str(dataset_dir / "artifacts/clinician_review_sample.jsonl"),
        target_size=75,
        seed=42,
    )

    summary = {
        "generation": generation,
        "validation": validation,
        "clinician_review_sample": clinician,
    }
    summary_path = dataset_dir / "artifacts/phase2_pipeline_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
