# Safari Power Tools — Specification Gaps

Critical gaps in the current planning that must be resolved before implementation.

---

## 1. Unified Architecture Decision

### The Problem

The research documents contradict each other:
- RESEARCH_DISTRIBUTION.md recommends "Raycast extension first"
- RESEARCH_CMD_K.md designs a Safari extension architecture
- HANDOFF.md lists Safari extension as the core deliverable

### Decision Matrix

| Criterion | Weight | Raycast | Safari Extension | Rationale |
|-----------|--------|---------|------------------|-----------|
| Reach (addressable market) | 25% | 2 (44K users) | 5 (100M+ users) | Safari has 2000x larger market |
| Dev time to MVP | 20% | 5 (3-4 weeks) | 2 (8-12 weeks) | Raycast is TypeScript; Safari needs Swift+JS |
| Maintenance burden | 15% | 4 (one language) | 2 (two codebases) | Safari needs JS extension + Swift companion |
| User friction | 15% | 3 (requires Raycast) | 3 (requires FDA permission) | Both have friction; different kinds |
| Feature completeness | 15% | 4 (tabs+bookmarks) | 5 (full native access) | Safari can do everything |
| Revenue potential | 10% | 1 (free platform) | 3 (App Store paid option) | Safari allows paid model |

**Weighted Scores:**
- Raycast: 3.25
- Safari Extension: 3.45

### The Call

**Build both, sequentially:**

| Phase | Timeline | Deliverable | Purpose |
|-------|----------|-------------|---------|
| **1. Raycast MVP** | Weeks 1-4 | Unified search + sessions | Validate UX, build audience |
| **2. Safari Tabs MVP** | Weeks 5-8 | Cmd+Shift+K for tabs only | Enter Safari ecosystem, no FDA needed |
| **3. Safari Full** | Weeks 9-14 | Add bookmarks + history | Full feature parity |

**Rationale:** Raycast de-risks UX decisions. Safari is the real product with 2000x market. Don't choose — do both.

---

## 2. Data Model and State Management

### State Locations

```
┌─────────────────────────────────────────────────────────────────┐
│                      State Architecture                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐ │
│  │ Extension        │  │ Native Companion │  │ SwiftUI App    │ │
│  │ (browser.storage)│  │ (App Group)      │  │ (App Group)    │ │
│  ├──────────────────┤  ├──────────────────┤  ├────────────────┤ │
│  │ • Search index   │  │ • Bookmark cache │  │ • API keys     │ │
│  │ • UI preferences │  │ • Session data   │  │ • Preferences  │ │
│  │ • Recent queries │  │ • Organize state │  │ • Backup meta  │ │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬────────┘ │
│           │                     │                     │          │
│           └─────────────────────┼─────────────────────┘          │
│                                 │                                │
│                    ┌────────────▼────────────┐                   │
│                    │ Shared UserDefaults     │                   │
│                    │ (App Group Container)   │                   │
│                    │ group.com.sagemarks     │                   │
│                    └─────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

### Data Models

```swift
// Session.swift
struct Session: Codable, Identifiable {
    let id: UUID
    var name: String
    var tabs: [SavedTab]
    var createdAt: Date
    var lastUsedAt: Date
    var tags: [String]
}

struct SavedTab: Codable {
    let url: URL
    let title: String
    let favicon: Data?  // Optional cached favicon
    let scrollPosition: CGFloat?  // Optional scroll position
}

// BookmarkIndex.swift
struct BookmarkIndex: Codable {
    let version: Int  // Schema version for migrations
    let generatedAt: Date
    let bookmarks: [IndexedBookmark]
    let folders: [String: [UUID]]  // folder path -> bookmark IDs
}

struct IndexedBookmark: Codable, Identifiable {
    let id: UUID
    let url: URL
    let title: String
    let folderPath: String
    let addedAt: Date?
    let visitCount: Int?
}

// Preferences.swift
struct Preferences: Codable {
    var keyboardShortcut: String = "Command+Shift+K"
    var searchSources: SearchSources = .all
    var maxResults: Int = 20
    var excludedFolders: [String] = []
    var theme: Theme = .system
}

enum SearchSources: String, Codable {
    case all, tabsOnly, bookmarksOnly, historyOnly
}
```

### Sync Strategy

| Data | Source of Truth | Sync Frequency | Conflict Resolution |
|------|-----------------|----------------|---------------------|
| Bookmarks | Safari Bookmarks.plist | On extension load + every 30s | Safari always wins |
| History | Safari History.db | On extension load + every 60s | Safari always wins |
| Sessions | App Group UserDefaults | Immediate | Last-write-wins |
| Preferences | App Group UserDefaults | Immediate | Last-write-wins |
| API Keys | Keychain | Immediate | Single source |
| Search Index | Extension memory | Rebuilt on data change | Regenerate |

### App Group Configuration

```xml
<!-- Entitlements.plist -->
<key>com.apple.security.application-groups</key>
<array>
    <string>group.com.sagemarks.safari-power-tools</string>
