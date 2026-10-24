"""
Ghost Data Still Exists: Identity Resolution Module
Resolves user identities from user_identities.csv and user_audit_log.csv.
"""

import os
import csv
from typing import Dict, Any, Optional, Set


class IdentityProfile:
    def __init__(self, user_id: str, name: str, email: str, phone: str, email_hash: str, updated_at: str):
        self.user_id = user_id
        self.name = name
        self.email = email.lower()
        self.phone = phone
        self.email_hash = email_hash
        self.updated_at = updated_at
        self.emails: Set[str] = {self.email}
        self.phones: Set[str] = {self.phone} if self.phone else set()
        self.names: Set[str] = {self.name} if self.name else set()
        self.email_hashes: Set[str] = {self.email_hash} if self.email_hash else set()

    def add_historical_email(self, email: str):
        if email:
            self.emails.add(email.lower())

    def add_historical_phone(self, phone: str):
        if phone:
            self.phones.add(phone)

    def add_historical_name(self, name: str):
        if name:
            self.names.add(name)

    def add_historical_hash(self, h: str):
        if h:
            self.email_hashes.add(h)

    def matches_email(self, email: str) -> bool:
        return email.lower() in self.emails

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "email_hash": self.email_hash,
            "updated_at": self.updated_at,
            "emails": list(self.emails),
            "phones": list(self.phones),
            "names": list(self.names),
            "email_hashes": list(self.email_hashes),
        }


class IdentityResolver:
    def __init__(self, dataset_dir: str):
        self.dataset_dir = dataset_dir
        self.users_by_id: Dict[str, IdentityProfile] = {}
        self.users_by_email: Dict[str, IdentityProfile] = {}
        self.users_by_hash: Dict[str, IdentityProfile] = {}
        self._load()

    def _load(self):
        identities_path = os.path.join(self.dataset_dir, "user_identities.csv")
        with open(identities_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                profile = IdentityProfile(
                    user_id=row["user_id"],
                    name=row["name"],
                    email=row["email"],
                    phone=row["phone"],
                    email_hash=row["email_hash"],
                    updated_at=row["updated_at"]
                )
                self.users_by_id[profile.user_id] = profile
                self.users_by_email[profile.email] = profile
                if profile.email_hash:
                    self.users_by_hash[profile.email_hash] = profile

        audit_path = os.path.join(self.dataset_dir, "user_audit_log.csv")
        if os.path.exists(audit_path):
            with open(audit_path, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    uid = row["user_id"]
                    if uid in self.users_by_id:
                        profile = self.users_by_id[uid]
                        field = row["field_name"]
                        if field == "email":
                            old_val = row["old_value"].lower() if row["old_value"] else ""
                            new_val = row["new_value"].lower() if row["new_value"] else ""
                            profile.add_historical_email(old_val)
                            profile.add_historical_email(new_val)
                            if old_val:
                                self.users_by_email[old_val] = profile
                            if new_val:
                                self.users_by_email[new_val] = profile
                        elif field == "phone":
                            profile.add_historical_phone(row["old_value"])
                            profile.add_historical_phone(row["new_value"])
                        elif field == "name":
                            profile.add_historical_name(row["old_value"])
                            profile.add_historical_name(row["new_value"])
                        elif field == "email_hash":
                            profile.add_historical_hash(row["old_value"])
                            profile.add_historical_hash(row["new_value"])
                            if row["old_value"]:
                                self.users_by_hash[row["old_value"]] = profile
                            if row["new_value"]:
                                self.users_by_hash[row["new_value"]] = profile

    def resolve_by_email(self, email: str) -> Optional[IdentityProfile]:
        return self.users_by_email.get(email.lower())

    def resolve_by_user_id(self, user_id: str) -> Optional[IdentityProfile]:
        return self.users_by_id.get(user_id)

    def resolve_by_hash(self, email_hash: str) -> Optional[IdentityProfile]:
        return self.users_by_hash.get(email_hash)
