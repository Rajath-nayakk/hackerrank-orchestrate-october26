"""
HackerRank Orchestrate October 2026: Ghost Data Still Exists
Main entry point for deletion-audit agent.
Produces output.csv with columns: case_id,deletion_status,steps_json
"""

import os
import sys
import csv
import json
import argparse
from typing import Dict, Any, List

from auditor import DeletionAuditor


def sort_case_key(cid: str) -> int:
    try:
        if cid.startswith("case_"):
            return int(cid[5:])
        return int(cid)
    except Exception:
        return 999999


def run_audit(dataset_dir: str = "dataset",
              input_csv: str = "dataset/deletion_requests.csv",
              output_csv: str = "output.csv"):
    print(f"[*] Initializing DeletionAuditor with dataset directory: {dataset_dir}")
    auditor = DeletionAuditor(dataset_dir)

    print(f"[*] Reading input cases from: {input_csv}")
    with open(input_csv, "r", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        cases = list(reader)

    print(f"[*] Loaded {len(cases)} cases to audit.")

    # Sort cases by case_id
    cases.sort(key=lambda c: sort_case_key(c["case_id"]))

    results = []
    status_counts = {"COMPLETE": 0, "INCOMPLETE": 0, "NOT_APPLICABLE": 0}

    for idx, case in enumerate(cases, 1):
        cid = case["case_id"]
        status, steps = auditor.audit_case(case)
        status_counts[status] = status_counts.get(status, 0) + 1

        steps_json_str = json.dumps(steps, separators=(",", ":"))
        results.append({
            "case_id": cid,
            "deletion_status": status,
            "steps_json": steps_json_str
        })

        if idx % 50 == 0 or idx == len(cases):
            print(f"    Progress: {idx}/{len(cases)} cases audited...")

    print(f"[*] Writing results to {output_csv}...")
    with open(output_csv, "w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["case_id", "deletion_status", "steps_json"])
        for r in results:
            writer.writerow([r["case_id"], r["deletion_status"], r["steps_json"]])

    print("[*] Deletion audit completed successfully!")
    print(f"    Total rows written: {len(results)}")
    print(f"    Status breakdown: {status_counts}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Ghost Data Still Exists: Deletion Audit Agent")
    parser.add_argument("--dataset-dir", default="dataset", help="Path to dataset directory")
    parser.add_argument("--input", default="dataset/deletion_requests.csv", help="Input CSV path")
    parser.add_argument("--output", default="output.csv", help="Output CSV path")
    args = parser.parse_args()

    run_audit(dataset_dir=args.dataset_dir, input_csv=args.input, output_csv=args.output)


if __name__ == "__main__":
    main()
