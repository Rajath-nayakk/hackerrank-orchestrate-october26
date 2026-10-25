# Evaluation Report: Ghost Data Still Exists

## 1. Executive Summary

This report documents the evaluation of the AI-powered deletion-audit agent developed for HackerRank Orchestrate (October 2026): **Ghost Data Still Exists**.

The solution implements a deterministic, multi-source evidence auditing engine that:
1. Reconstructs current and historical identity graphs (emails, phone numbers, names, and cryptographic SHA256 email hashes) from `user_identities.csv` and `user_audit_log.csv`.
2. Classifies user request intent according to privacy regulations (distinguishing genuine deletion requests from portability, access, rectification, or marketing opt-outs).
3. Indexes and parses 94 multi-format evidence files across SQLite relational databases, JSON snapshots, pipe-delimited records, ReportLab PDFs, and distributed service logs.
4. Performs temporal cutoff enforcement at each request's `audit_at` timestamp.
5. Applies the formal deletion policy defined in `deletion_rules.csv`, accounting for retention exceptions (Rule 12: Security Audit Logs), marketing profile distinctions (Rule 10), and account tombstones (Rule 15).
6. Generates canonically sorted, numbered findings, remediation plans, and post-remediation verification checks.

---

## 2. Sample Evaluation Metrics

The solution was evaluated against the public benchmark of 32 requests in `dataset/sample_deletion_requests.csv` with known ground truth in `dataset/sample_output.csv`.

| Metric | Previous Reported | Final Refined Result | Improvement |
|---|---|---|---|
| **Case-Level Deletion-Status Accuracy** | 31 / 32 (96.88%) | **32 / 32 (100.00%)** | **+3.12% (100% status match)** |
| **Step-Level & Field-Level Accuracy** | 145 / 193 (75.13%) | **188 / 193 (97.41%)** | **+22.28%** |
| **Exact Step-Sequence Accuracy** | 16 / 32 (50.00%) | **28 / 32 (87.50%)** | **+37.50%** |
| **Total Predicted Steps** | 218 | **188** | Reference ground truth: 193 |
| **Total Evaluated Cases** | 32 | **32** | 100% test coverage |

### Case-Level Status Breakdown
- **True Positives (INCOMPLETE)**: 21 / 21 (100%)
- **True Negatives (COMPLETE)**: 10 / 10 (100%)
- **Non-Deletion Requests (NOT_APPLICABLE)**: 1 / 1 (100%)
- **Status Accuracy**: **100.00%** (0 false complete, 0 false incomplete)

---

## 3. Synthetic Evaluation Cases

In accordance with AGENTS.md §6.8, three distinct synthetic evaluation cases were constructed, verified, and automated in `tests/test_deletion_audit.py`:

### Synthetic Case 1: Compliant Account Tombstone with Retained Audit Log
- **Scenario**: Subject requested permanent erasure under GDPR. At `audit_at`, the primary account profile in `account_service` has been removed. An `ACCOUNT_TOMBSTONE` exists in `identity_service` where direct PII (name, email, phone) has been redacted, preserving only the stable internal identifier `user_syn_01`. A security audit record `audit_record_syn_01` exists within the mandatory compliance retention window.
- **Applicable Rules**: Rule 01 (Delete Profile), Rule 12 (Retain Security Audit Log), Rule 15 (Redact Tombstone).
- **Decision**: `COMPLETE`
- **Verification Steps**:
  1. `VERIFY_RECORD_ABSENT` on `account_service` (`account_syn_01`, state: `ABSENT`)
  2. `VERIFY_RECORD_PRESENT` on `security_service` (`audit_record_syn_01`, state: `PRESENT`)
  3. `VERIFY_RECORD_REDACTED` on `identity_service` (`tombstone_syn_01`, state: `REDACTED`)

### Synthetic Case 2: Incomplete Deletion with Active Data Flow and Support Attachment
- **Scenario**: Workflow reported `COMPLETE`, but forensic evidence reveals:
  1. `integration_service` active pipeline `data_flow_syn_02` continues replicating customer events to an external partner.
  2. `support_platform` contains an un-deleted attachment `support_att_02` containing sensitive customer passport scans.
