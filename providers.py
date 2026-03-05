"""Multi-provider LLM and embedding support. BYOK — bring your own key."""

import json
import os

PROVIDERS = {
    "claude": {
        "env": "ANTHROPIC_API_KEY",
        "models": {"chat": "claude-sonnet-4-20250514", "embed": None},
        "name": "Anthropic (Claude)",
    },
    "openai": {
        "env": "OPENAI_API_KEY",
        "models": {"chat": "gpt-4o-mini", "embed": "text-embedding-3-small"},
        "name": "OpenAI (GPT)",
    },
    "gemini": {
        "env": "GEMINI_API_KEY",
        "models": {"chat": "gemini-2.0-flash", "embed": "text-embedding-004"},
        "name": "Google (Gemini)",
    },
}


def detect_provider() -> tuple[str, str]:
    """Auto-detect which provider the user has a key for. Returns (provider, key)."""
    for provider, info in PROVIDERS.items():
        key = os.environ.get(info["env"], "")
        if key:
            return provider, key
    return "", ""


def chat_complete(provider: str, api_key: str, system: str, user_msg: str, model: str | None = None) -> str:
    """Send a chat completion request to any supported provider. Returns raw text."""
    if provider == "claude":
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model or "claude-sonnet-4-20250514",
            max_tokens=8192,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        return msg.content[0].text.strip()

    elif provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=8192,
        )
        return resp.choices[0].message.content.strip()

    elif provider == "gemini":
        import urllib.request
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model or 'gemini-2.0-flash'}:generateContent?key={api_key}"
        body = json.dumps({
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user_msg}]}],
        }).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    raise ValueError(f"Unknown provider: {provider}")


def get_embeddings(provider: str, api_key: str, texts: list[str]) -> list[list[float]]:
    """Get embeddings from any supported provider. Returns list of vectors."""
    if provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        # Batch in groups of 100
        all_embeddings = []
        for i in range(0, len(texts), 100):
            batch = texts[i:i + 100]
            resp = client.embeddings.create(model="text-embedding-3-small", input=batch)
            all_embeddings.extend([e.embedding for e in resp.data])
        return all_embeddings

    elif provider == "gemini":
        import urllib.request
        all_embeddings = []
        for i in range(0, len(texts), 100):
            batch = texts[i:i + 100]
            url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents?key={api_key}"
            body = json.dumps({
                "requests": [{"model": "models/text-embedding-004", "content": {"parts": [{"text": t}]}} for t in batch]
            }).encode()
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
            all_embeddings.extend([e["values"] for e in data["embeddings"]])
        return all_embeddings

    elif provider == "claude":
        # Anthropic doesn't have embeddings — use Voyage AI or fall back to TF-IDF
        return _tfidf_embeddings(texts)

    raise ValueError(f"Unknown provider: {provider}")


def _tfidf_embeddings(texts: list[str]) -> list[list[float]]:
    """Fallback: simple TF-IDF embeddings when no embedding API is available."""
    import math
    import re
    from collections import Counter

    # Tokenize
    def tokenize(text):
        return re.findall(r'[a-z0-9]+', text.lower())

    docs = [tokenize(t) for t in texts]
    # Build vocabulary from top 500 terms by document frequency
    df = Counter()
    for doc in docs:
        df.update(set(doc))
    vocab = [word for word, _ in df.most_common(500)]
    word_to_idx = {w: i for i, w in enumerate(vocab)}

    n = len(docs)
    idf = {w: math.log(n / (df[w] + 1)) for w in vocab}

    vectors = []
    for doc in docs:
        tf = Counter(doc)
        vec = [0.0] * len(vocab)
        for word, idx in word_to_idx.items():
            if word in tf:
                vec[idx] = tf[word] * idf[word]
        # Normalize
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])

    return vectors