</array>
```

---

## 3. Error Handling and Failure Modes

### Error Categories

| Category | Examples | User Impact | Recovery Strategy |
|----------|----------|-------------|-------------------|
| **Transient** | Network timeout, API rate limit | Retry possible | Exponential backoff, queue retry |
| **Recoverable** | Invalid API key, FDA revoked | User action needed | Clear error message + action button |
| **Fatal** | Corrupt plist, missing files | Feature unavailable | Graceful degradation |
| **Silent** | Background sync fail | None visible | Log only, retry later |

### Specific Failure Modes

#### LLM API Fails Mid-Organize

```swift
enum OrganizeState: Codable {
    case idle
    case scanning
    case analyzing(progress: Double)
    case proposing(proposal: OrganizeProposal)
    case applying(progress: Double)
    case complete
    case failed(OrganizeError)
}

// Checkpoint after each phase
func organize() async throws {
    state = .scanning
    let bookmarks = try await scanBookmarks()
    saveCheckpoint(phase: .scanned, data: bookmarks)

    state = .analyzing(progress: 0)
    do {
        let proposal = try await analyzeWithLLM(bookmarks)
        saveCheckpoint(phase: .analyzed, data: proposal)
        state = .proposing(proposal: proposal)
    } catch {
        // Resume from last checkpoint on retry
        throw OrganizeError.llmFailed(resumable: true)
    }
}
```

**User sees:** "Organization paused - AI service temporarily unavailable. [Retry] [Cancel]"

#### Bookmarks.plist Locked or Inaccessible

```swift
func readBookmarks() throws -> [Bookmark] {
    do {
        return try readPlist()
    } catch CocoaError.fileReadNoPermission {
        throw BookmarkError.fullDiskAccessRequired
    } catch CocoaError.fileReadCorruptFile {
        // Try backup
        if let backup = findLatestBackup() {
            return try readPlist(from: backup)
        }
        throw BookmarkError.corruptNoBackup
    } catch {
        throw BookmarkError.unknown(error)
    }
}
```

**User sees:** "Unable to read bookmarks. Safari may be updating. [Retry in 5s]"

#### Full Disk Access Revoked

```swift
func checkFDAStatus() -> FDAStatus {
    let testPath = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Safari/Bookmarks.plist")

    if FileManager.default.isReadableFile(atPath: testPath.path) {
        return .granted
    } else {
        return .revoked
    }
}
```

**User sees:** Banner at top of extension: "Bookmark access disabled. [Grant Access →]"

#### Native Companion Crashes

```javascript
// In extension background script
let reconnectAttempts = 0;
const MAX_RECONNECT = 3;

