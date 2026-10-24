# Ghost Data Still Exists: System Discovery & Contract Analysis

## 1. Discovered Dataset Files & Schemas

The official evaluation and context files are located in `dataset/`:

| File Path | Rows | Columns / Schema | Purpose |
|---|---|---|---|
| `dataset/deletion_requests.csv` | 518 | `case_id,email,requested_at,reported_status,reported_at,audit_at,request_text` | Official evaluation requests (`case_33` to `case_550`). |
| `dataset/sample_deletion_requests.csv` | 32 | `case_id,email,requested_at,reported_status,reported_at,audit_at,request_text` | Public sample cases (`case_01` to `case_32`). |
| `dataset/sample_output.csv` | 32 | `case_id,deletion_status,steps_json` | Ground truth solutions for the 32 sample cases. |
| `dataset/user_identities.csv` | 550 | `user_id,name,email,phone,email_hash,updated_at` | Current authoritative identity snapshots for `user_01` through `user_550`. |
| `dataset/user_audit_log.csv` | 240 | `audit_id,user_id,changed_at,field_name,old_value,new_value` | Historical identity changes (primarily `email`, `phone`, `name`) for identity resolution. |
| `dataset/system_activity.csv` | 4011 | `activity_id,event_time,event_type,source_system,target_system,resource_id,reported_result,details` | Global log stream of system operations (deletions, syncs, index queries, exports, backups). |
| `dataset/deletion_rules.csv` | 15 | `rule_id,data_category,condition,required_action` | Canonical retention/redaction/anonymization policies across data categories. |
| `dataset/evidence_files.csv` | 94 | `file_id,file_path,origin,captured_at` | Manifest indexing all 94 evidence artifacts across 5 evidence categories. |
| `dataset/output.csv` | 0 | `case_id,deletion_status,steps_json` | Blank template indicating the required submission format. |

### Evidence Files Distribution (94 Files)
- **JSON Records (`.json`) [28 files]**:
  - `service_resource_export_*.json` (11 files): Snapshots of service endpoints (`account_service`, `analytics_platform`, `backup_service`, `export_service`, `integration_service`, `search_service`, `security_service`, `support_platform`).
  - `customer_data_snapshot_bundle_*.json` (12 files): Multi-store snapshots covering account, identity (tombstones), and security audit events.
  - `customer_export_jobs_*.json` (2 files): Scheduled export archives and object references.
  - `customer_analytics_report_*.json` (2 files): Analytics cohort and profile dumps.
- **SQL Snapshots (`.sql`) [24 files]**:
  - `customer_data_inventory_*.sql` (11 files): SQLite-compatible multi-table snapshots (`customer_profiles`, `customer_search_documents`, `customer_analytics_profiles`, `support_records`, `customer_exports`, `connector_subscriptions`, `backup_restore_entries`, `security_audit_records`).
  - `customer_data_read_replica_*.sql` (5 files): Read replica table snapshots for checking replication lag/drift.
  - `customer_accounts_failover_replica_*.sql` (1 file): Failover replica snapshot for `account_service`.
  - `customer_search_primary_*.sql` (1 file): Primary index document snapshot.
  - `customer_data_regional_replicas_*.sql` (3 files): Regional database replica captures.
  - `customer_data_reporting_replica_*.sql` (2 files): Reporting replica table captures.
  - `customer_account_history_*.sql` (1 file): Historical account state snapshots.
- **Log Files (`.log`) [26 files]**:
  - `central_observability_export_*.log` (12 files): JSON lines structured observability logs containing trace spans, query executions, and resource status.
  - `service_readback_logs_*.log` (11 files): JSON lines log traces validating readback consistency.
  - `resource_lookup_trace_*.log` (1 file): Diagnostic traces for resource lookups.
  - `support_replica_*.log` (1 file): Support ticket replication traces.
  - `structured_service_events_*.log` (1 file): Detailed regional service log lines.
- **Image Dashboards (`.png`) [11 files]**:
  - Dashboard UI screenshots (`dataset/evidence/images/`): System console captures corresponding to `LINK_RESOURCE_IDENTITY` activities in `system_activity.csv`.
- **PDF Documents (`.pdf`) [4 files]**:
  - ReportLab-generated documents (`dataset/evidence/documents/`) using FlateDecode + ASCII85 encoding (`delivery_correction_attachment.pdf`, `account_history_report_20260718.pdf`, `legal_retention_register_20260529.pdf`, `security_retention_extract.pdf`).
- **Plain Text (`.txt`) [1 file]**:
  - `customer_account_handover_20261001.txt`: Manual support/operations handover logs.

---

## 2. Verified Relationships and Join Keys

1. **User Identity Resolution**:
   - `deletion_requests.csv.email` links either to `user_identities.csv.email` (current snapshot) OR to `user_audit_log.csv.old_value` / `new_value` where `field_name = 'email'`.
   - Once resolved, the canonical `user_id`, current name, current email, phone, and `email_hash` form the subject's identity profile.
   - 100% of the 518 evaluation cases and 32 sample cases map cleanly to a single unique `user_id`.

2. **Temporal Audit Cutoff (`audit_at`)**:
   - Every case defines an exact point-in-time timestamp: `audit_at`.
   - Cases in `deletion_requests.csv` group into 72 distinct audit cutoff batches (typically 10 cases per batch).
   - Only evidence with `captured_at <= audit_at` is legally admissible as proof of state at audit time. Evidence captured after `audit_at` must never be cited or used to alter the audit verdict.

