# Safari Power Tools — Planning Handoff

## Vision

Rename/evolve **Sagemarks** into **Safari Power Tools** — a free, open-source Safari extension that fills the biggest gaps in Safari's ecosystem. The AI bookmark organizer becomes one feature of a broader toolkit.

## Why This Matters

- Safari has ~55-60M Mac users, ~790M-1B total users
- Chrome has 112K extensions; Safari has ~2-3K (40:1 ratio)
- The developer barrier (Xcode, $99/yr, no bookmarks API) keeps competition low
- Raindrop.io's Safari extension is buggy; Surfed is the only real competitor
- **No one has built the "Swiss Army knife" for Safari power users**

## The Product: 5 Core Features

### 1. Cmd+K Omni Search (THE headline feature)
- Fuzzy search across open tabs + bookmarks + history in one popup
- Chrome has Cmd+Shift+A and "Omni" extension — Safari has NOTHING
- This alone could drive adoption
- **Technical approach**: Safari extension popup with JavaScript fuzzy matching (Fuse.js or similar). Reads tabs via `browser.tabs`, bookmarks via native messaging bridge (since `browser.bookmarks` API is unsupported), history via native companion app.

### 2. Smart Bookmark Organize (already built as CLI)
- AI-powered categorization using BYOK (Claude/OpenAI/Gemini)
- Fetch page content → embed → cluster by vector similarity → name folders
- Free: scan, dedupe, dead link check
- AI features require user's own API key
- **Status**: CLI prototype working, needs Swift port for extension

### 3. Session Save/Restore
- Save current tab set as a named workspace
- Restore workspaces with one click
- Safari's existing session management is unreliable
- **Technical approach**: `browser.tabs.query()` works in Safari. Store sessions in `browser.storage.local` or via native companion app.

### 4. Dead Link & Duplicate Cleanup
- Already built in CLI (dedupe + deadlinks commands)
- Scan bookmarks for 404s, duplicates, redirect chains
- One-click cleanup
- **No API key needed** — this is a free feature

### 5. Tab Suspension Control
- Safari suspends tabs invisibly with no user control
- Expose controls: whitelist sites, configure timeout, show suspended indicator
- Chrome's Memory Saver lets users control this; Safari doesn't
- **Technical feasibility**: Limited — may require private APIs or native companion app to control WebKit's tab discarding. Needs research.

## Architecture (from EXTENSION_GUIDE.md)

```
┌─────────────────────────────────────────────────┐
│                  macOS App                        │
│  ┌──────────────┐    ┌─────────────────────────┐ │
│  │ Safari Web   │◄──►│ Native Swift Helper     │ │
│  │ Extension    │    │                          │ │
│  │ • Cmd+K UI   │    │ • Reads Bookmarks.plist  │ │
│  │ • Popup      │    │ • Calls LLM APIs (BYOK)  │ │
│  │ • Tab mgmt   │    │ • Session storage        │ │
│  └──────────────┘    └─────────────────────────┘ │
│         ▲               NSXPCConnection  ▲        │
│         └────────────────────────────────┘        │
│  ┌─────────────────────────────────────────────┐ │
│  │ SwiftUI Settings                             │ │
│  │ • API key management (Keychain)              │ │
│  │ • Feature toggles                            │ │
│  │ • Backup/restore                             │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

Key constraint: `browser.bookmarks` API is NOT supported in Safari. Must use native companion app to read/write `~/Library/Safari/Bookmarks.plist`.

## Market Context

| Competitor | Strengths | Weaknesses |
|-----------|-----------|------------|
| Raindrop.io | Cross-platform, full-text search | Buggy Safari ext, bad AI, $28/yr |
| Surfed | Most powerful Safari ext | Steep learning curve, niche |
| Tab Space | Good session management | Tab-only, no bookmarks |
| GoodLinks | Clean reading list replacement | $10, read-later only |
| (None) | — | No unified search, no fuzzy bookmark search, no AI organize |

## Distribution Strategy

- **Free and open source** on GitHub (MIT license)
- Post to HN: "Show HN: Safari Power Tools — the extensions Chrome users take for granted"
- Post to r/macapps, r/Safari, r/apple
- Goal: GitHub stars + community adoption, not revenue
- If massive traction: consider App Store + donations/sponsorship model

## What Exists Already

| Component | Status | Location |
|-----------|--------|----------|
| Bookmark plist parser | Done | `sagemarks.py` |
| AI organize (multi-provider BYOK) | Done | `providers.py`, `smart_organize.py` |
| Embed + cluster pipeline | Done | `smart_organize.py` |
| Dedupe | Done | `sagemarks.py` |
| Dead link checker | Done | `sagemarks.py` |
| Backup/restore | Done | `sagemarks.py` |
| Safari extension architecture | Documented | `EXTENSION_GUIDE.md` |

## What Needs Building

1. **Xcode project** — macOS app + Safari Web Extension targets
2. **Native messaging bridge** — Swift companion that reads bookmarks plist
3. **Cmd+K popup** — HTML/CSS/JS popup with fuzzy search (Fuse.js)
4. **Session manager** — save/restore tab sets
5. **SwiftUI settings UI** — API key input, feature toggles
6. **Port Python → Swift** — bookmark parsing, LLM API calls
7. **Landing page** — GitHub README with demo GIFs

## Planning Phase Goals

- Decompose into beads with proper dependencies
- Decide: build extension first or improve CLI first?
- Research tab suspension feasibility
- Design the Cmd+K popup UX
- Decide on project rename (Sagemarks → Safari Power Tools? or keep Sagemarks as brand?)
