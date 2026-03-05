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
STATE_FILE = Path(__file__).parent / ".sagemarks_state.json"
DAILY_LIMIT = 1  # max AI organizes per day

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
# Rate limiting
# ---------------------------------------------------------------------------

def check_rate_limit() -> bool:
    """Check if user has remaining AI organizes today. Returns True if allowed."""
    today = datetime.now().strftime("%Y-%m-%d")
    state = _load_state()
    if state.get("last_organize_date") != today:
        return True
    return state.get("organizes_today", 0) < DAILY_LIMIT


def record_organize():
    """Record that an organize was performed."""
    today = datetime.now().strftime("%Y-%m-%d")
    state = _load_state()
    if state.get("last_organize_date") != today:
        state["last_organize_date"] = today
        state["organizes_today"] = 1
    else:
        state["organizes_today"] = state.get("organizes_today", 0) + 1
    _save_state(state)


def _load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def _save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


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


def _resolve_provider(args) -> tuple[str, str]:
    """Resolve provider and API key from args or environment."""
    from providers import detect_provider, PROVIDERS

    provider = getattr(args, "provider", None)
    api_key = getattr(args, "api_key", None)

    if provider and api_key:
        return provider, api_key

    if provider:
        info = PROVIDERS.get(provider, {})
        api_key = os.environ.get(info.get("env", ""), "")
        if api_key:
            return provider, api_key
        print(f"  Error: Set {info.get('env', '???')} for {provider}", file=sys.stderr)
        sys.exit(1)

    # Auto-detect
    auto_provider, auto_key = detect_provider()
    if auto_provider:
        print(f"  Auto-detected provider: {PROVIDERS[auto_provider]['name']}")
        return auto_provider, auto_key

    print("  Error: No API key found. Set one of:", file=sys.stderr)
    for p, info in PROVIDERS.items():
        print(f"    {info['env']}  ({info['name']})", file=sys.stderr)
    print(f"\n  Or pass --provider and --api-key", file=sys.stderr)
    sys.exit(1)


def _preview_and_save(categorized: dict):
    """Print a preview and save proposal to JSON."""
    total = sum(len(v) for v in categorized.values())
    print(f"  Proposed organization ({total} bookmarks → {len(categorized)} folders):\n")
    for folder, items in sorted(categorized.items()):
        print(f"  📁 {folder} ({len(items)})")
        for item in items[:3]:
            print(f"     🔖 {item['title'][:55]}")
        if len(items) > 3:
            print(f"     ... +{len(items) - 3} more")
    print()

    proposal_path = Path(__file__).parent / "last_proposal.json"
    with open(proposal_path, "w") as f:
        json.dump(categorized, f, indent=2)
    print(f"  Saved proposal to {proposal_path}")
    print(f"  Run 'sagemarks apply' to write changes (backs up first).\n")


def cmd_organize(args):
    """Categorize bookmarks with AI (title + URL only) and preview the result."""
    if not check_rate_limit():
        print("  Rate limit: 1 AI organize per day. Try again tomorrow.", file=sys.stderr)
        sys.exit(1)

    provider, api_key = _resolve_provider(args)

    data = load_bookmarks()
    bookmarks = extract_bookmarks(data)
    print(f"\n  Analyzing {len(bookmarks)} bookmarks with AI...\n")

    categorized = categorize_with_llm(bookmarks, api_key, model=args.model)
    record_organize()
    _preview_and_save(categorized)


def cmd_smart_organize(args):
    """Smart organize: fetch page content, embed, cluster, name with AI."""
    if not check_rate_limit():
        print("  Rate limit: 1 AI organize per day. Try again tomorrow.", file=sys.stderr)
        sys.exit(1)

    provider, api_key = _resolve_provider(args)

    data = load_bookmarks()
    bookmarks = extract_bookmarks(data)
    print(f"\n  Smart-analyzing {len(bookmarks)} bookmarks...\n")

    from smart_organize import smart_organize
    categorized = smart_organize(
        bookmarks, provider, api_key,
        fetch_content=not args.no_fetch,
    )
    record_organize()
    _preview_and_save(categorized)


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


def cmd_restore(args):
    """Restore bookmarks from the most recent backup."""
    if not BACKUP_DIR.exists():
        print("  No backups found.", file=sys.stderr)
        sys.exit(1)

    backups = sorted(BACKUP_DIR.glob("Bookmarks_*.plist"), reverse=True)
    if not backups:
        print("  No backups found.", file=sys.stderr)
        sys.exit(1)

    print(f"\n  Available backups:")
    for i, b in enumerate(backups[:5]):
        print(f"    [{i}] {b.name}")

    latest = backups[0]
    print(f"\n  Restoring from: {latest.name}")

    import subprocess
    result = subprocess.run(["pgrep", "-x", "Safari"], capture_output=True)
    if result.returncode == 0:
        print("  ⚠️  Quit Safari first!")
        sys.exit(1)

    shutil.copy2(latest, BOOKMARKS_PATH)
    print(f"  Restored. Open Safari to see your bookmarks.\n")


def cmd_providers(args):
    """Show which API keys are configured."""
    from providers import PROVIDERS
    print("\n  Configured providers:\n")
    for provider, info in PROVIDERS.items():
        key = os.environ.get(info["env"], "")
        status = f"✓ {key[:12]}..." if key else "✗ not set"
        embed = "✓" if info["models"]["embed"] else "TF-IDF fallback"
        print(f"  {info['name']:25s}  {info['env']:20s}  {status}")
        print(f"  {'':25s}  Embeddings: {embed}")
    print(f"\n  Set any one key to use AI features.\n")


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
        description="Sagemarks — AI-powered Safari bookmark organizer. BYOK: bring your own Claude/OpenAI/Gemini key.",
    )
    sub = parser.add_subparsers(dest="command")

    # Free commands
    sub.add_parser("scan", help="Show current bookmark structure")
    sub.add_parser("dedupe", help="Find duplicate bookmarks")
    sub.add_parser("deadlinks", help="Check for dead links")

    # AI commands (BYOK)
    def add_provider_args(p):
        p.add_argument("--provider", choices=["claude", "openai", "gemini"], help="LLM provider (auto-detected from env)")
        p.add_argument("--api-key", help="API key (or set env: ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY)")

    org = sub.add_parser("organize", help="AI-categorize bookmarks using title + URL")
    add_provider_args(org)
    org.add_argument("--model", default=None, help="Override default model")

    smart = sub.add_parser("smart", help="Smart organize: fetch pages, embed, cluster, name")
    add_provider_args(smart)
    smart.add_argument("--no-fetch", action="store_true", help="Skip fetching page content (use titles only)")

    ap = sub.add_parser("apply", help="Apply last AI proposal to Safari")
    ap.add_argument("--force", action="store_true", help="Apply even if Safari is running")

    sub.add_parser("restore", help="Restore bookmarks from a backup")
    sub.add_parser("providers", help="Show which API keys are configured")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "scan": cmd_scan,
        "organize": cmd_organize,
        "smart": cmd_smart_organize,
        "apply": cmd_apply,
        "dedupe": cmd_dedupe,
        "deadlinks": cmd_deadlinks,
        "restore": cmd_restore,
        "providers": cmd_providers,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
