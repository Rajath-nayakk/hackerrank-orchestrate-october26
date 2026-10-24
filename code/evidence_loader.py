"""
Ghost Data Still Exists: Evidence Loader & Entity Extraction Engine
Parses and indexes JSON, SQL, LOG, TXT, and PDF evidence files.
"""

import os
import csv
import json
import sqlite3
import re
import base64
import zlib
from typing import Dict, Any, List, Optional, Set
from datetime import datetime


def extract_pdf_text(filepath: str) -> str:
    """Extract text from ReportLab-style PDFs using ASCII85 + FlateDecode."""
    try:
        with open(filepath, "rb") as fp:
            raw = fp.read()
        objs = re.findall(rb"(\d+ \d+ obj.*?endobj)", raw, re.DOTALL)
        extracted = []
        for obj in objs:
            if b"/Filter" in obj and b"stream" in obj:
                idx = obj.find(b"stream")
                end = obj.find(b"endstream", idx)
                sraw = obj[idx + 6:end].strip()
                try:
                    if b"ASCII85Decode" in obj:
                        sraw = base64.a85decode(sraw, adobe=True)
                    if b"FlateDecode" in obj:
                        decomp = zlib.decompress(sraw)
                        strings = re.findall(rb"\((.*?)\)\s*Tj", decomp)
                        if strings:
                            extracted.append(" ".join(s.decode("latin1", "ignore") for s in strings))
                except Exception:
                    pass
        return " ".join(extracted)
    except Exception:
        return ""


class EvidenceItem:
    def __init__(self, system_id: str, resource_id: str, category: str, state: str,
                 user_id: Optional[str] = None, email: Optional[str] = None,
                 phone: Optional[str] = None, raw_data: Optional[Dict[str, Any]] = None,
                 evidence_id: Optional[str] = None):
        self.system_id = system_id
        self.resource_id = resource_id
        self.category = category
        self.state = state  # 'PRESENT', 'ABSENT', 'PII_EXPOSED', 'REDACTED', 'ANONYMIZED', 'ACTIVE', 'DISABLED', 'BLOCKED'
        self.user_id = user_id
        self.email = email.lower() if email else None
        self.phone = phone
        self.raw_data = raw_data or {}
        self.evidence_id = evidence_id

    def __repr__(self):
        return f"<EvidenceItem {self.system_id} | {self.resource_id} | {self.state} | uid={self.user_id} email={self.email} ev={self.evidence_id}>"


