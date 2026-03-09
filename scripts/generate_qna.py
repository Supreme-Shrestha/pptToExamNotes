"""
generate_qna.py — Uses an LLM to transform extracted lecture text into a
comprehensive QNA study guide in Markdown.

Supported providers:
  LOCAL (default — no API key needed, no extra pip packages):
  • vllm     — Local vLLM server (recommended for A100 GPUs)
  • ollama   — Local Ollama server

  CLOUD (API key required, may need extra pip packages):
  • gemini   — Google Gemini      (pip install google-generativeai)
  • openai   — OpenAI             (pip install openai)
  • anthropic— Anthropic Claude   (pip install anthropic)
  • groq     — Groq cloud Llama   (pip install openai)
  • together — Together AI        (pip install openai)
"""
import os
import sys
import json
import textwrap
import logging
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("generate_qna")

# ──────────────────────────────────────────────
# Prompt templates
# ──────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""\
    You are an expert university professor and pedagogical assistant.
    Your objective is to take raw, often compressed or incomplete lecture notes
    (extracted from PDF/PPT) and transform them into a comprehensive,
    self-sufficient Question and Answer (QNA) study guide.

    Rules:
    • If the provided material is incomplete or missing necessary foundational
      context, you MUST independently fill in the gaps using your broad knowledge
      base to fully cover the implied chapter topics.
    • Cover every major concept mentioned or implied by the material.
    • Answers must be detailed, academically rigorous, and directly useful for
      exam preparation.
    • Output ONLY clean Markdown.  Use Headings (#, ##, ###), bold, lists, and
      code blocks where appropriate.  Do NOT wrap the entire output in a code
      fence.
""")


def build_user_prompt(subject_name: str, chapter_name: str, extracted_text: str) -> str:
    return textwrap.dedent(f"""\
        **Subject**: {subject_name}
        **Chapter / Lecture**: {chapter_name}

        **Extracted Material Content**:
        \"\"\"
        {extracted_text}
        \"\"\"

        **Your Task**:
        1. Identify every core topic discussed or implied in this material.
        2. Complete any missing concepts, definitions, formulas, diagrams
           descriptions, or broad context necessary for a student to fully
           understand the chapter.
        3. Generate a comprehensive QNA guide organised as:
           - **Basic Concepts & Definitions**
           - **Core Theory & Principles**
           - **Advanced / Applied Topics**
           - **Numerical / Practical Problems** (if applicable)
        4. Each question should be followed by a detailed, exam-ready answer.
        5. Aim for at least 25-40 high-quality questions covering the full breadth
           of the chapter.

        Output the result strictly in clean Markdown format.
    """)


# ──────────────────────────────────────────────
# Helper: lightweight HTTP caller (no openai SDK needed)
# ──────────────────────────────────────────────

def _call_chat_api(
    system: str, user: str, base_url: str, api_key: str, model: str
) -> str:
    """Call any OpenAI-compatible chat/completions endpoint using requests.
    Works with vLLM, Ollama, Groq, Together, and OpenAI without needing
    the openai Python SDK (avoids version conflicts with vLLM)."""
    import requests

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.4,
        "max_tokens": 16384,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=600)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


# ──────────────────────────────────────────────
# LOCAL providers (no API key, no extra packages)
# ──────────────────────────────────────────────

def _call_vllm(system: str, user: str) -> str:
    """Local vLLM server — recommended for A100 GPUs.

    Start vLLM before running the pipeline:
        python -m vllm.entrypoints.openai.api_server \\
            --model Qwen/Qwen2.5-72B-Instruct-AWQ \\
            --quantization awq \\
            --max-model-len 32768 \\
            --gpu-memory-utilization 0.95 \\
            --port 8000
    """
    base_url = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
    model = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-72B-Instruct-AWQ")
    return _call_chat_api(system, user, base_url, "not-needed", model)


def _call_ollama(system: str, user: str) -> str:
    """Local Ollama server.

    Start Ollama before running the pipeline:
        ollama pull qwen2.5:72b
        ollama serve
    """
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:72b")
    return _call_chat_api(system, user, base_url, "ollama", model)


# ──────────────────────────────────────────────
# CLOUD providers (API key required)
# ──────────────────────────────────────────────

def _call_gemini(system: str, user: str) -> str:
    """Google Gemini via the google-generativeai SDK.
    Install: pip install google-generativeai"""
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment / .env")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        system_instruction=system,
    )
    response = model.generate_content(
        user,
        generation_config=genai.GenerationConfig(
            temperature=0.4,
            max_output_tokens=65536,
        ),
    )
    return response.text


def _call_openai(system: str, user: str) -> str:
    """OpenAI (GPT-4o) via HTTP (no SDK needed)."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment / .env")

    return _call_chat_api(
        system, user,
        base_url="https://api.openai.com/v1",
        api_key=api_key,
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
    )


def _call_anthropic(system: str, user: str) -> str:
    """Anthropic Claude via the anthropic SDK.
    Install: pip install anthropic"""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment / .env")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        max_tokens=16384,
        system=system,
        messages=[{"role": "user", "content": user}],
        temperature=0.4,
    )
    return response.content[0].text


def _call_groq(system: str, user: str) -> str:
    """Groq-hosted models (extremely fast cloud inference)."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set in environment / .env")

    return _call_chat_api(
        system, user,
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key,
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    )


def _call_together(system: str, user: str) -> str:
    """Together AI hosted models."""
    api_key = os.getenv("TOGETHER_API_KEY")
    if not api_key:
        raise RuntimeError("TOGETHER_API_KEY not set in environment / .env")

    return _call_chat_api(
        system, user,
        base_url="https://api.together.xyz/v1",
        api_key=api_key,
        model=os.getenv("TOGETHER_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    )


# ──────────────────────────────────────────────
# Provider registry
# ──────────────────────────────────────────────

PROVIDERS = {
    # Local (default)
    "vllm":      _call_vllm,
    "ollama":    _call_ollama,
    # Cloud
    "gemini":    _call_gemini,
    "openai":    _call_openai,
    "anthropic": _call_anthropic,
    "groq":      _call_groq,
    "together":  _call_together,
}


def generate_qna_markdown(
    subject_name: str,
    chapter_name: str,
    extracted_text: str,
    provider: str | None = None,
) -> str:
    """Send the extracted text to the configured LLM and return QNA markdown."""
    provider = provider or os.getenv("LLM_PROVIDER", "vllm")
    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            f"Choose from: {', '.join(PROVIDERS.keys())}"
        )

    call_fn = PROVIDERS[provider]
    user_prompt = build_user_prompt(subject_name, chapter_name, extracted_text)
    return call_fn(SYSTEM_PROMPT, user_prompt)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python generate_qna.py <subject> <chapter> <text_or_file>")
        print(f"\nAvailable providers: {', '.join(PROVIDERS.keys())}")
        print(f"Current default: {os.getenv('LLM_PROVIDER', 'vllm')}")
        sys.exit(1)

    subject, chapter, text_arg = sys.argv[1], sys.argv[2], sys.argv[3]
    if os.path.isfile(text_arg):
        with open(text_arg) as f:
            text_arg = f.read()

    md = generate_qna_markdown(subject, chapter, text_arg)
    print(md)
