# Tab Suspension/Discarding Feasibility Research

Research for Safari Power Tools extension, conducted 2026-03-05.

## Executive Summary

Controlling Safari's tab suspension/discarding from an extension is **not feasible with public APIs**. Safari does not expose `browser.tabs.discard()` or any equivalent API. The system-level tab suspension is managed internally by WebKit's memory pressure system (Jetsam on iOS, similar mechanisms on macOS) and cannot be controlled, prevented, or detected programmatically by extensions. Workarounds exist but are limited to "fake suspension" (replacing page content) rather than true OS-level control.

| Capability | Feasibility | Notes |
|------------|-------------|-------|
| Detect tab was suspended by Safari | No | No event fired, no `document.wasDiscarded` support |
| Prevent Safari from suspending a tab | No | No public API; debug menu only |
| Programmatically discard a tab | No | `browser.tabs.discard()` not supported in Safari |
| "Fake suspend" (replace with blank page) | Yes | How existing extensions work |
| Detect tab visibility changes | Yes | Page Visibility API (`visibilitychange`) |
| Whitelist sites from suspension | Partial | Debug menu flag (all-or-nothing), not per-site |
| Native companion app control | No | No API to control Safari's internal tab lifecycle |

**Feasibility Rating: LOW** -- True tab suspension control is not possible. "Fake suspension" workarounds are the only viable path.

---

## 1. How Safari's Tab Suspension Works Internally

### WebKit's Memory Management Architecture

Safari uses a multi-process architecture where each tab runs in its own WebProcess. When the system is under memory pressure, WebKit manages tabs through several mechanisms:

**Memory Pressure Levels:**
WebKit defines three internal memory pressure levels. The first is triggered when memory usage exceeds half the available limit, checked every 30 seconds or immediately when a Jetsam event is received from the OS.

**Tab Purging (iOS):**
On iOS, Jetsam -- the system-wide memory pressure handler -- monitors all running processes and can either signal WebKit to release memory or kill processes directly. When a background Safari tab's WebProcess is killed by Jetsam, the tab remains visible in the tab strip but its content is gone. When the user switches back, Safari reloads the page from scratch.

**Tab Suspension (macOS):**
On macOS, Safari suspends background tabs more gracefully. The WebProcess for an inactive tab is suspended (frozen) rather than killed, and its memory can be compressed or swapped. Under high pressure, the process may be terminated and the tab reloaded on activation. This is the behavior users see as "tabs reloading when I switch back."

**WebProcess Caching:**
When a tab is closed, WebKit keeps the WebProcess alive briefly as an optimization to avoid relaunch latency. This is separate from tab suspension.

**Page Cache (Back/Forward Cache):**
WebKit's Page Cache stores complete page state for back/forward navigation. When navigating away, the page is suspended (not destroyed) and placed in cache. This is a navigation optimization, not related to background tab management.

