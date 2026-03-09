"""
extract_text.py — Extracts text content from PDF and PPTX files.
"""
import os
import sys

def extract_from_pdf(filepath: str) -> str:
    """Extract all text from a PDF file using PyMuPDF."""
    import fitz  # PyMuPDF

    text_parts = []
    with fitz.open(filepath) as doc:
        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text("text")
            if page_text.strip():
                text_parts.append(f"--- Page {page_num} ---\n{page_text.strip()}")
    return "\n\n".join(text_parts)


def extract_from_pptx(filepath: str) -> str:
    """Extract text from all slides (shapes + notes) of a PPTX file."""
    from pptx import Presentation

    text_parts = []
    prs = Presentation(filepath)
    for slide_num, slide in enumerate(prs.slides, start=1):
        slide_texts = []
        # Shape text
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    line = paragraph.text.strip()
                    if line:
                        slide_texts.append(line)
        # Speaker notes
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                slide_texts.append(f"[Speaker Notes]: {notes}")
        if slide_texts:
            text_parts.append(f"--- Slide {slide_num} ---\n" + "\n".join(slide_texts))
    return "\n\n".join(text_parts)


def extract_text(filepath: str) -> str:
    """Dispatch to the correct extractor based on file extension."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        return extract_from_pdf(filepath)
    elif ext in (".pptx", ".ppt"):
        return extract_from_pptx(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_text.py <filepath>")
        sys.exit(1)
    text = extract_text(sys.argv[1])
    print(text[:3000])
    print(f"\n... (total {len(text)} characters extracted)")
