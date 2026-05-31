import os
import json
import re
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
def analyze_marketing_content(document_text: str) -> str:
    """
    Analyze a marketing document for AWS AI product accuracy, brand voice signals,
    CTA presence, buzzword overuse, and audience clarity.

    Args:
        document_text: The raw text of the document to analyze.

    Returns:
        A JSON string with marketing-specific metrics and flags.
    """
    if not document_text or not document_text.strip():
        return json.dumps({"error": "Empty document provided"})

    text = document_text
    text_lower = text.lower()
    words = text.split()

    # --- Product name accuracy checks ---
    correct_names = [
        "Amazon Bedrock", "Amazon Nova", "Nova Micro", "Nova Lite", "Nova Pro", "Nova Premier",
        "AWS Trainium", "AWS Inferentia", "Amazon AgentCore", "Amazon Q", "Amazon Q Business",
        "Amazon Q Developer", "AWS SageMaker", "Amazon SageMaker",
    ]
    wrong_names = {
        "tranium": "AWS Trainium",
        "nova ai": "Amazon Nova",
        "aws nova": "Amazon Nova",
        "bedrock ai": "Amazon Bedrock",
        "agent core": "AgentCore",
        "inferencia": "AWS Inferentia",
        "q developer ai": "Amazon Q Developer",
    }
    correct_names_found = [n for n in correct_names if n in text]
    wrong_names_found = {k: v for k, v in wrong_names.items() if k in text_lower}

    # --- Buzzword / vague language audit ---
    buzzwords = [
        "ai-powered", "next-generation", "next gen", "cutting-edge", "state-of-the-art",
        "revolutionary", "game-changing", "groundbreaking", "transformative", "seamless",
        "robust", "leverage", "synergy", "streamline", "scalable solution", "best-in-class",
        "world-class", "industry-leading",
    ]
    buzzwords_found = [b for b in buzzwords if b in text_lower]

    # --- Audience signals ---
    technical_signals = ["api", "sdk", "inference", "training", "model weights", "tokens", "latency",
                         "throughput", "fine-tuning", "embedding", "rag", "retrieval", "endpoint"]
    business_signals = ["roi", "cost savings", "productivity", "revenue", "compliance", "enterprise",
                        "workforce", "business outcome", "time to market"]
    technical_count = sum(1 for s in technical_signals if s in text_lower)
    business_count = sum(1 for s in business_signals if s in text_lower)

    if technical_count > business_count + 3:
        audience_lean = "technical (developer/ML practitioner)"
    elif business_count > technical_count + 3:
        audience_lean = "business (executive/buyer)"
    else:
        audience_lean = "mixed — may need tightening for a single persona"

    # --- Customer benefit framing ---
    customer_benefit_signals = ["you can", "your team", "helps you", "so you", "customers can",
                                "enabling", "so that", "allowing you", "giving you", "save time",
                                "reduce cost", "increase", "faster"]
    customer_benefit_count = sum(text_lower.count(s) for s in customer_benefit_signals)

    # --- CTA detection ---
    cta_patterns = [
        r"get started", r"start building", r"try .{1,20} free", r"sign up", r"learn more",
        r"contact us", r"talk to an expert", r"request a demo", r"explore", r"visit aws\.amazon\.com",
        r"aws\.amazon\.com/", r"console\.aws",
    ]
    ctas_found = [p for p in cta_patterns if re.search(p, text_lower)]

    # --- Passive voice quick-check ---
    passive_patterns = [r"\bwill be \w+ed\b", r"\bcan be \w+ed\b", r"\bare \w+ed\b", r"\bwas \w+ed\b"]
    passive_count = sum(len(re.findall(p, text_lower)) for p in passive_patterns)

    # --- Structure ---
    lines = text.split("\n")
    headings = [l.strip() for l in lines if l.strip().startswith("#") or
                (len(l.strip()) > 3 and l.strip() == l.strip().upper() and len(l.strip()) < 80)]
    word_count = len(words)

    metrics = {
        "word_count": word_count,
        "correct_aws_product_names_found": correct_names_found,
        "incorrect_product_names_found": wrong_names_found,
        "buzzwords_found": buzzwords_found,
        "buzzword_count": len(buzzwords_found),
        "audience_lean": audience_lean,
        "technical_signal_count": technical_count,
        "business_signal_count": business_count,
        "customer_benefit_phrases": customer_benefit_count,
        "ctas_detected": ctas_found,
        "has_cta": len(ctas_found) > 0,
        "passive_voice_instances": passive_count,
        "heading_count": len(headings),
        "headings": headings[:8],
        "estimated_read_time_minutes": round(word_count / 238, 1),
    }

    return json.dumps(metrics, indent=2)


