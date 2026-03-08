# Cmd+K Popup Technical Feasibility Research

Research for Safari Power Tools extension, conducted 2026-03-05.

## Executive Summary

Building a Cmd+K omni-search popup for Safari is **technically feasible** but requires significant workarounds due to Safari's limited WebExtension API support. The architecture requires a native Swift companion app to access bookmarks and history, with the web extension handling tabs and UI.

| Feature | Feasibility | Notes |
|---------|-------------|-------|
| Keyboard shortcut (Cmd+K) | Partial | May conflict with Safari's "Search Field" shortcut |
| Keyboard shortcut (Cmd+Shift+K) | Likely | Better choice - no system conflict |
| Floating popup UI | Yes | Via content script injection or popup API |
| Tab search | Yes | `browser.tabs.query()` works |
| Bookmark search | Via workaround | Native messaging to read Bookmarks.plist |
| History search | Via workaround | Native messaging to read History.db |
| Fuzzy search | Yes | FlexSearch or Fuse.js in extension |

---

## 1. Keyboard Shortcuts in Safari Web Extensions

### Commands API Support

Safari supports the `browser.commands` API based on the WebExtensions standard (Chromium-derived). Key facts:

**Chrome/Firefox Commands API Requirements:**
- Must include `Ctrl` or `Alt` modifier (on macOS, `Ctrl` maps to `Command`)
- Maximum of 4 suggested keyboard shortcuts per extension
- Can use `_execute_action` special command to trigger the extension popup
- Users can customize shortcuts in browser settings

**Manifest Configuration:**
```json
{
  "commands": {
    "_execute_action": {
      "suggested_key": {
        "default": "Ctrl+Shift+K",
        "mac": "Command+Shift+K"
      },
      "description": "Open Omni Search"
    }
  }
}
```

### Cmd+K Conflict Analysis

**Problem:** Safari already uses Cmd+K for "Jump to Search Field" (focusing the URL bar).

**Solutions:**
1. **Use Cmd+Shift+K instead** - No system conflict, unique to our extension
2. **Use a different shortcut** like Cmd+Shift+Space or Cmd+E
3. **Let users customize** - The commands API allows user customization
4. **Content script listener** - Inject a script that captures Cmd+K before Safari handles it (unreliable)

**Recommendation:** Default to `Cmd+Shift+K` but allow customization. This mirrors how Raycast, Alfred, and other tools differentiate from system shortcuts.

---

## 2. Safari Extension Popup Implementation

### Option A: Toolbar Popup (Simpler)

Safari supports the standard toolbar popup that appears when clicking the extension icon.

```json
{
  "action": {
    "default_popup": "popup.html",
    "default_icon": {
      "16": "images/icon16.png",
      "32": "images/icon32.png"
    }
  }
}
```

**Trigger programmatically:**
```javascript
// In background script, when keyboard command fires
browser.action.openPopup();
```

**Limitations:**
- Popup anchored to toolbar icon (not centered/floating)
- Limited size (typically max ~800x600 depending on browser)
- Popup closes when it loses focus

### Option B: Content Script Modal (More Flexible)

Inject a floating modal directly into the current page via content script.

```javascript
// content-script.js
function showOmniSearch() {
  const overlay = document.createElement('div');
  overlay.id = 'safari-power-tools-overlay';
  overlay.innerHTML = `
    <div class="spt-modal">
      <input type="text" class="spt-search-input" placeholder="Search tabs, bookmarks, history..." autofocus>
      <div class="spt-results"></div>
    </div>
  `;
  document.body.appendChild(overlay);
}

// Listen for message from background script
browser.runtime.onMessage.addListener((message) => {
  if (message.action === 'openOmniSearch') {
    showOmniSearch();
  }
});
```

**Advantages:**
- True floating/centered popup
- Full control over appearance and size
- Can appear anywhere on screen

**Disadvantages:**
- Requires content script injection on all pages
- Won't work on extension pages, new tab, or privileged URLs
- CSS isolation challenges (use Shadow DOM)

### Recommended Approach

Use **Option B (content script modal)** for the best UX, with **Option A (toolbar popup)** as fallback for pages where content scripts can't run.

---