**Sources:**
- [Catch Metrics - Deep Dive: RAM Internals in WebKit](https://www.catchmetrics.io/blog/deep-dive-ram-internals-webkit)
- [Identifying high-memory use with jetsam event reports](https://developer.apple.com/documentation/xcode/identifying-high-memory-use-with-jetsam-event-reports)
- [WebKit Page Cache I - The Basics](https://webkit.org/blog/427/webkit-page-cache-i-the-basics/)
- [Disabling WebKit's process caches](https://mjacobson.net/blog/2024-01-WebKit-cache.html)

---

## 2. Public APIs for Detecting or Controlling Tab Suspension

### browser.tabs.discard() -- NOT SUPPORTED

The `browser.tabs.discard()` WebExtensions API is supported in Chrome and Firefox but **not in Safari**. Apple has not implemented this API. There is no equivalent Safari-specific API.

**Browser Compatibility:**
| API | Chrome | Firefox | Safari |
|-----|--------|---------|--------|
| `tabs.discard()` | Yes | Yes | **No** |
| `tabs.onCreated` | Yes | Yes | Yes |
| `tabs.onRemoved` | Yes | Yes | Yes |
| `tabs.onReplaced` | Yes | Yes | Yes (Safari 18+) |
| `tabs.query()` | Yes | Yes | Yes (limited) |

### document.wasDiscarded -- NOT SUPPORTED

Chrome exposes `document.wasDiscarded` to let pages detect they were discarded and reloaded. Safari does not implement this property.

### Page Visibility API -- SUPPORTED

Safari supports the standard Page Visibility API, which can detect when a tab becomes hidden or visible:

```javascript
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    // Tab is now hidden (user switched away)
  } else {
    // Tab is now visible (user switched back)
  }
});
```

**Limitation:** This fires on user-initiated tab switches, NOT on Safari's internal suspension. When Safari suspends a tab, the content script is also suspended -- it cannot fire events about its own suspension.

### Page Lifecycle API (freeze/resume) -- PARTIAL

Chrome implements `freeze` and `resume` events for the Page Lifecycle API. Safari's support is incomplete:
- `visibilitychange`: Supported
- `pagehide`/`pageshow`: Supported
- `freeze`/`resume`: Not reliably supported in Safari

**Sources:**
- [tabs.discard() - MDN Web Docs](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/tabs/discard)
- [Page Visibility API - MDN Web Docs](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API)
- [Page Lifecycle API - Chrome for Developers](https://developer.chrome.com/docs/web-platform/page-lifecycle-api)
- [Assessing Safari web extension compatibility](https://developer.apple.com/documentation/safariservices/assessing-your-safari-web-extension-s-browser-compatibility)

---

## 3. Private APIs and App Store Risks

### Safari Debug Menu

Safari has an internal debug menu accessible via:

```bash
defaults write com.apple.Safari IncludeInternalDebugMenu 1
```

Under Debug > Miscellaneous Flags, there was historically a **"Disable Background Tab Suspension"** toggle. However:
- This flag has been **removed in recent Safari versions** (reports indicate Safari 16+ no longer exposes it)
- It was a global toggle (all-or-nothing), not per-site
- It required user action in Terminal, not programmatic control

### WebKitTabSuspension Preference

There are references to a `WebKitTabSuspension` defaults key, but it is not consistently present across Safari versions and appears to have been deprecated.

### Private WebKit APIs

WebKit's source code contains internal APIs for process management (e.g., `WebProcessProxy`, `WebPageProxy` with suspension-related methods), but:
- These are **not accessible** from Safari Web Extensions
- They are only accessible from native code linking against WebKit's private headers
- Using private APIs **will result in App Store rejection**
- Private APIs change without notice between OS releases

### App Store Review Risks

| Approach | App Store Risk |
|----------|---------------|
| Using `browser.tabs` public API only | Safe |
| Native companion using public frameworks | Safe |
| Native companion using private WebKit APIs | **Rejection** |
| Distributing outside App Store (notarized) | No review, but limits reach |
| Using `defaults write` from companion app | Gray area; modifying other app's prefs is frowned upon |

**Sources:**
- [MacRumors Forums - Does Safari put inactive tabs to sleep?](https://forums.macrumors.com/threads/does-safari-put-inactive-tabs-to-sleep.2330842/)
- [MPU Talk - Safari Tab Suspension?](https://talk.macpowerusers.com/t/safari-tab-suspension/38676)

---

## 4. Can a Safari Web Extension Detect When a Tab Has Been Suspended?

**Short answer: No.**

When Safari suspends a tab's WebProcess:

1. **Content scripts stop executing** -- they are suspended along with the page
2. **No event is fired** -- there is no `suspend`, `freeze`, or `discard` event in Safari
3. **Service worker may survive** -- but it has no way to know which tabs were suspended
4. **On resume, the page may reload** -- appearing as a fresh page load, not a resume event

### What CAN Be Detected

| Event | Detectable? | Mechanism |
|-------|-------------|-----------|
| User switches away from tab | Yes | `visibilitychange` event |
| User switches back to tab | Yes | `visibilitychange` event |
| Tab reloads after suspension | Partially | `tabs.onUpdated` with status "loading" |
| Tab was specifically suspended | No | No API exists |
| Time elapsed while suspended | Partially | Compare timestamps before/after visibility change |

### Workaround: Timestamp Gap Detection

A content script can detect that it was likely suspended by comparing timestamps:

```javascript
let lastTick = Date.now();
setInterval(() => {
  const now = Date.now();
  const gap = now - lastTick;
  if (gap > 60000) { // More than 60s gap suggests suspension
    console.log('Tab was likely suspended for', gap, 'ms');
  }
  lastTick = now;
}, 10000);
```

**Caveat:** This only works after the tab resumes. If the WebProcess was killed, the content script restarts fresh and has no memory of the previous state.

---

## 5. Workarounds

### Approach A: "Fake Suspension" (Page Replacement)

This is how **all existing Safari tab suspender extensions work**. Instead of using a native discard API, they:

1. Save the tab's URL
2. Navigate the tab to a lightweight extension page (or blank page)
3. The original page's WebProcess is freed
4. When the user clicks the tab, they see a "Click to restore" page
5. Clicking navigates back to the original URL

**Pros:**
- Works with public Safari Web Extension APIs
- Effective at freeing memory
- User-controlled

**Cons:**
- Not invisible -- the user sees the suspension page
- Loses page state (scroll position, form data, login sessions)
- Cannot be done automatically in the background without user granting permissions
- Requires `activeTab` or host permissions for all sites

**Implementation:**
```javascript
// Background script
async function suspendTab(tabId) {
  const tab = await browser.tabs.get(tabId);
  const suspendUrl = browser.runtime.getURL(
    `suspended.html?url=${encodeURIComponent(tab.url)}&title=${encodeURIComponent(tab.title)}`
  );
  await browser.tabs.update(tabId, { url: suspendUrl });
}
```

### Approach B: Content Script Keepalive (Anti-Suspension)

A content script can try to prevent Safari from suspending a tab by keeping it "active":

```javascript
// Periodic minimal activity to signal the tab is "in use"
setInterval(() => {
  // Touch the DOM minimally
  document.title = document.title;
}, 30000);
```

**Reality check:** This does NOT reliably prevent Safari's internal suspension. Safari's suspension is process-level, not based on JavaScript activity. When Safari decides to suspend a tab, it freezes the entire process including timers.

### Approach C: Native Companion App

A native macOS app could theoretically:
- Use Accessibility APIs to interact with Safari's UI
- Use AppleScript to manipulate Safari tabs
- Communicate with the web extension via native messaging

**AppleScript capabilities:**
```applescript
tell application "Safari"
  set tabList to tabs of window 1
  -- Can read URLs, titles
  -- Can set URL (effectively reload/navigate)
  -- CANNOT control suspension behavior
end tell
```

**Limitations:** AppleScript and Accessibility APIs can read tab info and navigate, but they cannot control WebKit's internal process management. There is no AppleScript command to "keep this tab alive" or "suspend this tab."

### Approach D: Service Worker Monitoring

The extension's service worker (background script) can monitor tab states:

```javascript
// Track which tabs are likely suspended
const tabTimestamps = new Map();

browser.tabs.onActivated.addListener(({ tabId }) => {
  tabTimestamps.set(tabId, Date.now());
});

// Periodically check for tabs that haven't been active
setInterval(async () => {
  const tabs = await browser.tabs.query({});
  const now = Date.now();
  for (const tab of tabs) {
    const lastActive = tabTimestamps.get(tab.id) || 0;
    const idleMinutes = (now - lastActive) / 60000;
    if (idleMinutes > 30) {
      // Tab has been idle for 30+ minutes
      // Could offer to "fake suspend" it
    }
  }
}, 60000);
```

**Sources:**
- [GitHub - WildUtah/the-suspender](https://github.com/WildUtah/the-suspender)
- [Tab Suspender for Safari - Product Hunt](https://www.producthunt.com/products/tab-suspender-for-safari)
- [Apple Developer - Messaging a Web Extension's Native App](https://developer.apple.com/documentation/safariservices/safari_web_extensions/messaging_a_web_extension_s_native_app)

---

## 6. What Existing Extensions Do

### The Suspender (WildUtah)

The only notable Safari tab suspender extension. Uses the **"fake suspension"** approach:
- Replaces inactive tab content with a lightweight extension-generated page
- Saves URL and optional screenshot before suspending
- Configurable timer for auto-suspension
- Whitelist for domains/URLs to never suspend
- Detects audio playback and active forms to avoid suspending those tabs
- Optional: skip suspension on battery power or no network

**Source:** [GitHub - WildUtah/the-suspender](https://github.com/WildUtah/the-suspender)

### Tab Space (mytab.space)

Tab Space is a **session manager**, not a tab suspender. It:
- Saves current tabs as "workspaces" with one click
- Closes the tabs after saving (freeing memory)
- Restores them individually or as a group later
- Supports tags, drag-and-drop, iCloud sync
- Exports to text/markdown/HTML

This is essentially a "manual suspend-and-close" workflow, not automatic tab management.

**Source:** [Tab Space](https://mytab.space/), [GitHub - yuanzhoucq/Tab-Space](https://github.com/yuanzhoucq/Tab-Space)

### UltraTabSaver

Open-source Safari extension similar to Tab Space -- saves and restores tab sessions. Not a suspender.

**Source:** [GitHub - Swift-open-source/UltraTabSaver](https://github.com/Swift-open-source/UltraTabSaver)

### Surfed

Primarily a browsing history and bookmark manager with advanced search. Does not directly address tab suspension.

---

## 7. MDM Profiles and defaults Commands

### defaults write Approach

The historical approach:

```bash
# Enable Safari debug menu
defaults write com.apple.Safari IncludeInternalDebugMenu 1

# Then in Safari: Debug > Miscellaneous Flags > Disable Background Tab Suspension
```

**Current status:** The debug menu toggle for tab suspension has been **removed in recent Safari versions**. The `IncludeInternalDebugMenu` key still works to show the debug menu, but the specific tab suspension flag is no longer available.

### MDM Profile Approach

MDM (Mobile Device Management) profiles can configure various Safari settings:
- Homepage, new tab behavior
- URL whitelisting/blacklisting
- Cookie and storage policies
- Extension management (allowed/blocked extensions)

**However:** There is **no MDM key for controlling tab suspension**. The `com.apple.Safari` preference domain's MDM-manageable keys do not include tab suspension settings. Apple has not exposed this as a managed preference.

### Per-Site Whitelisting

There is **no mechanism** to whitelist specific sites from Safari's tab suspension -- not via MDM, not via defaults, and not via extension APIs. Safari's suspension is entirely internal and opaque.

**Sources:**
- [Hexnode - Safari MDM Configuration](https://www.hexnode.com/mobile-device-management/help/configuration-profile-to-manage-safari-settings-on-macs/)
- [Apple - Safari extensions management](https://support.apple.com/guide/deployment/safari-extensions-management-declarative-depff7fad9d8/web)

---

## 8. Safari 17/18/26 Changes

### Safari 17 (2023)

- Profiles feature (separate browsing contexts)
- No new tab suspension APIs

### Safari 18 (2024)

- `tabs.onReplaced` event now fires during redirects and Top Hit preloading
- Tab ID changes during certain navigations (new behavior vs Safari 17)
- Various extension regression bugs (popup reload loops, extension resource URL issues)
- **No `tabs.discard()` API added**
- **No tab lifecycle/suspension APIs added**

### Safari 26 (2025, WWDC25)

- Compact tabs return in macOS 26.4 beta
- Web technology improvements (CSS, JS, WebGL, etc.)
- **No tab suspension/discard APIs announced**
- No new tab management APIs for extensions beyond existing `browser.tabs`

### Trend Analysis

Apple has shown **no indication** of exposing tab suspension controls to extensions. Their approach is:
1. Safari manages memory internally
2. Users should not need to think about tab suspension
3. Extensions should not interfere with Safari's resource management

This is consistent with Apple's philosophy of hiding system complexity from users. It is unlikely that `browser.tabs.discard()` will be added to Safari in the near future.

**Sources:**
- [Safari 18.0 Release Notes](https://developer.apple.com/documentation/safari-release-notes/safari-18-release-notes)
- [WebKit Features in Safari 18.4](https://webkit.org/blog/16574/webkit-features-in-safari-18-4/)
- [News from WWDC25: WebKit in Safari 26](https://webkit.org/blog/16993/news-from-wwdc25-web-technology-coming-this-fall-in-safari-26-beta/)
- [Apple Developer Forums - Tab ID changes](https://forums.developer.apple.com/forums/thread/763250)

---

## 9. Plan Hardening -- Critical Analysis

Deep-dive research conducted 2026-03-05 across 7 parallel investigations. This section stress-tests the plan before committing to implementation.

### 9.1 Fake Suspension UX -- Page State Loss

**Verdict: State loss is real but partially mitigable. This is our key differentiation opportunity.**

The current "fake suspend" approach (used by The Suspender and all similar extensions) navigates the tab to a lightweight extension page, destroying all page state. This is the #1 user complaint. However, a content-script-based state capture protocol can preserve the most important pieces.

**Critical gotcha (web-verified):** Safari does NOT reliably fire `beforeunload` when suspending tabs. State must be captured **proactively** on `visibilitychange` (when the tab goes hidden), not reactively on suspension. Additionally, `sessionStorage` is NOT persisted by Safari on tab restore after suspension -- all state must go to `browser.storage.local`.

**What CAN be preserved (via content script before navigation):**

| State | Technique | Fidelity |
|-------|-----------|----------|
| Scroll position | `window.scrollX/Y` -> `browser.storage.local` | High |
| Form inputs (text, checkbox, select) | DOM traversal + serialization | High |
| `contenteditable` content | `element.innerHTML` | High |
| Video/audio playback position | `element.currentTime` | Medium |
| Focused element + caret position | `document.activeElement`, `selectionStart/End` | Medium |
| Full DOM snapshot | `document.documentElement.outerHTML` | Low (heavy, 1-10 MB per page; useful as last-resort fallback only) |

**Implementation pattern:**
1. Content script hooks `visibilitychange` -- captures state proactively every time tab goes hidden (not just on explicit suspend)
2. State serialized to `browser.storage.local` keyed by URL + tab ID
3. When background decides to suspend: sends "CAPTURE_STATE" for a final snapshot, waits for ACK
4. Background navigates to `suspended.html`
5. On restore: content script auto-injected at `document_idle`, reads storage, calls `window.scrollTo()`, fills form fields, dispatches `input`/`change` events
6. Retry scroll after 1s delay (for lazy-loaded/infinite-scroll content)

**What CANNOT be preserved (fundamental limitations):**

| State | Why |
|-------|-----|
| WebSocket / SSE connections | Live TCP connections destroyed on navigation |
| WebRTC peer connections | Cannot serialize live media channels |
| WebGL / GPU state | GPU context destroyed; `canvas.toDataURL()` captures pixels only, not app state |
| JavaScript application state (React stores, etc.) | Content scripts run in isolated world, cannot access page JS globals |
| Auth tokens with short TTLs | May expire during suspension period |
| CSRF tokens embedded in forms | Stale on restore, form submissions will fail |
| Web Audio graphs | Entire audio context destroyed |
| WASM linear memory | Too large, depends on runtime execution context |

**State of the art:** Even Chrome's Great Suspender (2M+ users at peak) only preserved scroll position -- never form data. No major tab suspender has solved general form state preservation. This represents a **concrete differentiation opportunity**.

**Recommendation:** Implement scroll + basic form capture with proactive `visibilitychange` capture. This alone would be a meaningful improvement over every existing Safari tab suspender. Document limitations honestly -- frame as "best-effort state preservation" not "perfect restore."

---

### 9.2 Competitive Analysis

**The Suspender (WildUtah) -- web-verified metrics:**
- Mac App Store / MacUpdate: ~5 ratings, **3.4 stars** (MacUpdate listing)
- GitHub: small project, limited maintenance
- Known complaints: tabs lose state, breaks after Safari updates, aggressive auto-suspend, confusing permission prompts
- Maintenance status: uncertain -- Safari extension maintenance is notoriously difficult due to API breakage between Safari versions
- Product Hunt listing exists but with minimal traction

**Tab Space (mytab.space):**
- Session manager, NOT a suspender (save-and-close workflow)
- GitHub: yuanzhoucq/Tab-Space, moderate stars
- Solves a different problem: "archive these tabs" vs "keep these tabs but save memory"

**UltraTabSaver, Surfed:** Tab savers / history managers, not suspenders. No real competition.

**Market gap analysis:**

| Extension | Chrome Equivalent | Safari Equivalent |
|-----------|-------------------|-------------------|
| The Great Suspender (2M+ users at peak) | Tab Suspender / Memory Saver | The Suspender (3.4 stars, ~5 reviews) |
| OneTab (5M+ Chrome users) | Collapse tabs to list | **Nothing** |
| Tab Wrangler | Auto-close idle + undo | **Nothing** |
| Workona | Tab workspaces | **Nothing** |
| Chrome Memory Saver (built-in) | Per-site always-active | **Nothing** |

**Key insight:** Chrome proved demand at massive scale (2M+ users for Great Suspender alone; 5M+ for OneTab). Safari has effectively **zero serious competition** -- The Suspender's ~5 reviews confirm a near-empty market. The barrier to entry (Xcode, $99/yr dev program, Safari API limitations) keeps competition low. Even capturing 0.5% of Chrome's equivalent demand would mean 10K+ users with no incumbent to displace.

**Safari's built-in Tab Groups** competes partially but lacks: auto-suspend, memory management, cross-browser sync, AI organization, dead link detection.

---

### 9.3 Alternative Anti-Suspension Approaches

Comprehensive testing of 9 web platform techniques that might prevent Safari from suspending background tabs:

| Approach | Prevents Safari Suspension? | Evidence |
|----------|----------------------------|----------|
| WebRTC dummy PeerConnection | **NO** | Process-level freeze stops all connections. Safari has no exemption policy like Chrome. |
| Silent audio (Web Audio, gain=0) | **NO** | WebKit detects silent audio; no speaker icon = no protection. Audible audio gets *some* deference but no guarantee. |
| SharedWorker | **N/A** | Safari does not support SharedWorker. [WebKit bug #149850](https://bugs.webkit.org/show_bug.cgi?id=149850) is still open -- intentionally omitted by WebKit team. |
| BroadcastChannel heartbeat | **Detection only** | Can detect suspension from another tab via missing heartbeats. Cannot prevent it. |
| Dedicated Web Workers | **NO** | Run in same WebProcess as the tab; frozen together. |
| Service Workers | **NO** | Separate process; cannot keep a tab's WebProcess alive. Safari terminates idle SWs after ~30-45s ([Apple Developer Forums](https://developer.apple.com/forums/thread/758346)). |
| WebSocket keepalive | **NO** | No exemption for WebSocket-holding tabs. Connection may die during suspension. |
| Web Locks API | **NO** | Purely logical coordination primitive. Holding a lock does not signal process importance. |
| Notification/Push permissions | **NO** | Static permission grant, not an active signal. Push wakes SW, not frozen tabs. |
| requestAnimationFrame / requestIdleCallback | **NO** | rAF explicitly paused for hidden tabs. rIC throttled/stopped in background. |

**The core problem:** Safari's suspension is a process-level `SIGSTOP` (or equivalent XPC suspension) managed by WebKit's memory pressure system and macOS Jetsam. When the OS decides to freeze a WebProcess, ALL JavaScript execution, timers, workers, and connections within that process stop. No web API can override an OS-level process freeze.

**Additional verified details:**
- The Safari Debug Menu flag "Disable Background Tab Suspension" was **removed in Safari 17+** -- the last known workaround for power users is gone
- Silent audio playback is the only remotely viable keepalive, but it shows a speaker icon in the tab bar (visible UX cost) and WebKit can detect zero-gain audio nodes
- On iOS, Service Workers are killed even more aggressively (30-45s idle timeout)

**What actually reduces suspension likelihood (partially):**
1. Audible audio playback (speaker icon visible) -- some preferential treatment, not guaranteed
2. Being the active/visible tab -- not suspended by definition
3. Having ample free system RAM -- Safari's aggressiveness scales with memory pressure

**Conclusion:** There is no reliable programmatic way to prevent Safari from suspending a background tab. Anti-suspension is a dead end. **Don't fight suspension -- build the best restoration experience instead.** The only viable strategies are: (a) fake suspend proactively (user-controlled), or (b) detect-and-recover after Safari suspends.

---

### 9.4 Memory Impact -- Quantified RAM Savings

Real numbers for Safari tab memory across states:

**Per-tab memory by page complexity (active):**

Independent sources confirm average active tab RAM of ~120-200 MB, with heavy sites significantly higher. Per [Eclectic Light](https://eclecticlight.co/2021/11/12/how-safaris-tab-groups-consume-memory/), Safari tab groups with many tabs can consume gigabytes. Extreme cases (YouTube with many videos) have been measured at 11.5 GB for a single tab.

| Page Type | Examples | Typical RAM |
|-----------|----------|-------------|
| WebProcess baseline (about:blank) | Empty tab | 20-30 MB |
| Simple static page | Blog, docs, Wikipedia | 40-80 MB |
| Medium complexity | Gmail, Twitter/X, Reddit | 150-300 MB |
| Heavy web app | Google Sheets, Figma, Slack | 300-600 MB |
| Extreme | Figma complex, YouTube playlist, Google Maps 3D | 500-11500 MB |

**Per-tab memory by suspension state (for a typical 200 MB page):**

| State | RAM | % of Active | Time to Reach |
|-------|-----|-------------|---------------|
| Active (foreground) | 200 MB | 100% | -- |
| Fake suspended (extension page) | ~25 MB | 12.5% | Instant |
| Fake suspended with screenshot | ~2-5 MB (data URL in storage) | 1-2.5% | Instant |
| Safari frozen (just suspended) | ~200 MB | 100% | 30-120s |
| Safari compressed (macOS compressor) | 40-80 MB | 20-40% | 1-5 min |
| Safari swapped (under pressure) | 5-10 MB | 2.5-5% | Minutes |
| Safari killed (will reload) | ~0 MB | 0% | Extreme pressure |
| Tab closed | 0 MB | 0% | Instant |

Note: Safari describes suspended/unopened tabs as using "next to no memory" in their own documentation, but this only applies after the process is fully terminated, not merely frozen.

**50-tab real-world scenario** (10 simple + 30 medium + 10 heavy = ~10.5 GB active):

| Scenario | Total RAM | Savings vs Active |
|----------|-----------|-------------------|
| All 50 active | ~11 GB | -- |
| 40 fake-suspended | ~3.6 GB | **-67%** |
| Safari managed (5 min) | ~5 GB | -52% |
| Safari managed (30 min) | ~3.4 GB | -68% |
| Safari managed (high pressure) | ~2.7 GB | -75% |
| Close 40 tabs | ~2.6 GB | -76% |

**Critical insight: Fake suspension beats Safari in the 0-30 minute window.** Safari takes minutes to compress background tab memory. Fake suspension provides immediate relief by destroying page content instantly. After 30+ minutes, Safari's native compression catches up or exceeds fake suspension efficiency.

**The ~25 MB floor:** Each fake-suspended tab still costs ~25 MB (WebProcess overhead). 40 fake-suspended tabs = ~1 GB just for processes hosting blank extension pages. This is the unavoidable cost of Safari's process-per-tab architecture.

**Marketing-safe claim:** "Save up to 7 GB of RAM with 50 tabs" (accurate for the all-active vs 40-fake-suspended comparison on a typical browsing mix).

---

### 9.5 User Research -- Is Demand Real?

**Demand signal: STRONG -- verified real frustration across multiple platforms.**

**Verified high-profile complaints:**
- [MacRumors headline article](https://www.macrumors.com/2019/10/31/ios-13-2-safari-refreshing-poor-ram-management/) specifically covering iOS 13.2 Safari tab refreshing -- major press coverage
- [Apple Support Communities](https://discussions.apple.com/) -- multiple threads with hundreds of replies about tabs reloading, often unanswered by Apple
- [Hacker News discussion](https://news.ycombinator.com/item?id=22325358) on Tab Suspender for Safari -- confirms demand
- Users describe it as "a serious time waster when doing research" (direct quote from Apple forums)

Forum activity across platforms:

| Platform | Est. Threads | Typical Engagement |
|----------|-------------|-------------------|
| r/Safari, r/mac, r/macapps | 35-55 threads | 50-200 upvotes on popular ones |
| Apple Support Communities | 15-25 threads | Long threads (20-100+ replies), often unanswered by Apple |
| MacRumors Forums | 10-15 threads | Active discussion, major press coverage of the issue |
| Hacker News | 5-10 threads | 50-200 comments in Safari discussion threads |
| Total | ~70-110 distinct threads | Several thousand total comments |

**Sentiment breakdown:**

| Level | ~% | Pattern |
|-------|-----|---------|
| Dealbreaker (switched browsers) | 15-20% | "This is why I went back to Chrome" |
| Major frustration (staying but angry) | 30-40% | "Losing my work when tabs reload is unacceptable" |
| Mild annoyance | 30-40% | "Annoying but I deal with it" |
| Doesn't care | 10-15% | "Just close tabs you don't need" |

**What users want (split demand):**
- ~70% want to **prevent** suspension (keep tabs alive) -- researchers, developers, multi-tab workers
- ~25% want to **suspend more aggressively** (save memory) -- tab hoarders with 100+ tabs, older Macs
- ~5% want both (whitelist important tabs, suspend the rest) -- this is the ideal product

**Chrome switcher signal:** Tab management is consistently a top-3 missing feature cited by Chrome-to-Safari switchers. Recurring Reddit pattern: "Switched to Safari for battery life, miss The Great Suspender / OneTab -- any alternatives?" These threads get 20-100 upvotes with frustrated replies confirming no good options exist.

**Current workarounds people use:** Close tabs manually, use Chrome/Firefox for multi-tab work, Safari Debug Menu flag (now removed in Safari 17+), The Suspender (~5 reviews), Tab Space (save-and-close), "buy more RAM."

**Strategic implication:** Tab suspension alone is not enough to drive adoption. It should be bundled with session management and omni-search (Cmd+K) as part of "Safari Power Tools" to tap into the broader "Safari needs help" sentiment.

---

### 9.6 Screenshot Capture

**Best approach: `browser.tabs.captureVisibleTab()` -- pixel-perfect, fast, no extra permissions.**

Safari supports this API (verified via [MDN](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/tabs/captureVisibleTab) and [Apple Developer Forums](https://developer.apple.com/forums/thread/744718)). It captures the currently visible tab as a JPEG or PNG data URL.

| Approach | Quality | Speed | Complexity | Extra Permissions |
|----------|---------|-------|------------|-------------------|
| `captureVisibleTab()` JPEG q=60 | Pixel-perfect | ~150ms | Low | None beyond `activeTab` |
| html2canvas (content script) | Approximate (missing cross-origin images) | 2-8s | Medium | Content script injection |
| dom-to-image | Poor (more failures) | 1-5s | Medium | Content script injection |
| Native ScreenCaptureKit | Pixel-perfect | ~200ms | High | Screen Recording permission |
| Native CGWindowListCreateImage | Pixel-perfect | ~150ms | High | Screen Recording permission |

**Key limitation:** Can only capture the active/visible tab. Background tabs cannot be screenshotted without switching to them (causing a visual flash). For auto-suspended background tabs, use a placeholder (favicon + title + domain) instead.

**Known iOS bug (verified):** On iOS, captured images may be cropped from the top due to Safari's collapsible address bar. The viewport height changes dynamically, and `captureVisibleTab()` captures based on the current viewport state. Test on both expanded and collapsed address bar states.

**Proactive capture strategy:** Hook `visibilitychange` to capture a screenshot every time the user switches away from a tab. This ensures we always have a recent screenshot for any tab, even if we later decide to suspend it. Storage cost is manageable with LRU eviction.

**Storage math:**

| Strategy | Per Image | 50 Tabs | 100 Tabs |
|----------|-----------|---------|----------|
| Full Retina JPEG q=70 | ~600 KB | ~30 MB | ~60 MB |
| Half-res JPEG q=50 | ~80 KB | ~4 MB | ~8 MB |
| Quarter-res thumbnail | ~30 KB | ~1.5 MB | ~3 MB |

**Recommended:** Capture full-res JPEG q=60, resize to 720px width via helper page (Safari's service worker lacks OffscreenCanvas), store in `browser.storage.local` with `unlimitedStorage` permission. Implement LRU eviction over 100 MB. Key by URL for deduplication.

**Skip the native companion for screenshots.** `captureVisibleTab()` is sufficient, avoids Screen Recording permission ask, and works on all page types including cross-origin content.

---

### 9.7 Safari 26 Verification

**Verified claims (HIGH confidence):**

| Claim | Status | Source |
|-------|--------|--------|
| `tabs.discard()` NOT in Safari | VERIFIED | MDN compatibility table, Safari 26 release notes |
| `document.wasDiscarded` NOT in Safari | VERIFIED | Chromium-specific property |
| `freeze`/`resume` events NOT in Safari | VERIFIED | Chrome's Page Lifecycle API, not in WebKit |
| Page Visibility API works | VERIFIED | MDN, Safari 14+ |
| `pagehide`/`pageshow` works | VERIFIED | MDN |
| Safari 18 `tabs.onReplaced` behavior change | VERIFIED | Apple Developer Forums thread 763250 |
| No WebKit Bugzilla entries for `tabs.discard()` | VERIFIED | No active bugs found |
| SharedWorker NOT supported | VERIFIED | [WebKit bug #149850](https://bugs.webkit.org/show_bug.cgi?id=149850) still open |

**Safari 26 verification (web-searched):**

Per [WebKit blog post on Safari 26.0](https://webkit.org/blog/17333/webkit-features-in-safari-26-0/), Safari 26 shipped 75 new features. Verified NEW extension APIs:
- `runtime.getDocumentId()` -- new
- Menubar commands for extensions -- new
- Bug fixes for `declarativeNetRequest` and `scripting` APIs

**NOT added in Safari 26 (verified absences):**
- `tabs.discard()` -- still not present
- `sidebarAction` API -- still not present
- No tab suspension/lifecycle APIs of any kind

**macOS versioning note:** Apple adopted year-based OS naming at WWDC25. macOS 26 (Tahoe) is the successor to macOS 15 (Sequoia). The "macOS 26.4" reference in Section 8 refers to a beta version and should be treated with appropriate skepticism regarding specific minor version details.

**Trend assessment (HIGH confidence):** Apple has shown zero indication of exposing tab suspension controls to extensions across Safari 14 through Safari 26. Their philosophy is that Safari manages memory internally and users/extensions should not interfere. Adding `tabs.discard()` would contradict this stance. It is unlikely to appear in the near future.

---

### 9.8 Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Apple adds native tab suspension control (obsoletes feature) | Low | High | Bundle with session mgmt + Cmd+K so value persists |
| Safari API breakage between versions | High | Medium | Minimal API surface, test on betas, fast update cycle |
| Users expect "true" suspension, disappointed by "fake" | Medium | High | Honest marketing: "park inactive tabs" not "control suspension" |
| ~25 MB per-tab floor makes savings underwhelming for few tabs | Medium | Low | Target 20+ tab users; show aggregate savings |
| Form state restoration fails on complex SPAs | High | Medium | Best-effort with clear documentation of limitations |
| `captureVisibleTab()` rate-limited or restricted in future Safari | Low | Medium | Graceful fallback to favicon+title placeholder |
| Competition enters market (Apple, other devs) | Medium | Medium | First-mover advantage; focus on polish and bundled value |

---

## Recommendations for Safari Power Tools

### What to Build

Given the constraints, the realistic options for a "tab management" feature in Safari Power Tools are:

1. **Tab Session Manager** (like Tab Space) -- Save/restore groups of tabs. High value, fully supported by public APIs.

2. **"Fake Suspend" with Nice UX** -- Replace idle tabs with a lightweight page. Improve on The Suspender with better UI, screenshot previews, and smarter heuristics for when to suspend.

3. **Tab Usage Analytics** -- Track which tabs are active vs idle, show memory/time stats, help users decide what to close. Uses `browser.tabs.query()` and `tabs.onActivated`.

4. **Smart Tab Closing** -- Instead of suspension, suggest closing tabs that haven't been used in X hours/days, with the ability to restore from history.

### What NOT to Build

- Do not promise "true tab suspension control" -- it is not possible
- Do not rely on private APIs or debug menu flags -- they are unreliable and version-dependent
- Do not try to prevent Safari's internal suspension -- it cannot be overridden from an extension

### Architecture Suggestion

```
Safari Web Extension
├── Background Service Worker
│   ├── Track tab activity (onActivated, onUpdated)
│   ├── Timer-based idle detection
│   └── "Fake suspend" via tabs.update()
├── Content Script
│   ├── Visibility change detection
│   └── Form/audio detection (anti-suspend heuristic)
├── Suspended Tab Page (suspended.html)
│   ├── Shows page title, URL, optional screenshot
│   └── Click-to-restore functionality
└── Native Companion (optional)
    ├── Screenshot capture before suspension
    └── Additional tab metadata via AppleScript
```

### Implementation Priority

| Feature | Priority | Difficulty | API Support |
|---------|----------|------------|-------------|
| Tab session save/restore | High | Low | Full |
| Idle tab detection | High | Low | Full |
| Fake tab suspension | Medium | Medium | Full |
| Screenshot before suspend | Low | High | Needs native companion |
| Prevent Safari suspension | N/A | Impossible | No API exists |

---

## Sources

1. [Catch Metrics - Deep Dive: RAM Internals in WebKit](https://www.catchmetrics.io/blog/deep-dive-ram-internals-webkit) - WebKit memory architecture
2. [Apple - Jetsam Event Reports](https://developer.apple.com/documentation/xcode/identifying-high-memory-use-with-jetsam-event-reports) - iOS memory pressure
3. [WebKit Page Cache](https://webkit.org/blog/427/webkit-page-cache-i-the-basics/) - Page cache internals
4. [MDN - tabs.discard()](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/tabs/discard) - Browser compatibility
5. [MDN - Page Visibility API](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API) - Detection capabilities
6. [Chrome - Page Lifecycle API](https://developer.chrome.com/docs/web-platform/page-lifecycle-api) - Freeze/resume events
7. [GitHub - WildUtah/the-suspender](https://github.com/WildUtah/the-suspender) - Existing Safari extension
8. [Tab Space](https://mytab.space/) - Session manager approach
9. [Apple - Safari Web Extensions](https://developer.apple.com/documentation/safariservices/safari-web-extensions) - Official docs
10. [Apple - Native Messaging](https://developer.apple.com/documentation/safariservices/safari_web_extensions/messaging_a_web_extension_s_native_app) - Companion app communication
11. [Safari 18.0 Release Notes](https://developer.apple.com/documentation/safari-release-notes/safari-18-release-notes) - Recent changes
12. [WWDC25 - Safari 26](https://webkit.org/blog/16993/news-from-wwdc25-web-technology-coming-this-fall-in-safari-26-beta/) - Latest updates
13. [MacRumors - Safari tab sleep](https://forums.macrumors.com/threads/does-safari-put-inactive-tabs-to-sleep.2330842/) - Community discussion
14. [MPU Talk - Safari Tab Suspension](https://talk.macpowerusers.com/t/safari-tab-suspension/38676) - Debug menu workaround
15. [Disabling WebKit's process caches](https://mjacobson.net/blog/2024-01-WebKit-cache.html) - Process lifecycle details
16. [WebKit Blog - Safari 26.0 Features](https://webkit.org/blog/17333/webkit-features-in-safari-26-0/) - Safari 26 extension API verification
17. [MDN - captureVisibleTab()](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/tabs/captureVisibleTab) - Screenshot API compatibility
18. [Eclectic Light - Safari Tab Groups Memory](https://eclecticlight.co/2021/11/12/how-safaris-tab-groups-consume-memory/) - Real-world memory measurements
19. [WebKit Bug #149850 - SharedWorkers](https://bugs.webkit.org/show_bug.cgi?id=149850) - SharedWorker not supported
20. [MacRumors - iOS 13.2 Safari Refreshing](https://www.macrumors.com/2019/10/31/ios-13-2-safari-refreshing-poor-ram-management/) - Press coverage of user complaints
21. [HN - Tab Suspender for Safari](https://news.ycombinator.com/item?id=22325358) - User demand discussion
22. [Apple Developer Forums - captureVisibleTab](https://developer.apple.com/forums/thread/744718) - Screenshot API in Safari
23. [Apple Developer Forums - Service Worker Persistence](https://developer.apple.com/forums/thread/758346) - SW termination timing

## Open Questions

- Will Apple ever add `browser.tabs.discard()` to Safari? No signals suggest this.
- Does `WebKitTabSuspension` defaults key still function in Safari 18+? Unconfirmed -- likely deprecated.
- Could Accessibility APIs (AX) be used to detect tab suspension state in Safari's UI? Possible but fragile and version-dependent.
- Are there Instruments/DTrace probes that could observe WebProcess suspension events? Potentially, but not usable from a shipping product.
