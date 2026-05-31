"""
Local test: run Jordan Blake's review on a sample document without deploying.

Usage:
    python test_local.py                     # reviews the built-in sample blog post
    python test_local.py path/to/your/doc.txt
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

# A deliberately mediocre AWS AI product blog post — buzzword-heavy,
# no CTA, wrong product name, company-centric framing.
SAMPLE_BLOG_POST = """
Revolutionizing AI with AWS: Our Next-Generation Approach

At Amazon Web Services, we are excited to announce our cutting-edge AI capabilities
that will revolutionize how enterprises leverage artificial intelligence. Our world-class
team has built a groundbreaking suite of tools that will transform your business.

AWS Tranium chips offer next-generation performance for AI training workloads. Our
state-of-the-art Nova AI models are now available, providing seamless integration
with your existing systems. We believe this represents a significant leap forward
in enterprise AI capabilities.

Our robust platform enables organizations to streamline their AI initiatives and
leverage synergies across their technology stack. The solution is scalable and
best-in-class, ensuring enterprise-grade reliability.

We have worked hard to build these capabilities and our team is proud of what we
have achieved. AWS Bedrock AI provides access to foundational models from leading
providers. We think customers will find this valuable.

The technology is very advanced and uses sophisticated algorithms to improve
outcomes substantially. Results will be enhanced significantly across various
use cases. Our goal is to be the industry leader in AI.
"""


def main():
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"Reading document from: {file_path}\n")
        from src.agent import review_document_from_path
        review = review_document_from_path(file_path)
    else:
        print("No file provided — using built-in sample blog post.\n")
        print("=" * 60)
        print("DOCUMENT SUBMITTED FOR REVIEW:")
        print("=" * 60)
        print(SAMPLE_BLOG_POST)
        print("=" * 60 + "\n")

        from src.agent import review_document_from_text
        review = review_document_from_text(SAMPLE_BLOG_POST, title="AWS AI Blog Post Draft")

    print("\n" + "=" * 60)
    print("JORDAN BLAKE'S REVIEW:")
    print("=" * 60)
    print(review)


if __name__ == "__main__":
    main()
