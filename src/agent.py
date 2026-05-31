import os
from strands import Agent
from strands.models import BedrockModel

from src.persona import JORDAN_BLAKE_SYSTEM_PROMPT
from src.tools import read_document, analyze_marketing_content, score_document


def build_agent() -> Agent:
    model = BedrockModel(
        model_id=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20251001-v2:0"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        streaming=True,
        max_tokens=8192,
        temperature=0.3,
    )

    return Agent(
        model=model,
        system_prompt=JORDAN_BLAKE_SYSTEM_PROMPT,
        tools=[read_document, analyze_marketing_content, score_document],
        load_tools_from_directory=False,
    )


def review_document_from_path(file_path: str) -> str:
    agent = build_agent()
    prompt = (
        f"Please review the marketing document at this path: {file_path}\n\n"
        "Use your tools to read the document, analyze its marketing content, and score it. "
        "Then deliver your full Jordan Blake review."
    )
    return str(agent(prompt))


def review_document_from_text(document_text: str, title: str = "Untitled Document") -> str:
    agent = build_agent()
    prompt = (
        f"I am submitting a document titled '{title}' for your review.\n\n"
        f"Here is the full document text:\n\n"
        f"{'='*60}\n"
        f"{document_text}\n"
        f"{'='*60}\n\n"
        "Use your analyze_marketing_content and score_document tools on this text, "
        "then deliver your full Jordan Blake marketing review."
    )
    return str(agent(prompt))


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
