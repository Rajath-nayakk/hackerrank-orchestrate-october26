import re
import os

log_path = r"c:\Users\Rajath Nayak\OneDrive\Desktop\hackerrank-orchestrate-october26\log.txt"

with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

print(f"log.txt total length: {len(content)} characters, {len(content.splitlines())} lines.")

# Check for keywords related to API keys, passwords, tokens, secret keys
secret_patterns = [
    r"(?i)api[_-]?key\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{16,}['\"]?",
    r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}",
    r"(?i)password\s*[:=]\s*['\"]?[^\s'\"]{6,}['\"]?",
    r"(?i)secret\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{16,}['\"]?",
]

secrets_found = []
for p in secret_patterns:
    matches = re.findall(p, content)
    if matches:
        secrets_found.extend(matches)

print(f"Secret checks: {len(secrets_found)} found: {secrets_found}")

# Check entries format
session_starts = re.findall(r"##\s*\[.*?\]\s*SESSION START", content)
print(f"Session starts found: {len(session_starts)}")

turns = re.findall(r"##\s*\[\d{4}-\d{2}-\d{2}T.*?\]\s*(?!SESSION START)(.*?)\n", content)
print(f"Turns found: {len(turns)}")

# Verify tool= and model= lines
tool_lines = re.findall(r"tool=(.+)", content)
model_lines = re.findall(r"model=(.+)", content)

print(f"tool= lines count: {len(tool_lines)}, unique: {set(tool_lines)}")
print(f"model= lines count: {len(model_lines)}, unique: {set(model_lines)}")
