# Sagemarks

AI-powered Safari bookmark organizer. Bring your own Claude, OpenAI, or Gemini key — we organize your bookmarks using LLMs and vector similarity.

## Why

Safari has zero AI bookmark tools. Chrome has 7+. This fixes that.

## Quick Start

```bash
pip install -r requirements.txt

# Set any ONE of these (we auto-detect which you have)
export ANTHROPIC_API_KEY=sk-ant-...
# or
export OPENAI_API_KEY=sk-...
# or
export GEMINI_API_KEY=AI...

# Free: see your bookmark mess
python sagemarks.py scan

# Free: find duplicates
python sagemarks.py dedupe

# AI: quick organize (title + URL only)
python sagemarks.py organize

# AI: smart organize (fetches pages, embeds, clusters by similarity)
python sagemarks.py smart

# Review last_proposal.json, then apply (quit Safari first!)
python sagemarks.py apply
```

## Commands

### Free (no API key needed)

| Command | What it does |
|---------|-------------|
| `scan` | Show current bookmark structure |
| `dedupe` | Find duplicate bookmark URLs |
| `deadlinks` | Check all bookmarks for 404s and timeouts |
| `providers` | Show which API keys are configured |
| `restore` | Restore bookmarks from a backup |

### AI-powered (BYOK)

| Command | What it does |
|---------|-------------|
| `organize` | Quick categorize using titles + URLs |
| `smart` | Fetch page content, embed, cluster by vector similarity, then name folders with AI |
| `apply` | Write the last proposal to Safari bookmarks (backs up first) |

## How Smart Organize Works

1. Reads `~/Library/Safari/Bookmarks.plist`
2. **Fetches metadata** from each page (title, description, keywords) in parallel
3. **Embeds** all bookmarks into vectors (OpenAI/Gemini embeddings, or TF-IDF fallback for Claude)
4. **Clusters** by vector similarity (k-means)
5. **Names** each cluster with AI
6. Saves proposal for review — `apply` writes it to Safari

## Providers

| Provider | Chat | Embeddings | Env Var |
|----------|------|-----------|---------|
| Claude | Sonnet 4 | TF-IDF fallback | `ANTHROPIC_API_KEY` |
| OpenAI | GPT-4o mini | text-embedding-3-small | `OPENAI_API_KEY` |
| Gemini | Flash 2.0 | text-embedding-004 | `GEMINI_API_KEY` |

Just set one key. We auto-detect the rest.

## Safety

- **Always backs up** before writing (saved to `backups/`)
- **Two-step process** — organize previews, apply writes
- **Safari check** — warns if Safari is running
- **Rate limit** — 1 AI organize per day (prevents accidents)
- **Restore** — one command to roll back
- Reading List is preserved untouched

## Requirements

- macOS (tested on Sonoma/Sequoia)
- Python 3.10+
- Full Disk Access for Terminal (System Settings > Privacy & Security > Full Disk Access)
- Any one API key: Anthropic, OpenAI, or Google

## Roadmap

See [EXTENSION_GUIDE.md](EXTENSION_GUIDE.md) for the Safari extension architecture.

- [x] CLI prototype
- [x] Multi-provider BYOK (Claude/OpenAI/Gemini)
- [x] Smart organize with page fetching + embeddings
- [ ] Safari Web Extension with native Swift companion app
- [ ] iOS Safari extension
- [ ] On-device inference (MLX / Apple Intelligence)
- [ ] App Store release

## License

MIT