async function sendToNative(message) {
    try {
        return await browser.runtime.sendNativeMessage(APP_ID, message);
    } catch (error) {
        if (error.message.includes("disconnected")) {
            if (reconnectAttempts < MAX_RECONNECT) {
                reconnectAttempts++;
                await delay(1000 * reconnectAttempts);
                return sendToNative(message); // Retry
            }
        }
        throw new NativeConnectionError(error);
    }
}
```

**User sees:** "Search limited to tabs. Native helper not responding. [Restart App]"

### Error Reporting

```swift
struct ErrorReport: Codable {
    let id: UUID
    let timestamp: Date
    let errorType: String
    let errorMessage: String
    let context: [String: String]
    let stackTrace: String?
    let appVersion: String
    let osVersion: String
    // NO user data, URLs, or bookmark content
}
```

---

## 4. Performance Budget

### Latency Targets

| Operation | Target | Hard Limit | Measurement Point |
|-----------|--------|------------|-------------------|
| Cmd+K popup appear | <100ms | 200ms | Keypress → first paint |
| Search results (cached) | <20ms | 50ms | Keystroke → results rendered |
| Search results (native msg) | <100ms | 200ms | Keystroke → results rendered |
| Tab switch | <50ms | 100ms | Enter key → tab focused |
| Session restore (10 tabs) | <2s | 5s | Click → all tabs loading |
| Initial index build | <500ms | 1s | Extension load → searchable |

### Scale Limits

| Resource | Tested Limit | Recommended Max | Graceful Degradation |
|----------|--------------|-----------------|----------------------|
| Bookmarks | 50,000 | 10,000 | Paginate index, warn user |
| History items | 100,000 | 25,000 | Limit to recent 90 days |
| Saved sessions | 1,000 | 100 | Archive old sessions |
| Search index size | 50MB | 20MB | Exclude long URLs/titles |
| Open tabs | 500 | N/A (Safari limit) | None needed |

### Memory Budget

| Component | Target | Max | Notes |
|-----------|--------|-----|-------|
| Extension background | 20MB | 50MB | Service worker limit varies |
| Extension popup | 10MB | 30MB | Includes search UI |
| Search index (FlexSearch) | 5MB | 15MB | For 10K bookmarks |
| Native companion idle | 15MB | 30MB | Swift runtime overhead |
| Native companion active | 50MB | 100MB | During LLM calls |

### API Token Cost Estimates

Based on Claude 3.5 Sonnet pricing ($3/1M input, $15/1M output):

| Bookmark Count | Avg Tokens/Bookmark | Input Cost | Output Cost | Total |
|----------------|---------------------|------------|-------------|-------|
| 100 | ~50 | $0.015 | $0.05 | **$0.07** |
| 1,000 | ~50 | $0.15 | $0.50 | **$0.65** |
| 5,000 | ~50 | $0.75 | $2.50 | **$3.25** |
| 10,000 | ~50 | $1.50 | $5.00 | **$6.50** |

**Recommendation:** Warn users before organizing >1,000 bookmarks. Show estimated cost in UI.

### Benchmark Suite

```javascript
// benchmarks/search.js
const benchmarks = {
    async indexBuild(bookmarkCount) {
        const bookmarks = generateMockBookmarks(bookmarkCount);
        const start = performance.now();
        const index = new FlexSearch.Index({ tokenize: 'forward' });
        bookmarks.forEach((bm, i) => index.add(i, `${bm.title} ${bm.url}`));
        return performance.now() - start;
    },

    async searchLatency(index, queries) {
        const times = [];
        for (const query of queries) {
            const start = performance.now();
            index.search(query, { limit: 20 });
            times.push(performance.now() - start);
        }
        return { avg: avg(times), p95: percentile(times, 95), max: max(times) };
    }
};
```

---

## 5. Migration and Upgrade Path

### CLI to Extension Migration

```
┌─────────────────────────────────────────────────────────────────┐
│                     Migration Flow                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CLI User                    Extension Install                   │
│     │                              │                             │
│     │  Has ~/.sagemarks/          │                             │
│     │  config.json                │  Detect on first run        │
│     │  backups/                   │         │                   │
│     │      │                      │         ▼                   │
│     │      └──────────────────────┼─► Import Dialog             │
│     │                              │   "Found CLI data.          │
│     │                              │    Import settings?"        │
│     │                              │   [Import] [Skip]           │
│     │                              │         │                   │
│     │                              │         ▼                   │
│     │                              │   Copy to App Group:        │
│     │                              │   • Preferences             │
│     │                              │   • Backup history          │
│     │                              │   • (NOT API keys - re-enter)│
└─────────────────────────────────────────────────────────────────┘
```

**Migration script:**

```swift
func migrateCLIData() throws {
    let cliConfigPath = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".sagemarks/config.json")

    guard FileManager.default.fileExists(atPath: cliConfigPath.path) else {
        return // No CLI data to migrate
    }

    let cliConfig = try JSONDecoder().decode(CLIConfig.self, from: Data(contentsOf: cliConfigPath))

    // Migrate preferences (not secrets)
    var prefs = Preferences()
    prefs.excludedFolders = cliConfig.excludedFolders ?? []
    prefs.theme = Theme(rawValue: cliConfig.theme ?? "system") ?? .system

    try savePreferences(prefs)

    // Mark migration complete
    UserDefaults.appGroup.set(true, forKey: "cliMigrationComplete")
    UserDefaults.appGroup.set(Date(), forKey: "cliMigrationDate")
}
```

### Raycast to Safari Migration

If user has both installed, they can run independently. No data migration needed since:
- Raycast reads bookmarks directly (read-only)
- Safari extension reads bookmarks directly (read-only)
- Sessions are extension-specific

### Schema Versioning

```swift
struct SchemaVersion {
    static let current = 1

    static func migrate(from oldVersion: Int) throws {
        var version = oldVersion

        while version < current {
            switch version {
            case 0:
                try migrateV0ToV1()
            default:
                throw MigrationError.unknownVersion(version)
            }
            version += 1
        }
    }