3. **Request Intent Classification (`NOT_APPLICABLE`)**:
   - Cases where `request_text` does not explicitly demand personal data erasure (e.g., subject access requests, invoice copies, data rectification, marketing opt-outs) evaluate to `deletion_status = "NOT_APPLICABLE"` and `steps_json = []`.
   - In `deletion_requests.csv`, exactly 10 cases (`case_533` to `case_542`) are non-deletion requests.

4. **Resource Linking Across Systems**:
   - Every subject is linked to system-specific resource IDs:
     - `account_service`: Primary profile `account_XXXX` (recorded in deletion activities in `system_activity.csv` between `requested_at` and `reported_at`, or found in database snapshots).
     - `security_service`: Security audit record `audit_record_XXXX` (retained by policy under `rule_12`).
     - `search_service`: Index document `search_XXXX`.
     - `support_platform`: Support ticket/attachment `support_XXXX`.
     - `analytics_platform`: Behavioral cohort record `analytics_XXXX`.
     - `export_service`: Export file `export_XXXX`.
     - `integration_service`: Active sync connector `data_flow_XXXX`.
     - `backup_service`: Backup restore target `backup_XXXX`.
     - `identity_service`: Tombstone record `tombstone_XXXX`.

---

## 3. Policy Engine & Allowed Operations

Applying `deletion_rules.csv`:

| Data Category | Target System | Required Action | Finding Op (State) | Remediation Op (State) | Verification Op (State) |
|---|---|---|---|---|---|
| `USER_PROFILE` | `account_service` | `DELETE` | `REPORT_REMAINING_RECORD` (`PRESENT`) | `DELETE_RECORD` (`ABSENT`) | `VERIFY_RECORD_ABSENT` (`ABSENT`) |
| `SEARCH_INDEX_ENTRY` | `search_service` | `DELETE` | `REPORT_REMAINING_RECORD` (`PRESENT`) | `DELETE_RECORD` (`ABSENT`) | `VERIFY_RECORD_ABSENT` (`ABSENT`) |
| `USER_EXPORT` | `export_service` | `DELETE` | `REPORT_REMAINING_RECORD` (`PRESENT`) | `DELETE_RECORD` (`ABSENT`) | `VERIFY_RECORD_ABSENT` (`ABSENT`) |
| `SUPPORT_MESSAGE` | `support_platform` | `REDACT` | `REPORT_EXPOSED_PII` (`PRESENT`) | `REDACT_RECORD` (`REDACTED`) | `VERIFY_RECORD_REDACTED` (`REDACTED`) |
| `ANALYTICS_PROFILE` | `analytics_platform` | `ANONYMIZE` | `REPORT_EXPOSED_PII` (`PRESENT`) | `ANONYMIZE_RECORD` (`ANONYMIZED`) | `VERIFY_RECORD_ANONYMIZED` (`ANONYMIZED`) |
| `ACCOUNT_TOMBSTONE` | `identity_service` | `REDACT` | `REPORT_EXPOSED_PII` (`PRESENT`) | `REDACT_RECORD` (`REDACTED`) | `VERIFY_RECORD_REDACTED` (`REDACTED`) |
| Connector / Sync | `integration_service` | `DISABLE` | `REPORT_ACTIVE_DATA_FLOW` (`ACTIVE`) | `DISABLE_DATA_FLOW` (`DISABLED`) | `VERIFY_DATA_FLOW_DISABLED` (`DISABLED`) |
| Backup Restore | `backup_service` | `BLOCK` | `REPORT_RESTORE_RISK` (`ACTIVE`) | `BLOCK_RESTORE` (`BLOCKED`) | `VERIFY_RESTORE_BLOCKED` (`BLOCKED`) |
| `SECURITY_AUDIT_LOG` | `security_service` | `RETAIN` | N/A (compliant) | N/A | `VERIFY_RECORD_PRESENT` (`PRESENT`) |

### Canonical Sorting Contract
1. **Phases**: `FINDING` -> `REMEDIATION` -> `VERIFICATION`.
2. **Operations within Phase**:
   - Finding: `REPORT_REMAINING_RECORD` -> `REPORT_EXPOSED_PII` -> `REPORT_ACTIVE_DATA_FLOW` -> `REPORT_RESTORE_RISK`.
   - Remediation: `DISABLE_DATA_FLOW` -> `BLOCK_RESTORE` -> `DELETE_RECORD` -> `REDACT_RECORD` -> `ANONYMIZE_RECORD`.
   - Verification: `VERIFY_RECORD_ABSENT` -> `VERIFY_RECORD_PRESENT` -> `VERIFY_RECORD_REDACTED` -> `VERIFY_RECORD_ANONYMIZED` -> `VERIFY_DATA_FLOW_DISABLED` -> `VERIFY_RESTORE_BLOCKED`.
3. **Tie-breaking**: `system_id` ascending, then `resource_id` ascending.
4. **Step Numbering**: Strictly consecutive integers starting at `1`.

### Evidence Citation Contract
- For `COMPLETE` cases: All verification steps cite valid participant-visible evidence (`file_id`) captured at or before `audit_at` proving the compliant state.
- For `INCOMPLETE` cases: Findings cite participant-visible evidence proving non-compliance. Future remediation and future verification steps use empty `evidence_id: ""`.