## 3. browser.tabs.query() - Tab Access

### Confirmed Working in Safari

Based on the SolanaSafariWalletExtension reference implementation, Safari supports:

```javascript
// Query all tabs
const tabs = await browser.tabs.query({});

// Query active tab in current window
const [activeTab] = await browser.tabs.query({ active: true, currentWindow: true });

// Send message to a tab
browser.tabs.sendMessage(tabId, { action: 'someAction' });
```

### Permissions Required

```json
{
  "permissions": ["tabs"]
}
```

**Note:** In Safari, users may need to grant "Allow on All Websites" permission for the extension to access tab URLs and titles across all origins.

### Limitations

- Tab URLs may be restricted for certain pages (extensions, settings)
- No access to tab contents without separate `activeTab` permission or host permissions
- Cross-origin restrictions apply to content script injection

---

## 4. Bookmarks API - NOT Supported, Workarounds Required

### The Problem

Safari does **NOT** support `browser.bookmarks` API. This is documented in Apple's compatibility notes and confirmed by community testing.

### Workaround: Native Messaging Bridge

Safari Web Extensions support native messaging via `browser.runtime.sendNativeMessage()`. This allows the web extension to communicate with a native Swift/Objective-C companion app.

**Architecture:**
```
┌─────────────────┐         ┌─────────────────────────┐
│ Web Extension   │◄───────►│ Native Helper (Swift)   │
│ (JavaScript)    │  Native │                         │
│                 │ Message │ • Reads Bookmarks.plist │
│ Cmd+K Popup     │─────────│ • Returns JSON to ext   │
└─────────────────┘         └─────────────────────────┘
```

### Bookmarks.plist Location and Format

**Location:** `~/Library/Safari/Bookmarks.plist`

**Format:** Binary plist with nested structure:
```
{
  "Children" => [
    {
      "Title" => "BookmarksBar",
      "WebBookmarkType" => "WebBookmarkTypeList",
      "Children" => [
        {
          "URIDictionary" => { "title" => "Example Site" },
          "URLString" => "https://example.com/",
          "WebBookmarkType" => "WebBookmarkTypeLeaf"
        }
      ]
    }
  ]
}
```

### Native Companion Implementation (Swift)

```swift
// SafariExtensionHandler.swift
import SafariServices

class SafariExtensionHandler: SFSafariExtensionHandler {
    override func messageReceived(
        withName messageName: String,
        from page: SFSafariPage,
        userInfo: [String: Any]?
    ) {
        if messageName == "getBookmarks" {
            let bookmarks = readBookmarksPlist()
            page.dispatchMessageToScript(
                withName: "bookmarksData",
                userInfo: ["bookmarks": bookmarks]
            )
        }
    }

    func readBookmarksPlist() -> [[String: Any]] {
        let url = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Safari/Bookmarks.plist")

        guard let data = try? Data(contentsOf: url),
              let plist = try? PropertyListSerialization.propertyList(
                  from: data, format: nil
              ) as? [String: Any] else {
            return []
        }

        return parseBookmarks(plist)
    }
}
```

### Sandbox Considerations

The native app requires appropriate entitlements to access Safari data:

```xml
<!-- entitlements.plist -->
<key>com.apple.security.files.user-selected.read-only</key>
<true/>
<!-- May need Full Disk Access for Safari folder -->
```

**Important:** Safari's data folder (`~/Library/Safari/`) requires **Full Disk Access** permission on macOS Catalina and later. Users must manually grant this in System Preferences.

---

## 5. History API - Limited Support, Native Workaround Recommended

### browser.history Status

Safari's support for `browser.history` API is **uncertain/limited**. Most documentation focuses on Chrome/Firefox implementations.

### Native Workaround: History.db

**Location:** `~/Library/Safari/History.db`

**Format:** SQLite database with the following schema:

```sql
-- Key table: history_items
CREATE TABLE history_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    domain_expansion TEXT NULL,
    visit_count INTEGER NOT NULL,
    daily_visit_counts BLOB NOT NULL,
    weekly_visit_counts BLOB NULL,
    visit_count_score INTEGER NOT NULL
);

-- Visit details
CREATE TABLE history_visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    history_item INTEGER NOT NULL,
    visit_time REAL NOT NULL,
    title TEXT,
    load_successful BOOLEAN DEFAULT 1,
    -- ...
);
```