    private static func migrateV0ToV1() throws {
        // Example: Add new field with default value
        var sessions = try loadSessionsV0()
        for i in sessions.indices {
            sessions[i].tags = []  // New field in V1
        }
        try saveSessionsV1(sessions)
    }
}
```

### Upgrade Notifications

```swift
func checkForUpgrade() {
    let lastVersion = UserDefaults.appGroup.string(forKey: "lastAppVersion") ?? "0.0.0"
    let currentVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "0.0.0"

    if lastVersion != currentVersion {
        // Show what's new
        showWhatsNew(from: lastVersion, to: currentVersion)

        // Run migrations
        try? SchemaVersion.migrate(from: schemaVersion(for: lastVersion))

        // Update stored version
        UserDefaults.appGroup.set(currentVersion, forKey: "lastAppVersion")
    }
}
```

---

## 6. Privacy and Security Design

### API Key Storage

```swift
// KeychainManager.swift
struct KeychainManager {
    private static let service = "com.sagemarks.api-keys"

    static func store(key: String, provider: LLMProvider) throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: provider.rawValue,
            kSecValueData as String: key.data(using: .utf8)!,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]

        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess || status == errSecDuplicateItem else {
            throw KeychainError.storeFailed(status)
        }
    }

    static func retrieve(provider: LLMProvider) throws -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: provider.rawValue,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess, let data = result as? Data else {
            return nil
        }

        return String(data: data, encoding: .utf8)
    }
}
```

### Data Sent to LLMs

| Data Type | Sent to LLM? | Purpose | Redaction |
|-----------|--------------|---------|-----------|
| Bookmark URLs | Yes | Categorization | None (needed for context) |
| Bookmark titles | Yes | Categorization | None (needed for context) |
| Page content | Optional | Better categorization | Strip PII patterns |
| User API key | Yes (to provider) | Authentication | N/A |
| Tab URLs | No | N/A | N/A |
| History | No | N/A | N/A |
| Session names | No | N/A | N/A |

**Privacy notice for AI organize:**

> "When you organize bookmarks with AI, your bookmark URLs and titles are sent to [Provider]. Your API key is sent directly to [Provider]'s servers. We do not store or transmit this data ourselves. [Learn more]"

### Content Security Policy (Extension)

```json
{
  "content_security_policy": {
    "extension_pages": "script-src 'self'; object-src 'self'; connect-src https://api.anthropic.com https://api.openai.com https://generativelanguage.googleapis.com"
  }
}
```

### GDPR Considerations

| Requirement | Implementation |
|-------------|----------------|
| Data minimization | Only collect data needed for features |
| Right to erasure | "Delete all data" button in settings |
| Data portability | Export sessions/preferences as JSON |
| Consent | No data collection without explicit feature use |
| Third-party disclosure | API key usage disclosed before AI features |

**No analytics, no telemetry, no cloud sync (except Safari's own iCloud).**

### Audit Log

```swift
// For sensitive operations
struct AuditLog {
    static func log(event: AuditEvent) {
        // Local-only, user-viewable
        let entry = AuditEntry(
            timestamp: Date(),
            event: event,
            details: event.details
        )

        var log = loadAuditLog()
        log.append(entry)
        log = log.suffix(1000)  // Keep last 1000 entries
        saveAuditLog(log)
    }
}

enum AuditEvent {
    case apiKeyAdded(provider: String)
    case apiKeyRemoved(provider: String)
    case bookmarksSentToLLM(count: Int, provider: String)
    case organizeApplied(folderCount: Int)
    case dataExported
    case dataDeleted
}
```

---

## 7. Testing Strategy

### Test Categories

| Category | Tools | Coverage Target | CI/CD |
|----------|-------|-----------------|-------|
| Unit tests (Swift) | XCTest | 80% | Yes |
| Unit tests (JS) | Jest | 80% | Yes |
| Integration tests | XCTest + Safari | Critical paths | Yes (macOS runner) |
| E2E tests | Playwright + Safari | Happy paths | Manual |
| Performance tests | XCTest Performance | Regressions | Yes |
| Manual testing | Checklist | All features | Pre-release |

### Swift Unit Tests

```swift
// BookmarkParserTests.swift
class BookmarkParserTests: XCTestCase {
    func testParseValidPlist() throws {
        let plistData = loadTestFixture("valid_bookmarks.plist")
        let parser = BookmarkParser()
        let bookmarks = try parser.parse(data: plistData)

        XCTAssertEqual(bookmarks.count, 42)
        XCTAssertEqual(bookmarks[0].title, "Apple")
        XCTAssertEqual(bookmarks[0].url.absoluteString, "https://www.apple.com/")
    }

