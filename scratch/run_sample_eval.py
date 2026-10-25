import os
import sys
import json
import csv

# Add code to sys.path
sys.path.insert(0, os.path.abspath("code"))

from auditor import DeletionAuditor

def evaluate_samples():
    requests_path = os.path.join("dataset", "sample_deletion_requests.csv")
    truth_path = os.path.join("dataset", "sample_output.csv")
    
    # Load truth
    truth = {}
    with open(truth_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            truth[row["case_id"]] = {
                "deletion_status": row["deletion_status"],
                "steps": json.loads(row["steps_json"])
            }
            
    # Initialize auditor
    auditor = DeletionAuditor("dataset")
    
    # Load sample requests
    sample_requests = []
    with open(requests_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sample_requests.append(row)
            
    status_correct = 0
    total_cases = len(sample_requests)
    
    total_truth_steps = sum(len(truth[c["case_id"]]["steps"]) for c in sample_requests)
    total_pred_steps = 0
    matched_steps = 0
    exact_seq_cases = 0
    
    results_by_case = {}
    
    for row in sample_requests:
        cid = row["case_id"]
        pred_status, pred_steps = auditor.audit_case(row)
        total_pred_steps += len(pred_steps)
        
        t_info = truth[cid]
        t_status = t_info["deletion_status"]
        t_steps = t_info["steps"]
        
        if pred_status == t_status:
            status_correct += 1
            
        def step_key(s):
            return (s.get("phase"), s.get("system_id"), s.get("resource_id"), s.get("operation"), s.get("state"), s.get("evidence_id", ""))
            
        t_step_keys = [step_key(s) for s in t_steps]
        p_step_keys = [step_key(s) for s in pred_steps]
        
        case_matches = 0
        p_remaining = list(p_step_keys)
        for tk in t_step_keys:
            if tk in p_remaining:
                case_matches += 1
                p_remaining.remove(tk)
        matched_steps += case_matches
        
        is_exact_seq = (t_step_keys == p_step_keys)
        if is_exact_seq:
            exact_seq_cases += 1
            
        results_by_case[cid] = {
            "status_match": pred_status == t_status,
            "exact_seq": is_exact_seq,
            "pred_status": pred_status,
            "truth_status": t_status,
            "pred_steps_len": len(pred_steps),
            "truth_steps_len": len(t_steps),
            "matched_steps": case_matches
        }
        
    print(f"Sample Evaluation Results ({total_cases} cases):")
    print(f"Status Accuracy: {status_correct}/{total_cases} ({status_correct/total_cases*100:.2f}%)")
    print(f"Step Match: {matched_steps}/{total_truth_steps} ({matched_steps/total_truth_steps*100:.2f}%)")
    print(f"Total Predicted Steps: {total_pred_steps} (Truth: {total_truth_steps})")
    print(f"Exact Step Sequence: {exact_seq_cases}/{total_cases} ({exact_seq_cases/total_cases*100:.2f}%)")
    
    mismatches = [cid for cid, r in results_by_case.items() if not r["exact_seq"]]
    print(f"Cases with non-exact sequence ({len(mismatches)}): {mismatches}")

if __name__ == "__main__":
    evaluate_samples()
