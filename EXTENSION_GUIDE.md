# Sagemarks — Safari Extension Architecture Guide

How to evolve the CLI into a real Safari Web Extension on the App Store.

## The Problem

Safari's WebExtensions API **does not support `browser.bookmarks`**. This is confirmed across multiple Apple Developer Forum threads with no fix planned. Chrome extensions can freely read/write bookmarks — Safari cannot.

This means a pure JavaScript Safari extension cannot manage bookmarks. We need a **hybrid architecture**.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  macOS App                        │
│                                                   │
│  ┌──────────────┐    ┌─────────────────────────┐ │
│  │ Safari Web   │◄──►│ Native Swift Helper     │ │
│  │ Extension    │    │                          │ │
│  │              │    │ • Reads Bookmarks.plist  │ │
│  │ • Toolbar UI │    │ • Writes Bookmarks.plist │ │
│  │ • Popup      │    │ • Calls Claude API       │ │
│  │ • Triggers   │    │ • Manages backups        │ │
│  └──────────────┘    └─────────────────────────┘ │
│         ▲                       ▲                 │
│         │     App Groups /      │                 │
│         └──── NSXPCConnection ──┘                 │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │ SwiftUI Settings                             │ │
│  │ • API key management (Keychain)              │ │
│  │ • Organize button                            │ │
│  │ • Folder preview / approval                  │ │
│  │ • Backup management                          │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### Component Breakdown

**1. Container App (SwiftUI)**
- Required by Apple — every Safari extension needs a host app
- Settings UI: API key input (stored in Keychain), model selection
- Main organize flow: scan → preview → approve → apply
- Backup browser: view/restore previous bookmark states

**2. Safari Web Extension (JS + HTML)**
- Toolbar button that opens a popup
- Popup shows: bookmark count, last organized date, "Organize Now" button
- Communicates with the native helper via `browser.runtime.sendNativeMessage()`

**3. Native Swift Helper (App Extension)**
- Reads/writes `~/Library/Safari/Bookmarks.plist` using Foundation's `PropertyListSerialization`
- Calls the Anthropic API for categorization
- Handles backup/restore
- Communicates with the web extension via the native messaging protocol

## Step-by-Step Build Guide

### Phase 1: Xcode Project Setup

```bash
# Create a new Xcode project
# Template: macOS > App
# Add target: Safari Web Extension
```

1. Open Xcode → File → New → Project
2. Choose **App** under macOS
3. Product name: `Sagemarks`
4. Team: Your Apple Developer account
5. Bundle ID: `com.yourname.sagemarks`
6. Interface: **SwiftUI**
7. After creation: File → New → Target → **Safari Web Extension**
8. Name it `Sagemarks Extension`
9. Check "Include native messaging" (critical!)

### Phase 2: Native Messaging Bridge

The web extension talks to Swift via `browser.runtime.sendNativeMessage()`.

**In the extension's `background.js`:**
```javascript
// Send a message to the native Swift helper
async function organizeBookmarks() {
  const response = await browser.runtime.sendNativeMessage(
    "application.id", // your bundle ID
    { action: "organize" }
  );
  return response; // { status: "ok", folders: {...} }
}
```

**In the native helper (Swift):**
```swift
import SafariServices

class SafariExtensionHandler: SFSafariExtensionHandler {
    override func messageReceived(
        withName messageName: String,
        from page: SFSafariPage,
        userInfo: [String: Any]?
    ) {
        guard let action = userInfo?["action"] as? String else { return }

        switch action {
        case "scan":
            let bookmarks = BookmarkManager.scan()
            page.dispatchMessageToScript(
                withName: "scanResult",
                userInfo: ["bookmarks": bookmarks]
            )
        case "organize":
            Task {
                let result = await BookmarkManager.organize()
                page.dispatchMessageToScript(
                    withName: "organizeResult",
                    userInfo: ["folders": result]
                )
            }
        case "apply":
            BookmarkManager.apply(userInfo?["proposal"] as? [String: Any] ?? [:])
            page.dispatchMessageToScript(
                withName: "applyResult",
                userInfo: ["status": "ok"]
            )
        default:
            break
        }
    }
}
```

### Phase 3: BookmarkManager (Swift)

Port the Python logic to Swift:

