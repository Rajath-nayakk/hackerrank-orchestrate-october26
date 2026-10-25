import os
import sys
import json
import csv

sys.path.insert(0, os.path.abspath("code"))
from auditor import DeletionAuditor

truth_path = os.path.join("dataset", "sample_output.csv")
truth = {}
with open(truth_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        truth[row["case_id"]] = {
            "deletion_status": row["deletion_status"],
            "steps": json.loads(row["steps_json"])
        }

auditor = DeletionAuditor("dataset")
requests_path = os.path.join("dataset", "sample_deletion_requests.csv")
sample_requests = []
with open(requests_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        sample_requests.append(row)

for row in sample_requests:
    cid = row["case_id"]
    if cid in ['case_04', 'case_18', 'case_20', 'case_23']:
        pred_status, pred_steps = auditor.audit_case(row)
        t_info = truth[cid]
        print(f"\n=== {cid} ===")
        print(f"Status: Pred={pred_status}, Truth={t_info['deletion_status']}")
        print("Expected steps:")
        for s in t_info['steps']:
            print(f"  {s['step_no']}. {s['phase']} | {s['system_id']} | {s['resource_id']} | {s['operation']} | {s['state']} | {s['evidence_id']}")
        print("Predicted steps:")
        for s in pred_steps:
            print(f"  {s['step_no']}. {s['phase']} | {s['system_id']} | {s['resource_id']} | {s['operation']} | {s['state']} | {s['evidence_id']}")
