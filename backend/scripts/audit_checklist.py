#!/usr/bin/env python3
"""
Audit checklist generator for HealthPulse AI project.
Generates a markdown file `audit_checklist.md` summarising presence of
key PRD items in the codebase.

The script is intentionally lightweight – it scans the repository for
specific filenames, class names, and function names that correspond to the
PRD checklist items.
"""
import os
import re
from pathlib import Path

# Repository root (assumed to be two levels up from this script)
REPO_ROOT = Path(__file__).resolve().parents[2]

# Mapping of PRD items to search patterns (file/path or regex)
CHECKLIST = {
    "Authentication": [r"auth/"],
    "Authorization / RBAC": [r"auth/", r"rbac"],
    "Multi‑tenancy": [r"tenant", r"hospital_id"],
    "Hospital lifecycle": [r"Hospital"],
    "Doctor lifecycle": [r"Doctor"],
    "Calendar / Availability": [r"calendar", r"availability"],
    "AI capabilities": [r"search_hospitals", r"create_appointment"],
    "LangGraph / workflow": [r"langgraph", r"workflow"],
    "EHR connector": [r"EHRConnector", r"integrations/"],
    "Notification service": [r"notification"],
    "Tests": [r"tests/"],
    "Docker / deployment": [r"docker-compose.yml", r"Dockerfile"],
    "Security – secrets": [r"\.env", r"SECRET"],
}

def find_matches(patterns):
    """Return True if any file in the repo matches one of the regex patterns."""
    regexes = [re.compile(p, re.IGNORECASE) for p in patterns]
    for root, _, files in os.walk(REPO_ROOT):
        for f in files:
            path = os.path.join(root, f)
            rel = os.path.relpath(path, REPO_ROOT)
            for rx in regexes:
                if rx.search(rel):
                    return True
    return False

def generate_markdown():
    lines = ["# HealthPulse AI – PRD Audit Checklist", "", "| Requirement | Detected |", "|---|---|"]
    for item, patterns in CHECKLIST.items():
        detected = "✅" if find_matches(patterns) else "❌"
        lines.append(f"| {item} | {detected} |")
    return "\n".join(lines)

if __name__ == "__main__":
    md = generate_markdown()
    out_path = REPO_ROOT / "audit_checklist.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"Audit checklist written to {out_path}")
