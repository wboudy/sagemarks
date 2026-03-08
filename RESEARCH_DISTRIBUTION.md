# Safari Power Tools — Distribution Research

## Executive Summary

**Recommended path**: Raycast extension first, Safari extension later.

Raycast already has 47K+ installs for its browser-bookmarks extension and handles Safari tabs, bookmarks, history, and reading list natively. Building a Raycast extension gives us instant access to Mac power users without the $99/year Apple Developer Program, no Xcode friction, and the Cmd+K interface we want already exists.

---

## 1. Most Successful Open Source Safari Extensions

| Extension | Stars | Distribution | Open Source? | Price |
|-----------|-------|--------------|--------------|-------|
| [refined-github](https://github.com/refined-github/refined-github) | 30.6k | App Store + GitHub | Yes (MIT) | Free |
| [immersive-translate](https://github.com/nicedoc/immersive-translate) | 17.1k | App Store | Partially | Freemium |
| [ChatGPTBox](https://github.com/nicedoc/ChatGPTBox) | 10.7k | Multiple stores | Yes | Free |
| [uBlock](https://github.com/nicedoc/nicedoc.io) | 8.3k | TestFlight beta | Yes | Free |
| [Userscripts](https://github.com/quoid/userscripts) | 4.4k | App Store | Yes (GPL v3) | Free |
| [Hush](https://github.com/oblador/hush) | 3.6k | App Store + DMG | Yes (MIT) | Free |
| [AdGuard Safari](https://github.com/AdguardTeam/AdGuardForSafari) | 1.2k | App Store + releases | Yes | Free |

### What Made Them Popular

1. **Cross-browser support** — Most successful extensions (refined-github, immersive-translate) support Chrome/Firefox/Safari, not Safari-only
2. **Clear value prop** — Hush: "blocks cookie nags", Userscripts: "run custom scripts"
3. **Free and lightweight** — Hush is under 500KB
4. **HN/Reddit launches** — Hush's HN thread drove significant adoption
5. **Daring Fireball mentions** — Hush and others got coverage from Apple-focused blogs

### Notable Non-Open-Source Extensions

| Extension | Price | Notes |
|-----------|-------|-------|
| Noir | $3 | Closed source, very popular dark mode |
| Vinegar/Baking Soda | $2 each | Closed source, replace YouTube player |
| StopTheMadness Pro | $10-25 | Closed source, very feature-rich |
| SponsorBlock | $1.99 | Source available for building, paid on App Store |

---

## 2. Distribution Methods

### App Store (Primary channel)
- **Pros**: Discovery, automatic updates, trust signal, iOS support
- **Cons**: Requires $99/year Apple Developer Program, review delays, 15-30% cut if paid
- **Used by**: Hush, Userscripts, AdGuard, Noir

### Direct DMG Download
- **Pros**: No App Store fees, immediate releases
- **Cons**: No auto-updates, requires notarization ($99/year anyway), users must trust unsigned apps
- **Used by**: Hush (GitHub releases), AdGuard

### Homebrew Cask
- **Status**: Limited Safari extension support
- **Issue**: [homebrew-cask#7710](https://github.com/Homebrew/homebrew-cask/issues/7710) — Safari extensions bundled in apps can be cask'd, but pure extensions cannot
- **Reality**: Most Safari extensions are App Store-only, so Homebrew cask isn't a viable primary distribution

### Build from Source
- **How**: Clone repo → open in Xcode → build → enable unsigned extensions
- **Used by**: SponsorBlock, uBlock Origin Safari ports
- **Target audience**: Developers only

---

## 3. Can Open Source Extensions Be on the App Store?

**Yes, absolutely.** Examples:

| Extension | License | App Store? | How They Handle It |
|-----------|---------|------------|-------------------|
| Hush | MIT | Yes | Full source on GitHub, App Store for convenience |
| Userscripts | GPL v3 | Yes | Full source on GitHub, App Store build by maintainer |
| AdGuard Safari | GPL v3 | Yes | Source on GitHub, official App Store build |

### The Pattern
1. Keep full source on GitHub under permissive license
2. Build and submit to App Store yourself
3. Users who don't want to pay or build can use the free App Store version
4. GitHub stars + App Store presence reinforce each other

### The Risk (Amplosion's Story)
Amplosion (by Apollo developer Christian Selig) was originally open source, but the code was removed because:
> "There were some issues causing headaches, such as people taking the codebase and trying to sell/distribute it as their own."

**Mitigation**: Use GPL (not MIT) to require derivative works stay open source, or trademark the name so clones can't use it.

---

## 4. Building Without the $99/year Apple Developer Program

### Yes, It's Possible (With Limitations)

From [Apple's docs](https://developer.apple.com/documentation/safariservices/running-your-safari-web-extension):

1. Build the extension in Xcode (free)
2. Enable Safari's Developer menu (Preferences → Advanced → Show Develop menu)
3. Develop → Allow Unsigned Extensions (requires password)
4. **Limitation**: This setting resets every time Safari quits

### Automation Workaround
[allow-unsigned-extensions](https://github.com/apuokenas/allow-unsigned-extensions) automates re-enabling unsigned extensions on Safari launch.

### Reality Check
- Good for **personal use** and **development**
- Not viable for distribution to normal users
- Every user would need to enable Developer mode and allow unsigned extensions after every Safari restart

### Verdict
**For distribution, you need the $99/year program.** The unsigned path only works for developers building from source.

---

## 5. Hybrid Architecture: CLI + Lightweight Extension

### The Pattern

```
┌─────────────────────────────────────────────────────┐
│  Safari Extension (thin UI layer)                   │
│  • Cmd+K popup overlay                              │
│  • Renders search results                           │
│  • Sends queries via native messaging               │
└──────────────────┬──────────────────────────────────┘
                   │ NSXPCConnection / Native Messaging
┌──────────────────▼──────────────────────────────────┐
│  Native Companion App (thick logic layer)           │
│  • Reads ~/Library/Safari/Bookmarks.plist           │
│  • Handles LLM API calls (BYOK)                     │
│  • Vector embeddings, clustering                    │
│  • Session storage                                  │
│  • Can bundle CLI or call external CLI              │
└─────────────────────────────────────────────────────┘
```

### Real Examples

1. **Claude Code Browser Extension** — Extension for tabs/pages, native messaging to Claude CLI
2. **Video DownloadHelper** — Browser extension UI, companion app (`vdhcoapp`) does the downloading
3. **Bitwarden** — Browser extension for autofill, native app for vault management
4. **1Password** — Same pattern, browser extension + native app

### Safari-Specific: Native Messaging

From [Apple's docs](https://developer.apple.com/documentation/safariservices/safari_web_extensions/messaging_a_web_extension_s_native_app):
- Safari web extensions use `browser.runtime.sendNativeMessage()` or `browser.runtime.connectNative()`
- The native app must be bundled in the same macOS app bundle (or registered)
- Communication is via stdin/stdout or NSXPCConnection

### Benefits of Hybrid

| Aspect | Extension-Only | Hybrid CLI + Extension |
|--------|---------------|------------------------|
| Bookmark access | Needs native messaging anyway | Native app reads plist directly |
| LLM API calls | CORS issues in extension | Native app handles cleanly |
| Python existing code | Must rewrite in JS/Swift | Keep Python, call from native |
| Distribution | App Store bundle | CLI: brew/pip, Extension: App Store |
| Maintenance | Single codebase | Two codebases but cleaner separation |

### Our Situation

We already have working Python code for:
- Bookmark plist parsing
- Multi-provider LLM calls (Claude/OpenAI/Gemini)
- Embedding + clustering
- Dedupe + dead link checking

**Hybrid lets us keep this Python code** and just add a thin Swift wrapper + Safari extension UI.

---

## 6. Raycast as an Alternative

### Why This Is Compelling

Raycast already provides:
- ✅ **Cmd+K interface** — exactly what we want
- ✅ **Fuzzy search** — built-in
- ✅ **Safari integration** — existing [Safari extension](https://www.raycast.com/loris/safari) with 8 commands
- ✅ **Browser Bookmarks** — [47,225 installs](https://www.raycast.com/raycast/browser-bookmarks), searches Safari + Chrome + Firefox
- ✅ **Mac power user base** — exactly our target audience
- ✅ **No Apple Developer Program** — Raycast extensions are free to publish
- ✅ **TypeScript/React** — familiar web tech

### Existing Raycast Safari Capabilities

The [Safari extension](https://www.raycast.com/loris/safari) already provides:
- Search Tabs
- Search Bookmarks
- Search History
- Search Reading List
- Add to Reading List
- Copy URL/Title to Clipboard
- Close Other Tabs

The [Browser Bookmarks extension](https://www.raycast.com/raycast/browser-bookmarks) provides:
- Unified bookmark search across 15+ browsers including Safari
- Fuzzy search by name, domain, or tag
- Profile/folder support

### What We'd Add

A "Safari Power Tools" Raycast extension could add:
1. **AI Organize** — "Organize my bookmarks" command, uses BYOK
2. **Dead Link Scan** — "Find broken bookmarks" command
3. **Duplicate Finder** — "Find duplicate bookmarks" command
4. **Session Save/Restore** — "Save workspace" / "Restore workspace" commands
5. **Smart Search** — Combined tabs + bookmarks + history with better ranking

### Raycast Extension Development

- Extensions written in TypeScript + React
- Published to [Raycast Store](https://www.raycast.com/store) (free)
- [Docs](https://developers.raycast.com/) are excellent
- Active community, 2000+ extensions

### Limitations

- **Raycast isn't free** — $8/month for Pro (though free tier exists)
- **No iOS** — Mac-only
- **Dependency** — Users must have Raycast installed
- **Not in-browser** — Cmd+K works from anywhere, not inside Safari

### Verdict

**Raycast is the fastest path to market** for the core use cases (unified search, session management). Consider:
1. Build Raycast extension first (weeks, not months)
2. Validate demand and UX
3. Port to Safari extension later if adoption warrants the investment

---

## 7. Tools & Frameworks for Safari Extensions

### Official Apple Tools

| Tool | Purpose |
|------|---------|
| `xcrun safari-web-extension-converter` | Convert Chrome/Firefox extension to Safari |
| Xcode Safari Extension Template | Boilerplate for new extensions |
| Safari Web Extension API | Standard WebExtensions API subset |

### Chrome → Safari Conversion

```bash
xcrun safari-web-extension-converter /path/to/chrome-extension \
  --app-name "Safari Power Tools" \
  --macos-only
```

This creates an Xcode project with a macOS app wrapper + Safari extension.

### Cross-Browser Templates

| Template | Stars | Safari Support |
|----------|-------|----------------|
| [WebExtensionTemplate](https://github.com/kyle-n/WebExtensionTemplate) | ~100 | Yes, includes SwiftUI container apps |
| [extension-boilerplate](https://github.com/nicedoc/extension-boilerplate) | 3.3k | Chrome/Firefox/Opera only |
| [WXT](https://wxt.dev/) | Rising | Chrome/Firefox, Safari experimental |
| [Bepp](https://bepp.pigeonposse.com/) | New | Packages for 13+ browsers including Safari |

### WebExtensionTemplate Details

From [kyle-n/WebExtensionTemplate](https://github.com/kyle-n/WebExtensionTemplate):
- TypeScript + esbuild for fast builds
- Svelte or React for popup UI
- Includes iOS and macOS SwiftUI container apps
- webextension-polyfill for Chrome API compatibility
- ~15 steps to configure Safari (bundle IDs, signing, icons)

### Third-Party Converters

- [C2S_Converter](https://github.com/CHRISmorang/C2S_Converter) — Python GUI for Chrome → Safari
- [Bepp](https://bepp.pigeonposse.com/) — Config-driven cross-browser packaging

---

## 8. Revenue/Sustainability Models

### Open Source Safari Extension Models

| Model | Examples | Notes |
|-------|----------|-------|
| **Free + GitHub Sponsors** | Hush, Userscripts | GitHub takes 0% but Stripe takes fees |
| **Free App Store + Donations** | Many | Low conversion rate |
| **Paid App Store** | Noir ($3), StopTheMadness ($10-25) | Steady revenue, not open source |
| **Freemium** | Immersive Translate | Free tier + paid Pro |
| **BYOK (Bring Your Own Key)** | Our model | Free app, user pays LLM provider directly |

### GitHub Sponsors Reality

From research:
> "Utilities like smaller tools rarely bring in meaningful amounts of money from donations, no matter how widely used or beloved they are."

**Expect**: ~$50-500/month from sponsors for a popular extension, not $5K+.

### Our Model (BYOK)

- Extension is **100% free**
- AI features require user's own API key
- We never see user data or API usage
- Aligns with open source ethos
- No recurring revenue, but also no costs (users pay OpenAI/Anthropic directly)

---

## 9. Recommended Path

### Option A: Raycast First (Recommended)

**Timeline**: 2-4 weeks to MVP

1. Build Raycast extension with:
   - Unified search (tabs + bookmarks + history)
   - Session save/restore
   - Dead link scanner
   - AI organize (BYOK)

2. Publish to Raycast Store (free)

3. Validate with Mac power users

4. If successful, consider Safari extension port

**Pros**:
- No $99/year fee
- Cmd+K already exists
- Faster development (TypeScript vs Swift)
- Access to Raycast's user base

**Cons**:
- Requires Raycast (limits audience)
- Not in-browser experience
- Mac-only (no iOS)

### Option B: Safari Extension (Higher investment)

**Timeline**: 6-12 weeks to MVP

1. Pay $99/year for Apple Developer Program

2. Use WebExtensionTemplate for cross-browser support

3. Build native companion app in Swift for:
   - Bookmarks.plist access
   - LLM API calls
   - Session storage

4. Port Python code or rewrite in Swift

5. Submit to App Store

**Pros**:
- In-browser experience
- iOS support
- No Raycast dependency
- Larger potential audience

**Cons**:
- $99/year recurring
- Longer development time
- App Store review delays
- Must maintain Swift + JS codebases

### Option C: CLI-Only Enhancement

**Timeline**: 1-2 weeks

1. Enhance existing Python CLI
2. Add `brew install sagemarks` / `pip install sagemarks`
3. No Safari extension
4. Power users only

**Pros**:
- Fastest path
- No Apple fees
- Keep existing Python code

**Cons**:
- No GUI/popup
- Limited audience
- No Cmd+K experience

---

## 10. Plan Hardening — Critical Analysis

This section stress-tests the Raycast-first recommendation against real-world data, edge cases, and missing considerations.

---

### 10.1 Gap: Raycast User Base vs Safari Total Users

**The numbers don't lie:**

| Metric | Value | Source |
|--------|-------|--------|
| Safari desktop market share | 6.14% | Statcounter Feb 2026 |
| Estimated Safari desktop users | ~100-150M | 6.14% of ~2B desktops |
| Mac active install base | ~100M+ | Apple investor reports |
| Raycast Safari extension installs | 44,277 | Raycast Store |
| Raycast Browser Bookmarks installs | 47,226 | Raycast Store |
| Raycast penetration of Safari users | **~0.03-0.04%** | 44K / 100M |

**The contradiction:** We're recommending building for a tool that reaches 0.03% of Safari users, while positioning this as a "Safari Power Tools" product for the broader Safari ecosystem.

**Counter-argument:** The 44K Raycast Safari users are *exactly* the power users who would want our features. They've already demonstrated:
- Willingness to install third-party tools
- Preference for keyboard-driven workflows
- Mac-first mentality

**The $8/month dependency problem:**

| Raycast Tier | Price | Our Features Work? |
|--------------|-------|-------------------|
| Free | $0 | ✅ Yes (extensions work on free tier) |
| Pro | $8-10/mo | ✅ Yes |
| Teams | $12-15/user/mo | ✅ Yes |

**Key insight:** Raycast extensions work on the free tier. Users don't need Pro to use our extension. The $8/mo is only for Raycast's own premium features (unlimited AI, cloud sync, etc.).

**Verdict:** The Raycast-first approach is **not contradictory** for a free tool, since the extension works on Raycast's free tier. But we should be explicit: *this is a niche play for power users, not a mass-market Safari tool.*

---

### 10.2 Competition Depth: GitHub Stars vs Real Usage

**App Store ratings as a proxy for downloads:**

Industry rule of thumb: 1-5% of users leave ratings. Using 2% as midpoint:

| Extension | GitHub Stars | App Store Ratings | Est. Downloads | Stars:Downloads |
|-----------|--------------|-------------------|----------------|-----------------|
| Hush | 3,600 | 1,021 | ~51K | 1:14 |
| Userscripts | 4,400 | 173 | ~8.6K | 1:2 |
| StopTheMadness Pro | N/A (closed) | 173 | ~8.6K | N/A |

**Key insight:** Hush's GitHub stars significantly undercount its real user base (14x). Userscripts' stars are closer to actual downloads.

**StopTheMadness revenue estimate:**

```
Price: $14.99 (iOS/Mac universal)
Ratings: 173
Est. downloads (2% rate): ~8,600
Est. revenue (pre-Apple 30%): $129K
Est. revenue (post-30%): $90K
Timeline: ~3-4 years
Annual revenue: ~$22-30K/year
```

This is a **sustainable indie business**, not a venture-scale outcome. For a solo developer, $25K/year from a side project is meaningful.

**Non-open-source competitive landscape:**

| Competitor | Price | Est. Annual Revenue | Moat |
|------------|-------|---------------------|------|
| StopTheMadness Pro | $15 | ~$25K | Feature depth, years of refinement |
| Noir (dark mode) | $3 | Unknown | Single-purpose, polished |
| Vinegar/Baking Soda | $2 each | Unknown | YouTube-specific |
| 1Blocker | $3-15 | Likely $100K+ | Content blocking, huge feature set |

**Takeaway:** The paid Safari extension market exists but is small. Open-source extensions compete on reputation and GitHub presence, not revenue.

---

### 10.3 Technical Risk: Python + Safari Extension Architecture

**Has anyone shipped this pattern?**

Extensive search found **no examples** of Python-backend + Safari Web Extension frontends in production. The pattern is:

| Architecture | Examples | Prevalence |
|--------------|----------|------------|
| Swift/ObjC companion + Safari ext | 1Password, Bitwarden, Solana Wallet | Common |
| Node.js companion + Safari ext | None found | Rare |
| Python companion + Safari ext | **None found** | Nonexistent |

**Why this matters:**

Safari's native messaging requires an app bundle with specific entitlements. Python can't be bundled directly — you'd need:

1. **PyInstaller/py2app** to create a .app bundle
2. **Code signing** the bundle ($99/year)
3. **Notarization** for distribution
4. **App Sandbox entitlements** for file access

**The real architecture would be:**

```
Safari Extension (JS)
        ↓ native messaging
Swift Companion App (thin wrapper)
        ↓ subprocess/XPC
Python CLI (bundled via py2app)
```

**IPC latency concerns:**

| Hop | Estimated Latency | Source |
|-----|-------------------|--------|
| Extension → Swift (XPC) | 1-5ms | Apple docs |
| Swift → Python (subprocess) | 10-50ms | Process spawn |
| Python processing | Variable | Depends on operation |
| **Total round-trip** | **20-100ms** | Cumulative |

**For typeahead search, this is too slow.** The correct architecture:

1. **On load**: Python generates JSON index → Swift caches it → Extension loads cache
2. **On search**: Extension searches local cache (no IPC)
3. **On write**: Extension → Swift → Python (async, not blocking UI)

**Recommendation:** Either rewrite Python logic in Swift, or treat Python as a batch processor (not real-time).

---

### 10.4 Distribution Blindspots

**SetApp as a distribution channel:**

| Aspect | Details |
|--------|---------|
| Revenue share | 70% guaranteed + up to 20% from partners |
| Requirements | Quality bar, native Mac app |
| Safari extension support | Not explicitly supported; unclear |
| User base | ~1M+ subscribers |
| Fit for us | ❌ Poor — we're free/BYOK, SetApp is paid subscription |

**Verdict:** SetApp doesn't fit our model. They pay developers based on usage of *paid* apps. A free BYOK tool doesn't generate revenue to share.

**Mac App Store vs iOS App Store for Safari extensions:**

| Factor | Mac App Store | iOS App Store |
|--------|---------------|---------------|
| Review time | 1-3 days typical | 1-3 days typical |
| Rejection rate | Lower (fewer restrictions) | Higher (stricter sandboxing) |
| Extension capabilities | Full (with FDA) | Limited (no file access) |
| Distribution outside store | Possible (notarized DMG) | Not possible |
| Price flexibility | One-time or subscription | One-time or subscription |

**Key insight:** Mac has more flexibility — we can distribute via DMG if App Store rejects us. iOS has no escape hatch.

**TestFlight for beta testing:**

| Feature | Support |
|---------|---------|
| Safari extension beta | ✅ Yes |
| macOS beta | ✅ Yes (since Big Sur) |
| External testers | Up to 10,000 |
| Duration | 90 days per build |
| Requirements | $99/year Apple Developer Program |

**TestFlight is viable** for beta testing Safari extensions. We'd need the $99/year program anyway for App Store distribution.

---

### 10.5 Timeline Reality Check

**"2-4 weeks for Raycast MVP" — is this realistic?**

Evidence from similar-complexity Raycast extensions:

| Extension | Created | First Stable | Complexity | Dev Time |
|-----------|---------|--------------|------------|----------|
| Safari (raycast/extensions) | Oct 2021 | Nov 2021 | 8 commands, AppleScript | ~4 weeks |
| Easydict | May 2022 | Jun 2022 | Translation, OCR, Swift | ~4-6 weeks |
| PromptLab | Mar 2023 | Apr 2023 | AI commands, complex UI | ~4 weeks |
| Hush (Safari ext, not Raycast) | Dec 11, 2020 | Dec 15, 2020 | Simple blocker | **4 days** |

**Analysis:**

- Simple Raycast extensions: 1-2 weeks
- Medium complexity (our case: bookmark parsing, search, LLM calls): 3-4 weeks
- Complex (custom Swift, multiple data sources): 4-6 weeks

**Our scope:**

| Feature | Complexity | Estimated Time |
|---------|------------|----------------|
| Unified search (tabs+bookmarks+history) | Medium | 1 week |
| Session save/restore | Low | 2-3 days |
| Dead link scanner | Medium | 3-4 days |
| AI organize (BYOK) | High | 1-2 weeks |
| **Total** | | **3-4 weeks** |

**Verdict:** 2-4 weeks is realistic for MVP with unified search + session management. AI organize may push to 5-6 weeks.

---

### 10.6 Decision Matrix: Raycast vs Safari Extension

Weighted criteria (1-5 scale, weights sum to 100%):

| Criterion | Weight | Raycast | Safari Ext | Notes |
|-----------|--------|---------|------------|-------|
| **Reach (potential users)** | 25% | 2 (44K Raycast Safari users) | 5 (100M+ Safari users) | Safari wins on raw numbers |
| **Dev time to MVP** | 20% | 5 (3-4 weeks) | 2 (8-12 weeks) | Raycast is faster |
| **Maintenance burden** | 15% | 4 (TypeScript, familiar) | 2 (Swift + JS, two codebases) | Raycast simpler |
| **User friction** | 15% | 3 (requires Raycast install) | 4 (App Store install only) | Safari slightly better |
| **Feature completeness** | 15% | 4 (tabs, bookmarks, history all accessible) | 5 (native access to everything) | Safari wins |
| **Revenue potential** | 10% | 1 (free platform) | 3 (paid option possible) | Safari allows paid model |

**Weighted scores:**

- **Raycast:** (2×0.25) + (5×0.20) + (4×0.15) + (3×0.15) + (4×0.15) + (1×0.10) = **3.25**
- **Safari Extension:** (5×0.25) + (2×0.20) + (2×0.15) + (4×0.15) + (5×0.15) + (3×0.10) = **3.60**

**Surprise:** Safari extension scores higher when weighted, despite higher dev time.

**But consider risk-adjusted scoring:**

| Risk Factor | Raycast | Safari Ext |
|-------------|---------|------------|
| Will we actually ship? | High (simpler) | Medium (complexity) |
| Will users adopt? | Medium (requires Raycast) | Medium (requires FDA permission) |
| Will it work long-term? | High (stable API) | Medium (Safari updates break things) |

**Risk-adjusted recommendation:**

1. **If optimizing for learning/shipping quickly:** Raycast first
2. **If optimizing for maximum reach:** Safari extension
3. **If optimizing for both:** Raycast MVP → Safari port if validated

---

### 10.7 Revised Recommendation

Based on this analysis, the recommendation changes slightly:

**Original:** "Raycast extension first, Safari extension later"

**Revised:** "Raycast extension for validation, Safari extension as the real product"

**Rationale:**
- Raycast is a 44K-user sandbox to test UX and feature set
- Safari extension is the 100M+ user market we actually want
- Raycast success ≠ Safari success (different user bases)
- Safari extension is harder but has 2000x the addressable market

**Concrete plan:**

| Phase | Timeline | Deliverable | Success Metric |
|-------|----------|-------------|----------------|
| 1. Raycast MVP | Weeks 1-4 | Unified search + sessions | 1K installs, 100 weekly active |
| 2. Raycast AI | Weeks 5-6 | Add AI organize (BYOK) | 50 users try AI feature |
| 3. Safari Tabs MVP | Weeks 7-10 | Cmd+Shift+K for tabs only | App Store approval |
| 4. Safari Full | Weeks 11-14 | Add bookmarks (with FDA flow) | 500 downloads |
| 5. Evaluate | Week 15 | Compare Raycast vs Safari adoption | Decide where to focus |

**Key insight:** Don't abandon Safari extension because Raycast is easier. Use Raycast to de-risk and learn, then tackle the larger market.

---

## Sources

### Safari Extensions
- [Hush - GitHub](https://github.com/oblador/hush)
- [Userscripts - GitHub](https://github.com/quoid/userscripts)
- [AdGuard Safari - GitHub](https://github.com/AdguardTeam/AdGuardForSafari)
- [Amplosion - GitHub](https://github.com/christianselig/Amplosion)
- [safari-extension GitHub Topics](https://github.com/topics/safari-extension)

### Apple Documentation
- [Running Your Safari Web Extension](https://developer.apple.com/documentation/safariservices/running-your-safari-web-extension)
- [Troubleshooting Safari Web Extensions](https://developer.apple.com/documentation/safariservices/troubleshooting-your-safari-web-extension)
- [Converting a Web Extension for Safari](https://developer.apple.com/documentation/safariservices/safari_web_extensions/converting_a_web_extension_for_safari)
- [Native Messaging](https://developer.apple.com/documentation/safariservices/safari_web_extensions/messaging_a_web_extension_s_native_app)

### Raycast
- [Raycast Safari Extension](https://www.raycast.com/loris/safari)
- [Raycast Browser Bookmarks](https://www.raycast.com/raycast/browser-bookmarks)
- [Raycast Developer Docs](https://developers.raycast.com/)

### Tools & Templates
- [WebExtensionTemplate](https://github.com/kyle-n/WebExtensionTemplate)
- [C2S_Converter](https://github.com/CHRISmorang/C2S_Converter)
- [Bepp](https://bepp.pigeonposse.com/)
- [allow-unsigned-extensions](https://github.com/apuokenas/allow-unsigned-extensions)

### Chrome to Safari Conversion
- [Evil Martians Guide](https://evilmartians.com/chronicles/how-to-quickly-and-weightlessly-convert-chrome-extensions-to-safari)
- [Converting Chrome Extensions to Safari](https://gist.github.com/rxliuli/940584d75f55de3a4e9e2c5682bbcae8)
