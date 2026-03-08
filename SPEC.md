# Safari Power Tools — Product Specification

**Version**: 1.0
**Date**: 2026-03-05
**Status**: Planning Complete, Ready for Implementation

---

## Table of Contents

1. [Vision and Product Definition](#1-vision-and-product-definition)
2. [Decision Record: Platform Strategy](#2-decision-record-platform-strategy)
3. [Feature Specifications](#3-feature-specifications)
4. [System Architecture](#4-system-architecture)
5. [Technical Constraints and Risks](#5-technical-constraints-and-risks)
6. [Implementation Phases](#6-implementation-phases)
7. [Open Questions](#7-open-questions)

---

## 1. Vision and Product Definition

### 1.1 Mission

Build the "Swiss Army knife" for Safari power users — a free, open-source extension that fills the biggest gaps in Safari's ecosystem where Chrome has abundant options.

### 1.2 Why This Matters

| Metric | Value |
|--------|-------|
| Safari Mac users | ~100M+ |
| Safari total users (incl. iOS) | ~790M-1B |
| Chrome extensions | 112,000+ |
| Safari extensions | ~2-3K |
| Extension ratio | **40:1 Chrome advantage** |

Safari's developer barriers (Xcode, $99/yr, no bookmarks API) keep competition low. No one has built the unified power-user toolkit that Chrome users take for granted.

### 1.3 Target User

**Primary**: Mac power users who:
- Have 50+ bookmarks and 10+ open tabs regularly
- Use keyboard shortcuts over mouse
- Want to search everything from one place
- Would use Raycast, Alfred, or similar tools

**Secondary**: Safari loyalists frustrated by:
- Tabs reloading randomly
- No fuzzy search for bookmarks
- Poor session management
- Bookmark chaos with no AI assistance

### 1.4 Product Principles

1. **Free and open source** — MIT license, BYOK for AI features
2. **Privacy-first** — All processing local, user owns their API keys
3. **Progressive disclosure** — Core features work without permissions; advanced features earn trust first
4. **Safari-native** — Feels like it belongs in Safari, not a Chrome port

### 1.5 Branding Decision

**Name**: Safari Power Tools
**Codename**: Sagemarks (original CLI name, may keep for branding)
**Positioning**: "The extensions Chrome users take for granted"

---

## 2. Decision Record: Platform Strategy

### 2.1 The Core Tension

| Document | Recommendation |
|----------|----------------|
| EXTENSION_GUIDE.md | Safari extension (assumes this path) |
| RESEARCH_DISTRIBUTION.md | "Raycast extension first, Safari extension later" |
| RESEARCH_DISTRIBUTION.md (Section 10.7) | "Raycast for validation, Safari as the real product" |

### 2.2 Quantitative Analysis

**Decision Matrix (from RESEARCH_DISTRIBUTION.md Section 10.6):**

| Criterion | Weight | Raycast | Safari Ext |
|-----------|--------|---------|------------|
| Reach (potential users) | 25% | 2 | 5 |
| Dev time to MVP | 20% | 5 | 2 |
| Maintenance burden | 15% | 4 | 2 |
| User friction | 15% | 3 | 4 |
| Feature completeness | 15% | 4 | 5 |
| Revenue potential | 10% | 1 | 3 |
| **Weighted Score** | | **3.25** | **3.60** |

Safari extension scores higher on objective criteria.

**But risk-adjusted:**

| Risk | Raycast | Safari |
|------|---------|--------|
| Will we ship? | High (simpler) | Medium |
| Will users adopt? | Medium (requires Raycast) | Medium (requires FDA) |
| Will it work long-term? | High (stable API) | Medium (Safari breaks things) |

### 2.3 Decision: Dual-Track with Safari as Primary

**We will build BOTH, but Safari is the real product.**

```
┌─────────────────────────────────────────────────────────────┐
│                    DUAL-TRACK STRATEGY                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  RAYCAST EXTENSION              SAFARI EXTENSION             │
│  (Validation Track)             (Primary Product)            │
│                                                              │
│  • 3-4 weeks to MVP             • 8-12 weeks to MVP          │
│  • 44K user sandbox             • 100M+ addressable market   │
│  • TypeScript familiar          • Swift + JS dual codebase   │
│  • Test UX, validate demand     • Full feature set           │
│  • No $99/year fee              • $99/year required          │
│                                                              │
│  Success metric:                Success metric:               │
│  1K installs → proceed          500 downloads → focus here   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Rationale:**
1. Raycast is a low-cost way to test UX and validate features
2. Safari extension is where the market is (2000x larger)
3. Learnings from Raycast inform Safari implementation
4. We don't abandon Safari because Raycast is easier

**What we WON'T do:**
- Build Raycast-only and declare victory
- Build Safari extension without testing UX first
- Try to make one codebase serve both (different tech stacks)

---

## 3. Feature Specifications

### 3.1 Feature 1: Cmd+K Omni Search (Headline Feature)

**Description**: Fuzzy search across open tabs, bookmarks, and history in one popup — the single feature that could drive adoption.

**Safari Status**: Nothing like this exists. Chrome has Cmd+Shift+A and the "Omni" extension.

#### Acceptance Criteria

| ID | Criteria | Priority |
|----|----------|----------|
| F1.1 | Cmd+Shift+K opens search modal within 200ms | P0 |
| F1.2 | Typing filters results with <50ms perceived latency | P0 |
| F1.3 | Results show tabs, bookmarks, and history with type indicators | P0 |
| F1.4 | Arrow keys navigate results, Enter opens/switches | P0 |
| F1.5 | Escape closes modal, returns focus to page | P0 |
| F1.6 | Works on 95% of websites (CSP-compatible) | P0 |
| F1.7 | Toolbar icon fallback for sites where content script fails | P1 |
| F1.8 | Keyboard shortcut customizable in Safari 26+ | P1 |
| F1.9 | Frecency scoring (frequency × recency) for ranking | P2 |
| F1.10 | VoiceOver accessible with proper ARIA roles | P1 |

#### Technical Implementation

```
Keyboard Shortcut: Cmd+Shift+K (not Cmd+K — conflicts with Safari)
Search Library: FlexSearch (benchmark first) or fuzzysort fallback
Architecture: Cache-first (load all data at startup, search locally)
Modal: Content script with Shadow DOM + external CSS (CSP-safe)
Fallback: Toolbar popup for privileged pages
```

#### Dependencies
- Native companion app (for bookmarks/history)
- Full Disk Access permission (for bookmarks/history)
- `browser.tabs.query()` (for tabs — works without FDA)

---

### 3.2 Feature 2: Smart Bookmark Organize (Existing CLI)

**Description**: AI-powered bookmark categorization using BYOK (Claude/OpenAI/Gemini). Fetch page content, embed into vectors, cluster by similarity, name folders with AI.

**Safari Status**: No AI bookmark tools exist. Raindrop.io's AI is mediocre.

**CLI Status**: ✅ Working prototype in Python

#### Acceptance Criteria

| ID | Criteria | Priority |
|----|----------|----------|
| F2.1 | Scan shows current bookmark structure | P0 |
| F2.2 | Dedupe finds duplicate URLs | P0 |
| F2.3 | Dead link check finds 404s with progress indicator | P0 |
| F2.4 | AI organize works with any of 3 providers | P0 |
| F2.5 | Smart organize fetches pages, embeds, clusters | P1 |
| F2.6 | Two-step flow: preview proposal → user confirms → apply | P0 |
| F2.7 | Always backs up before writing | P0 |
| F2.8 | Rate limit: 1 AI organize per day (prevent accidents) | P1 |
| F2.9 | Reading List preserved untouched | P0 |
| F2.10 | Works via extension UI (not just CLI) | P2 |

#### Technical Implementation

```
Providers: Claude Sonnet, GPT-4o mini, Gemini Flash 2.0
Embeddings: OpenAI text-embedding-3-small, Gemini text-embedding-004, TF-IDF fallback
Clustering: k-means on embedding vectors
Storage: ~/Library/Safari/Bookmarks.plist (binary plist)
Backup: backups/ directory with timestamped copies
```

#### Raycast vs Safari Implementation

| Platform | Implementation |
|----------|----------------|
| Raycast | TypeScript, call existing Python CLI via shell |
| Safari | Port to Swift, or Swift thin wrapper calling bundled Python |

---

### 3.3 Feature 3: Session Save/Restore

**Description**: Save current tab set as a named workspace. Restore with one click. Safari's built-in session management is unreliable.

**Safari Status**: Tab Space ($4.99) is the only decent option. No free alternatives.

#### Acceptance Criteria

| ID | Criteria | Priority |
|----|----------|----------|
| F3.1 | "Save Session" saves all current tabs with custom name | P0 |
| F3.2 | "Restore Session" reopens all tabs from saved session | P0 |
| F3.3 | Sessions persist across browser restarts | P0 |
| F3.4 | Sessions show tab count and preview | P1 |
| F3.5 | Delete/rename sessions | P1 |
| F3.6 | Import/export sessions as JSON | P2 |
| F3.7 | Optional: close tabs after saving ("archive") | P1 |
| F3.8 | iCloud sync across devices (Safari extension) | P2 |

#### Technical Implementation

```
Tabs API: browser.tabs.query() — works in Safari
Storage: browser.storage.local (Safari extension)
         or App Groups SharedContainer (native companion)
Format: JSON array of {url, title, favicon, position}
```

---

### 3.4 Feature 4: Dead Link & Duplicate Cleanup

**Description**: Scan bookmarks for 404s, duplicates, and redirect chains. One-click cleanup.

**Safari Status**: No tools exist. Users must manually check links.

**CLI Status**: ✅ Working prototype (`dedupe`, `deadlinks` commands)

#### Acceptance Criteria

| ID | Criteria | Priority |
|----|----------|----------|
| F4.1 | Dedupe finds bookmarks with identical URLs | P0 |
| F4.2 | Dead link check tests each URL with timeout | P0 |
| F4.3 | Progress indicator during scan | P1 |
| F4.4 | Results show: working, redirect, broken, timeout | P0 |
| F4.5 | One-click to remove all broken links | P1 |
| F4.6 | One-click to remove duplicates (keep first) | P1 |
| F4.7 | Preview before deletion | P0 |
| F4.8 | Works without API key (free feature) | P0 |

#### Technical Implementation

```
HTTP Checks: HEAD request with 5s timeout, follow redirects
Concurrency: 10 parallel requests (respect rate limits)
Storage: Results cached in browser.storage.local
```

---

### 3.5 Feature 5: Tab Suspension Control — DESCOPED

**Original Vision**: Expose controls for Safari's invisible tab suspension. Whitelist sites, configure timeout, show suspended indicator.

**Research Conclusion (RESEARCH_TAB_SUSPENSION.md)**: **NOT FEASIBLE with public APIs.**

- Safari does NOT expose `browser.tabs.discard()` or any equivalent
- Tab suspension is managed internally by WebKit/Jetsam
- No event fired when tab is suspended
- No way to prevent, detect, or control suspension programmatically
- Debug menu toggle was removed in Safari 16+
- Private APIs would cause App Store rejection

#### Revised Scope: "Tab Manager" (Reduced Feature)

| Capability | Feasibility | What We Can Build |
|------------|-------------|-------------------|
| True suspension control | ❌ No | — |
| Detect suspension | ❌ No | — |
| "Fake suspend" (replace with blank) | ✅ Yes | Like "The Suspender" extension |
| Tab idle detection | ✅ Yes | Track time since last activation |
| Session save/restore | ✅ Yes | Already Feature 3 |

**Decision**: Merge useful parts into Feature 3 (Session Save/Restore). Drop "Tab Suspension Control" as a standalone feature.

**What we'll add to Feature 3:**
- Idle tab indicators (which tabs haven't been viewed in 1hr+)
- "Archive idle tabs" — save & close tabs not viewed recently
- Optional "fake suspend" — replace tab content with lightweight restore page

---

## 4. System Architecture

### 4.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SAFARI POWER TOOLS                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        macOS App Bundle                                 │ │
│  │  ┌─────────────────────┐         ┌────────────────────────────────┐   │ │
│  │  │  Safari Web         │         │  Native Swift Companion        │   │ │
│  │  │  Extension          │◄───────►│                                │   │ │
│  │  │                     │  Native │  • Reads Bookmarks.plist       │   │ │
│  │  │  • Cmd+K modal      │ Message │  • Queries History.db          │   │ │
│  │  │  • Tab search       │         │  • LLM API calls (BYOK)        │   │ │
│  │  │  • Session UI       │         │  • Backup/restore              │   │ │
│  │  │  • FlexSearch       │         │  • Keychain for API keys       │   │ │
│  │  └─────────────────────┘         └────────────────────────────────┘   │ │
│  │           │                                    │                       │ │
│  │           │ Content Script                     │ App Groups            │ │
│  │           ▼                                    ▼                       │ │
│  │  ┌─────────────────────┐         ┌────────────────────────────────┐   │ │
│  │  │  Injected Modal     │         │  SwiftUI Settings App          │   │ │
│  │  │  (Shadow DOM)       │         │                                │   │ │
│  │  │                     │         │  • API key management          │   │ │
│  │  │  • Search input     │         │  • Feature toggles             │   │ │
│  │  │  • Results list     │         │  • FDA permission guide        │   │ │
│  │  │  • Keyboard nav     │         │  • Backup browser              │   │ │
│  │  └─────────────────────┘         └────────────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        Data Flow                                        │ │
│  │                                                                         │ │
│  │  STARTUP:                                                               │ │
│  │  Extension loads → sendNativeMessage("getAll") → Swift reads files     │ │
│  │  → Returns JSON → Extension caches in memory → FlexSearch indexes      │ │
│  │                                                                         │ │
│  │  SEARCH (hot path):                                                     │ │
│  │  User types → FlexSearch queries local cache → Results render (<10ms)  │ │
│  │                                                                         │ │
│  │  REFRESH (background):                                                  │ │
│  │  Every 30s → sendNativeMessage("refresh") → Update cache if changed    │ │
│  │                                                                         │ │
│  │  WRITE:                                                                 │ │
│  │  User confirms → sendNativeMessage("apply", proposal) → Swift writes   │ │
│  │  → Backup first → Update Bookmarks.plist → Confirm to extension        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Raycast Extension Architecture (Simpler)

```
┌─────────────────────────────────────────────────────────────────┐
│                    RAYCAST EXTENSION                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TypeScript + React Commands                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │ Search Tabs      │  │ Search Bookmarks │  │ AI Organize   │ │
│  │                  │  │                  │  │               │ │
│  │ AppleScript →    │  │ Read plist →     │  │ Shell exec →  │ │
│  │ Safari tabs      │  │ Parse JSON       │  │ Python CLI    │ │
│  └──────────────────┘  └──────────────────┘  └───────────────┘ │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │ Save Session     │  │ Dead Link Scan   │  │ Dedupe        │ │
│  │                  │  │                  │  │               │ │
│  │ AppleScript +    │  │ HTTP HEAD →      │  │ Compare URLs  │ │
│  │ LocalStorage     │  │ Check status     │  │ in plist      │ │
│  └──────────────────┘  └──────────────────┘  └───────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 File Locations

| Data | Path | Access Method |
|------|------|---------------|
| Safari Bookmarks | `~/Library/Safari/Bookmarks.plist` | Native companion (FDA required) |
| Safari History | `~/Library/Safari/History.db` | Native companion (FDA required) |
| Safari Reading List | Within Bookmarks.plist | Native companion |
| Extension Storage | Safari's sandboxed storage | `browser.storage.local` |
| API Keys | macOS Keychain | Native companion (Keychain Services) |
| Backups | `~/Library/Application Support/SafariPowerTools/backups/` | Native companion |
| Sessions | App Groups SharedContainer | Native companion + Extension |

### 4.4 Native Messaging Protocol

```typescript
// Extension → Native (requests)
interface NativeRequest {
  action: 'getAll' | 'refresh' | 'apply' | 'backup' | 'restore' | 'organize';
  payload?: {
    proposal?: BookmarkProposal;  // for 'apply'
    backupId?: string;            // for 'restore'
    apiKey?: string;              // for 'organize'
    provider?: 'claude' | 'openai' | 'gemini';
  };
}

// Native → Extension (responses)
interface NativeResponse {
  status: 'ok' | 'error';
  error?: string;
  data?: {
    bookmarks?: Bookmark[];
    history?: HistoryItem[];
    sessions?: Session[];
    backups?: BackupMetadata[];
  };
}
```

---

## 5. Technical Constraints and Risks

### 5.1 Hard Constraints (Cannot Be Changed)

| Constraint | Impact | Source |
|------------|--------|--------|
| No `browser.bookmarks` API in Safari | Must use native companion | Apple decision |
| Full Disk Access required for bookmarks/history | 8-step permission flow, significant drop-off | macOS security |
| $99/year Apple Developer Program required | Barrier to entry for distribution | Apple policy |
| iOS cannot access Bookmarks.plist | iOS version is tabs-only | iOS sandboxing |
| Safari 18.x keyboard shortcut bugs | Must have toolbar fallback | Safari bugs |
| Content scripts don't run on privileged pages | Modal won't appear on extensions/settings | WebExtensions spec |

### 5.2 High-Risk Items

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Safari update breaks extension** | High | High | Test on Safari betas, monitor WebKit changelogs |
| **FDA permission rejected by users** | High | High | Launch tabs-only MVP first, progressive disclosure |
| **App Store rejection** | Medium | High | Prepare privacy disclosure, avoid private APIs |
| **FlexSearch too heavy for iOS** | Medium | Medium | Benchmark early, have fuzzysort fallback |
| **Content script modal blocked by CSP** | Medium | Medium | External stylesheet, toolbar popup fallback |
| **Python→Swift port takes too long** | Medium | Medium | Consider thin Swift wrapper calling bundled Python |
| **Raycast validates but Safari doesn't ship** | Medium | Medium | Time-box Raycast to 4 weeks, don't over-invest |

### 5.3 CSP and Modal Compatibility

| Site Category | CSP Policy | Modal Works? | Solution |
|---------------|------------|--------------|----------|
| Banks, enterprise | Strict (`style-src 'self'`) | No (inline blocked) | External CSS via `browser.runtime.getURL()` |
| Google properties | Moderate | Maybe | Constructable Stylesheets |
| Social media (Twitter, YouTube) | Permissive but z-index wars | Yes with workarounds | `position: fixed; z-index: 2147483647` |
| Most websites | Permissive or none | Yes | Standard approach |
| Extension pages, Safari settings | N/A | Content scripts blocked | Toolbar popup fallback |

### 5.4 iOS-Specific Constraints

| Feature | macOS | iOS |
|---------|-------|-----|
| Native messaging | XPC built-in | XPC built-in |
| Bookmarks.plist access | With FDA | **Not possible** |
| History.db access | With FDA | **Not possible** |
| Tab search | Works | Works |
| Session save/restore | Works | Works (tabs only) |
| AI organize | Works | **Tabs only** (no bookmark access) |
| Background script lifetime | Persistent | **Crashes after ~30s** |

**iOS Strategy**: Ship tabs-only version. Explore iCloud CloudKit for bookmark sync (requires additional entitlement and user permission).

### 5.5 Performance Budgets

| Operation | Budget | Measurement |
|-----------|--------|-------------|
| Modal open | <200ms | Time from keypress to modal visible |
| Search result | <50ms | Time from keystroke to results render |
| Initial data load | <2s | Time from extension enable to searchable |
| FlexSearch index (10K items) | <500ms | Benchmark before committing |
| Native messaging round-trip | <100ms | Single message, no search |

---

## 6. Implementation Phases

### Phase 0: Foundation (Week 1)

**Goal**: Set up both projects, validate core assumptions.

| Task | Platform | Deliverable |
|------|----------|-------------|
| Create Raycast extension scaffold | Raycast | Working "Hello World" command |
| Create Xcode project with Safari Web Extension | Safari | Extension appears in Safari settings |
| Implement bookmark plist parser in TypeScript | Raycast | Can read and display bookmarks |
| Implement native messaging bridge in Swift | Safari | Extension can call Swift, Swift can read plist |
| Benchmark FlexSearch with 10K mock bookmarks | Both | Decision: FlexSearch or fuzzysort |
| Test Cmd+Shift+K on Safari 17, 18, 26 | Safari | Document which versions work |

**Exit Criteria**: Both projects build and run. Native messaging works. FlexSearch decision made.

---

### Phase 1: Raycast MVP (Weeks 2-4)

**Goal**: Ship to Raycast Store, validate UX with real users.

| Feature | Commands | Priority |
|---------|----------|----------|
| Tab Search | `Search Safari Tabs` | P0 |
| Bookmark Search | `Search Safari Bookmarks` | P0 |
| History Search | `Search Safari History` | P1 |
| Unified Search | `Search All` (tabs + bookmarks + history) | P0 |
| Session Save | `Save Session` | P0 |
| Session Restore | `Restore Session` | P0 |

**Not in MVP**: AI organize, dead link scan, dedupe (add in Phase 2).

**Success Metrics**:
- 1,000 installs within 2 weeks of launch
- 100 weekly active users
- <5 critical bug reports

**Exit Criteria**: Published to Raycast Store. Metrics tracking in place.

---

### Phase 2: Raycast AI Features (Weeks 5-6)

**Goal**: Add AI organize, validate BYOK model works.

| Feature | Commands | Priority |
|---------|----------|----------|
| AI Organize | `Organize Bookmarks` (calls Python CLI) | P0 |
| Dead Link Scan | `Find Broken Bookmarks` | P1 |
| Dedupe | `Find Duplicate Bookmarks` | P1 |
| API Key Config | Raycast preferences | P0 |

**Success Metrics**:
- 50+ users try AI organize
- <10% error rate on AI calls
- Positive feedback on proposal preview UX

**Exit Criteria**: AI features working. User feedback collected.

---

### Phase 3: Safari Tabs MVP (Weeks 7-10)

**Goal**: Ship Safari extension with tabs-only search. No FDA required.

| Feature | Notes | Priority |
|---------|-------|----------|
| Cmd+Shift+K opens modal | Content script + toolbar fallback | P0 |
| Tab search with fuzzy matching | FlexSearch, `browser.tabs.query()` | P0 |
| Keyboard navigation | Arrow keys, Enter, Escape | P0 |
| VoiceOver accessibility | ARIA dialog + combobox roles | P1 |
| Session save/restore (tabs only) | `browser.storage.local` | P0 |

**Not in this phase**: Bookmarks, history (requires FDA).

**Distribution**: TestFlight beta → App Store submission.

**Success Metrics**:
- App Store approval
- 100 TestFlight testers
- No critical accessibility issues

**Exit Criteria**: On App Store. Tabs-only search working reliably.

---

### Phase 4: Safari Full Features (Weeks 11-14)

**Goal**: Add bookmarks and history (with FDA flow).

| Feature | Notes | Priority |
|---------|-------|----------|
| FDA permission guide | In-app walkthrough with screenshots | P0 |
| Bookmark search | Via native companion | P0 |
| History search | Via native companion | P1 |
| Dead link scan | Via native companion | P1 |
| Dedupe | Via native companion | P1 |
| AI organize (in extension) | Native companion calls LLM APIs | P2 |

**Success Metrics**:
- 50% of users who attempt FDA flow complete it
- 500 total downloads
- <5 critical bugs in bookmark handling

**Exit Criteria**: Full feature set live on App Store.

---

### Phase 5: Evaluate and Decide (Week 15)

**Goal**: Compare Raycast vs Safari adoption, decide focus.

| Question | Raycast Answer | Safari Answer | Decision |
|----------|----------------|---------------|----------|
| Weekly active users? | ? | ? | Focus on higher |
| User satisfaction (NPS)? | ? | ? | Focus on higher |
| Feature requests? | ? | ? | Inform roadmap |
| Maintenance burden? | Lower (TypeScript) | Higher (dual codebase) | Factor in |

**Possible Outcomes**:
1. **Safari dominates** → Focus Safari, maintain Raycast
2. **Raycast dominates** → Keep Raycast, Safari as secondary
3. **Both have traction** → Maintain both, share learnings
4. **Neither has traction** → Pivot or sunset

---

### Phase 6: iOS Safari (Weeks 16-20, if warranted)

**Goal**: Port tabs-only experience to iOS.

| Feature | iOS Status |
|---------|------------|
| Tab search | Works (`browser.tabs.query()`) |
| Bookmark search | **Not feasible** (no plist access) |
| History search | **Not feasible** (no db access) |
| Session save/restore | Works (tabs only) |
| iCloud bookmark sync | Research needed (CloudKit) |

**Decision point**: Only proceed if Safari macOS has traction.

---

## 7. Open Questions

### 7.1 Technical Questions

| # | Question | Status | Owner |
|---|----------|--------|-------|
| 1 | Can we reliably override Cmd+K in content scripts before Safari handles it? | Needs testing | — |
| 2 | Does `browser.commands` API work consistently across Safari 17/18/26? | Needs testing | — |
| 3 | What is the actual native messaging latency in Safari? | Needs benchmarking | — |
| 4 | Does FlexSearch work in Safari service workers without crashing? | Needs testing | — |
| 5 | Can we read Reading List separately from Bookmarks.plist? | Needs verification | — |
| 6 | Does iCloud keep Bookmarks.plist up-to-date locally when syncing? | Needs verification | — |
| 7 | Can iOS access Safari bookmarks via iCloud CloudKit? | Needs research | — |

### 7.2 Product Questions

| # | Question | Status | Owner |
|---|----------|--------|-------|
| 8 | What percentage of users will complete the FDA flow? | Unknown until launch | — |
| 9 | Is "tabs-only" valuable enough to launch without bookmarks? | Hypothesis: yes | — |
| 10 | Should we charge for AI features or stay 100% free? | Leaning free (BYOK) | — |
| 11 | Final branding: Safari Power Tools vs Sagemarks? | TBD | — |

### 7.3 Business Questions

| # | Question | Status | Owner |
|---|----------|--------|-------|
| 12 | Will Apple approve a native companion that reads Safari's data files? | Unknown until submission | — |
| 13 | Should we use GPL instead of MIT to prevent code theft (Amplosion lesson)? | Leaning GPL | — |
| 14 | Is there a path to sustainable funding if this takes off? | GitHub Sponsors, likely <$500/mo | — |

---

## Appendix: Document Sources

This spec synthesizes findings from:

1. **HANDOFF.md** — Original vision and product definition
2. **EXTENSION_GUIDE.md** — Safari extension architecture and Swift implementation details
3. **RESEARCH_DISTRIBUTION.md** — Distribution channels, open source models, Raycast vs Safari analysis
4. **RESEARCH_CMD_K.md** — Cmd+K popup technical feasibility, keyboard shortcuts, fuzzy search libraries
5. **RESEARCH_TAB_SUSPENSION.md** — Tab suspension API research (conclusion: not feasible)
6. **README.md** — Existing CLI features and capabilities

---

*Document version 1.0 — Ready for implementation planning.*