class EvidenceFile:
    def __init__(self, file_id: str, file_path: str, origin: str, captured_at: str, full_path: str):
        self.file_id = file_id
        self.file_path = file_path
        self.origin = origin
        self.captured_at = captured_at
        self.full_path = full_path
        self.items: List[EvidenceItem] = []
        self._parsed = False

    def parse(self):
        if self._parsed or not os.path.exists(self.full_path):
            return
        ext = os.path.splitext(self.full_path)[1].lower()
        if ext == ".json":
            self._parse_json()
        elif ext == ".sql":
            self._parse_sql()
        elif ext == ".log":
            self._parse_log()
        elif ext == ".txt":
            self._parse_txt()
        elif ext == ".pdf":
            self._parse_pdf()
        for it in self.items:
            if not it.evidence_id:
                it.evidence_id = self.file_id
        self._parsed = True

    def _parse_json(self):
        try:
            with open(self.full_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except Exception:
            return

        # 1. Service Resource Export format
        if "service_exports" in data:
            exports = data["service_exports"]
            # account_service
            for rec in exports.get("account_service", {}).get("profile_lookups", []):
                res_id = rec.get("resource_id")
                status_code = rec.get("status_code", 200)
                prof = rec.get("profile") or {}
                state = "ABSENT" if status_code == 404 else "PRESENT"
                self.items.append(EvidenceItem(
                    system_id="account_service",
                    resource_id=res_id,
                    category="USER_PROFILE",
                    state=state,
                    user_id=prof.get("customer_reference"),
                    email=prof.get("email"),
                    phone=prof.get("phone"),
                    raw_data=rec
                ))

            # analytics_platform
            for rec in exports.get("analytics_platform", {}).get("profiles", []):
                res_id = rec.get("resource_id")
                email = rec.get("email")
                phone = rec.get("phone")
                state = "PII_EXPOSED" if (email or phone) else "ANONYMIZED"
                self.items.append(EvidenceItem(
                    system_id="analytics_platform",
                    resource_id=res_id,
                    category="ANALYTICS_PROFILE",
                    state=state,
                    user_id=rec.get("customer_reference"),
                    email=email,
                    phone=phone,
                    raw_data=rec
                ))

            # backup_service
            for rec in exports.get("backup_service", {}).get("restore_entries", []):
                res_id = rec.get("resource_id")
                allowed = rec.get("restore_allowed", False)
                state = "ACTIVE" if allowed else "BLOCKED"
                self.items.append(EvidenceItem(
                    system_id="backup_service",
                    resource_id=res_id,
                    category="BACKUP_ARCHIVE",
                    state=state,
                    user_id=rec.get("customer_reference"),
                    email=rec.get("customer_email"),
                    raw_data=rec
                ))

            # export_service
            for rec in exports.get("export_service", {}).get("exports", []):
                res_id = rec.get("resource_id")
                self.items.append(EvidenceItem(
                    system_id="export_service",
                    resource_id=res_id,
                    category="USER_EXPORT",
                    state="PRESENT",
                    user_id=rec.get("customer_reference"),
                    email=rec.get("owner_email"),
                    phone=rec.get("owner_phone"),
                    raw_data=rec
                ))

            # integration_service
            for rec in exports.get("integration_service", {}).get("connectors", []):
                res_id = rec.get("resource_id")
                enabled = rec.get("enabled", False)
                state = "ACTIVE" if enabled else "DISABLED"
                self.items.append(EvidenceItem(
                    system_id="integration_service",
                    resource_id=res_id,
                    category="DATA_FLOW",
                    state=state,
                    user_id=rec.get("customer_reference"),
                    email=rec.get("customer_email"),
                    raw_data=rec
                ))

            # search_service
            for rec in exports.get("search_service", {}).get("index_queries", []):
                res_id = rec.get("resource_id")
                hits = rec.get("hits", {}).get("documents", [])
                if hits:
                    doc = hits[0]
                    self.items.append(EvidenceItem(
                        system_id="search_service",
                        resource_id=res_id,
                        category="SEARCH_INDEX_ENTRY",
                        state="PRESENT",
                        user_id=doc.get("customer_reference"),
                        email=doc.get("email") or rec.get("query"),
                        phone=doc.get("phone"),
                        raw_data=rec
                    ))

            # security_service
            for rec in exports.get("security_service", {}).get("audit_records", []):
                res_id = rec.get("resource_id")
                self.items.append(EvidenceItem(
                    system_id="security_service",
                    resource_id=res_id,
                    category="SECURITY_AUDIT_LOG",
                    state="PRESENT",
                    user_id=rec.get("subject_reference"),
                    raw_data=rec
                ))

            # support_platform
            for rec in exports.get("support_platform", {}).get("tickets", []):
                res_id = rec.get("resource_id")
                email = rec.get("requester_email")
                phone = rec.get("requester_phone")
                name = rec.get("requester_name")
                state = "PII_EXPOSED" if (email or phone or name) else "REDACTED"
                self.items.append(EvidenceItem(
                    system_id="support_platform",
                    resource_id=res_id,
                    category="SUPPORT_MESSAGE",
                    state=state,
                    user_id=rec.get("customer_reference"),
                    email=email,
                    phone=phone,
                    raw_data=rec
                ))

        # 2. Customer Data Snapshot Bundle format
        elif "snapshots" in data:
            for s in data["snapshots"]:
                store = s.get("data_store")
                recs = s.get("records", [])
                if store == "account_service":
                    for rec in recs:
                        self.items.append(EvidenceItem(
                            system_id="account_service",
                            resource_id=rec.get("resource_id"),
                            category="USER_PROFILE",
                            state="PRESENT",
                            user_id=rec.get("user_id") or rec.get("customer_reference"),
                            email=rec.get("email"),
                            phone=rec.get("phone"),
                            raw_data=rec
                        ))
                elif store == "identity_service":
                    for rec in recs:
                        name = rec.get("name")
                        email = rec.get("email")
                        phone = rec.get("phone")
                        state = "PII_EXPOSED" if (name or email or phone) else "REDACTED"
                        self.items.append(EvidenceItem(
                            system_id="identity_service",
                            resource_id=rec.get("resource_id"),
                            category="ACCOUNT_TOMBSTONE",
                            state=state,
                            user_id=rec.get("subject_reference") or rec.get("user_id"),
                            email=email,
                            phone=phone,
                            raw_data=rec
                        ))
                elif store == "security_service":
                    for rec in recs:
                        self.items.append(EvidenceItem(
                            system_id="security_service",
                            resource_id=rec.get("resource_id"),
                            category="SECURITY_AUDIT_LOG",
                            state="PRESENT",
                            user_id=rec.get("subject_reference") or rec.get("user_id"),
                            raw_data=rec
                        ))

        # 3. Direct records collection format
        elif "records" in data:
            coll = data.get("collection", "")
            for rec in data.get("records", []):
                sys_id = rec.get("system") or rec.get("service")
                res_id = rec.get("resource_id")
                cat = rec.get("record_type", "")
                result = rec.get("result", "")
                sub = rec.get("subject_reference") or rec.get("customer_reference")
                email = rec.get("email") or rec.get("owner_email")
                phone = rec.get("phone") or rec.get("owner_phone")
                user_id = rec.get("user_id")

                if sub:
                    if "@" in str(sub):
                        email = str(sub)
                    elif str(sub).startswith("user_"):
                        user_id = str(sub)

                if coll == "customer_export_jobs":
                    sys_id = "export_service"
                    cat = "CUSTOMER_EXPORT"
                    state = "PRESENT" if rec.get("download_available") in (True, "true", 1) else "ABSENT"
                elif coll == "customer_analytics_report":
                    sys_id = "analytics_platform"
                    cat = "ANALYTICS_PROFILE"
                    state = "PII_EXPOSED" if (email or phone) else "ANONYMIZED"
                else:
                    if result in ("NOT_FOUND", "DELETED"):
                        state = "ABSENT"
                    elif result in ("FOUND", "PRESENT"):
                        state = "PRESENT"
                    elif result in ("ACTIVE", "DISABLED", "BLOCKED", "REDACTED", "ANONYMIZED"):
                        state = result
                    else:
                        state = "PRESENT"

                if sys_id and res_id:
                    self.items.append(EvidenceItem(
                        system_id=sys_id,
                        resource_id=res_id,
                        category=cat,
                        state=state,
                        user_id=user_id,
                        email=email,
                        phone=phone,
                        raw_data=rec
                    ))

    def _parse_sql(self):
        try:
            with open(self.full_path, "r", encoding="utf-8") as fp:
                sql = fp.read()
        except Exception:
            return

        con = sqlite3.connect(":memory:")
        try:
            con.executescript(sql)
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t[0] for t in cur.fetchall()]

            for tname in tables:
                cur.execute(f"PRAGMA table_info({tname})")
                cols = [c[1] for c in cur.fetchall()]

                # Case A: structured tables
                if "customer_profiles" in tname:
                    cur.execute(f"SELECT * FROM {tname}")
                    for row in cur.fetchall():
                        rd = dict(zip(cols, row))
                        status = rd.get("account_status", "ACTIVE")
                        state = "ABSENT" if status in ("DELETED", "NOT_FOUND") else "PRESENT"
                        self.items.append(EvidenceItem(
                            system_id="account_service",
                            resource_id=rd.get("resource_id"),
                            category="USER_PROFILE",
                            state=state,
                            user_id=rd.get("user_id") or rd.get("customer_reference"),
                            email=rd.get("email"),
                            phone=rd.get("phone"),
                            raw_data=rd
                        ))

                elif "search_documents" in tname:
                    cur.execute(f"SELECT * FROM {tname}")
                    for row in cur.fetchall():
                        rd = dict(zip(cols, row))
                        self.items.append(EvidenceItem(
                            system_id="search_service",
                            resource_id=rd.get("resource_id"),
                            category="SEARCH_INDEX_ENTRY",
                            state="PRESENT",
                            user_id=rd.get("customer_reference"),
                            email=rd.get("email"),
                            phone=rd.get("phone"),
                            raw_data=rd
                        ))

                elif "analytics_profiles" in tname:
                    cur.execute(f"SELECT * FROM {tname}")
                    for row in cur.fetchall():
                        rd = dict(zip(cols, row))
                        email = rd.get("email")
                        phone = rd.get("phone")
                        state = "PII_EXPOSED" if (email or phone) else "ANONYMIZED"
                        self.items.append(EvidenceItem(
                            system_id="analytics_platform",
                            resource_id=rd.get("resource_id"),
                            category="ANALYTICS_PROFILE",
                            state=state,
                            user_id=rd.get("customer_reference"),
                            email=email,
                            phone=phone,
                            raw_data=rd
                        ))

                elif "support_records" in tname:
                    cur.execute(f"SELECT * FROM {tname}")
                    for row in cur.fetchall():
                        rd = dict(zip(cols, row))
                        email = rd.get("requester_email")
                        phone = rd.get("requester_phone")
                        name = rd.get("requester_name")
                        state = "PII_EXPOSED" if (email or phone or name) else "REDACTED"
                        self.items.append(EvidenceItem(
                            system_id="support_platform",
                            resource_id=rd.get("resource_id"),
                            category="SUPPORT_MESSAGE",
                            state=state,
                            user_id=rd.get("customer_reference"),
                            email=email,
                            phone=phone,
                            raw_data=rd
                        ))

                elif "customer_exports" in tname:
                    cur.execute(f"SELECT * FROM {tname}")
                    for row in cur.fetchall():
                        rd = dict(zip(cols, row))
                        self.items.append(EvidenceItem(
                            system_id="export_service",
                            resource_id=rd.get("resource_id"),
                            category="USER_EXPORT",
                            state="PRESENT",
                            user_id=rd.get("customer_reference"),
                            email=rd.get("owner_email"),
                            phone=rd.get("owner_phone"),
                            raw_data=rd
                        ))

                elif "connector_subscriptions" in tname:
                    cur.execute(f"SELECT * FROM {tname}")
                    for row in cur.fetchall():
                        rd = dict(zip(cols, row))
                        enabled = bool(rd.get("enabled"))
                        state = "ACTIVE" if enabled else "DISABLED"
                        self.items.append(EvidenceItem(
                            system_id="integration_service",
                            resource_id=rd.get("resource_id"),
                            category="DATA_FLOW",
                            state=state,
                            user_id=rd.get("customer_reference"),
                            email=rd.get("customer_email"),
                            raw_data=rd
                        ))

                elif "backup_restore_entries" in tname:
                    cur.execute(f"SELECT * FROM {tname}")
                    for row in cur.fetchall():
                        rd = dict(zip(cols, row))
                        allowed = bool(rd.get("restore_allowed"))
                        state = "ACTIVE" if allowed else "BLOCKED"
                        self.items.append(EvidenceItem(
                            system_id="backup_service",
                            resource_id=rd.get("resource_id"),
                            category="BACKUP_ARCHIVE",
                            state=state,
                            user_id=rd.get("customer_reference"),
                            email=rd.get("customer_email"),
                            raw_data=rd
                        ))

                elif "security_audit_records" in tname:
                    cur.execute(f"SELECT * FROM {tname}")
                    for row in cur.fetchall():
                        rd = dict(zip(cols, row))
                        self.items.append(EvidenceItem(
                            system_id="security_service",
                            resource_id=rd.get("resource_id"),
                            category="SECURITY_AUDIT_LOG",
                            state="PRESENT",
                            user_id=rd.get("subject_reference"),
                            raw_data=rd
                        ))

                # Case B: payload_json / record_json tables (e.g. customer_data_primary, customer_data_read_replica, regional replicas)
                elif "payload_json" in cols or "record_json" in cols:
                    json_col = "payload_json" if "payload_json" in cols else "record_json"
                    sys_col = "service_name" if "service_name" in cols else ("origin_system" if "origin_system" in cols else cols[1])
                    cur.execute(f"SELECT resource_id, {sys_col}, {json_col} FROM {tname}")
                    for r_id, s_name, p_json in cur.fetchall():
                        try:
                            pj = json.loads(p_json)
                        except Exception:
                            pj = {}
                        if s_name == "account_service":
                            status = pj.get("account_status", "ACTIVE")
                            state = "ABSENT" if status in ("DELETED", "NOT_FOUND") else "PRESENT"
                            self.items.append(EvidenceItem(
                                system_id="account_service",
                                resource_id=r_id,
                                category="USER_PROFILE",
                                state=state,
                                user_id=pj.get("customer_reference") or pj.get("user_id"),
                                email=pj.get("email"),
                                phone=pj.get("phone"),
                                raw_data=pj
                            ))
                        elif s_name == "security_service":
                            self.items.append(EvidenceItem(
                                system_id="security_service",
                                resource_id=r_id,
                                category="SECURITY_AUDIT_LOG",
                                state="PRESENT",
                                user_id=pj.get("subject_reference") or pj.get("user_id"),
                                raw_data=pj
                            ))
                        elif s_name == "search_service":
                            doc = pj.get("document", {}) if isinstance(pj.get("document"), dict) else {}
                            self.items.append(EvidenceItem(
                                system_id="search_service",
                                resource_id=r_id,
                                category="SEARCH_INDEX_ENTRY",
                                state="PRESENT",
                                user_id=doc.get("customer_reference") or pj.get("customer_reference"),
                                email=doc.get("email") or pj.get("email"),
                                phone=doc.get("phone") or pj.get("phone"),
                                raw_data=pj
                            ))
                        elif s_name == "analytics_platform":
                            email = pj.get("email")
                            phone = pj.get("phone")
                            state = "PII_EXPOSED" if (email or phone) else "ANONYMIZED"
                            self.items.append(EvidenceItem(
                                system_id="analytics_platform",
                                resource_id=r_id,
                                category="ANALYTICS_PROFILE",
                                state=state,
                                user_id=pj.get("customer_reference") or pj.get("user_id"),
                                email=email,
                                phone=phone,
                                raw_data=pj
                            ))
                        elif s_name == "support_platform":
                            email = pj.get("requester_email") or pj.get("email")
                            phone = pj.get("requester_phone") or pj.get("phone")
                            name = pj.get("requester_name") or pj.get("name")
                            state = "PII_EXPOSED" if (email or phone or name) else "REDACTED"
                            self.items.append(EvidenceItem(
                                system_id="support_platform",
                                resource_id=r_id,
                                category="SUPPORT_MESSAGE",
                                state=state,
                                user_id=pj.get("customer_reference") or pj.get("user_id"),
                                email=email,
                                phone=phone,
                                raw_data=pj
                            ))
                        elif s_name == "integration_service":
                            enabled = pj.get("enabled", True)
                            state = "ACTIVE" if enabled in (True, "true", 1, "1") else "DISABLED"
                            self.items.append(EvidenceItem(
                                system_id="integration_service",
                                resource_id=r_id,
                                category="DATA_FLOW",
                                state=state,
                                user_id=pj.get("customer_reference") or pj.get("user_id"),
                                email=pj.get("customer_email") or pj.get("email"),
                                raw_data=pj
                            ))
                        elif s_name == "backup_service":
                            allowed = pj.get("restore_allowed", True)
                            del_block = pj.get("deletion_block", False)
                            state = "BLOCKED" if del_block or not allowed else "ACTIVE"
                            self.items.append(EvidenceItem(
                                system_id="backup_service",
                                resource_id=r_id,
                                category="BACKUP_ARCHIVE",
                                state=state,
                                user_id=pj.get("customer_reference") or pj.get("user_id"),
                                email=pj.get("customer_email") or pj.get("email"),
                                raw_data=pj
                            ))
        except Exception:
            pass

    def _parse_txt(self):
        try:
            with open(self.full_path, "r", encoding="utf-8", errors="ignore") as fp:
                for line in fp:
                    line = line.strip()
                    if not line.startswith("- "):
                        continue
                    parts = [p.strip() for p in line[2:].split("|")]
                    if len(parts) < 6:
                        continue
                    # timestamp | system | resource_id | category | status | identifier
                    _ts, sys_id, res_id, cat, status, ident = parts[:6]
                    ident_email = ident if "@" in ident else None
                    ident_user = ident if ident.startswith("user_") else None

                    state = "PRESENT"
                    if status in ("NOT_FOUND", "DELETED"):
                        state = "ABSENT"
                    elif status == "IDENTIFIABLE":
                        state = "PII_EXPOSED"
                    elif status == "ANONYMIZED":
                        state = "ANONYMIZED"
                    elif status == "ACTIVE":
                        state = "ACTIVE"
                    elif status in ("BLOCKED", "DISABLED"):
                        state = status
                    elif status == "FOUND":
                        state = "PRESENT"

                    self.items.append(EvidenceItem(
                        system_id=sys_id,
                        resource_id=res_id,
                        category=cat,
                        state=state,
                        user_id=ident_user,
                        email=ident_email,
                        raw_data={"line": line}
                    ))
        except Exception:
            pass

    def _parse_log(self):
        try:
            trace_map = {}
            with open(self.full_path, "r", encoding="utf-8", errors="ignore") as fp:
                for line in fp:
                    # JSON line
                    if line.strip().startswith("{") or "{" in line:
                        jstart = line.find("{")
                        jend = line.rfind("}")
                        if jstart != -1 and jend != -1:
                            try:
                                pj = json.loads(line[jstart:jend + 1])
                                self._process_log_dict(pj, trace_map)
                                continue
                            except Exception:
                                pass

                    # key=value line
                    kv_dict = {}
                    for match in re.finditer(r'([a-zA-Z0-9_]+)=([^\s"]+|"[^"]*")', line):
                        val = match.group(2).strip('"')
                        if val.lower() in ("null", "none"):
                            val = None
                        kv_dict[match.group(1)] = val
                    if kv_dict:
                        self._process_log_dict(kv_dict, trace_map)
        except Exception:
            pass

    def _process_log_dict(self, d: Dict[str, Any], trace_map: Dict[str, Any]):
        for k, v in list(d.items()):
            if isinstance(v, str) and v.lower() in ("null", "none"):
                d[k] = None

        tr = d.get("trace_id")
        sys_id = d.get("service") or d.get("source_system") or d.get("system_id") or ""
        res_id = d.get("resource_id")
        user_id = (d.get("subject_reference") or d.get("subject_ref") or d.get("customer_reference") or
                   d.get("lookup_key") or d.get("correlation_key") or d.get("subject_key"))
        email = d.get("customer_email") or d.get("requester_email") or d.get("email") or d.get("query")
        event = d.get("event") or d.get("event_type") or ""

        if user_id in ("null", "None", ""):
            user_id = None
        if email in ("null", "None", ""):
            email = None

        # Normalize system name
        if "support" in sys_id:
            sys_id = "support_platform"
        elif "account" in sys_id:
            sys_id = "account_service"
        elif "analytics" in sys_id:
            sys_id = "analytics_platform"
        elif "search" in sys_id:
            sys_id = "search_service"
        elif "export" in sys_id:
            sys_id = "export_service"
        elif "integration" in sys_id or "connector" in sys_id:
            sys_id = "integration_service"
        elif "backup" in sys_id:
            sys_id = "backup_service"
        elif "identity" in sys_id or "profile" in sys_id:
            sys_id = "identity_service"
        elif "security" in sys_id:
            sys_id = "security_service"

        if user_id and not str(user_id).startswith("user_"):
            if "@" in str(user_id):
                email = user_id
                user_id = None
            elif len(str(user_id)) == 64:  # SHA256 email hash
                d["_email_hash"] = str(user_id)
                user_id = None
            else:
                user_id = None

        if tr:
            if tr not in trace_map:
                trace_map[tr] = {}
            if user_id:
                trace_map[tr]["user_id"] = user_id
            if email:
                trace_map[tr]["email"] = email
            if res_id:
                trace_map[tr]["resource_id"] = res_id
            if sys_id:
                trace_map[tr]["system_id"] = sys_id

            # inherit
            user_id = user_id or trace_map[tr].get("user_id")
            email = email or trace_map[tr].get("email")
            res_id = res_id or trace_map[tr].get("resource_id")
            sys_id = sys_id or trace_map[tr].get("system_id")

        if not sys_id or not res_id:
            return

        if event.endswith("_started") or "query_started" in event:
            return

        state = "PRESENT"
        if sys_id == "account_service":
            status_code = d.get("http_status") or d.get("status_code")
            rows = d.get("rows")
            if status_code in (404, "404") or rows in (0, "0"):
                state = "ABSENT"
            else:
                state = "PRESENT"
            self.items.append(EvidenceItem(sys_id, res_id, "USER_PROFILE", state, user_id, email, raw_data=d))

        elif sys_id == "security_service":
            self.items.append(EvidenceItem(sys_id, res_id, "SECURITY_AUDIT_LOG", "PRESENT", user_id, email, raw_data=d))

        elif sys_id == "search_service":
            result = d.get("result")
            total_hits = d.get("total_hits")
            if result == "miss" or total_hits in (0, "0"):
                state = "ABSENT"
            else:
                state = "PRESENT"
            self.items.append(EvidenceItem(sys_id, res_id, "SEARCH_INDEX_ENTRY", state, user_id, email, raw_data=d))

        elif sys_id == "analytics_platform":
            if d.get("email_opt_in") in (True, "true", "True", 1, "1"):
                cat = "MARKETING_PROFILE"
                state = "PRESENT"
            else:
                cat = "ANALYTICS_PROFILE"
                state = "PII_EXPOSED" if (email or d.get("phone") or (user_id and not str(user_id).startswith("user_"))) else "ANONYMIZED"
            self.items.append(EvidenceItem(sys_id, res_id, cat, state, user_id, email, raw_data=d))

        elif sys_id == "support_platform":
            marker = d.get("marker_found")
            rows = d.get("rows")
            if marker in (False, "false", "False", 0, "0") or (rows and int(rows) > 0 and event in ("deletion_marker_check", "contact_query_completed")):
                state = "PRESENT"
                self.items.append(EvidenceItem(sys_id, res_id, "SUPPORT_MESSAGE", state, user_id, email, raw_data=d))
            else:
                state = "PII_EXPOSED" if (email or d.get("requester_name")) else "REDACTED"
                self.items.append(EvidenceItem(sys_id, res_id, "SUPPORT_MESSAGE", state, user_id, email, raw_data=d))

        elif sys_id == "integration_service":
            enabled = d.get("enabled")
            if enabled in (True, "true", 1, "1"):
                state = "ACTIVE"
            elif enabled in (False, "false", 0, "0") or d.get("last_delivery_status") == "stopped":
                state = "DISABLED"
            else:
                state = "ACTIVE"
            self.items.append(EvidenceItem(sys_id, res_id, "DATA_FLOW", state, user_id, email, raw_data=d))

        elif sys_id == "backup_service":
            allowed = d.get("restore_allowed")
            del_block = d.get("deletion_block")
            eligible = d.get("eligible")
            if allowed in (True, "true", 1, "1") or eligible in (True, "true", 1, "1") or del_block in (False, "false", 0, "0"):
                state = "ACTIVE"
            elif del_block in (True, "true", 1, "1") or allowed in (False, "false", 0, "0"):
                state = "BLOCKED"
            else:
                state = "BLOCKED"
            self.items.append(EvidenceItem(sys_id, res_id, "BACKUP_ARCHIVE", state, user_id, email, raw_data=d))

    def _parse_pdf(self):
        text = extract_pdf_text(self.full_path)
        if not text:
            return
        m_user = re.search(r"\b(user_\d+)\b", text)
        m_email = re.search(r"\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b", text)
        m_audit = re.search(r"\b(audit_record_\d+)\b", text)
        m_supp = re.search(r"\b(support_\d+)\b", text)

        uid = m_user.group(1) if m_user else None
        email = m_email.group(1) if m_email else None

        cat = "SUPPORT_ATTACHMENT" if ("attachment" in self.origin or "attachment" in self.file_path) else "SUPPORT_MESSAGE"
        if m_supp:
            self.items.append(EvidenceItem(
                system_id="support_platform",
                resource_id=m_supp.group(1),
                category=cat,
                state="PRESENT",
                user_id=uid,
                email=email,
                raw_data={"pdf_text": text[:200]}
            ))
        if m_audit:
            self.items.append(EvidenceItem(
                system_id="security_service",
                resource_id=m_audit.group(1),
                category="SECURITY_AUDIT_LOG",
                state="PRESENT",
                user_id=uid,
                email=email,
                raw_data={"pdf_text": text[:200]}
            ))


