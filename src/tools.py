# -----------------------------------------------------------------------------
# What's in this file:
#   Three Strands tool functions that Nathan Webb's agent calls before writing
#   its review. Tools give the agent structured data to ground its critique:
#   (1) read_document — loads raw text from disk
#   (2) analyze_document_structure — produces word count, vague-word list,
#       bullet ratio, 6-pager compliance, and more as JSON
#   (3) check_customer_obsession — scans for customer-centric vs
#       company-centric language and returns a plain-text verdict
#
# Technologies used:
#   - Strands Agents SDK (@tool decorator) — registers each function as a
#     tool the LLM can invoke via tool-use (function calling)
#   - PyPDF2 — optional PDF text extraction
#   - python-docx — optional .docx text extraction
#   - Python stdlib: os, json
#
# Example of what this file does:
#   Agent receives a 400-word proposal. It calls analyze_document_structure,
#   which returns {"six_pager_standard": "TOO SHORT", "vague_word_count": 7,
#   "has_citations_or_sources": false}. Nathan then cites these exact numbers
#   in his "What's Not Working" section.
# -----------------------------------------------------------------------------

import os
import json
from typing import Any
from strands import tool


@tool
def read_document(file_path: str) -> str:
    """
    Read a document from the filesystem. Supports .txt, .md, .pdf, and .docx formats.

    Args:
        file_path: Absolute or relative path to the document to review.

    Returns:
        The full text content of the document.
    """
    if not os.path.exists(file_path):
        return f"ERROR: File not found at path: {file_path}"

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext in (".txt", ".md", ".rst"):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()

        elif ext == ".pdf":
            try:
                import PyPDF2
                with open(file_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    pages = [page.extract_text() for page in reader.pages]
                    return "\n\n".join(p for p in pages if p)
            except ImportError:
                return "ERROR: PyPDF2 is not installed. Run: pip install PyPDF2"

        elif ext == ".docx":
            try:
                from docx import Document
                doc = Document(file_path)
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                return "\n\n".join(paragraphs)
            except ImportError:
                return "ERROR: python-docx is not installed. Run: pip install python-docx"

        else:
            return f"ERROR: Unsupported file type '{ext}'. Supported: .txt, .md, .rst, .pdf, .docx"

    except Exception as e:
        return f"ERROR reading file: {str(e)}"


@tool
def analyze_document_structure(document_text: str) -> str:
    """
    Perform a structural analysis of a document: word count, section count,
    heading detection, bullet point ratio, and data citation presence.

    Args:
        document_text: The raw text of the document to analyze.

    Returns:
        A JSON string with structural metrics.
    """
    if not document_text or not document_text.strip():
        return json.dumps({"error": "Empty document provided"})

    lines = document_text.split("\n")
    words = document_text.split()
    sentences = [s.strip() for s in document_text.replace("!", ".").replace("?", ".").split(".") if s.strip()]

    headings = [l for l in lines if l.strip().startswith("#") or (len(l.strip()) > 0 and l.strip() == l.strip().upper() and len(l.strip()) > 3)]
    bullets = [l for l in lines if l.strip().startswith(("-", "*", "•", "·")) or (len(l.strip()) > 2 and l.strip()[0].isdigit() and l.strip()[1] in (".", ")"))]

    has_numbers = any(any(c.isdigit() for c in word) for word in words)
    has_percentages = "%" in document_text
    has_citations = any(marker in document_text for marker in ["[1]", "[2]", "Source:", "Reference:", "http", "www."])
    has_data_tables = "|" in document_text or "\t" in document_text

    avg_sentence_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)

    vague_words = ["significant", "substantial", "improved", "better", "large", "many", "some", "various", "several", "numerous", "enhance", "leverage", "synergy", "robust", "streamline"]
    vague_count = sum(document_text.lower().count(w) for w in vague_words)

    metrics = {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "line_count": len(lines),
        "heading_count": len(headings),
        "headings_detected": headings[:10],
        "bullet_point_lines": len(bullets),
        "bullet_ratio_pct": round(len(bullets) / max(len(lines), 1) * 100, 1),
        "avg_sentence_length_words": round(avg_sentence_len, 1),
        "has_numbers": has_numbers,
        "has_percentages": has_percentages,
        "has_citations_or_sources": has_citations,
        "has_data_tables": has_data_tables,
        "vague_word_count": vague_count,
        "vague_words_found": [w for w in vague_words if w in document_text.lower()],
        "estimated_read_time_minutes": round(len(words) / 238, 1),
        "six_pager_standard": "YES" if 800 <= len(words) <= 3000 else ("TOO SHORT" if len(words) < 800 else "TOO LONG"),
    }

    return json.dumps(metrics, indent=2)


@tool
def check_customer_obsession(document_text: str) -> str:
    """
    Scan a document for customer-centric language and identify gaps.
    Returns a report on how customer-focused the document is.

    Args:
        document_text: The raw text of the document to analyze.

    Returns:
        A plain text report on customer obsession signals found (or missing).
    """
    text_lower = document_text.lower()

    customer_signals = {
        "direct_customer_mentions": ["customer", "user", "client", "buyer", "consumer", "shopper"],
        "customer_problem_framing": ["pain point", "problem for", "struggle", "frustrated", "need", "want", "desire", "expect"],
        "customer_outcome_language": ["benefit", "value for", "saves time", "saves money", "reduces friction", "delights", "improves their"],
        "customer_voice": ["feedback", "survey", "interview", "research", "they said", "customers told us", "data shows"],
        "working_backwards": ["press release", "faq", "working backwards", "customer perspective", "from the customer"],
    }

    report_lines = ["=== CUSTOMER OBSESSION SCAN ===\n"]

    total_signals = 0
    for category, signals in customer_signals.items():
        found = [s for s in signals if s in text_lower]
        count = sum(text_lower.count(s) for s in found)
        total_signals += count
        status = "PRESENT" if found else "MISSING"
        label = category.replace("_", " ").title()
        report_lines.append(f"[{status}] {label}")
        if found:
            report_lines.append(f"         Signals found: {', '.join(found)} ({count} occurrences)")
        report_lines.append("")

    company_centric = ["we will", "our team", "the company", "our product", "we believe", "we think", "our goal", "our strategy", "our revenue", "our growth"]
    company_count = sum(text_lower.count(phrase) for phrase in company_centric)

    report_lines.append(f"Company-centric language occurrences: {company_count}")
    report_lines.append(f"Customer-centric signal occurrences:   {total_signals}")

    if total_signals == 0:
        report_lines.append("\nVERDICT: The document contains NO customer-centric language. This is a critical failure.")
    elif total_signals < 5:
        report_lines.append("\nVERDICT: Minimal customer focus. The customer is an afterthought, not the starting point.")
    elif company_count > total_signals * 2:
        report_lines.append("\nVERDICT: The document is more focused on the company than the customer. Reframe from the outside in.")
    else:
        report_lines.append("\nVERDICT: Reasonable customer focus detected. Nathan will probe for depth and specificity.")

    return "\n".join(report_lines)
