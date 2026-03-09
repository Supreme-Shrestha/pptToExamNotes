"""
agent.py — Agentic LLM engine with tool-use capabilities.

Implements a ReAct-style (Reasoning + Acting) loop where the LLM:
  1. Analyzes the extracted material and identifies gaps
  2. Autonomously decides what to search for on the internet
  3. Reads relevant web pages for detailed content
  4. Iterates until it has comprehensive coverage
  5. Returns compiled research notes

Works with any OpenAI-compatible API (Ollama, vLLM, etc.).
"""
import os
import json
import time
import logging
import textwrap

from tools import TOOL_DEFINITIONS, execute_tool

log = logging.getLogger("agent")

# ──────────────────────────────────────────────
# Agent configuration
# ──────────────────────────────────────────────

MAX_AGENT_ITERATIONS = int(os.getenv("AGENT_MAX_ITERATIONS", "12"))
AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "600"))  # seconds

RESEARCH_SYSTEM_PROMPT = textwrap.dedent("""\
    You are an expert academic researcher. Your job is to gather comprehensive
    supplementary material from the internet to fill gaps in incomplete lecture
    notes.

    You have access to these tools:
    • web_search(query)      — Search the web for information
    • read_webpage(url)      — Read the full content of a web page
    • done(research_notes)   — Call this when you have enough information

    Strategy:
    1. First, analyze the extracted material to identify ALL topics covered
       and any gaps where the slides are incomplete or unclear.
    2. Search for each major topic to find detailed explanations, formulas,
       examples, and exam-style content.
    3. When a search result looks promising, use read_webpage to get the
       full content.
    4. Focus on: definitions, theorems, formulas/derivations, algorithms,
       worked examples, comparisons, and real-world applications.
    5. VERY IMPORTANT: You MUST use your tools. Do not just talk about
       searching. Use the web_search tool.
    6. When you have gathered enough information for EVERY topic in the
       chapter, call done() with your organized research notes.

    Rules for Tool Use:
    • Every turn MUST result in a tool call until you are finished.
    • If a search returns no results, try broader or different keywords.
    • Consolidate everything into a structure like:
      # [Topic Name]
      ## Definitions
      ## Formulas/Theorems
      ## Examples
      ...
""")


# ──────────────────────────────────────────────
# HTTP caller with tool support
# ──────────────────────────────────────────────

def _call_llm_with_tools(
    messages: list[dict],
    tools: list[dict],
    base_url: str,
    api_key: str,
    model: str,
) -> dict:
    """Call the LLM with tool definitions and return the raw response."""
    import requests

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


# ──────────────────────────────────────────────
# Agent loop
# ──────────────────────────────────────────────

def run_research_agent(
    subject: str,
    chapter: str,
    extracted_text: str,
    provider: str | None = None,
) -> str:
    """Run the research agent to gather supplementary material.

    Returns compiled research notes as a string.
    """
    provider = provider or os.getenv("LLM_PROVIDER", "ollama")

    # Resolve provider settings
    if provider == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        api_key = "ollama"
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:32b")
    elif provider == "vllm":
        base_url = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
        api_key = "not-needed"
        model = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-72B-Instruct-AWQ")
    else:
        log.warning(f"  Research agent not supported for provider '{provider}', skipping")
        return ""

    # Truncate extracted text if extremely long to leave room for conversation
    max_extract_chars = int(os.getenv("AGENT_MAX_EXTRACT_CHARS", "15000"))
    if len(extracted_text) > max_extract_chars:
        extracted_text = (
            extracted_text[:max_extract_chars]
            + f"\n\n[... truncated, {len(extracted_text)} total chars ...]"
        )

    # Initialize conversation
    user_message = textwrap.dedent(f"""\
        I need you to research supplementary material for the following chapter.

        **Subject**: {subject}
        **Chapter**: {chapter}

        **Extracted lecture material** (may be incomplete/OCR'd):
        \"\"\"
        {extracted_text}
        \"\"\"

        Please:
        1. Identify the key topics in this material
        2. Search the web for comprehensive explanations of each topic
        3. Read the most relevant pages for detailed content
        4. When done, call the done() tool with your organized research notes

        Be thorough — search for definitions, formulas, algorithms, examples,
        comparisons, and any content that would help a student ace the exam.
    """)

    messages = [
        {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    log.info(f"  🤖 Research agent started (max {MAX_AGENT_ITERATIONS} iterations)")
    start_time = time.time()

    for iteration in range(1, MAX_AGENT_ITERATIONS + 1):
        elapsed = time.time() - start_time
        if elapsed > AGENT_TIMEOUT:
            log.warning(f"  ⏰ Agent timeout after {elapsed:.0f}s")
            break

        log.info(f"  📍 Iteration {iteration}/{MAX_AGENT_ITERATIONS}")

        try:
            response = _call_llm_with_tools(
                messages, TOOL_DEFINITIONS, base_url, api_key, model
            )
        except Exception as e:
            log.error(f"  ✗ LLM call failed: {e}")
            break

        choice = response["choices"][0]
        message = choice["message"]

        # Add assistant's response to conversation history
        messages.append(message)

        # Check if the LLM made tool calls
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            # No tool calls — LLM responded with text only
            content = message.get("content", "")
            if content:
                log.info(f"  💬 Agent response (no tool call): {content[:100]}...")
                
                # If the agent is actually providing research notes in text, we're done
                if "RESEARCH NOTES" in content.upper() or len(content) > 1000:
                    log.info("  ✓ Agent provided research notes in text form")
                    return content
                
                # Otherwise, nudge the agent to use its tools
                messages.append({
                    "role": "user",
                    "content": "You haven't called the done() tool or any research tools. If you are finished, call done(research_notes). If you need more info, use web_search or read_webpage."
                })
                continue
            
            # If no content and no tools, something is wrong
            break

        # Execute each tool call
        for tool_call in tool_calls:
            fn_name = tool_call["function"]["name"]
            try:
                fn_args = json.loads(tool_call["function"]["arguments"])
            except json.JSONDecodeError:
                fn_args = {}

            # Execute the tool
            result = execute_tool(fn_name, fn_args)

            # Check if agent signaled completion
            if fn_name == "done":
                research_notes = fn_args.get("research_notes", result)
                log.info(
                    f"  ✅ Research complete after {iteration} iterations "
                    f"({elapsed:.0f}s) — {len(research_notes)} chars of notes"
                )
                return research_notes

            # Add tool result to conversation
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.get("id", f"call_{iteration}"),
                "content": result,
            })

    # If we exhausted iterations without done(), compile what we have
    elapsed = time.time() - start_time
    log.warning(
        f"  ⚠ Agent finished without calling done() ({iteration} iterations, {elapsed:.0f}s)"
    )

    # Try to extract any useful content from the conversation
    research_parts = []
    for msg in messages:
        if msg["role"] == "tool" and not msg["content"].startswith("["):
            research_parts.append(msg["content"][:2000])

    if research_parts:
        return "\n\n---\n\n".join(research_parts)

    return ""


# ──────────────────────────────────────────────
# CLI (for testing)
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    if len(sys.argv) < 3:
        print("Usage: python agent.py <subject> <chapter> [text_or_file]")
        sys.exit(1)

    subject, chapter = sys.argv[1], sys.argv[2]
    text = sys.argv[3] if len(sys.argv) > 3 else "Introduction to the topic"

    if os.path.isfile(text):
        with open(text) as f:
            text = f.read()

    notes = run_research_agent(subject, chapter, text)
    print("\n" + "=" * 60)
    print("RESEARCH NOTES:")
    print("=" * 60)
    print(notes[:5000])
