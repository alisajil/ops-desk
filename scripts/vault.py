"""The Claude folder (a OneDrive folder): layout, project and bid folders, file lookups (stdlib only).

Layout under the folder:
  data/       CSV files, config, logs, huddle minutes, drafts (the plugin's own records)
  Company/    statutory and company documents, one subfolder per category
  Projects/   one folder per project code: Submissions, Documents, Site, Commercial
  Bids/       one folder per bid: Bid-document, Prepared-pack
  Cash/       the cash flow workbook
Document locations in documents.csv and project_submissions.csv are paths relative to this folder.
Imported by ops.py, which owns the CLI.
"""
import re
from pathlib import Path

import ops

COMPANY_CATEGORIES = [
    "registration", "tax", "quality", "financial", "experience", "authorisation",
    "insurance", "bank", "technical", "policy", "people",
]
PROJECT_SUBFOLDERS = ["Submissions", "Documents", "Site", "Commercial"]
BID_SUBFOLDERS = ["Bid-document", "Prepared-pack"]
TOP_LEVEL = ["data", "Company", "Projects", "Bids", "Cash"]


def claude_folder():
    return ops.claude_folder()


def slug(text, limit=40):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit].strip("-")


def safe_code(code):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", code).strip("-")


def project_folder_name(project):
    tail = slug(project["name"])
    return f"{safe_code(project['id'])}-{tail}" if tail else safe_code(project["id"])


def bid_folder_name(bid):
    tail = slug(bid["bid_no"])
    return f"{safe_code(bid['id'])}-{tail}" if tail else safe_code(bid["id"])


def resolve(location):
    """Absolute path for a document location, or None when it cannot be placed (relative path and no folder set)."""
    if not location:
        return None
    path = Path(location).expanduser()
    if path.is_absolute():
        return path
    root = claude_folder()
    if root is None:
        return None
    full = (root / path).resolve()
    return full if full.is_relative_to(root.resolve()) else None  # a location may not climb out of the folder


def file_found(location):
    """True or False when the file can be looked up, None when it cannot (no location, or no folder set)."""
    path = resolve(location)
    return None if path is None else path.exists()


def wanted_dirs(root, projects=(), bids=()):
    dirs = [root / name for name in TOP_LEVEL] + [root / "Company" / c for c in COMPANY_CATEGORIES]
    for p in projects:
        dirs += [root / "Projects" / project_folder_name(p) / s for s in PROJECT_SUBFOLDERS]
    for b in bids:
        dirs += [root / "Bids" / bid_folder_name(b) / s for s in BID_SUBFOLDERS]
    return dirs


def ensure_structure(root, projects=(), bids=(), create=True):
    """Create (or, with create=False, only list) the missing folders. Returns paths relative to root."""
    root = Path(root)
    missing = [d for d in wanted_dirs(root, projects, bids) if not d.exists()]
    if create:
        for d in missing:
            d.mkdir(parents=True, exist_ok=True)
    return [str(d.relative_to(root)) for d in missing]


def _orphans(root, parent, expected_prefixes):
    base = root / parent
    if not base.exists():
        return []
    return sorted(
        f"{parent}/{d.name}" for d in base.iterdir()
        if d.is_dir() and not any(d.name == p or d.name.startswith(p + "-") for p in expected_prefixes)
    )


def sync(data, check_only=False):
    """Make sure every project and bid has its folders, and report missing files and unknown folders."""
    root = claude_folder()
    if root is None:
        return {"ok": False, "errors": ["no Claude folder configured: run the setup skill or `ops.py init --claude-folder <path>`"]}
    if not root.exists():
        return {"ok": False, "errors": [f"Claude folder not found: {root}. Is OneDrive syncing it?"]}
    live = [p for p in data["projects"] if p["status"] != "cancelled"]
    made = ensure_structure(root, live, data["bids"], create=not check_only)
    missing_files = [
        {"kind": "document", "id": d["id"], "name": d["name"], "location": d["location"]}
        for d in data["documents"] if file_found(d["location"]) is False
    ] + [
        {"kind": "submission", "id": s["project_id"], "name": s["doc_name"], "location": s["location"]}
        for s in data["project_submissions"]
        if s["status"] in ("ready", "submitted", "accepted") and file_found(s["location"]) is False
    ]
    return {
        "ok": True, "folder": str(root), "check_only": check_only,
        ("would_create" if check_only else "created"): made,
        "missing_files": missing_files,
        "unknown_project_folders": _orphans(root, "Projects", [safe_code(p["id"]) for p in data["projects"]]),
        "unknown_bid_folders": _orphans(root, "Bids", [safe_code(b["id"]) for b in data["bids"]]),
    }