### Querying History (Swift)

```swift
import SQLite3

func queryHistory(limit: Int = 100) -> [HistoryItem] {
    let dbPath = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Safari/History.db").path

    var db: OpaquePointer?
    guard sqlite3_open_v2(dbPath, &db, SQLITE_OPEN_READONLY, nil) == SQLITE_OK else {
        return []
    }
    defer { sqlite3_close(db) }

    let query = """
        SELECT h.url, h.domain_expansion, v.title, v.visit_time
        FROM history_items h
        JOIN history_visits v ON h.id = v.history_item
        ORDER BY v.visit_time DESC
        LIMIT ?
    """
    // ... execute query and return results
}
```

### Permission Requirements

Same as bookmarks - requires Full Disk Access for the native companion app.

---

## 6. Chrome Omni-Style Extension Reference

### Note on "nicokimmel/omni-bar"

The referenced repository `github.com/nicokimmel/omni-bar` does **not exist**. The GitHub user "nicokimmel" exists but maintains unrelated projects (robotarena, thunfisch-sync, etc.).

### Similar Extensions

**chrome-omnicomplete** (chrisseroka/chrome-omnicomplete)
- Fuzzy search across tabs, bookmarks, and history
- Searches through bookmark folder hierarchies
- Example: searching "bpama" matches "**B**logs / **Pa**renting / Super**ma**ma"
- Prioritizes already-open tabs when matching bookmarks

**Architecture Patterns:**
1. Background script aggregates data from all sources (tabs, bookmarks, history)
2. Popup/modal displays search input and results
3. Fuzzy matching ranks results by relevance
4. Keyboard navigation (arrow keys + Enter) for selection
5. Action dispatches based on result type (switch tab vs. open URL)

### Safari Equivalent Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Safari Power Tools                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────┐    ┌─────────────────────────────┐│
│  │ Content Script   │    │ Background Script            ││
│  │ (per-page)       │    │ (service worker)             ││
│  │                  │    │                              ││
│  │ • Cmd+K listener │◄──►│ • Aggregates data sources   ││
│  │ • Modal UI       │    │ • browser.tabs.query()      ││
│  │ • Result display │    │ • Native messaging bridge   ││
│  └──────────────────┘    └──────────────┬──────────────┘│
│                                          │               │
│                              ┌───────────▼─────────────┐ │
│                              │ Native Companion (Swift)│ │
│                              │                         │ │
│                              │ • Reads Bookmarks.plist │ │
│                              │ • Queries History.db    │ │
│                              │ • Returns JSON via      │ │
│                              │   native messaging      │ │
│                              └─────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 7. Fuzzy Search Library Recommendations

### Comparison

| Library | Stars | Size (gzip) | Speed | Features |
|---------|-------|-------------|-------|----------|
| **Fuse.js** | 20K | ~6KB | Good | Simple API, zero deps |
| **FlexSearch** | 14K | 4.5KB (light) | Excellent | 1M× faster, workers, IndexedDB |
| **fuzzysort** | 4K | ~3KB | Very good | SublimeText-like scoring |
| **fuzzysearch** | 3K | <1KB | Fast | Minimal, boolean only |

### Recommendation: FlexSearch (Light Bundle)

**Why FlexSearch:**
1. **Performance:** Up to 1,000,000× faster than alternatives in benchmarks
2. **Size:** Light bundle is only 4.5KB gzipped
3. **Worker support:** Can offload indexing to prevent UI blocking
4. **IndexedDB persistence:** Cache index for faster subsequent loads
5. **Scoring:** Built-in relevance scoring

**Basic Usage:**
```javascript
import FlexSearch from 'flexsearch';

// Create index
const index = new FlexSearch.Index({
    tokenize: 'forward',  // For fuzzy prefix matching
    cache: true
});

// Add documents
bookmarks.forEach((bm, id) => {
    index.add(id, `${bm.title} ${bm.url} ${bm.folderPath}`);
});

// Search
const results = index.search('github repo', { limit: 10 });
```

