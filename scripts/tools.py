"""
tools.py — Tools available to the research agent.

  • web_search(query)   — Search the web via DuckDuckGo
  • read_webpage(url)   — Fetch and extract clean text from a URL
  • done(notes)         — Signal that research is complete

Install: pip install duckduckgo-search beautifulsoup4
"""
import logging
import json

log = logging.getLogger("tools")

# ──────────────────────────────────────────────
# Tool definitions (OpenAI function-calling format)
# ──────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the internet for academic content, lecture notes, "
                "textbook explanations, or exam questions on a topic. "
                "Use specific, targeted queries for best results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query. Be specific, e.g. 'pattern recognition Bayes decision theory explained'",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_webpage",
            "description": (
                "Read the full text content of a webpage. Use this to get "
                "detailed explanations, examples, or formulas from a URL "
                "found in search results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the page to read",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": (
                "Call this when you have gathered enough supplementary "
                "information to fully cover all topics in the chapter. "
                "Include your compiled research notes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "research_notes": {
                        "type": "string",
                        "description": (
                            "Your compiled research notes covering all "
                            "supplementary information gathered. Organize "
                            "by topic."
                        ),
                    }
                },
                "required": ["research_notes"],
            },
        },
    },
]


# ──────────────────────────────────────────────
# Tool implementations
# ──────────────────────────────────────────────

def tool_web_search(query: str, max_results: int = 6) -> str:
    """Execute a web search and return formatted results."""
    from duckduckgo_search import DDGS

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        return f"[SEARCH ERROR: {e}]. The search engine is temporarily unavailable or rate-limited. Please try a different query or proceed with read_webpage if you have a URL, or call done() if you have enough info."

    if not results:
        return "[No results found. Try a different query.]"

    formatted = []
    for i, r in enumerate(results, start=1):
        formatted.append(
            f"[{i}] {r.get('title', 'Untitled')}\n"
            f"    URL: {r.get('href', '')}\n"
            f"    {r.get('body', '')}"
        )

    return "\n\n".join(formatted)


def tool_read_webpage(url: str, max_chars: int = 8000) -> str:
    """Fetch a webpage and extract clean text content."""
    import requests
    from bs4 import BeautifulSoup

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return f"[Failed to fetch page: {e}]"

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove noise elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                      "form", "button", "iframe", "noscript", "svg"]):
        tag.decompose()

    # Extract text from content-rich elements
    text_parts = []
    for elem in soup.find_all(["p", "li", "h1", "h2", "h3", "h4", "td", "th",
                                "pre", "code", "blockquote", "dt", "dd"]):
        text = elem.get_text(separator=" ", strip=True)
        if len(text) > 20:  # Skip tiny fragments
            tag_name = elem.name
            if tag_name in ("h1", "h2", "h3", "h4"):
                text_parts.append(f"\n## {text}\n")
            elif tag_name == "li":
                text_parts.append(f"• {text}")
            elif tag_name in ("pre", "code"):
                text_parts.append(f"```\n{text}\n```")
            else:
                text_parts.append(text)

    content = "\n".join(text_parts)

    if not content.strip():
        return "[Page had no extractable text content.]"

    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n[... content truncated ...]"

    return content


# ──────────────────────────────────────────────
# Tool executor
# ──────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "web_search": tool_web_search,
    "read_webpage": tool_read_webpage,
}


def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name and return the result as a string."""
    if name == "done":
        return arguments.get("research_notes", "")

    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return f"[Unknown tool: {name}]"

    log.info(f"  🔧 {name}({json.dumps(arguments, ensure_ascii=False)[:100]})")

    try:
        result = fn(**arguments)
        log.info(f"  → Got {len(result)} chars")
        return result
    except Exception as e:
        log.error(f"  Tool {name} failed: {e}")
        return f"[Tool error: {e}]"