@tool
def score_document(document_text: str) -> str:
    """
    Produce a structured 100-point marketing quality score for an AWS AI product
    document across five dimensions: brand voice, customer focus, messaging clarity,
    differentiation, and call to action.

    Args:
        document_text: The raw text of the document to score.

    Returns:
        A JSON string with per-dimension scores, deductions, and a total score.
    """
    if not document_text or not document_text.strip():
        return json.dumps({"error": "Empty document provided"})

    text_lower = document_text.lower()
    words = document_text.split()

    # --- Dimension 1: Brand Voice & Accuracy (0-20) ---
    brand_score = 20
    brand_notes = []

    wrong_names = ["tranium", "nova ai", "aws nova", "bedrock ai", "agent core"]
    for w in wrong_names:
        if w in text_lower:
            brand_score -= 5
            brand_notes.append(f"Wrong product name '{w}' found (-5)")

    buzzwords = ["ai-powered", "next-generation", "cutting-edge", "revolutionary",
                 "game-changing", "groundbreaking", "seamless", "world-class"]
    buzz_hits = [b for b in buzzwords if b in text_lower]
    if len(buzz_hits) >= 3:
        brand_score -= 4
        brand_notes.append(f"{len(buzz_hits)} unsubstantiated superlatives ({', '.join(buzz_hits[:3])}) (-4)")
    elif len(buzz_hits) == 2:
        brand_score -= 2
        brand_notes.append(f"2 unsubstantiated superlatives ({', '.join(buzz_hits)}) (-2)")

    passive_count = len(re.findall(r"\bwill be \w+ed\b|\bcan be \w+ed\b", text_lower))
    if passive_count >= 4:
        brand_score -= 3
        brand_notes.append(f"Heavy passive voice ({passive_count} instances) (-3)")
    elif passive_count >= 2:
        brand_score -= 1
        brand_notes.append(f"Some passive voice ({passive_count} instances) (-1)")

    brand_score = max(0, brand_score)

    # --- Dimension 2: Customer Focus (0-20) ---
    customer_score = 20
    customer_notes = []

    customer_signals = ["you ", "your ", "customer", "user", "developer", "team",
                        "helps you", "so you", "so that", "allowing", "enabling"]
    customer_hits = sum(text_lower.count(s) for s in customer_signals)

    company_signals = ["we will", "our product", "we believe", "our team", "we are",
                       "our goal", "aws is", "amazon is", "we have built"]
    company_hits = sum(text_lower.count(s) for s in company_signals)

    if customer_hits == 0:
        customer_score -= 10
        customer_notes.append("No customer-facing language detected (-10)")
    elif customer_hits < 3:
        customer_score -= 6
        customer_notes.append("Minimal customer-facing language (-6)")
    elif company_hits > customer_hits * 2:
        customer_score -= 5
        customer_notes.append("Company-centric language outweighs customer-centric (-5)")

    # No named audience
    audience_words = ["developer", "data scientist", "ml engineer", "cto", "cio",
                      "enterprise", "startup", "line of business", "builder"]
    if not any(a in text_lower for a in audience_words):
        customer_score -= 4
        customer_notes.append("No explicit target audience named (-4)")

    customer_score = max(0, customer_score)

    # --- Dimension 3: Messaging Clarity (0-20) ---
    clarity_score = 20
    clarity_notes = []

    if len(words) > 1500:
        clarity_score -= 3
        clarity_notes.append(f"Long content ({len(words)} words) — check if scannable (-3)")

    lines = document_text.split("\n")
    headings = [l for l in lines if l.strip().startswith("#") or
                (len(l.strip()) > 3 and l.strip() == l.strip().upper() and len(l.strip()) < 80)]
    if len(words) > 300 and len(headings) == 0:
        clarity_score -= 4
        clarity_notes.append("No headings or sections detected — hard to scan (-4)")

    jargon = ["paradigm", "holistic", "synergize", "operationalize", "ideate",
              "productize", "frictionless", "end-to-end solution"]
    jargon_hits = [j for j in jargon if j in text_lower]
    if jargon_hits:
        clarity_score -= 2 * len(jargon_hits)
        clarity_notes.append(f"Jargon detected: {', '.join(jargon_hits)} (-{2*len(jargon_hits)})")

    clarity_score = max(0, clarity_score)

    # --- Dimension 4: Differentiation (0-20) ---
    diff_score = 20
    diff_notes = []

    diff_signals = ["only aws", "only amazon", "unlike", "compared to", "vs ", "versus",
                    "percent", "%", "faster", "cheaper", "lower cost", "better than",
                    "benchmark", "study shows", "customers report"]
    diff_hits = sum(1 for s in diff_signals if s in text_lower)

    if diff_hits == 0:
        diff_score -= 12
        diff_notes.append("No concrete differentiation claims or data points (-12)")
    elif diff_hits <= 2:
        diff_score -= 6
        diff_notes.append("Weak differentiation — only 1-2 concrete signals (-6)")

    diff_score = max(0, diff_score)

    # --- Dimension 5: Call to Action (0-20) ---
    cta_score = 20
    cta_notes = []

    cta_patterns = [
        r"get started", r"start building", r"try .{1,20} free", r"sign up",
        r"learn more", r"contact us", r"talk to an expert", r"request a demo",
        r"explore", r"aws\.amazon\.com", r"console\.aws",
    ]
    ctas = [p for p in cta_patterns if re.search(p, text_lower)]

    if not ctas:
        cta_score -= 15
        cta_notes.append("No call to action found (-15)")
    elif len(ctas) == 1:
        cta_score -= 3
        cta_notes.append("Only one CTA — consider adding a secondary next step (-3)")

    cta_score = max(0, cta_score)

    # --- Total ---
    total = brand_score + customer_score + clarity_score + diff_score + cta_score

    if total >= 90:
        grade = "A"
    elif total >= 80:
        grade = "B"
    elif total >= 70:
        grade = "C"
    elif total >= 60:
        grade = "D"
    else:
        grade = "F"

    result = {
        "scores": {
            "brand_voice_and_accuracy": {"score": brand_score, "max": 20, "notes": brand_notes},
            "customer_focus": {"score": customer_score, "max": 20, "notes": customer_notes},
            "messaging_clarity": {"score": clarity_score, "max": 20, "notes": clarity_notes},
            "differentiation": {"score": diff_score, "max": 20, "notes": diff_notes},
            "call_to_action": {"score": cta_score, "max": 20, "notes": cta_notes},
        },
        "total_score": total,
        "grade": grade,
        "word_count": len(words),
    }

    return json.dumps(result, indent=2)
