"""
web_search.py — Searches the web for supplementary academic content
to fill gaps in incomplete lecture materials.

Uses DuckDuckGo (free, no API key needed).
Install: pip install ddgs
"""
import logging
from typing import Optional

log = logging.getLogger("web_search")


def search_topic(
    subject: str,
    chapter: str,
    key_topics: list[str] | None = None,
    max_results: int = 8,
) -> str:
    """Search the web for academic content related to the chapter.

    Returns a formatted string of search results that can be appended
    to the LLM prompt as supplementary context.
    """
    from ddgs import DDGS

    # Build search queries
    queries = [
        f"{subject} {chapter} lecture notes",
        f"{subject} {chapter} concepts explained",
        f"{subject} {chapter} exam questions and answers",
    ]

    # Add topic-specific queries if provided
    if key_topics:
        for topic in key_topics[:5]:  # Limit to avoid too many searches
            queries.append(f"{subject} {topic} explanation")

    all_results = []
    seen_urls = set()

    with DDGS() as ddgs:
        for query in queries:
            try:
                results = list(ddgs.text(query, max_results=max_results))
                for r in results:
                    url = r.get("href", "")
                    if url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append({
                            "title": r.get("title", ""),
                            "body": r.get("body", ""),
                            "url": url,
                        })
            except Exception as e:
                log.warning(f"  Search failed for '{query}': {e}")
                continue

    if not all_results:
        log.warning("  No web results found")
        return ""

    log.info(f"  → Found {len(all_results)} unique web results")

    # Format results for the LLM
    formatted = []
    for i, r in enumerate(all_results, start=1):
        formatted.append(
            f"[Source {i}] {r['title']}\n"
            f"URL: {r['url']}\n"
            f"{r['body']}\n"
        )

    return "\n".join(formatted)


def extract_key_topics(extracted_text: str, max_topics: int = 10) -> list[str]:
    """Extract potential key topics from the extracted text for targeted searches.
    Uses simple heuristic: finds text after page/slide headers and headings."""
    topics = []
    lines = extracted_text.split("\n")

    for line in lines:
        line = line.strip()
        # Look for likely topic indicators
        if line.startswith("--- Page") or line.startswith("--- Slide"):
            continue
        if line.startswith("[Visual:") or line.startswith("["):
            continue
        # Short, capitalized lines are often slide titles / headings
        if 3 < len(line) < 80 and not line.startswith("•") and not line.startswith("-"):
            # Basic heuristic: title-case or all-caps lines
            if line.istitle() or line.isupper() or line.endswith(":"):
                clean = line.rstrip(":").strip()
                if clean and clean not in topics:
                    topics.append(clean)

        if len(topics) >= max_topics:
            break

    return topics


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python web_search.py <subject> <chapter> [topics...]")
        sys.exit(1)

    subject = sys.argv[1]
    chapter = sys.argv[2]
    topics = sys.argv[3:] if len(sys.argv) > 3 else None

    logging.basicConfig(level=logging.INFO)
    results = search_topic(subject, chapter, topics)
    print(results[:3000])
    print(f"\n... (total {len(results)} characters)")
