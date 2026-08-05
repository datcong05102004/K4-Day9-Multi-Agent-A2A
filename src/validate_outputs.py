"""Kiểm tra toàn bộ artifact trước khi đóng gói."""

from __future__ import annotations

import json
from collections import Counter

from src.config import (
    INPUT_DIR,
    LOGGING_DIR,
    MODEL_NAME,
    MODEL_PROVIDER,
    OUTPUT_DIR,
)
from src.data_store import DataStore
from src.output_schema import CaseOutput
from src.verifier import VerifierAgent


def main() -> None:
    expected_names = [
        f"EC_{number:03d}.json"
        for number in range(1, 51)
    ]
    input_names = sorted(
        path.name for path in INPUT_DIR.glob("EC_*.json")
    )
    output_paths = sorted(OUTPUT_DIR.glob("EC_*.json"))
    output_names = [path.name for path in output_paths]

    if input_names != expected_names:
        raise ValueError("Input không đủ EC_001 đến EC_050")
    if output_names != expected_names:
        raise ValueError("Output không đủ EC_001 đến EC_050")

    verifier = VerifierAgent(DataStore())
    issue_counts: Counter = Counter()

    for output_path in output_paths:
        result = CaseOutput.model_validate_json(
            output_path.read_text(encoding="utf-8")
        )
        if result.case_id != output_path.stem:
            raise ValueError(
                f"{output_path.name}: case_id không khớp tên file"
            )
        verifier.verify(result)
        issue_counts[result.case_assessment.primary_issue] += 1

    trace_path = LOGGING_DIR / "trace.jsonl"
    events = [
        json.loads(line)
        for line in trace_path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    if len(events) != 300:
        raise ValueError(
            f"Trace phải có 300 event, hiện có {len(events)}"
        )
    if [event["sequence"] for event in events] != list(
        range(1, 301)
    ):
        raise ValueError("Trace sequence không liên tục từ 1 đến 300")

    event_counts = Counter(event["case_id"] for event in events)
    if set(event_counts.values()) != {6} or len(event_counts) != 50:
        raise ValueError("Mỗi case phải có đúng 6 trace event")

    verifier_counts = Counter(
        event["case_id"]
        for event in events
        if event["agent"] == "verifier_agent"
        and event["output_summary"].get("valid") is True
    )
    if set(verifier_counts.values()) != {1} or len(verifier_counts) != 50:
        raise ValueError("Mỗi case phải có một verifier event hợp lệ")

    metadata = json.loads(
        (LOGGING_DIR / "metadata.json").read_text(encoding="utf-8")
    )
    if metadata.get("model_provider") != MODEL_PROVIDER:
        raise ValueError("metadata model_provider không khớp source")
    if metadata.get("model_name") != MODEL_NAME:
        raise ValueError("metadata model_name không khớp source")
    if metadata.get("processed_cases") != 50:
        raise ValueError("metadata processed_cases phải là 50")

    print("VALID: 50 outputs, 300 trace events, metadata matched")
    for issue, count in sorted(issue_counts.items()):
        print(f"  {issue}: {count}")


if __name__ == "__main__":
    main()
