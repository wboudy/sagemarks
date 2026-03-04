# Sagemarks

AI-powered Safari bookmark organizer. Uses Claude to automatically categorize your messy bookmarks into smart folders.

## Why

Safari has no AI bookmark tools. Chrome has 7+. This fixes that — starting as a CLI, with a Safari extension on the roadmap.

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# See your current bookmark mess
python sagemarks.py scan

# Let AI organize them (preview only, nothing changes yet)
python sagemarks.py organize

# Review the proposal in last_proposal.json, then apply
# (quit Safari first!)
python sagemarks.py apply
```

## Commands

| Command | What it does |
|---------|-------------|
| `scan` | Show current bookmark structure |
| `organize` | AI-categorize bookmarks (saves proposal, doesn't modify anything) |
| `apply` | Write the proposal to Safari bookmarks (backs up first) |
| `dedupe` | Find duplicate bookmark URLs |
| `deadlinks` | Check all bookmarks for 404s and timeouts |

## How It Works

1. Reads `~/Library/Safari/Bookmarks.plist` (binary plist)
2. Extracts all bookmarks (skips Reading List)
3. Sends titles + URLs to Claude for categorization
4. Saves a JSON proposal for you to review
5. On `apply`: backs up the original, writes the new structure, Safari picks it up on relaunch

## Safety

- **Always backs up** before writing (saved to `backups/`)
- **Two-step process** — `organize` previews, `apply` writes
- **Safari check** — warns if Safari is running (will overwrite changes)
- Reading List is preserved untouched

## Requirements

- macOS (tested on Sonoma/Sequoia)
- Python 3.10+
- Full Disk Access for Terminal (System Settings > Privacy & Security > Full Disk Access)
- Anthropic API key

## Roadmap

See [EXTENSION_GUIDE.md](EXTENSION_GUIDE.md) for the full plan to ship this as a Safari extension.

- [ ] CLI prototype (done)
- [ ] Safari Web Extension with native Swift companion app
- [ ] iOS Safari extension
- [ ] On-device inference (MLX / Apple Intelligence)
- [ ] App Store release

## License

MIT
