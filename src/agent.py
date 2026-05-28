import os
from strands import Agent
from strands.models import BedrockModel

from src.persona import NATHAN_WEBB_SYSTEM_PROMPT
from src.tools import read_document, analyze_document_structure, check_customer_obsession


def build_agent() -> Agent:
    """Construct and return the Nathan Webb doc-review agent."""
    model = BedrockModel(
        model_id=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20251001-v2:0"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        streaming=True,
        max_tokens=8192,
        temperature=0.3,   # precise, consistent — Nathan does not ramble
    )

    agent = Agent(
        model=model,
        system_prompt=NATHAN_WEBB_SYSTEM_PROMPT,
        tools=[read_document, analyze_document_structure, check_customer_obsession],
        load_tools_from_directory=False,
    )

    return agent


def review_document_from_path(file_path: str) -> str:
    """
    High-level helper: read a file and ask Nathan Webb to review it.
    Returns the full review as a string.
    """
    agent = build_agent()
    prompt = (
        f"Please review the document at this path: {file_path}\n\n"
        "Use your tools to read the document, analyze its structure, and check its customer focus. "
        "Then deliver your full Nathan Webb document review."
    )
    result = agent(prompt)
    return str(result)


def review_document_from_text(document_text: str, title: str = "Untitled Document") -> str:
    """
    High-level helper: review document text directly (no file needed).
    Returns the full review as a string.
    """
    agent = build_agent()
    prompt = (
        f"I am submitting a document titled '{title}' for your review.\n\n"
        f"Here is the full document text:\n\n"
        f"{'='*60}\n"
        f"{document_text}\n"
        f"{'='*60}\n\n"
        "Use your analyze_document_structure and check_customer_obsession tools on this text, "
        "then deliver your full Nathan Webb document review."
    )
    result = agent(prompt)
    return str(result)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.agent <path-to-document>")
        print("       python -m src.agent --text 'Your document text here'")
        sys.exit(1)

    if sys.argv[1] == "--text":
        text = " ".join(sys.argv[2:])
        print(review_document_from_text(text))
    else:
        print(review_document_from_path(sys.argv[1]))
