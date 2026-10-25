import os
import sys
import json
import csv
import zipfile
import subprocess

REPO_ROOT = r"c:\Users\Rajath Nayak\OneDrive\Desktop\hackerrank-orchestrate-october26"
PYTHON_EXE = r"C:\Users\Rajath Nayak\AppData\Local\Python\pythoncore-3.14-64\python.exe"

def check_output_csv():
    path = os.path.join(REPO_ROOT, "output.csv")
    if not os.path.exists(path):
        return False, "output.csv missing"
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        if header != ["case_id", "deletion_status", "steps_json"]:
            return False, f"Invalid header: {header}"
        rows = list(reader)
    if len(rows) != 518:
        return False, f"Row count is {len(rows)}, expected 518"
    
    # check sorted by case_id
    case_ids = [r[0] for r in rows]
    # check integer sort or string sort? Usually case_id format case_33 to case_550
    # Let's check both
    def key_func(cid):
        # extracts number or string
        parts = cid.split("_")
        if len(parts) == 2 and parts[1].isdigit():
            return int(parts[1])
        return cid
    
    # verify each row
    statuses = set()
    for idx, (cid, status, steps_str) in enumerate(rows):
        if status not in ("COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"):
            return False, f"Invalid status {status} at row {idx+1}"
        statuses.add(status)
        try:
            steps = json.loads(steps_str)
            if not isinstance(steps, list):
                return False, f"steps_json is not a list at {cid}"
            if status == "NOT_APPLICABLE" and len(steps) != 0:
                return False, f"NOT_APPLICABLE must have steps_json=[] at {cid}"
            for s_idx, step in enumerate(steps):
                if step.get("step_no") != s_idx + 1:
                    return False, f"step_no mismatch at {cid}: expected {s_idx+1}, got {step.get('step_no')}"
                if step.get("phase") not in ("FINDING", "REMEDIATION", "VERIFICATION"):
                    return False, f"invalid phase {step.get('phase')} at {cid}"
        except Exception as e:
            return False, f"JSON error at {cid}: {e}"

    return True, f"518 rows, valid schema, statuses: {statuses}"

def main():
    print("--- 1. Checking output.csv ---")
    ok, msg = check_output_csv()
    print("output.csv check:", ok, msg)

if __name__ == "__main__":
    main()
