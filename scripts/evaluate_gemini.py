"""Live, opt-in evaluation on synthetic notes. Never report fixture labels as results."""

import argparse
import json
from pathlib import Path

from operations.domain.common import Problem
from operations.integrations.gemini import Gemini


def summarize(output):
    return {
        "completed": output["completed"],
        "equipment_id": output["equipment_id"],
        "installed": sum(
            m["quantity"] for m in output["materials"] if m["disposition"] == "installed"
        ),
        "returned": sum(
            m["quantity"] for m in output["materials"] if m["disposition"] == "unused_return"
        ),
        "has_unknowns": bool(output["unknowns"]),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fixtures", type=Path, default=Path("docs/backend/gemini-evaluation.json"))
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    suite = json.loads(args.fixtures.read_text())
    provider = Gemini()
    results = []
    for case in suite["cases"]:
        try:
            output, metadata = provider.extract(case["note"], suite["context"])
            observed = summarize(output)
            correct = {key: observed[key] == value for key, value in case["expected"].items()}
            results.append(
                {
                    "id": case["id"],
                    "fields": correct,
                    "observed": observed,
                    "metadata": metadata,
                    "raw_extraction": output,
                }
            )
        except Problem as exc:
            results.append(
                {
                    "id": case["id"],
                    "error": exc.message,
                    "fields": {key: False for key in case["expected"]},
                }
            )
    total = sum(len(r["fields"]) for r in results)
    passed = sum(sum(r["fields"].values()) for r in results)
    report = {
        "dataset": "synthetic; not representative customer validation",
        "model": __import__("os").environ.get("GEMINI_MODEL"),
        "field_accuracy": passed / total if total else None,
        "correct_fields": passed,
        "total_fields": total,
        "failed_requests": sum("error" in r for r in results),
        "cases": results,
        "reviewer_effort": "Not measured by this script; record manual review/edit time separately.",
    }
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))


if __name__ == "__main__":
    main()
