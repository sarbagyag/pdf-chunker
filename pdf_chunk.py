#!/usr/bin/env python3
"""
pdf_chunk.py — Extract a page range from a PDF and save it as a new file.

Usage:
    python pdf_chunk.py -i input.pdf -f 3 -t 7
    python pdf_chunk.py -i report.pdf -f 1 -t 5 -n chapter_one
    python pdf_chunk.py --input report.pdf --from-page 1 --to-page 5 --name intro

Page-offset usage (when TOC page 1 ≠ PDF page 1):
    python pdf_chunk.py -i book.pdf -f 1 -t 10 --offset 31
    # TOC pages 1–10  →  actual PDF pages 32–41
"""

import argparse
import sys
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    try:
        from PyPDF2 import PdfReader, PdfWriter
    except ImportError:
        print("Error: PDF library not found.")
        print("Install it with:  pip install pypdf")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract a page range from a PDF file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pdf_chunk.py -i report.pdf -f 1 -t 5
  python pdf_chunk.py -i report.pdf -f 10 -t 20 -n chapter_two
  python pdf_chunk.py -i report.pdf -f 10 -t 20 -o /tmp/section.pdf
  python pdf_chunk.py --input report.pdf --from-page 3 --to-page 3   # single page

  # When the TOC starts at 1 but the PDF starts at page 32:
  python pdf_chunk.py -i book.pdf -f 1 -t 10 --offset 31
  python pdf_chunk.py -i book.pdf -f 45 -t 60 --offset 31 -n chapter_three
        """,
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        metavar="FILE",
        help="Path to the source PDF file",
    )
    parser.add_argument(
        "-f", "--from-page",
        required=True,
        type=int,
        metavar="N",
        dest="from_page",
        help="First page to extract (1-based, inclusive)",
    )
    parser.add_argument(
        "-t", "--to-page",
        required=True,
        type=int,
        metavar="N",
        dest="to_page",
        help="Last page to extract (1-based, inclusive)",
    )
    parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        help=(
            "Full path for the output PDF "
            "(default: <input>_pages_<from>-<to>.pdf)"
        ),
    )
    parser.add_argument(
        "-n", "--name",
        metavar="NAME",
        help=(
            "Custom filename stem (no extension) for the output PDF. "
            "Example: -n chapter_one → chapter_one.pdf. "
            "Ignored if --output is also given."
        ),
    )
    parser.add_argument(
        "-d", "--dir",
        metavar="DIR",
        help=(
            "Output directory to save the PDF in. "
            "Created automatically if it does not exist. "
            "Combined with --name if provided, otherwise uses the auto-name. "
            "Ignored if --output is also given."
        ),
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Page offset to add to --from-page and --to-page. "
            "Use this when the PDF's physical pages don't match the table-of-contents "
            "numbering. For example, if TOC page 1 is actually PDF page 32, pass "
            "--offset 31 and then supply TOC page numbers with -f/-t as usual. "
            "The output filename uses your TOC numbers; the success message shows both."
        ),
    )

    return parser.parse_args()


def build_output_path(
    input_path: Path,
    from_page: int,
    to_page: int,
    custom_name: str | None = None,
    out_dir: Path | None = None,
) -> Path:
    suffix = input_path.suffix or ".pdf"
    base_dir = out_dir if out_dir else input_path.parent

    if custom_name:
        # Strip any accidental extension the user may have included
        stem = Path(custom_name).stem
        return base_dir / f"{stem}{suffix}"

    stem = input_path.stem
    return base_dir / f"{stem}_pages_{from_page}-{to_page}{suffix}"


def extract_pages(
    input_path: Path,
    from_page: int,
    to_page: int,
    output_path: Path,
    offset: int = 0,
    toc_from: int | None = None,
    toc_to: int | None = None,
) -> None:
    """
    Extract pages [from_page, to_page] (1-based, actual PDF page numbers).

    offset / toc_from / toc_to are only used for display purposes so the
    success message can show the user the TOC numbers they originally gave.
    """
    reader = PdfReader(str(input_path))
    total_pages = len(reader.pages)

    # Validate range against the actual document
    if from_page < 1:
        toc_msg = f" (TOC page {toc_from})" if toc_from is not None and offset else ""
        print(f"Error: --from-page must be ≥ 1 (got PDF page {from_page}{toc_msg}).")
        sys.exit(1)
    if to_page < from_page:
        print(
            f"Error: --to-page ({to_page}) must be ≥ --from-page ({from_page})."
        )
        sys.exit(1)
    if to_page > total_pages:
        toc_msg = f" (TOC page {toc_to})" if toc_to is not None and offset else ""
        print(
            f"Error: --to-page ({to_page}{toc_msg}) exceeds the document's "
            f"total page count ({total_pages})."
        )
        sys.exit(1)

    writer = PdfWriter()

    # pypdf uses 0-based indices internally
    for page_index in range(from_page - 1, to_page):
        writer.add_page(reader.pages[page_index])

    with open(output_path, "wb") as out_file:
        writer.write(out_file)

    extracted = to_page - from_page + 1

    if offset:
        print(
            f"✓ Extracted {extracted} page(s) "
            f"(TOC pages {toc_from}–{toc_to}  →  PDF pages {from_page}–{to_page} "
            f"of {total_pages}, offset +{offset}) "
            f"→ {output_path}"
        )
    else:
        print(
            f"✓ Extracted {extracted} page(s) "
            f"(pages {from_page}–{to_page} of {total_pages}) "
            f"→ {output_path}"
        )


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)
    if not input_path.is_file():
        print(f"Error: Not a file: {input_path}")
        sys.exit(1)

    # TOC page numbers as the user entered them (before offset is applied)
    toc_from = args.from_page
    toc_to   = args.to_page

    # Actual PDF page numbers after adding the offset
    pdf_from = args.from_page + args.offset
    pdf_to   = args.to_page   + args.offset

    if args.output:
        output_path = Path(args.output)
    else:
        out_dir = Path(args.dir) if args.dir else None
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)
        # Use TOC page numbers in the filename so it matches the book's numbering
        output_path = build_output_path(
            input_path, toc_from, toc_to, args.name, out_dir
        )

    extract_pages(
        input_path,
        pdf_from,
        pdf_to,
        output_path,
        offset=args.offset,
        toc_from=toc_from,
        toc_to=toc_to,
    )


if __name__ == "__main__":
    main()
