"""
generate_pdf.py — Converts a Markdown string (or .md file) to a styled PDF.
Uses weasyprint for high-quality PDF rendering.
"""
import os
import sys
import markdown


# ──────────────────────────────────────────────
# Stylesheet for the generated PDF
# ──────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

@page {
    size: A4;
    margin: 2cm;
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9pt;
        color: #888;
    }
}

body {
    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a1a1a;
}

h1 {
    font-size: 22pt;
    color: #1e3a5f;
    border-bottom: 3px solid #1e3a5f;
    padding-bottom: 6px;
    margin-top: 28px;
}
h2 {
    font-size: 16pt;
    color: #2b5c8a;
    border-bottom: 1px solid #ccc;
    padding-bottom: 4px;
    margin-top: 22px;
}
h3 {
    font-size: 13pt;
    color: #3a7abd;
    margin-top: 16px;
}

strong {
    color: #1e3a5f;
}

code {
    background: #f4f4f4;
    padding: 2px 5px;
    border-radius: 3px;
    font-size: 10pt;
}
pre {
    background: #f4f4f4;
    padding: 12px;
    border-radius: 5px;
    overflow-x: auto;
    font-size: 10pt;
    border-left: 4px solid #2b5c8a;
}

ul, ol {
    margin-left: 18px;
}
li {
    margin-bottom: 4px;
}

blockquote {
    border-left: 4px solid #2b5c8a;
    margin: 12px 0;
    padding: 8px 16px;
    background: #f0f6fc;
    color: #333;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
}
th, td {
    border: 1px solid #ccc;
    padding: 8px 10px;
    text-align: left;
}
th {
    background: #1e3a5f;
    color: white;
    font-weight: 600;
}
tr:nth-child(even) {
    background: #f9f9f9;
}

img {
    max-width: 100%;
    height: auto;
    border-radius: 6px;
    margin: 16px 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    display: block;
}
"""


def md_to_pdf(md_content: str, output_path: str) -> str:
    """Convert markdown text to a styled PDF file. Returns the output path."""
    from weasyprint import HTML, CSS as WCSS

    # Convert Markdown → HTML
    extensions = ["tables", "fenced_code", "codehilite", "toc", "nl2br"]
    html_body = markdown.markdown(md_content, extensions=extensions)

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"></head>
<body>
{html_body}
</body>
</html>"""

    # WeasyPrint needs a base_url to resolve relative paths like `assets/img.png`
    base_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(base_dir, exist_ok=True)
    
    HTML(string=full_html, base_url=base_dir).write_pdf(output_path, stylesheets=[WCSS(string=CSS)])
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_pdf.py <input.md> <output.pdf>")
        sys.exit(1)

    md_file, pdf_file = sys.argv[1], sys.argv[2]
    with open(md_file) as f:
        content = f.read()

    result = md_to_pdf(content, pdf_file)
    print(f"PDF generated: {result}")