    func testParseCorruptPlist() {
        let plistData = "not a plist".data(using: .utf8)!
        let parser = BookmarkParser()

        XCTAssertThrowsError(try parser.parse(data: plistData)) { error in
            XCTAssertTrue(error is BookmarkParseError)
        }
    }
}
```

### JavaScript Tests

```javascript
// __tests__/search.test.js
describe('SearchIndex', () => {
    let index;

    beforeEach(() => {
        index = new SearchIndex();
        index.addBookmarks([
            { id: '1', title: 'GitHub', url: 'https://github.com' },
            { id: '2', title: 'GitLab', url: 'https://gitlab.com' },
        ]);
    });

    test('fuzzy matches partial title', () => {
        const results = index.search('git');
        expect(results).toHaveLength(2);
        expect(results[0].id).toBe('1'); // GitHub ranks higher
    });

    test('returns empty for no match', () => {
        const results = index.search('zzzzz');
        expect(results).toHaveLength(0);
    });
});
```

### Native Messaging Tests

```swift
// NativeMessagingTests.swift
class NativeMessagingTests: XCTestCase {
    func testGetBookmarksMessage() async throws {
        let handler = MockExtensionHandler()
        let response = try await handler.handleMessage(["action": "getBookmarks"])

        XCTAssertNotNil(response["bookmarks"])
        let bookmarks = response["bookmarks"] as! [[String: Any]]
        XCTAssertGreaterThan(bookmarks.count, 0)
    }

    func testInvalidMessageReturnsError() async throws {
        let handler = MockExtensionHandler()
        let response = try await handler.handleMessage(["invalid": "message"])

        XCTAssertNotNil(response["error"])
    }
}
```

### Safari Extension Integration Tests

```swift
// SafariExtensionIntegrationTests.swift
class SafariExtensionIntegrationTests: XCTestCase {
    var safari: XCUIApplication!

    override func setUp() {
        safari = XCUIApplication(bundleIdentifier: "com.apple.Safari")
        safari.launch()
    }

    func testExtensionLoadsPopup() {
        // Click extension toolbar button
        let toolbar = safari.toolbars.firstMatch
        let extensionButton = toolbar.buttons["Safari Power Tools"]
        XCTAssertTrue(extensionButton.waitForExistence(timeout: 5))

        extensionButton.click()

        // Verify popup appears
        let popup = safari.webViews["Safari Power Tools Popup"]
        XCTAssertTrue(popup.waitForExistence(timeout: 3))
    }
}
```

### CI/CD Pipeline

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  swift-tests:
    runs-on: macos-14
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: xcodebuild build -scheme "Safari Power Tools" -destination "platform=macOS"
      - name: Test
        run: xcodebuild test -scheme "Safari Power Tools" -destination "platform=macOS"

  js-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
      - run: npm test

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm run lint
      - run: swiftlint lint --strict
```

---

## 8. Offline and Degradation

### Feature Availability Matrix

| Feature | No Network | No API Key | No FDA | Native Crashed |
|---------|------------|------------|--------|----------------|
| Tab search | Full | Full | Full | Full |
| Tab switch | Full | Full | Full | Full |
| Session save | Full | Full | Full | Limited* |
| Session restore | Full | Full | Full | Limited* |
| Bookmark search | Full | Full | None | None |
| History search | Full | Full | None | None |
| AI organize | None | None | Degraded** | None |
| Dead link check | None | Full | None | None |
| Dedupe check | Full | Full | None | None |

*Sessions stored in extension storage if native unavailable
**Can scan/preview but not apply changes

### Offline Detection

```javascript
// Network status detection
class NetworkStatus {
    constructor() {
        this.online = navigator.onLine;
        window.addEventListener('online', () => this.setOnline(true));
        window.addEventListener('offline', () => this.setOnline(false));
    }

    setOnline(status) {
        this.online = status;
        this.emit('change', status);
    }

    async checkLLMReachability(provider) {
        if (!this.online) return false;

        try {
            const endpoint = provider.healthEndpoint;
            const response = await fetch(endpoint, {
                method: 'HEAD',
                signal: AbortSignal.timeout(3000)
            });
            return response.ok;
        } catch {
            return false;
        }
    }
}
```

### Degradation UI

