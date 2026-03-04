#!/usr/bin/env python3
"""Sagemarks — AI-powered Safari bookmark organizer."""

import argparse
import json
import os
import plistlib
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path

BOOKMARKS_PATH = Path.home() / "Library" / "Safari" / "Bookmarks.plist"
BACKUP_DIR = Path(__file__).parent / "backups"

# ---------------------------------------------------------------------------
# Plist helpers
# ---------------------------------------------------------------------------

def load_bookmarks(path: Path = BOOKMARKS_PATH) -> dict:
    with open(path, "rb") as f:
        return plistlib.load(f)


def save_bookmarks(data: dict, path: Path = BOOKMARKS_PATH) -> None:
    with open(path, "wb") as f:
        plistlib.dump(data, f, fmt=plistlib.FMT_BINARY)


def backup_bookmarks() -> Path:
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"Bookmarks_{ts}.plist"
    shutil.copy2(BOOKMARKS_PATH, dest)
    return dest


# ---------------------------------------------------------------------------
# Tree traversal
# ---------------------------------------------------------------------------

def extract_bookmarks(node: dict, folder: str = "") -> list[dict]:
    """Flatten the bookmark tree into a list of {title, url, folder}."""
    results = []
    btype = node.get("WebBookmarkType", "")

    if btype == "WebBookmarkTypeLeaf":
        title = node.get("URIDictionary", {}).get("title", "")
        url = node.get("URLString", "")
        if url:
            results.append({"title": title, "url": url, "folder": folder})

    elif btype == "WebBookmarkTypeList":
        name = node.get("Title", "")
        # Skip Reading List and History
        if name in ("com.apple.ReadingList",):
            return results
        display = name if name not in ("", "BookmarksBar", "BookmarksMenu") else folder
        for child in node.get("Children", []):
            results.extend(extract_bookmarks(child, display))

    return results


def build_folder_node(name: str, children: list[dict]) -> dict:
    """Create a plist folder node."""
    return {
        "WebBookmarkType": "WebBookmarkTypeList",
        "WebBookmarkUUID": str(uuid.uuid4()).upper(),
        "Title": name,
        "Children": children,
    }


def build_leaf_node(title: str, url: str) -> dict:
    """Create a plist bookmark leaf node."""
    return {
        "WebBookmarkType": "WebBookmarkTypeLeaf",
        "WebBookmarkUUID": str(uuid.uuid4()).upper(),
        "URLString": url,
        "URIDictionary": {"title": title},
    }


# ---------------------------------------------------------------------------
# LLM categorization
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a bookmark organizer. Given a list of bookmarks (title + URL), categorize \
each into a folder. Create sensible folder names (5-12 folders max). Be concise.

Rules:
- Folder names should be short (1-3 words), capitalized (e.g. "Dev Tools", "Social Media")
- Every bookmark must go into exactly one folder
- Group by purpose/topic, not by domain
- If bookmarks are already well-organized in a folder, keep that grouping

