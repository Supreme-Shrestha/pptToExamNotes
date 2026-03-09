"""
generate_qna.py — Uses an LLM (Gemini or OpenAI) to transform extracted
lecture text into a comprehensive QNA study guide in Markdown.
"""
import os
import sys
import textwrap
from dotenv import load_dotenv

load_dotenv()

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
# LLM Backends
# ──────────────────────────────────────────────

def _call_gemini(system: str, user: str) -> str:
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment / .env")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
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
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment / .env")

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
        max_tokens=16384,
    )
    return response.choices[0].message.content


PROVIDERS = {
    "gemini": _call_gemini,
    "openai": _call_openai,
}


def generate_qna_markdown(
    subject_name: str,
    chapter_name: str,
    extracted_text: str,
    provider: str | None = None,
) -> str:
    """Send the extracted text to the configured LLM and return QNA markdown."""
    provider = provider or os.getenv("LLM_PROVIDER", "gemini")
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown LLM provider '{provider}'. Choose from: {list(PROVIDERS.keys())}")

    call_fn = PROVIDERS[provider]
    user_prompt = build_user_prompt(subject_name, chapter_name, extracted_text)
    return call_fn(SYSTEM_PROMPT, user_prompt)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # Quick test: python generate_qna.py "Pattern Recognition" "Introduction" "some text..."
    if len(sys.argv) < 4:
        print("Usage: python generate_qna.py <subject> <chapter> <text_or_file>")
        sys.exit(1)

    subject, chapter, text_arg = sys.argv[1], sys.argv[2], sys.argv[3]
    if os.path.isfile(text_arg):
        with open(text_arg) as f:
            text_arg = f.read()

    md = generate_qna_markdown(subject, chapter, text_arg)
    print(md)
