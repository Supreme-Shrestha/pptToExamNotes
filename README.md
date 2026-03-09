# 📚 pptToExamNotes — Automated QNA Generation Pipeline

Turn your compressed/incomplete lecture PDFs and PPTs into **comprehensive, exam-ready QNA study guides** — automatically.

## How It Works

```
Subjects/
  └── PatternRecognition/
        ├── 1_Introduction_PR_SV.pdf        ← teacher's slides
        ├── 1_Introduction_PR_SV_QNA.md     ← generated Markdown
        └── 1_Introduction_PR_SV_QNA.pdf    ← generated PDF
```

1. **Extract** text from PDF/PPTX files
2. **Expand & Complete** the material using an LLM (Gemini / OpenAI) that fills in missing context
3. **Generate** a styled QNA PDF study guide
4. **Auto-commit & push** results to the remote repository

## Quick Start

### 1. Clone & Install

```bash
git clone <your-repo-url>
cd pptToExamNotes
pip install -r requirements.txt
```

### 2. Configure API Key

```bash
cp .env.example .env
# Edit .env — set LLM_PROVIDER and add the matching API key
# Supported providers: gemini, openai, anthropic, groq, together, ollama
```

### 3. Run the Pipeline

```bash
# Process all subjects
python scripts/run_pipeline.py

# Process a single subject
python scripts/run_pipeline.py --subject "PatternRecognition"

# Force re-generate existing QNAs
python scripts/run_pipeline.py --force

# Use a specific LLM provider
python scripts/run_pipeline.py --provider groq
# Providers: gemini | openai | anthropic | groq | together | ollama
```

### 4. Sync to Git

```bash
bash scripts/git_sync.sh
```

## CI/CD (GitHub Actions)

The pipeline runs automatically when you push new PDF/PPT files to the `Subjects/` folder.

**Setup**: Add your `GEMINI_API_KEY` (or `OPENAI_API_KEY`) as a **repository secret** in GitHub Settings → Secrets.

You can also trigger runs manually from the Actions tab.

## Project Structure

| File | Purpose |
|---|---|
| `scripts/extract_text.py` | PDF & PPTX text extraction |
| `scripts/generate_qna.py` | LLM prompts & API calls |
| `scripts/generate_pdf.py` | Markdown → styled PDF |
| `scripts/run_pipeline.py` | Main orchestrator |
| `scripts/git_sync.sh` | Auto-commit & push |
| `.github/workflows/qna_pipeline.yml` | CI/CD automation |

## Requirements

- Python 3.10+
- An API key for at least one provider: **Gemini** (free tier), **OpenAI**, **Anthropic**, **Groq** (free tier), or **Together AI** — or a local **Ollama** install (no key needed)
- System dependencies for PDF rendering: `libpango`, `libharfbuzz` (installed automatically in CI)