### Alternative: Fuse.js for Simplicity

If performance isn't critical (< 1000 items), Fuse.js is simpler:

```javascript
import Fuse from 'fuse.js';

const fuse = new Fuse(items, {
    keys: ['title', 'url', 'folderPath'],
    threshold: 0.4,  // Fuzzy tolerance
    includeScore: true
});

const results = fuse.search('github');
```

---

## 8. Known Safari Web Extension Limitations

### Background Script Timeout Bug

**Issue:** Non-persistent background scripts crash after ~30 seconds on physical iOS/iPadOS devices, even when actively receiving messages from content scripts.

**Source:** alexkates/content-script-non-responsive-bug

**Impact:** On iOS Safari, the extension may become unresponsive if users don't interact frequently.

**Workarounds:**
- Use persistent background script if possible (check Safari support)
- Keep background script alive with periodic messaging
- Handle reconnection gracefully in content scripts

### Permission Model

Safari requires users to explicitly grant:
- "Allow on [current website]" - Per-site permission
- "Always Allow on Every Website" - Required for cross-site functionality
- Full Disk Access (for native companion) - Must be granted manually in System Preferences

### Data Isolation

Safari implements stricter data isolation than Chrome:
- Extension storage is sandboxed
- Cross-origin requests require explicit permissions
- Native messaging requires app group configuration

---

## 9. Implementation Roadmap

### Phase 1: MVP (Tabs Only)
1. Create Safari Web Extension project in Xcode
2. Implement content script with Cmd+Shift+K listener
3. Build floating modal UI
4. Query tabs via `browser.tabs.query()`
5. Integrate FlexSearch for fuzzy matching
6. Handle tab switching

### Phase 2: Add Bookmarks
1. Create native Swift companion app
2. Implement native messaging bridge
3. Read and parse Bookmarks.plist
4. Merge bookmark results with tab results
5. Handle bookmark opening (new tab)

### Phase 3: Add History
1. Extend native companion to query History.db
2. Add history to search index
3. Implement result type icons/indicators
4. Add frecency scoring (frequency × recency)

### Phase 4: Polish
1. Add keyboard navigation (arrow keys, Enter, Escape)
2. Implement result highlighting
3. Add settings UI (customize shortcut, exclude folders)
4. Performance optimization (lazy loading, virtual scrolling)

---

## 10. Open Questions

1. **Cmd+K Override:** Can we reliably override Safari's Cmd+K in content scripts before Safari handles it? Needs testing.

2. **iOS Support:** Will the same extension work on iOS Safari, or does it need a separate implementation?

3. **Private Browsing:** Do the APIs work in Private Browsing mode? What data is accessible?

4. **iCloud Sync:** If bookmarks are synced via iCloud, does Bookmarks.plist stay up-to-date locally?

5. **App Store Approval:** Will Apple approve a native companion that reads Safari's data files? May need to justify with privacy disclosure.

---

## 11. Plan Hardening — Critical Analysis

This section stress-tests the recommendations above against real-world edge cases and missing considerations.

### 11.1 Keyboard Shortcut Risk: Cmd+Shift+K Validation

