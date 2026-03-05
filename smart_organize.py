"""Smart organizer: fetches page content, embeds, clusters by similarity, then names folders with LLM."""

import json
import math
import random
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path


# ---------------------------------------------------------------------------
# Page content fetching
# ---------------------------------------------------------------------------

class MetaExtractor(HTMLParser):
    """Extract title, description, and og:tags from HTML."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.description = ""
        self.og_title = ""
        self.og_description = ""
        self.keywords = ""
        self._in_title = False
        self._title_data = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "title":
            self._in_title = True
            self._title_data = []
        elif tag == "meta":
            name = attrs_dict.get("name", "").lower()
            prop = attrs_dict.get("property", "").lower()
            content = attrs_dict.get("content", "")
            if name == "description":
                self.description = content
            elif name == "keywords":
                self.keywords = content
            elif prop == "og:title":
                self.og_title = content
            elif prop == "og:description":
                self.og_description = content

    def handle_data(self, data):
        if self._in_title:
            self._title_data.append(data)

    def handle_endtag(self, tag):
        if tag == "title" and self._in_title:
            self.title = " ".join(self._title_data).strip()
            self._in_title = False


def fetch_page_metadata(url: str, timeout: int = 8) -> dict:
    """Fetch a page and extract metadata. Returns {title, description, keywords}."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Sagemarks/1.0 (bookmark organizer)",
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # Only read first 50KB to get metadata
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return {"title": "", "description": "", "keywords": ""}
            raw = resp.read(50_000)
            html = raw.decode("utf-8", errors="replace")

        parser = MetaExtractor()
        parser.feed(html)
        return {
            "title": parser.og_title or parser.title,
            "description": parser.og_description or parser.description,
            "keywords": parser.keywords,
        }
    except Exception:
        return {"title": "", "description": "", "keywords": ""}


def enrich_bookmarks(bookmarks: list[dict], max_workers: int = 10) -> list[dict]:
    """Fetch metadata for all bookmarks in parallel."""
    enriched = list(bookmarks)  # shallow copy

    print(f"  Fetching page content for {len(bookmarks)} bookmarks...")

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fetch_page_metadata, b["url"]): i for i, b in enumerate(bookmarks)}
        done = 0
        for future in as_completed(futures):
            idx = futures[future]
            meta = future.result()
            enriched[idx] = {**enriched[idx], **meta}
            done += 1
            if done % 25 == 0:
                print(f"  Fetched {done}/{len(bookmarks)}...")

    print(f"  Done fetching metadata.\n")
    return enriched


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (norm_a * norm_b)


def kmeans_cluster(vectors: list[list[float]], k: int, max_iter: int = 50) -> list[int]:
    """Simple k-means clustering. Returns list of cluster assignments."""
    n = len(vectors)
    dim = len(vectors[0])

    # Initialize centroids with k-means++
    centroids = [vectors[random.randint(0, n - 1)][:]]
    for _ in range(1, k):
        dists = []
        for v in vectors:
            min_d = min(sum((a - b) ** 2 for a, b in zip(v, c)) for c in centroids)
            dists.append(min_d)
        total = sum(dists)
        if total == 0:
            centroids.append(vectors[random.randint(0, n - 1)][:])
            continue
        probs = [d / total for d in dists]
        r = random.random()
        cumsum = 0
        for i, p in enumerate(probs):
            cumsum += p
            if cumsum >= r:
                centroids.append(vectors[i][:])
                break

    assignments = [0] * n
    for _ in range(max_iter):
        # Assign
        changed = False
        for i, v in enumerate(vectors):
            best = min(range(k), key=lambda c: sum((a - b) ** 2 for a, b in zip(v, centroids[c])))
            if assignments[i] != best:
                changed = True
                assignments[i] = best
        if not changed:
            break

        # Update centroids
        for c in range(k):
            members = [vectors[i] for i in range(n) if assignments[i] == c]
            if members:
                centroids[c] = [sum(col) / len(members) for col in zip(*members)]

    return assignments


def auto_k(n_bookmarks: int) -> int:
    """Heuristic for number of clusters."""
    if n_bookmarks <= 20:
        return 5
    elif n_bookmarks <= 50:
        return 7
    elif n_bookmarks <= 100:
        return 10
    elif n_bookmarks <= 200:
        return 13
    else:
        return 15


# ---------------------------------------------------------------------------
# Smart organize pipeline
# ---------------------------------------------------------------------------

NAMING_PROMPT = """\
You are naming bookmark folders. Given groups of bookmarks (title + URL + description), \
create a short, descriptive folder name for each group.

Rules:
- Folder names: 1-3 words, Title Case (e.g. "ML Research", "Job Search", "Dev Tools")
- Names should reflect the common theme/purpose of the bookmarks in that group
- Be specific: "Quant Interview Prep" is better than "Career"

Return ONLY valid JSON — an object where keys are the group numbers (as strings) and \
values are the folder names. No markdown, no explanation."""


def smart_organize(bookmarks: list[dict], provider: str, api_key: str, fetch_content: bool = True) -> dict:
    """Full pipeline: fetch → embed → cluster → name → return categorized dict."""
    from providers import get_embeddings, chat_complete

    # Step 1: Enrich with page content
    if fetch_content:
        enriched = enrich_bookmarks(bookmarks)
    else:
        enriched = bookmarks

    # Step 2: Build text for embedding
    texts = []
    for b in enriched:
        parts = [b.get("title", ""), b.get("url", "")]
        if b.get("description"):
            parts.append(b["description"])
        if b.get("keywords"):
            parts.append(b["keywords"])
        if b.get("folder"):
            parts.append(f"folder: {b['folder']}")
        texts.append(" | ".join(parts))

    # Step 3: Embed
    print(f"  Generating embeddings for {len(texts)} bookmarks...")
    embeddings = get_embeddings(provider, api_key, texts)
    print(f"  Done.\n")

    # Step 4: Cluster
    k = auto_k(len(bookmarks))
    print(f"  Clustering into ~{k} groups...")
    assignments = kmeans_cluster(embeddings, k)

    # Step 5: Build groups
    groups = {}
    for i, cluster_id in enumerate(assignments):
        groups.setdefault(cluster_id, []).append(enriched[i])

    # Step 6: Ask LLM to name each group
    group_descriptions = []
    for gid in sorted(groups.keys()):
        items = groups[gid]
        desc_lines = []
        for b in items[:8]:  # Show up to 8 per group
            line = f"  - {b.get('title', '(no title)')}"
            if b.get("description"):
                line += f" — {b['description'][:80]}"
            line += f" ({b['url'][:60]})"
            desc_lines.append(line)
        if len(items) > 8:
            desc_lines.append(f"  ... and {len(items) - 8} more")
        group_descriptions.append(f"Group {gid} ({len(items)} bookmarks):\n" + "\n".join(desc_lines))

    naming_input = "\n\n".join(group_descriptions)
    print(f"  Asking AI to name {len(groups)} clusters...")
    raw = chat_complete(provider, api_key, NAMING_PROMPT, naming_input)

    # Parse names
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    names = json.loads(raw)

    # Step 7: Build final categorized dict
    categorized = {}
    for gid in sorted(groups.keys()):
        folder_name = names.get(str(gid), f"Group {gid}")
        categorized[folder_name] = [
            {"title": b.get("title", ""), "url": b["url"]}
            for b in groups[gid]
        ]

    return categorized