```javascript
// Status banner component
function StatusBanner({ status }) {
    if (status.online && status.fdaGranted && status.nativeConnected) {
        return null; // No banner when everything works
    }

    const messages = [];
    if (!status.online) {
        messages.push({ level: 'warning', text: 'Offline - some features unavailable' });
    }
    if (!status.fdaGranted) {
        messages.push({
            level: 'info',
            text: 'Bookmark access disabled',
            action: { label: 'Grant Access', onClick: openFDASettings }
        });
    }
    if (!status.nativeConnected) {
        messages.push({
            level: 'error',
            text: 'Native helper not responding',
            action: { label: 'Restart', onClick: restartHelper }
        });
    }

    return <BannerStack messages={messages} />;
}
```

### Partial Offline for Dead Links

```swift
// Queue-based dead link checking
class DeadLinkChecker {
    private var queue: [URL] = []
    private var results: [URL: CheckResult] = [:]
    private var isProcessing = false

    func checkAll(urls: [URL]) {
        queue = urls
        processNext()
    }

    private func processNext() {
        guard !queue.isEmpty else {
            finishProcessing()
            return
        }

        guard NetworkStatus.shared.isOnline else {
            // Pause processing, resume when online
            NotificationCenter.default.addObserver(
                self, selector: #selector(resumeProcessing),
                name: .networkBecameOnline, object: nil
            )
            saveProgress()
            return
        }

        let url = queue.removeFirst()
        checkURL(url) { [weak self] result in
            self?.results[url] = result
            self?.processNext()
        }
    }
}
```

---

## 9. Bookmark Write-Back Feasibility

### CRITICAL RISK ASSESSMENT

**This is the highest-risk technical decision in the project.**

### Current Evidence

| Finding | Source | Implication |
|---------|--------|-------------|
| Safari keeps Bookmarks.plist open for reading | `lsof` on running Safari (FD 64r) | File is actively in use |
| Existing tools (SafariBookmarkEditor) use direct plistlib.writePlist() | Source code review | No coordination mechanism |
| No NSFileCoordinator usage found in bookmark tools | GitHub code search (0 results) | Industry practice ignores coordination |
| Safari uses iCloud sync for bookmarks | Apple documentation | Additional sync complexity |

### Write Scenarios

#### Scenario A: Safari is Running, User is Idle

```
Timeline:
0ms     - Extension requests write via native companion
10ms    - Native companion reads current plist (may be stale)
50ms    - Native companion writes modified plist
51ms    - Safari's cached view is now stale
???     - Safari may or may not detect file change
```

**Possible outcomes:**
1. Safari detects change, reloads (best case)
2. Safari doesn't detect, overwrites on next internal save (data loss)
3. Safari and companion write simultaneously (corruption)

#### Scenario B: Safari is Actively Using Bookmarks

```
Timeline:
0ms     - User clicks bookmark in Safari
5ms     - Safari reads bookmark URL from memory
10ms    - Extension writes to plist
15ms    - Safari writes bookmark change (visit count)
```

**Possible outcomes:**
1. Safari's write overwrites extension's changes
2. plist corrupted due to concurrent writes
3. Extension changes saved, Safari changes lost

### Technical Options

#### Option 1: Require Safari Quit (Safest)

```swift
func ensureSafariNotRunning() throws {
    let runningApps = NSWorkspace.shared.runningApplications
    if runningApps.contains(where: { $0.bundleIdentifier == "com.apple.Safari" }) {
        throw WriteError.safariRunning
    }
}

// UI: "Please quit Safari to apply changes. [Quit Safari] [Cancel]"
```

**Pros:** Guaranteed safe
**Cons:** Terrible UX, defeats purpose of extension

#### Option 2: NSFileCoordinator (Theoretically Correct)

```swift
func writeBookmarksWithCoordination(_ bookmarks: [Bookmark]) throws {
    let fileURL = bookmarksPlistURL
    let coordinator = NSFileCoordinator()
    var coordError: NSError?

    coordinator.coordinate(
        writingItemAt: fileURL,
        options: .forReplacing,
        error: &coordError
    ) { newURL in
        do {
            try PropertyListSerialization.write(bookmarks, to: newURL)
        } catch {
            // Handle error
        }
    }

    if let error = coordError {
        throw error
    }
}
```

**Pros:** Apple's recommended approach for shared file access
**Cons:** Safari may not participate in file coordination; untested with Safari

#### Option 3: Write-Then-Signal (Optimistic)

