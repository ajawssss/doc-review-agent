"""
Local test: run Nathan Webb's review on a sample document without deploying.

Usage:
    python test_local.py                     # reviews the built-in sample memo
    python test_local.py path/to/your/doc.txt
"""

import sys
import os

# Make sure src/ is importable
sys.path.insert(0, os.path.dirname(__file__))

SAMPLE_MEMO = """
Project Titan: Expanding into Same-Day Grocery Delivery

Executive Summary
We believe there is a significant opportunity to leverage our existing logistics
infrastructure to substantially improve our grocery delivery offering. This initiative
will enhance customer satisfaction and drive revenue growth.

Background
Over the past several years, the grocery delivery market has seen substantial growth.
Many customers are interested in same-day delivery options. Our competitors have
various programs in this space and we need to respond to remain competitive.

Proposal
We propose to expand our same-day grocery delivery to 50 new cities by Q3. This
will require investment in temperature-controlled vehicles and warehouse improvements.
The team believes this will significantly improve our market position.

Financials
We estimate the investment will be around $200M. Returns should be positive within
18-24 months. The exact figures are still being finalized by the finance team.

Conclusion
Same-day grocery delivery is a large opportunity. We should move quickly to capture
market share before our competitors further entrench themselves. The team is excited
about this initiative and ready to execute.
"""


def main():
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"Reading document from: {file_path}\n")
        from src.agent import review_document_from_path
        review = review_document_from_path(file_path)
    else:
        print("No file provided — using built-in sample memo.\n")
        print("=" * 60)
        print("DOCUMENT SUBMITTED FOR REVIEW:")
        print("=" * 60)
        print(SAMPLE_MEMO)
        print("=" * 60 + "\n")

        from src.agent import review_document_from_text
        review = review_document_from_text(SAMPLE_MEMO, title="Project Titan Memo")

    print("\n" + "=" * 60)
    print("NATHAN WEBB'S REVIEW:")
    print("=" * 60)
    print(review)


if __name__ == "__main__":
    main()