- **Applicable Rules**: Rule 06 (Delete Support Attachment), Deletion Decision Rules (Disable data flows before dependent record deletions).
- **Decision**: `INCOMPLETE`
- **Ordered Plan**:
  - **FINDING 1**: `REPORT_ACTIVE_DATA_FLOW` on `integration_service` (`data_flow_syn_02`, state: `ACTIVE`)
  - **FINDING 2**: `REPORT_REMAINING_RECORD` on `support_platform` (`support_att_02`, state: `PRESENT`)
  - **REMEDIATION 1**: `DISABLE_DATA_FLOW` on `integration_service` (`data_flow_syn_02`, state: `DISABLED`)
  - **REMEDIATION 2**: `DELETE_RECORD` on `support_platform` (`support_att_02`, state: `ABSENT`)
  - **VERIFICATION 1-4**: `VERIFY_RECORD_ABSENT` on `account_service`, `VERIFY_RECORD_ABSENT` on `support_platform`, `VERIFY_RECORD_PRESENT` on `security_service`, `VERIFY_DATA_FLOW_DISABLED` on `integration_service`.

### Synthetic Case 3: Unauthorized Data Portability Request
- **Scenario**: Subject submitted request text: *"Under Article 20, please generate and download a full export of all my purchase transactions and activity logs in JSON format."*
- **Policy Decision**: The request text is an Article 20 data portability request, not an erasure authorization under Article 17. Even if internal systems recorded `reported_status: NOT_STARTED`, the case is classified as non-deletion.
- **Decision**: `NOT_APPLICABLE`
- **Output**: `steps_json = []`

---

## 4. Root-Cause Analysis and Forensic Improvements

During diagnostic analysis of mismatched cases against public sample ground truth, specific failure causes were isolated and resolved through general evidence-grounded logic without hardcoding:

1. **String Literal Null Parsing in Service Logs (`case_03`)**:
   - *Issue*: In `evidence_94`, `analytics_9406` had `customer_reference=null email=null phone=null`. Python key-value parsers parsed `"null"` as a truthy string (`bool("null") == True`), falsely flagging `PII_EXPOSED` and yielding `INCOMPLETE`.
   - *Fix*: Standardized log token sanitization converting `"null"` and `"none"` strings to Python `None`. This correctly identified `analytics_9406` as `ANONYMIZED`, resolving the single incorrect status prediction and bringing **Status Accuracy to 100.00%**.

2. **Rule 10 Marketing Profiles vs Analytics Profiles (`case_12`)**:
   - *Issue*: An analytics profile with `email_opt_in=true` was previously treated as an analytics profile requiring `ANONYMIZE_RECORD`.
   - *Fix*: Governed by Rule 10 in `deletion_rules.csv`, records with opt-in marketing flags are categorized as `MARKETING_PROFILE` requiring complete deletion (`DELETE_RECORD` and `VERIFY_RECORD_ABSENT`).

3. **Global Direct Evidence Account Locking (`case_22`)**:
   - *Issue*: Accounts directly cited in evidence (e.g. `account_6138` via trace `tr-1225047` in `evidence_06`) were previously not locked globally. When evaluating later batch timestamps, greedy matching allowed subsequent requests to steal the already-assigned account.
   - *Fix*: Direct evidence account assignments are locked globally at initialization, preventing greedy duplication. `case_22` correctly receives its true account `account_4990`.

4. **Temporal Causality in Deletion Activity Matching (`case_30` vs `case_04`)**:
   - *Issue*: `account_4163` activity occurred at `2026-08-27T10:55:42Z`. A greedy symmetric time window previously allowed `case_04` (`reported_at: 08:54:00Z`) to match an operation that occurred 2 hours *after* it was reported.
   - *Fix*: Enforced temporal causality (`activity_time <= reported_at + 5min`). `account_4163` correctly maps to `case_30` (`reported_at: 12:00:00Z`), allowing `case_04` to verify its true account `account_004`.

5. **Continuous Workflow Session Clustering (`case_25`, `case_26`, `case_27`, `case_28`)**:
   - *Issue*: Batch activities spanning across clock-hour boundaries (e.g. starting at 10:45Z and concluding at 11:35Z) were split when grouping strictly by hour strings (`[:13]`), severing the link between account deletions and their accompanying anonymized analytics profiles.
   - *Fix*: Replaced clock-hour string grouping with continuous session clustering (gap <= 45 minutes) and chronological result pairing (`SUCCESS` accounts paired with `SUCCESS` analytics).

6. **Exclusion of Non-Violated Analytics from Incomplete Cases (`case_09`, `case_11`, `case_18`, `case_29`)**:
   - *Issue*: In incomplete deletion cases, non-violated analytics profiles were being added to the future verification checks even when no violation existed.
   - *Fix*: Strictly adhere to AGENTS.md §6.3: an `INCOMPLETE` plan includes only the findings, remediation operations, and verification checks covering those remediated resources, eliminating false positive verification steps.

---

## 5. Output Verification

- The final full audit was executed on all 518 cases from `dataset/deletion_requests.csv`.
- `output.csv` was written at the repository root containing 518 rows, perfectly sorted by `case_id` (`case_33` through `case_550`).
- Every row contains valid JSON array syntax and conforms strictly to the official contract.
