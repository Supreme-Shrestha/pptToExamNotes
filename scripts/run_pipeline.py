"""
run_pipeline.py — Main orchestrator that scans the Subjects/ folder,
extracts text, generates QNA via LLM, converts to PDF, and saves the result.

Usage:
    python scripts/run_pipeline.py                 # process all subjects
    python scripts/run_pipeline.py --subject "PatternRecognition"  # single subject
    python scripts/run_pipeline.py --force          # re-generate even if QNA exists
"""
import argparse
import os
import sys
import time
import logging

# Ensure the scripts package is importable when run from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from extract_text import extract_text
from generate_qna import generate_qna_markdown
from generate_pdf import md_to_pdf
from agent import run_research_agent

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
SUBJECTS_DIR = os.path.join(os.path.dirname(__file__), "..", "Subjects")
SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".ppt"}
QNA_SUFFIX = "_QNA"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")


def qna_pdf_path(source_path: str) -> str:
    """Return the expected QNA PDF path for a given source file."""
    base, _ = os.path.splitext(source_path)
    return base + QNA_SUFFIX + ".pdf"


def qna_md_path(source_path: str) -> str:
    """Return the intermediate Markdown path for a given source file."""
    base, _ = os.path.splitext(source_path)
    return base + QNA_SUFFIX + ".md"


def discover_files(subjects_dir: str, subject_filter: str | None = None) -> list[dict]:
    """Walk the Subjects/ tree and find processable files."""
    targets = []
    for subject in sorted(os.listdir(subjects_dir)):
        subject_path = os.path.join(subjects_dir, subject)
        if not os.path.isdir(subject_path):
            continue
        if subject_filter and subject != subject_filter:
            continue

        for fname in sorted(os.listdir(subject_path)):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            # Skip already-generated QNA files
            if QNA_SUFFIX in fname:
                continue

            full_path = os.path.join(subject_path, fname)
            targets.append({
                "subject": subject,
                "chapter": os.path.splitext(fname)[0],
                "source_path": full_path,
                "qna_pdf": qna_pdf_path(full_path),
                "qna_md": qna_md_path(full_path),
            })
    return targets


def process_file(target: dict, force: bool = False) -> bool:
    """Process a single file through the pipeline. Returns True if a new QNA was generated."""
    subject = target["subject"]
    chapter = target["chapter"]
    source = target["source_path"]
    pdf_out = target["qna_pdf"]
    md_out = target["qna_md"]

    if not force and os.path.exists(pdf_out):
        log.info(f"SKIP  {chapter} — QNA already exists")
        return False

    log.info(f"START  [{subject}] {chapter}")

    # Step 1 — Extract
    log.info("  → Extracting text …")
    try:
        raw_text = extract_text(source)
    except Exception as e:
        log.error(f"  ✗ Extraction failed: {e}")
        return False

    if len(raw_text.strip()) < 50:
        log.warning(f"  ⚠ Very little text extracted ({len(raw_text)} chars), skipping")
        return False

    log.info(f"  → Extracted {len(raw_text)} characters")

    # Step 1.5 — Agentic Research
    log.info("  → Running autonomous research agent to fill gaps …")
    t0 = time.time()
    try:
        research_notes = run_research_agent(subject, chapter, raw_text)
    except Exception as e:
        log.error(f"  ✗ Research failed (proceeding without it): {e}")
        research_notes = ""
    elapsed = time.time() - t0
    log.info(f"  → Research finished in {elapsed:.1f}s ({len(research_notes)} chars)")
    
    # Combine original text with research notes
    combined_content = raw_text
    if research_notes.strip():
        combined_content += "\n\n" + "="*50 + "\nSUPPLEMENTARY RESEARCH NOTES:\n" + "="*50 + "\n\n" + research_notes

    # Step 2 — LLM QNA generation
    log.info("  → Generating QNA via LLM …")
    t0 = time.time()
    try:
        md_content = generate_qna_markdown(subject, chapter, combined_content)
    except Exception as e:
        log.error(f"  ✗ LLM generation failed: {e}")
        return False
    elapsed = time.time() - t0
    log.info(f"  → LLM responded in {elapsed:.1f}s  ({len(md_content)} chars)")

    # Save intermediate markdown
    with open(md_out, "w", encoding="utf-8") as f:
        f.write(md_content)
    log.info(f"  → Saved Markdown: {os.path.basename(md_out)}")

    # Step 3 — PDF conversion
    log.info("  → Converting to PDF …")
    try:
        md_to_pdf(md_content, pdf_out)
    except Exception as e:
        log.error(f"  ✗ PDF conversion failed: {e}")
        return False

    log.info(f"  ✓ DONE  → {os.path.basename(pdf_out)}")
    return True


def main():
    parser = argparse.ArgumentParser(description="PPT-to-Exam-Notes QNA Pipeline")
    parser.add_argument("--subject", type=str, default=None, help="Process a single subject folder")
    parser.add_argument("--force", action="store_true", help="Re-generate even if QNA PDF already exists")
    parser.add_argument("--provider", type=str, default=None, help="LLM provider: vllm | ollama | gemini | openai | anthropic | groq | together")
    args = parser.parse_args()

    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    subjects_dir = os.path.abspath(SUBJECTS_DIR)
    log.info(f"Scanning: {subjects_dir}")

    targets = discover_files(subjects_dir, subject_filter=args.subject)
    if not targets:
        log.warning("No processable files found.")
        return

    log.info(f"Found {len(targets)} file(s) to process")

    generated = 0
    for target in targets:
        if process_file(target, force=args.force):
            generated += 1

    log.info(f"\nPipeline complete — {generated}/{len(targets)} QNA PDFs generated.")


if __name__ == "__main__":
    main()