```swift
func writeAndNotifySafari(_ bookmarks: [Bookmark]) throws {
    // 1. Write to temp file first
    let tempURL = URL(fileURLWithPath: NSTemporaryDirectory())
        .appendingPathComponent("Bookmarks.plist")
    try PropertyListSerialization.write(bookmarks, to: tempURL)

    // 2. Atomic move
    let backupURL = bookmarksPlistURL.appendingPathExtension("backup")
    try FileManager.default.moveItem(at: bookmarksPlistURL, to: backupURL)
    try FileManager.default.moveItem(at: tempURL, to: bookmarksPlistURL)

    // 3. Try to notify Safari via AppleScript
    let script = """
        tell application "Safari"
            -- No direct "reload bookmarks" command exists
            -- This is a placeholder
        end tell
    """
    NSAppleScript(source: script)?.executeAndReturnError(nil)
}
```

**Pros:** Atomic file replacement reduces corruption window
**Cons:** Safari may not notice the change; no reliable notification mechanism

#### Option 4: Shadow Write + User Trigger (Recommended)

```
┌─────────────────────────────────────────────────────────────────┐
│                   Shadow Write Strategy                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Extension                    User Action                       │
│      │                             │                             │
│      ▼                             │                             │
│   Apply Changes                    │                             │
│      │                             │                             │
│      ▼                             │                             │
│   Write to shadow file             │                             │
│   ~/Library/Safari/                │                             │
│   Bookmarks.sagemarks.plist        │                             │
│      │                             │                             │
│      ▼                             │                             │
│   Show dialog:                     │                             │
│   "Changes ready. Quit Safari      │                             │
│    to apply, or Apply Later."      │                             │
│                                    │                             │
│   [Apply Now] ──────────────────► Quit Safari (user confirms)   │
│                                    │                             │
│                                    ▼                             │
│                              Move shadow → real                  │
│                                    │                             │
│                                    ▼                             │
│                              User relaunches Safari              │
│                                                                  │
│   [Apply Later] ─────────────────► Store pending changes        │
│                                    │                             │
│                                    ▼                             │
│                              On next Safari quit,               │
│                              apply automatically                 │
└─────────────────────────────────────────────────────────────────┘
```

**Pros:** Safe, user-controlled, handles edge cases
**Cons:** Requires user action for immediate application

### Recommendation

**Start with Option 4 (Shadow Write + User Trigger):**

1. Never write directly to Bookmarks.plist while Safari is running
2. Store changes in a shadow file
3. Apply changes when Safari quits (detect via NSWorkspace)
4. Offer "Apply Now" which quits Safari with user permission

**Future investigation:**
- Test NSFileCoordinator with Safari (does Safari participate?)
- Monitor Safari's bookmark file watching behavior
- Investigate iCloud sync implications

### iCloud Sync Complication

If bookmarks sync via iCloud:
1. Local Bookmarks.plist is periodically synced to CloudKit
2. Changes from other devices arrive asynchronously
3. Writing locally may conflict with incoming sync

**Mitigation:** After applying changes, wait 30 seconds and re-read plist to verify changes persisted.

---

## 10. User Journey and Interaction Design

### First-Run Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      First Run Experience                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Step 1: App Store Install                                       │
│  ─────────────────────────────────────────────────────────────  │
│  User downloads "Safari Power Tools" from App Store              │
│                                                                  │
│  Step 2: Launch Container App                                    │
│  ─────────────────────────────────────────────────────────────  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                                                          │   │
│  │   Welcome to Safari Power Tools                          │   │
│  │                                                          │   │
│  │   [Icon]  Search tabs, bookmarks, and history            │   │
│  │   [Icon]  Save and restore browser sessions              │   │
│  │   [Icon]  AI-powered bookmark organization               │   │
│  │                                                          │   │
│  │              [Enable Safari Extension →]                  │   │
│  │                                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Step 3: Enable Extension (Opens Safari Settings)               │
│  ─────────────────────────────────────────────────────────────  │
│  Safari > Settings > Extensions > Safari Power Tools > ☑        │
│                                                                  │
│  Step 4: First Cmd+Shift+K                                       │
│  ─────────────────────────────────────────────────────────────  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ ┌────────────────────────────────────────────────────┐   │   │
│  │ │ 🔍 Search tabs...                                  │   │   │
│  │ └────────────────────────────────────────────────────┘   │   │
│  │                                                          │   │
│  │   📑 Open Tabs (12)                                      │   │
│  │   ├─ GitHub - Your Repositories                          │   │
│  │   ├─ Apple Developer                                     │   │
│  │   └─ ...                                                 │   │
│  │                                                          │   │
│  │   💡 Tip: Add bookmarks and history by granting          │   │
│  │      Full Disk Access. [Learn More]                      │   │
│  │                                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Step 5: Progressive FDA Prompt (Optional)                       │
│  ─────────────────────────────────────────────────────────────  │
│  When user searches and no bookmarks appear:                     │
│  "Want to search bookmarks too? [Grant Access] [Maybe Later]"    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Permission Granting Sequence

