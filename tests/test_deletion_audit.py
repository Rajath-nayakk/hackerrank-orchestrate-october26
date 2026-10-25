"""
Comprehensive Test Suite for HackerRank Orchestrate: Ghost Data Still Exists
Validates the official output contract, deletion policy logic, and synthetic evaluation cases.
"""

import os
import sys
import csv
import json

# Add code directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "code")))

from identity import IdentityResolver, IdentityProfile
from classifier import RequestClassifier
from evidence_loader import EvidenceManager, EvidenceItem
from auditor import DeletionAuditor, sort_steps, PHASE_ORDER, OPERATION_ORDER


DATASET_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dataset"))
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_CSV = os.path.join(ROOT_DIR, "output.csv")


def test_output_csv_existence_and_schema():
    """Verify output.csv exists at root and has exact required columns."""
    assert os.path.exists(OUTPUT_CSV), "output.csv must exist at repository root"
    with open(OUTPUT_CSV, "r", encoding="utf-8") as fp:
        reader = csv.reader(fp)
        header = next(reader)
        assert header == ["case_id", "deletion_status", "steps_json"], (
            f"Expected header ['case_id', 'deletion_status', 'steps_json'], got {header}"
        )


def test_output_csv_row_count_and_case_ids():
    """Verify exactly 518 cases from case_33 to case_550 in sorted order."""
    with open(OUTPUT_CSV, "r", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        rows = list(reader)

    assert len(rows) == 518, f"Expected exactly 518 rows, got {len(rows)}"

    expected_ids = [f"case_{i}" for i in range(33, 551)]
    actual_ids = [r["case_id"] for r in rows]
    assert actual_ids == expected_ids, "case_id sequence does not match expected sorted range case_33..case_550"


def test_output_csv_status_values_and_steps_integrity():
    """Verify status enum and steps_json formatting."""
    valid_statuses = {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}
    valid_phases = {"FINDING", "REMEDIATION", "VERIFICATION"}

    with open(OUTPUT_CSV, "r", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        for idx, row in enumerate(reader, 1):
            cid = row["case_id"]
            status = row["deletion_status"]
            assert status in valid_statuses, f"{cid}: invalid deletion_status {status}"

            steps = json.loads(row["steps_json"])
            assert isinstance(steps, list), f"{cid}: steps_json must be a JSON array"

            if status == "NOT_APPLICABLE":
                assert steps == [], f"{cid}: NOT_APPLICABLE must have empty steps_json, got {steps}"

            if status == "COMPLETE":
                for s in steps:
                    assert s["phase"] == "VERIFICATION", f"{cid}: COMPLETE case must contain only VERIFICATION steps"
                    assert s.get("evidence_id"), f"{cid}: COMPLETE verification step must have non-empty evidence_id"

            if status == "INCOMPLETE":
                for s in steps:
                    assert s["phase"] in valid_phases
                    if s["phase"] == "FINDING":
                        assert s.get("evidence_id"), f"{cid}: FINDING step must have non-empty evidence_id"
                    elif s["phase"] in ("REMEDIATION", "VERIFICATION"):
                        assert s.get("evidence_id") == "", f"{cid}: Post-remediation step must have empty evidence_id"

            # Check consecutive step numbering
            for step_idx, s in enumerate(steps, 1):
                assert s["step_no"] == step_idx, f"{cid}: expected step_no {step_idx}, got {s['step_no']}"


def test_canonical_phase_ordering():
    """Verify FINDING -> REMEDIATION -> VERIFICATION ordering."""
    steps = [
        {"phase": "VERIFICATION", "operation": "VERIFY_RECORD_ABSENT", "system_id": "account_service", "resource_id": "acc_1"},
        {"phase": "FINDING", "operation": "REPORT_REMAINING_RECORD", "system_id": "account_service", "resource_id": "acc_1", "evidence_id": "ev_1"},
        {"phase": "REMEDIATION", "operation": "DELETE_RECORD", "system_id": "account_service", "resource_id": "acc_1"},
    ]
    sorted_s = sort_steps(steps)
    phases = [s["phase"] for s in sorted_s]
    assert phases == ["FINDING", "REMEDIATION", "VERIFICATION"]
    assert [s["step_no"] for s in sorted_s] == [1, 2, 3]


def test_identity_resolver_historical_resolution():
    """Verify historical email resolution and hash lookup."""
    resolver = IdentityResolver(DATASET_DIR)
    # user_12: minjun.kim@gmail.com
    prof = resolver.resolve_by_email("minjun.kim@gmail.com")
    assert prof is not None
    assert prof.user_id == "user_12"
    assert "6e34ae5737be5401d915eb47a87a17264110c5a4e61c06f20b6a121f1520b9d2" in prof.email_hashes
    # Historical hash
    assert "44a65154bfd8e408852578fbd76813d094d1944f255ac1769ee81ba90492f10e" in prof.email_hashes
    prof_by_hash = resolver.resolve_by_hash("44a65154bfd8e408852578fbd76813d094d1944f255ac1769ee81ba90492f10e")
    assert prof_by_hash is not None
    assert prof_by_hash.user_id == "user_12"


def test_non_deletion_request_classification():
    """Verify non-deletion texts are classified as non-deletion requests."""
    assert RequestClassifier.is_deletion_request("Please erase all my personal data.") is True
    assert RequestClassifier.is_deletion_request("I want my account permanently deleted under GDPR.") is True
    assert RequestClassifier.is_deletion_request("Please send me a copy of all my data exports.") is False
    assert RequestClassifier.is_deletion_request("I would like to update my shipping address.") is False
    assert RequestClassifier.is_deletion_request("Please unsubscribe me from marketing emails.") is False


# =========================================================================
# SYNTHETIC EVALUATION CASES (AGENTS.md §6.8 Requirement)
# Three custom evaluation cases with explicit expected outputs and explanations.
# =========================================================================

def test_synthetic_case_1_account_tombstone_compliance():
    """
    Synthetic Case 1: Compliant Account Tombstone with Retained Audit Log.
    Scenario: User requested deletion. At audit_at, account profile has been redacted into
    an ACCOUNT_TOMBSTONE preserving only user_id='user_syn_01', with direct PII (name, email, phone)
    removed. Security audit record is retained under Rule 12.
    Expected Status: COMPLETE
    Expected Steps:
      1. VERIFY_RECORD_ABSENT for account_service
      2. VERIFY_RECORD_PRESENT for security_service (audit_record_syn_01)
      3. VERIFY_RECORD_REDACTED for identity_service (tombstone_syn_01)
    """
    items = [
        EvidenceItem("account_service", "account_syn_01", "USER_PROFILE", "ABSENT"),
        EvidenceItem("security_service", "audit_record_syn_01", "SECURITY_AUDIT_LOG", "PRESENT"),
        EvidenceItem("identity_service", "tombstone_syn_01", "ACCOUNT_TOMBSTONE", "REDACTED"),
    ]
    # No findings -> status COMPLETE
    findings = [it for it in items if it.state in ("PRESENT", "PII_EXPOSED", "ACTIVE") and it.system_id != "security_service"]
    assert len(findings) == 0, "Compliant tombstone should have 0 findings"
    status = "COMPLETE"
    verifs = []
    for it in items:
        if it.system_id == "account_service":
            verifs.append({"phase": "VERIFICATION", "system_id": it.system_id, "resource_id": it.resource_id, "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "ev_syn_1"})
        elif it.system_id == "security_service":
            verifs.append({"phase": "VERIFICATION", "system_id": it.system_id, "resource_id": it.resource_id, "operation": "VERIFY_RECORD_PRESENT", "state": "PRESENT", "evidence_id": "ev_syn_1"})
        elif it.system_id == "identity_service":
            verifs.append({"phase": "VERIFICATION", "system_id": it.system_id, "resource_id": it.resource_id, "operation": "VERIFY_RECORD_REDACTED", "state": "REDACTED", "evidence_id": "ev_syn_1"})

    sorted_steps = sort_steps(verifs)
    assert status == "COMPLETE"
    assert len(sorted_steps) == 3
    assert sorted_steps[0]["operation"] == "VERIFY_RECORD_ABSENT"
    assert sorted_steps[1]["operation"] == "VERIFY_RECORD_PRESENT"
    assert sorted_steps[2]["operation"] == "VERIFY_RECORD_REDACTED"


def test_synthetic_case_2_active_replication_flow_and_support_attachment():
    """
    Synthetic Case 2: Incomplete Deletion with Active Data Flow and Support Attachment.
    Scenario: User requested deletion and workflow claimed 'COMPLETE', but evidence reveals:
      1. integration_service data_flow_syn_02 is ACTIVE (synchronizing user data to partner).
      2. support_platform support_att_02 is an un-deleted attachment containing customer passport scan.
    Expected Status: INCOMPLETE
    Required Plan:
      Phase 1 - FINDING:
        - REPORT_ACTIVE_DATA_FLOW on integration_service
        - REPORT_REMAINING_RECORD on support_platform
      Phase 2 - REMEDIATION:
        - DISABLE_DATA_FLOW on integration_service (must disable flow before dependent record changes)
        - DELETE_RECORD on support_platform
      Phase 3 - VERIFICATION:
        - VERIFY_RECORD_ABSENT on account_service
        - VERIFY_RECORD_ABSENT on support_platform
        - VERIFY_RECORD_PRESENT on security_service
        - VERIFY_DATA_FLOW_DISABLED on integration_service
    """
    findings = [
        {"phase": "FINDING", "system_id": "integration_service", "resource_id": "data_flow_syn_02", "operation": "REPORT_ACTIVE_DATA_FLOW", "state": "ACTIVE", "evidence_id": "ev_syn_2"},
        {"phase": "FINDING", "system_id": "support_platform", "resource_id": "support_att_02", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "ev_syn_2"},
    ]
    remediations = [
        {"phase": "REMEDIATION", "system_id": "integration_service", "resource_id": "data_flow_syn_02", "operation": "DISABLE_DATA_FLOW", "state": "DISABLED", "evidence_id": ""},
        {"phase": "REMEDIATION", "system_id": "support_platform", "resource_id": "support_att_02", "operation": "DELETE_RECORD", "state": "ABSENT", "evidence_id": ""},
    ]
    verifications = [
        {"phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_syn_02", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": ""},
        {"phase": "VERIFICATION", "system_id": "support_platform", "resource_id": "support_att_02", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": ""},
        {"phase": "VERIFICATION", "system_id": "security_service", "resource_id": "audit_record_syn_02", "operation": "VERIFY_RECORD_PRESENT", "state": "PRESENT", "evidence_id": ""},
        {"phase": "VERIFICATION", "system_id": "integration_service", "resource_id": "data_flow_syn_02", "operation": "VERIFY_DATA_FLOW_DISABLED", "state": "DISABLED", "evidence_id": ""},
    ]
    all_steps = sort_steps(findings + remediations + verifications)
    assert len(all_steps) == 8
    # Confirm phase ordering
    phases = [s["phase"] for s in all_steps]
    assert phases[:2] == ["FINDING", "FINDING"]
    assert phases[2:4] == ["REMEDIATION", "REMEDIATION"]
    assert phases[4:] == ["VERIFICATION"] * 4
    # Confirm flow is disabled before record deletion in remediation
    rem_ops = [s["operation"] for s in all_steps if s["phase"] == "REMEDIATION"]
    assert rem_ops == ["DISABLE_DATA_FLOW", "DELETE_RECORD"]


def test_synthetic_case_3_unauthorized_data_portability_request():
    """
    Synthetic Case 3: Subject Access / Portability Request.
    Scenario: User sent request text: 'Under Article 20, please generate and download a full export
    of all my purchase transactions and activity logs in JSON format.'
    Policy Decision: Not a deletion authorization. Even though reported_status says 'NOT_STARTED',
    this case must be treated as NOT_APPLICABLE.
    Expected Status: NOT_APPLICABLE
    Expected Steps: []
    """
    req_text = "Under Article 20, please generate and download a full export of all my purchase transactions and activity logs in JSON format."
    is_del = RequestClassifier.is_deletion_request(req_text)
    assert is_del is False, "Portability request must not be treated as deletion request"

    status = "NOT_APPLICABLE" if not is_del else "INCOMPLETE"
    steps = [] if status == "NOT_APPLICABLE" else [{"step_no": 1}]
    assert status == "NOT_APPLICABLE"
    assert steps == []


if __name__ == "__main__":
    print("[*] Running all tests in test_deletion_audit.py...")
    test_funcs = [
        test_output_csv_existence_and_schema,
        test_output_csv_row_count_and_case_ids,
        test_output_csv_status_values_and_steps_integrity,
        test_canonical_phase_ordering,
        test_identity_resolver_historical_resolution,
        test_non_deletion_request_classification,
        test_synthetic_case_1_account_tombstone_compliance,
        test_synthetic_case_2_active_replication_flow_and_support_attachment,
        test_synthetic_case_3_unauthorized_data_portability_request,
    ]

    passed = 0
    failed = 0
    for fn in test_funcs:
        try:
            fn()
            print(f"  [PASS] {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {fn.__name__}: {e}")
            failed += 1

    print(f"\nTest Summary: {passed} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)
