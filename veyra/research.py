"""Web research for the reader. Uses the `ddgs` package (pip install ddgs)."""


def search(query, n=4):
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return []
    try:
        return [f"{r.get('title', '')}: {r.get('body', '')}"[:400] for r in DDGS().text(query, max_results=n)]
    except Exception:
        return []