| Step | User Action | Clicks | Notes |
|------|-------------|--------|-------|
| 1 | Install from App Store | 2 | Get → Install |
| 2 | Launch app | 1 | Click app icon |
| 3 | Click "Enable Extension" | 1 | In container app |
| 4 | Toggle extension in Safari Settings | 2 | Check box + Done |
| 5 | Use Cmd+Shift+K | 0 | Keyboard shortcut |
| **TOTAL (tabs only)** | | **6** | |
| 6 (optional) | Grant FDA in System Preferences | 5+ | Complex flow |
| **TOTAL (with bookmarks)** | | **11+** | |

**Goal:** Minimize clicks to first value. Tabs work with 6 clicks.

### Result Type Visual Differentiation

```
┌────────────────────────────────────────────────────────────┐
│ 🔍 git                                                     │
├────────────────────────────────────────────────────────────┤
│                                                            │
│ 📑 Tabs                                                    │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ [🔵]  GitHub - nicokimmel/robotarena                   │ │
│ │       github.com/nicokimmel/robotarena     ← faded     │ │
│ └────────────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ [🔵]  GitLab - My Projects                             │ │
│ │       gitlab.com/user/projects                         │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                            │
│ ⭐ Bookmarks                                               │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ [⭐]  GitHub Documentation                             │ │
│ │       docs.github.com       📁 Dev / Reference         │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                            │
│ 🕐 History                                                 │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ [🕐]  Gitpod - Cloud Development                       │ │
│ │       gitpod.io              2 hours ago               │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                            │
└────────────────────────────────────────────────────────────┘

Legend:
🔵 = Tab (blue dot, active/current)
⭐ = Bookmark (star, saved)
🕐 = History (clock, visited)
📁 = Folder path
```

### Keyboard Navigation

| Key | Action |
|-----|--------|
| ↓ / ↑ | Move selection |
| Enter | Open selected (switch tab / open URL) |
| ⌘+Enter | Open in new tab |
| ⇧+Enter | Open in new window |
| Tab | Cycle through sections (Tabs → Bookmarks → History) |
| Esc | Close popup |
| ⌘+K | Focus search when in popup |

### Click Counts for Key Workflows

| Workflow | Clicks | Keystrokes | Notes |
|----------|--------|------------|-------|
| Search and switch tab | 0 | 3+ (⌘⇧K + query + ↵) | Keyboard-only |
| Search and open bookmark | 0 | 3+ | Keyboard-only |
| Save current session | 2 | 0 | Toolbar → Save |
| Restore session | 2 | 0 | Toolbar → Session → Click |
| AI organize (first time) | 5 | 0 | Settings → API Key → Organize → Approve |
| AI organize (subsequent) | 3 | 0 | Toolbar → Organize → Approve |

### Accessibility Requirements

| Requirement | Implementation |
|-------------|----------------|
| Screen reader support | ARIA labels on all interactive elements |
| Keyboard navigation | Full tab order, arrow key navigation |
| High contrast | Respect system preferences |
| Reduced motion | Skip animations if prefers-reduced-motion |
| Focus indicators | Visible focus ring on all focusable elements |
| Text scaling | Support Dynamic Type up to 200% |

---

## Summary: Risk Matrix

| Gap | Severity | Likelihood | Mitigation Complexity |
|-----|----------|------------|----------------------|
| 1. Architecture decision | Low | Resolved | N/A |
| 2. Data model | Medium | Low | Low |
| 3. Error handling | Medium | Medium | Medium |
| 4. Performance | Medium | Low | Low |
| 5. Migration | Low | Low | Low |
| 6. Privacy/Security | High | Low | Medium |
| 7. Testing | Medium | Medium | Medium |
| 8. Offline | Low | Medium | Low |
| **9. Bookmark write-back** | **Critical** | **High** | **High** |
| 10. User journey | Medium | Low | Low |

**Priority order for resolution:**
1. **Gap 9** - Bookmark write-back (showstopper if wrong)
2. **Gap 6** - Privacy/Security (trust-critical)
3. **Gap 3** - Error handling (UX-critical)
4. **Gap 4** - Performance (UX-critical)
5. Remaining gaps in parallel

---

## Next Steps

1. **Prototype bookmark write-back** with NSFileCoordinator and test with Safari running
2. **Implement keychain storage** for API keys
3. **Create test fixtures** for Bookmarks.plist and History.db
4. **Design error UI components** (banners, dialogs)
5. **Benchmark FlexSearch** with 10K bookmarks on Safari