```swift
import Foundation

struct BookmarkManager {
    static let bookmarksURL = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Safari/Bookmarks.plist")

    static func scan() -> [[String: String]] {
        guard let data = try? Data(contentsOf: bookmarksURL),
              let plist = try? PropertyListSerialization.propertyList(
                  from: data, format: nil
              ) as? [String: Any] else {
            return []
        }
        return extractBookmarks(from: plist, folder: "")
    }

    private static func extractBookmarks(
        from node: [String: Any], folder: String
    ) -> [[String: String]] {
        var results: [[String: String]] = []
        let type = node["WebBookmarkType"] as? String ?? ""

        if type == "WebBookmarkTypeLeaf" {
            let uri = node["URIDictionary"] as? [String: Any] ?? [:]
            let title = uri["title"] as? String ?? ""
            let url = node["URLString"] as? String ?? ""
            if !url.isEmpty {
                results.append(["title": title, "url": url, "folder": folder])
            }
        } else if type == "WebBookmarkTypeList" {
            let name = node["Title"] as? String ?? ""
            if name == "com.apple.ReadingList" { return results }
            let display = ["", "BookmarksBar", "BookmarksMenu"].contains(name)
                ? folder : name
            for child in node["Children"] as? [[String: Any]] ?? [] {
                results.append(contentsOf: extractBookmarks(from: child, folder: display))
            }
        }
        return results
    }
}
```

### Phase 4: Anthropic API Integration (Swift)

```swift
import Foundation

struct AnthropicClient {
    let apiKey: String
    let model: String

    func categorize(bookmarks: [[String: String]]) async throws -> [String: Any] {
        let url = URL(string: "https://api.anthropic.com/v1/messages")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let bookmarkText = bookmarks.map {
            "- [\($0["title"] ?? "")](\($0["url"] ?? ""))"
        }.joined(separator: "\n")

        let body: [String: Any] = [
            "model": model,
            "max_tokens": 4096,
            "system": "You are a bookmark organizer...", // same prompt as CLI
            "messages": [["role": "user", "content": "Organize: \n\(bookmarkText)"]]
        ]

        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
    }
}
```

### Phase 5: Full Disk Access

The app needs to read `~/Library/Safari/Bookmarks.plist`. Two approaches:

**Option A: Entitlements (sandboxed, App Store)**
- Request `com.apple.security.temporary-exception.files.home-relative-path.read-write`
- Specifically for `Library/Safari/Bookmarks.plist`
- Apple may reject this — test with App Review

**Option B: User-granted access**
- Use `NSOpenPanel` to let the user select the bookmarks file
- Store a security-scoped bookmark for future access
- More App Store friendly

**Option C: Unsandboxed (direct distribution)**
- Skip the App Store, distribute via your website
- No sandbox = direct file access
- Notarize with `notarytool` for Gatekeeper

### Phase 6: App Store Submission

1. **Developer account**: $99/year Apple Developer Program
2. **Archive**: Xcode → Product → Archive
3. **Notarize**: Xcode handles this automatically
4. **App Store Connect**: Upload, fill metadata, screenshots
5. **Review**: Typically 1-3 days

**Pricing strategy** (based on successful indie extensions):
- Free tier: scan + dedupe + deadlinks
- One-time purchase ($4.99): AI organize + apply
- Or subscription ($1.99/mo) if including API costs

## iOS Extension (Stretch Goal)

iOS Safari extensions work similarly but with key differences:
- Same WebExtensions JS, different native layer (UIKit/SwiftUI instead of AppKit)
- Universal Purchase: one buy covers both macOS and iOS
- iOS bookmarks are at a different path, synced via iCloud
- Major differentiator: **Chrome extensions don't exist on iOS**

## On-Device AI (Future)

Replace the Anthropic API with local inference:
- **MLX** (Apple Silicon): Run a small model locally for categorization
- **Apple Intelligence**: If Apple exposes on-device LLM APIs
- **Core ML**: Convert a fine-tuned small model to Core ML format
- Eliminates API costs and privacy concerns

## File Structure

```
Sagemarks/
├── Sagemarks/                    # Container app
│   ├── SagemarksApp.swift
│   ├── ContentView.swift         # Main UI
│   ├── SettingsView.swift        # API key, preferences
│   ├── BookmarkManager.swift     # Plist read/write
│   ├── AnthropicClient.swift     # API calls
│   └── Assets.xcassets/
├── Sagemarks Extension/          # Safari Web Extension
│   ├── manifest.json
│   ├── background.js
│   ├── popup.html
│   ├── popup.js
│   ├── popup.css
│   └── SafariExtensionHandler.swift
├── Sagemarks.xcodeproj
└── README.md
```

## Key References

- [Safari Web Extensions - Apple Docs](https://developer.apple.com/documentation/safariservices/safari-web-extensions)
- [Converting a Chrome Extension to Safari](https://developer.apple.com/documentation/safariservices/converting-a-web-extension-for-safari)
- [Native Messaging in Safari Extensions](https://developer.apple.com/documentation/safariservices/messaging-between-the-app-and-javascript-in-a-safari-web-extension)
- [App Extension Programming Guide](https://developer.apple.com/library/archive/documentation/General/Conceptual/ExtensibilityPG/)
