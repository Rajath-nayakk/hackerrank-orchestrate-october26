"""
Ghost Data Still Exists: Request Intent Classifier Module
Determines whether request_text actually authorizes account deletion.
"""

import re


class RequestClassifier:
    EXPLICIT_NON_DELETION_PATTERNS = [
        # Explicit negation / keep active
        r"\b(?:not asking for deletion|leave the account active|keep the account as it is)\b",
        r"\b(?:do not close the account|without removing any of my records)\b",
        r"\b(?:marketing lists only|not a request to erase|leave my profile and purchase history)\b",
        r"\b(?:want to continue using the service|don't delete or change anything|do not delete)\b",
        r"\b(?:keep my account active|do not erase|this is an information request)\b",
        r"\b(?:please leave my profile|leave my profile)\b",

        # Marketing opt-out
        r"\b(?:stop the promotional emails|unsubscribe me from marketing|remove me from marketing lists)\b",

        # Data export / portability requests
        r"\b(?:download my account information in a portable format|portable format|generate and download a full export|export of all my purchase)\b",
        r"\b(?:send me a copy of all my data exports|data portability)\b",

        # Correction / update requests
        r"\b(?:mobile number on my profile is out of date|replace it with the new one)\b",
        r"\b(?:surname is misspelled|change the email address used for this account|update my shipping address)\b",

        # Access requests
        r"\b(?:tell me what personal information you hold|information held on my account|copy of last year's invoices)\b",
        r"\b(?:need help resetting the login)\b",
    ]

    @classmethod
    def is_deletion_request(cls, request_text: str) -> bool:
        if not request_text or not request_text.strip():
            return False

        text = request_text.lower()

        # Check for non-deletion patterns
        for pattern in cls.EXPLICIT_NON_DELETION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False

        return True