**Good news (2025/2026):** Safari 26 (macOS Tahoe) [now allows users to customize extension keyboard shortcuts](https://www.1password.community/discussions/1password/is-there-still-no-way-to-change-safari-shortcut-from-command-shift-x/54565) directly in Safari Settings > Extensions. This resolves the historical limitation where shortcuts were developer-defined only.

**Remaining concerns:**

| Issue | Evidence | Mitigation |
|-------|----------|------------|
| Safari 18.x shortcut bugs | [Dark Reader #13088](https://github.com/darkreader/darkreader/issues/13088): "Safari ignores all keyboard shortcuts" (Aug 2024) | Test on Safari 17, 18, and 26; provide fallback click-to-open |
| Extension breakage on Safari updates | Safari 18.3 (Jan 2025) broke previously-working extensions including App Store versions | Pin to known-good Safari versions in docs; monitor WebKit changelogs |
| `browser.commands` API gaps | Safari's implementation may differ from Chrome/Firefox | Test `_execute_action` specifically; don't assume feature parity |

**Verdict:** Cmd+Shift+K is viable, but **must have a clickable toolbar fallback**. Users on older Safari versions won't have customization options. Keyboard shortcuts have a history of breaking between Safari releases.

---

### 11.2 Content Script Modal: Shadow DOM + CSP + Z-Index Reality

**Shadow DOM + CSP Conflict:**

Sites with strict CSP (e.g., `style-src 'self'`) will **block inline styles** inside Shadow DOM. This is a [documented issue](https://github.com/hypothesis/client/issues/293) affecting annotation tools like Hypothesis.

| Site Category | CSP Behavior | Our Modal |
|---------------|--------------|-----------|
| Banks, enterprise apps | Strict CSP, no inline styles | **Broken** unless external stylesheet |
| Google properties | Moderate CSP | May work with nonce |
| Most websites | Permissive or no CSP | Works |

**Solutions ranked by reliability:**

1. **External stylesheet** in Shadow DOM (most reliable)
   ```javascript
   const shadow = element.attachShadow({ mode: 'closed' });
   const link = document.createElement('link');
   link.rel = 'stylesheet';
   link.href = browser.runtime.getURL('modal.css');
   shadow.appendChild(link);
   ```

2. **Constructable Stylesheets** (Safari 16.4+)
   ```javascript
   const sheet = new CSSStyleSheet();
   sheet.replaceSync(cssText);
   shadow.adoptedStyleSheets = [sheet];
   ```

3. **Inline styles via CSSOM** (bypasses CSP in some browsers)

**Z-Index Wars (Twitter, YouTube, etc.):**

[Known issue](https://devcommunity.x.com/t/z-index-for-shadow-dom-embedded-tweets-breaks-dom-order-layering/67005): Embedded tweets and YouTube iframes create isolated stacking contexts that fight with overlays.

| Site | Problem | Workaround |
|------|---------|------------|
| Twitter/X | Embedded tweets with aggressive z-index | Use `position: fixed` + `z-index: 2147483647` |
| YouTube | Video player captures focus, overlays under iframe | Pause video on modal open; add `wmode=opaque` param detection |
| Notion, Figma | Complex layering systems | Test explicitly; may need per-site fixes |

**Recommendation:** Ship with `position: fixed; z-index: 2147483647;` and add a **"modal not visible" escape hatch** (e.g., "Can't see the search? Click the toolbar icon").

---

### 11.3 FlexSearch Reality Check: Actual Benchmarks

**The "1,000,000x faster" claim** is marketing based on micro-benchmarks. Real-world numbers from [FlexSearch benchmarks](https://nextapps-de.github.io/flexsearch/):

| Metric | FlexSearch | Fuse.js | Notes |
|--------|-----------|---------|-------|
| Search ops/sec | ~300x faster than Wade | Baseline | Based on Gulliver's Travels text |
| Memory (10M words) | "Lowest consumption" | Higher | No exact numbers published |
| Index build time | Not documented | Not documented | Must benchmark ourselves |

**What we need to test before committing:**

```javascript
// Benchmark script for our use case
const bookmarks = generateMockBookmarks(10000);
console.time('FlexSearch index');
const index = new FlexSearch.Index({ tokenize: 'forward' });
bookmarks.forEach((bm, i) => index.add(i, `${bm.title} ${bm.url}`));
console.timeEnd('FlexSearch index');
// Target: < 500ms for 10K items

console.time('FlexSearch search');
for (let i = 0; i < 100; i++) {
  index.search('github', { limit: 10 });
}
console.timeEnd('FlexSearch search');
// Target: < 1ms per search (100 searches < 100ms)
```

**Safari Service Worker compatibility:** FlexSearch uses `Uint8Array` and standard APIs — should work, but Safari service workers have [documented instability](https://github.com/nicedoc/content-script-non-responsive-bug) (30-second timeouts on iOS). **Test in Safari specifically before committing.**

**Memory footprint concern:** FlexSearch can use 6MB+ with certain configs. For 50K bookmarks, expect 20-50MB index. This may be acceptable for desktop Safari but problematic for iOS Safari's memory constraints.

**Fallback plan:** If FlexSearch is too heavy, [fuzzysort](https://github.com/farzher/fuzzysort) at ~3KB is a lighter alternative with SublimeText-style scoring.

---

### 11.4 Native Messaging Latency: Is <50ms Achievable?

**The requirement:** Typeahead search needs **<50ms round-trip** per keystroke to feel responsive.

**Evidence on native messaging performance:**

| Browser | Documented Latency | Source |
|---------|-------------------|--------|
| Firefox | "Few milliseconds" expected; bugs caused 20-25x slowdowns | [Bug 2002517](https://bugzilla.mozilla.org/show_bug.cgi?id=2002517) |
| Safari | Not documented | Apple provides no latency guarantees |
| Chrome | ~1-5ms typical | Community benchmarks |

**Safari's advantage:** Native messaging is built into the Safari extension architecture via XPC, not a bolted-on protocol. This *should* mean lower latency than Chrome/Firefox's stdin/stdout approach.

**Architecture recommendation:**

```
WRONG: Every keystroke → sendNativeMessage → read plist → return results
RIGHT:
  1. On extension load: sendNativeMessage("getAll") → cache in extension
  2. On keystroke: search local cache (FlexSearch)
  3. On background: periodic refresh every 30s
```

**Cache-first architecture eliminates native messaging from the typeahead hot path.** Native messaging only needed for:
- Initial load
- Periodic refresh
- Write operations (if any)

**Measured expectation:** With caching, we should achieve **<10ms search latency** (FlexSearch in-memory) regardless of native messaging speed.

---

### 11.5 Full Disk Access: UX Friction Analysis

**The problem:** Reading `~/Library/Safari/Bookmarks.plist` and `~/Library/Safari/History.db` requires **Full Disk Access** (FDA) on macOS Catalina+.

**User journey:**

```
1. Install extension from App Store
2. Enable extension in Safari Settings
3. Try to use Cmd+K → "Bookmarks unavailable"
4. See prompt: "Grant Full Disk Access in System Preferences"
5. Open System Preferences → Security & Privacy → Privacy → Full Disk Access
6. Click lock to make changes → Enter password
7. Click + → Navigate to app → Select app
8. Restart app (some cases)
```

**This is 8 steps with password entry.** Compare to Chrome extensions: 0 extra steps.

**User acceptance data:** No published statistics found, but anecdotal evidence from backup apps (CrashPlan, Arq) and security tools (Intego, Malwarebytes) suggests **significant drop-off** at FDA prompts.

**Mitigations:**

| Strategy | Implementation |
|----------|----------------|
| **Progressive disclosure** | Show tabs-only search first (no FDA needed); prompt for FDA only when user clicks "Add bookmarks" |
| **In-app guide** | Show animated GIF/video walkthrough of FDA process |
| **Clipboard fallback** | Let users paste exported bookmarks HTML if they refuse FDA |
| **iCloud approach** | If user has iCloud Bookmarks enabled, Safari may sync to CloudKit (research needed) |

**Partial functionality without FDA:**
- Tabs: ✅ Works via `browser.tabs.query()`
- Bookmarks: ❌ Requires FDA
- History: ❌ Requires FDA
- Reading List: ❓ May be in separate plist (needs verification)

**Recommendation:** Launch with **tabs-only MVP** that requires no FDA. Add bookmark/history as opt-in feature with clear FDA walkthrough.

---

### 11.6 iOS Safari Feasibility

**Key differences from macOS:**

| Feature | macOS | iOS |
|---------|-------|-----|
| Native messaging | ✅ XPC built-in | ✅ XPC built-in |
| File system access | ✅ With FDA | ❌ No direct file access |
| Bookmarks.plist | ✅ Readable | ❌ Not accessible |
| History.db | ✅ Readable | ❌ Not accessible |
| App Groups | ✅ SharedContainer | ✅ SharedContainer |
| Extension popup | HTML/CSS/JS | HTML/CSS/JS only |
| Native UI in popup | ❌ Web only | ❌ Web only |

**iOS Safari data access strategy:**

Since iOS sandboxing prevents direct file access, alternatives:

1. **iCloud sync**: If Safari syncs bookmarks via iCloud, query CloudKit directly (requires iCloud entitlement + user permission)

2. **Share Extension workaround**: User manually shares URLs to our app, building a shadow bookmark database

3. **Tabs only**: `browser.tabs.query()` works on iOS Safari — ship tabs-only version

4. **Reading List API**: [Research needed] Safari may expose Reading List via different mechanism

**iOS background script crash bug:**

[Documented issue](https://github.com/nicedoc/content-script-non-responsive-bug): Non-persistent background scripts crash after ~30 seconds on physical iOS devices even when receiving messages.

**Workarounds:**
- Keep background alive with periodic alarms
- Handle reconnection gracefully
- Store state in `browser.storage.local` (survives crashes)

**Recommendation:** iOS version should be **tabs-only + optional iCloud bookmarks** (if feasible). Do not promise bookmark plist access on iOS.

---

### 11.7 Accessibility: VoiceOver + ARIA Requirements

**Required ARIA attributes for Cmd+K modal:**

```html
<div role="dialog"
     aria-modal="true"
     aria-labelledby="search-title"
     aria-describedby="search-desc">
  <h2 id="search-title" class="sr-only">Quick Search</h2>
  <p id="search-desc" class="sr-only">Search tabs, bookmarks, and history</p>

  <input type="text"
         role="combobox"
         aria-expanded="true"
         aria-controls="results-list"
         aria-activedescendant="result-0"
         aria-autocomplete="list">

  <ul id="results-list" role="listbox">
    <li id="result-0" role="option" aria-selected="true">...</li>
  </ul>
</div>
```

**VoiceOver-specific bugs:**

| Issue | Platform | Workaround |
|-------|----------|------------|
| `display: none` to `display: block` doesn't announce | iOS Safari | Use `visibility: hidden/visible` instead |
| `aria-hidden="true"` + `inert` traps users | All | Remove `inert` or provide Escape key handler |
| Focus doesn't follow `aria-activedescendant` | Safari | Manually move focus with `.focus()` |

**Keyboard navigation requirements:**

| Key | Action |
|-----|--------|
| ↓/↑ | Move selection in results |
| Enter | Open selected result |
| Escape | Close modal, return focus to page |
| Tab | Move between input and results (or trap in modal) |

**Testing checklist:**
- [ ] VoiceOver (macOS): Enable with Cmd+F5, navigate entire modal
- [ ] VoiceOver (iOS): Enable in Settings, test on physical device
- [ ] Keyboard-only: Unplug mouse, complete full search flow
- [ ] High contrast mode: Test with macOS Accessibility settings
- [ ] Reduced motion: Respect `prefers-reduced-motion`

---

### 11.8 Summary: Risk-Adjusted Implementation Order

Based on this analysis, recommended implementation phases:

| Phase | Scope | Risk Level | Dependencies |
|-------|-------|------------|--------------|
| **1. Tabs MVP** | Cmd+Shift+K → search open tabs | Low | None |
| **2. Bookmarks (macOS)** | Add bookmark search | Medium | FDA permission |
| **3. History (macOS)** | Add history search | Medium | FDA permission |
| **4. iOS Tabs** | Port tabs-only to iOS | Medium | iOS-specific testing |
| **5. iOS iCloud** | iCloud bookmark sync | High | CloudKit entitlement, user auth |

**Deferred/Reconsidered:**

- ❌ **Cmd+K override**: Too fragile, Safari may reclaim it
- ⚠️ **Content script modal**: Start with toolbar popup, add content script modal as enhancement
- ⚠️ **FlexSearch**: Benchmark first, have fuzzysort as fallback
- ❌ **iOS bookmark plist access**: Not feasible

---

## References

- [Chrome Commands API](https://developer.chrome.com/docs/extensions/reference/api/commands)
- [SolanaSafariWalletExtension](https://github.com/solana-mobile/SolanaSafariWalletExtension) - Native messaging example
- [chrome-omnicomplete](https://github.com/chrisseroka/chrome-omnicomplete) - Fuzzy tab/bookmark search
- [FlexSearch](https://github.com/nextapps-de/flexsearch) - High-performance fuzzy search
- [Fuse.js](https://fusejs.io/) - Lightweight fuzzy search