Return ONLY valid JSON — an object where keys are folder names and values are arrays \
of objects with "title" and "url" fields. No markdown, no explanation."""


def categorize_with_llm(bookmarks: list[dict], api_key: str, model: str = "claude-sonnet-4-20250514") -> dict:
    """Send bookmarks to Claude for categorization. Returns {folder: [{title, url}]}."""
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)

    bookmark_text = "\n".join(
        f"- [{b['title']}]({b['url']})" + (f" (was in: {b['folder']})" if b["folder"] else "")
        for b in bookmarks
    )

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Organize these {len(bookmarks)} bookmarks:\n\n{bookmark_text}"}],
    )

    raw = message.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Apply reorganization
# ---------------------------------------------------------------------------

def build_reorganized_tree(original: dict, categorized: dict) -> dict:
    """Replace BookmarksBar children with the new categorized folders."""
    data = plistlib.loads(plistlib.dumps(original, fmt=plistlib.FMT_BINARY))  # deep copy

    # Find root children
    root_children = data.get("Children", [])

    # Preserve Reading List and other special nodes
    special = []
    for child in root_children:
        title = child.get("Title", "")
        if title in ("com.apple.ReadingList",) or child.get("WebBookmarkType") == "WebBookmarkTypeProxy":
            special.append(child)

    # Build new folder nodes from LLM output
    new_folders = []
    for folder_name, items in categorized.items():
        leaves = [build_leaf_node(item["title"], item["url"]) for item in items]
        new_folders.append(build_folder_node(folder_name, leaves))

    # Rebuild: BookmarksBar with new folders, then special nodes
    bar = build_folder_node("BookmarksBar", new_folders)
    menu = build_folder_node("BookmarksMenu", [])

    data["Children"] = [bar, menu] + special
    return data


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_scan(args):
    """Show current bookmark structure."""
    data = load_bookmarks()
    bookmarks = extract_bookmarks(data)
    folders = {}
    for b in bookmarks:
        folders.setdefault(b["folder"] or "(root)", []).append(b)

    print(f"\n  Sagemarks — {len(bookmarks)} bookmarks in {len(folders)} groups\n")
    for folder, items in sorted(folders.items()):
        print(f"  📁 {folder} ({len(items)})")
        for item in items[:3]:
            print(f"     🔖 {item['title'][:55]}")
        if len(items) > 3:
            print(f"     ... +{len(items) - 3} more")
    print()


def cmd_organize(args):
    """Categorize bookmarks with AI and preview the result."""
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: Set ANTHROPIC_API_KEY or pass --api-key", file=sys.stderr)
        sys.exit(1)

    data = load_bookmarks()
    bookmarks = extract_bookmarks(data)
    print(f"\n  Analyzing {len(bookmarks)} bookmarks with AI...\n")

    categorized = categorize_with_llm(bookmarks, api_key, model=args.model)

    # Preview
    total = sum(len(v) for v in categorized.values())
    print(f"  Proposed organization ({total} bookmarks → {len(categorized)} folders):\n")
    for folder, items in sorted(categorized.items()):
        print(f"  📁 {folder} ({len(items)})")
        for item in items[:3]:
            print(f"     🔖 {item['title'][:55]}")
        if len(items) > 3:
            print(f"     ... +{len(items) - 3} more")
    print()

    # Save proposal to JSON for review / apply later
    proposal_path = Path(__file__).parent / "last_proposal.json"
    with open(proposal_path, "w") as f:
        json.dump(categorized, f, indent=2)
    print(f"  Saved proposal to {proposal_path}")
    print(f"  Run 'sagemarks apply' to write changes (backs up first).\n")


def cmd_apply(args):
    """Apply the last proposal to Safari bookmarks."""
    proposal_path = Path(__file__).parent / "last_proposal.json"
    if not proposal_path.exists():
        print("Error: No proposal found. Run 'sagemarks organize' first.", file=sys.stderr)
        sys.exit(1)

    with open(proposal_path) as f:
        categorized = json.load(f)

    # Check Safari is not running
    import subprocess
    result = subprocess.run(["pgrep", "-x", "Safari"], capture_output=True)
    if result.returncode == 0:
        print("  ⚠️  Safari is running. Quit Safari first to avoid data loss.")
        if not args.force:
            print("  Use --force to apply anyway (not recommended).")
            sys.exit(1)

    # Backup
    backup_path = backup_bookmarks()
    print(f"\n  Backed up to {backup_path}")

    # Apply
    data = load_bookmarks()
    new_data = build_reorganized_tree(data, categorized)
    save_bookmarks(new_data)

    total = sum(len(v) for v in categorized.values())
    print(f"  Applied: {total} bookmarks → {len(categorized)} folders")
    print(f"  Open Safari to see your organized bookmarks.\n")


def cmd_dedupe(args):
    """Find duplicate bookmarks."""
    data = load_bookmarks()
    bookmarks = extract_bookmarks(data)
    seen = {}
    dupes = []
    for b in bookmarks:
        url = b["url"].rstrip("/")
        if url in seen:
            dupes.append((seen[url], b))
        else:
            seen[url] = b

    if not dupes:
        print("\n  No duplicates found.\n")
        return

    print(f"\n  Found {len(dupes)} duplicate(s):\n")
    for original, dupe in dupes:
        print(f"  🔗 {dupe['url'][:70]}")
        print(f"     In: {original['folder'] or '(root)'} & {dupe['folder'] or '(root)'}")
    print()


def cmd_deadlinks(args):
    """Check for dead links (404s, timeouts)."""
    import urllib.request
    import urllib.error

    data = load_bookmarks()
    bookmarks = extract_bookmarks(data)
    print(f"\n  Checking {len(bookmarks)} bookmarks for dead links...\n")

    dead = []
    for i, b in enumerate(bookmarks):
        try:
            req = urllib.request.Request(b["url"], method="HEAD", headers={"User-Agent": "Sagemarks/1.0"})
            resp = urllib.request.urlopen(req, timeout=5)
            status = resp.getcode()
            if status >= 400:
                dead.append((b, status))
        except urllib.error.HTTPError as e:
            dead.append((b, e.code))
        except Exception:
            dead.append((b, "timeout/error"))

        if (i + 1) % 20 == 0:
            print(f"  Checked {i + 1}/{len(bookmarks)}...")

    if not dead:
        print("  All links are alive!\n")
        return

    print(f"\n  Found {len(dead)} dead link(s):\n")
    for b, status in dead:
        print(f"  ❌ [{status}] {b['title'][:50]}")
        print(f"     {b['url'][:70]}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="sagemarks",
        description="Sagemarks — AI-powered Safari bookmark organizer",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("scan", help="Show current bookmark structure")

    org = sub.add_parser("organize", help="AI-categorize bookmarks (preview only)")
    org.add_argument("--api-key", help="Anthropic API key (or set ANTHROPIC_API_KEY)")
    org.add_argument("--model", default="claude-sonnet-4-20250514", help="Claude model to use")

    ap = sub.add_parser("apply", help="Apply last AI proposal to Safari")
    ap.add_argument("--force", action="store_true", help="Apply even if Safari is running")

    sub.add_parser("dedupe", help="Find duplicate bookmarks")
    sub.add_parser("deadlinks", help="Check for dead links")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "scan": cmd_scan,
        "organize": cmd_organize,
        "apply": cmd_apply,
        "dedupe": cmd_dedupe,
        "deadlinks": cmd_deadlinks,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