class EvidenceManager:
    def __init__(self, dataset_dir: str):
        self.dataset_dir = dataset_dir
        self.files: Dict[str, EvidenceFile] = {}
        self._load_manifest()

    def _load_manifest(self):
        manifest_path = os.path.join(self.dataset_dir, "evidence_files.csv")
        with open(manifest_path, "r", encoding="utf-8") as fp:
            for row in csv.DictReader(fp):
                fid = row["file_id"]
                fpath = row["file_path"]
                full_path = os.path.join(self.dataset_dir, fpath)
                ef = EvidenceFile(
                    file_id=fid,
                    file_path=fpath,
                    origin=row["origin"],
                    captured_at=row["captured_at"],
                    full_path=full_path
                )
                self.files[fid] = ef

    def get_file(self, file_id: str) -> Optional[EvidenceFile]:
        ef = self.files.get(file_id)
        if ef:
            ef.parse()
        return ef

    def get_candidate_files_for_audit(self, audit_at: str) -> List[EvidenceFile]:
        """Return all evidence files captured at or before audit_at, sorted descending by capture time."""
        t_audit = datetime.fromisoformat(audit_at.replace("Z", "+00:00"))
        candidates = []
        for ef in self.files.values():
            t_cap = datetime.fromisoformat(ef.captured_at.replace("Z", "+00:00"))
            if t_cap <= t_audit:
                candidates.append((t_cap, ef))
        # Sort descending by capture time (closest to audit_at first)
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [c[1] for c in candidates]
