"""Batch runner xử lý 50 case và ghi output/trace."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from src.config import INPUT_DIR, LOGGING_DIR, OUTPUT_DIR
from src.coordinator import CoordinatorAgent
from src.data_store import DataStore
from src.input_schema import load_case
from src.metadata import write_metadata
from src.trace_logger import TraceLogger
from src.verifier import VerifierAgent


def run_all(
    input_dir: Path = INPUT_DIR,
    output_dir: Path = OUTPUT_DIR,
) -> Counter:
    case_files = sorted(input_dir.glob("EC_*.json"))
    expected_names = [
        f"EC_{number:03d}.json"
        for number in range(1, 51)
    ]
    actual_names = [path.name for path in case_files]
    if actual_names != expected_names:
        raise ValueError(
            "Input phải gồm đúng EC_001.json đến EC_050.json"
        )

    store = DataStore()
    trace = TraceLogger(
        LOGGING_DIR / "trace.jsonl",
        reset=True,
    )
    coordinator = CoordinatorAgent(store, trace)
    verifier = VerifierAgent(store)
    output_dir.mkdir(parents=True, exist_ok=True)

    issue_counts: Counter = Counter()

    for case_file in case_files:
        case = load_case(case_file)
        if case.case_id != case_file.stem:
            raise ValueError(
                f"{case_file.name}: tên file không khớp case_id"
            )

        result = coordinator.process_case(case)
        verified = verifier.verify(result)

        trace.handoff(
            case_id=case.case_id,
            agent=verifier.name,
            recipient=coordinator.name,
            input_refs=verified.evidence_ids,
            output_summary={
                "valid": True,
                "evidence_count": len(verified.evidence_ids),
                "action_count": len(verified.resolution_actions),
            },
        )

        destination = output_dir / case_file.name
        destination.write_text(
            verified.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        issue_counts[
            verified.case_assessment.primary_issue
        ] += 1

    write_metadata(
        LOGGING_DIR / "metadata.json",
        processed_cases=len(case_files),
    )
    return issue_counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process 50 Olist dispute cases"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT_DIR,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
    )
    args = parser.parse_args()

    issue_counts = run_all(args.input, args.output)
    print(f"Generated {sum(issue_counts.values())} outputs")
    for issue, count in sorted(issue_counts.items()):
        print(f"  {issue}: {count}")


if __name__ == "__main__":
    main()
