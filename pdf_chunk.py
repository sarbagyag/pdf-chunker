#!/usr/bin/env python3
"""
pdf_chunk.py — Extract a page range from a PDF and save it as a new file.

Usage:
    python pdf_chunk.py -i input.pdf -f 3 -t 7
    python pdf_chunk.py -i report.pdf -f 1 -t 5 -n chapter_one
    python pdf_chunk.py --input report.pdf --from-page 1 --to-page 5 --name intro

Strip images from the output:
    python pdf_chunk.py -i report.pdf -f 1 -t 5 --no-images
    # Figure labels and all text are kept; only embedded images are removed.
    # Install pymupdf for best results:  pip install pymupdf

Page-offset usage (when TOC page 1 ≠ PDF page 1):
    python pdf_chunk.py -i book.pdf -f 1 -t 10 --offset 31
    # TOC pages 1–10  →  actual PDF pages 32–41
"""

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------

# pypdf / PyPDF2  — always required
_pdf_generic_module: str | None = None

try:
    from pypdf import PdfReader, PdfWriter
    _pdf_generic_module = "pypdf"
except ImportError:
    try:
        from PyPDF2 import PdfReader, PdfWriter  # type: ignore[no-redef]
        _pdf_generic_module = "PyPDF2"
    except ImportError:
        print("Error: PDF library not found.")
        print("Install it with:  pip install pypdf")
        sys.exit(1)

# PyMuPDF (fitz) — optional; used for higher-quality image removal
_fitz_available = False
try:
    import fitz  # type: ignore[import]
    _fitz_available = True
except ImportError:
    pass


def _import_generic(name: str):
    """Import a class from whichever pypdf-compatible generic module is installed."""
    import importlib
    mod = importlib.import_module(f"{_pdf_generic_module}.generic")
    return getattr(mod, name)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

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

  # Strip all embedded images (Figure labels / text are kept):
  python pdf_chunk.py -i report.pdf -f 1 -t 5 --no-images
  python pdf_chunk.py -i book.pdf -f 10 -t 20 --no-images -n chapter_two

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
    parser.add_argument(
        "--no-images",
        action="store_true",
        dest="no_images",
        help=(
            "Strip all embedded images from the extracted pages. "
            "Figure labels, captions, and all other text are preserved. "
            "Install pymupdf for best results (pip install pymupdf); "
            "falls back to pypdf automatically."
        ),
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------

def build_output_path(
    input_path: Path,
    from_page: int,
    to_page: int,
    custom_name: str | None = None,
    out_dir: Path | None = None,
    no_images: bool = False,
) -> Path:
    suffix = input_path.suffix or ".pdf"
    base_dir = out_dir if out_dir else input_path.parent

    if custom_name:
        # Strip any accidental extension the user may have included
        stem = Path(custom_name).stem
        return base_dir / f"{stem}{suffix}"

    stem = input_path.stem
    tag = "_no_images" if no_images else ""
    return base_dir / f"{stem}_pages_{from_page}-{to_page}{tag}{suffix}"


# ---------------------------------------------------------------------------
# Image-stripping helpers (used only when --no-images is passed)
# ---------------------------------------------------------------------------

def _strip_images_from_page_pypdf(page, writer) -> int:
    """
    Remove image XObjects from *page*'s resources and strip the corresponding
    ``Do`` operators from its content stream.
    Returns the number of images removed.
    """
    NameObject = _import_generic("NameObject")

    # 1. Collect image XObject names and remove them from /Resources/XObject
    image_names: set[str] = set()
    try:
        res = page.get("/Resources")
        if res is None:
            return 0
        if hasattr(res, "get_object"):
            res = res.get_object()

        xobjs = res.get("/XObject")
        if xobjs is None:
            return 0
        if hasattr(xobjs, "get_object"):
            xobjs = xobjs.get_object()

        keys_to_del: list[str] = []
        for key in list(xobjs.keys()):
            obj = xobjs[key]
            if hasattr(obj, "get_object"):
                obj = obj.get_object()
            if obj.get("/Subtype") == "/Image":
                image_names.add(key.lstrip("/"))
                keys_to_del.append(key)

        for key in keys_to_del:
            del xobjs[key]

    except Exception:
        return 0

    if not image_names:
        return 0

    # 2. Strip Do operators that reference the removed images
    try:
        ContentStream = _import_generic("ContentStream")

        contents = page.get("/Contents")
        if contents is None:
            return len(image_names)

        content_obj = contents.get_object()
        cs = ContentStream(content_obj, writer)

        cs.operations = [
            (ops, op)
            for ops, op in cs.operations
            if not (
                op == b"Do"
                and ops
                and str(ops[0]).lstrip("/") in image_names
            )
        ]

        page[NameObject("/Contents")] = writer._add_object(cs)

    except Exception as exc:
        # Image data already removed from resources; orphaned Do stubs are
        # harmless — most renderers silently skip missing XObjects.
        print(
            f"  Warning: content stream rewrite failed ({exc}). "
            "Image data removed from resources; Do stubs may remain.",
            file=sys.stderr,
        )

    return len(image_names)


def _strip_images_fitz(input_path: Path, from_page: int, to_page: int,
                       output_path: Path) -> int:
    """
    Extract pages [from_page, to_page] and strip all images using PyMuPDF.
    Returns the total number of images removed.
    Raises on any error so the caller can fall back to pypdf.
    """
    src = fitz.open(str(input_path))
    dst = fitz.open()
    dst.insert_pdf(src, from_page=from_page - 1, to_page=to_page - 1)
    src.close()

    total_removed = 0
    for page in dst:
        imgs = page.get_images(full=True)
        if not imgs:
            continue
        for img in imgs:
            xref = img[0]
            try:
                rects = page.get_image_rects(xref, transform=False)
            except TypeError:
                rects = page.get_image_rects(xref)
            for rect in rects:
                # fill=(1,1,1) → white background where the image was
                # text=0       → PDF_REDACT_TEXT_NONE: never erase text
                # graphics=0   → keep vector art
                page.add_redact_annot(rect, fill=(1, 1, 1))
        page.apply_redactions(images=2, graphics=0, text=0)
        total_removed += len(imgs)

    # garbage=4 removes orphaned objects; deflate recompresses streams
    dst.save(str(output_path), garbage=4, deflate=True)
    dst.close()
    return total_removed


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def extract_pages(
    input_path: Path,
    from_page: int,
    to_page: int,
    output_path: Path,
    offset: int = 0,
    toc_from: int | None = None,
    toc_to: int | None = None,
    no_images: bool = False,
) -> None:
    """
    Extract pages [from_page, to_page] (1-based, actual PDF page numbers)
    and write them to output_path.

    When no_images=True every embedded image is removed; text (including
    Figure labels and captions) is always preserved.

    offset / toc_from / toc_to are used only for the success message.
    """
    reader = PdfReader(str(input_path))
    total_pages = len(reader.pages)

    # --- Validate range ----------------------------------------------------
    if from_page < 1:
        toc_msg = f" (TOC page {toc_from})" if toc_from is not None and offset else ""
        print(f"Error: --from-page must be ≥ 1 (got PDF page {from_page}{toc_msg}).")
        sys.exit(1)
    if to_page < from_page:
        print(f"Error: --to-page ({to_page}) must be ≥ --from-page ({from_page}).")
        sys.exit(1)
    if to_page > total_pages:
        toc_msg = f" (TOC page {toc_to})" if toc_to is not None and offset else ""
        print(
            f"Error: --to-page ({to_page}{toc_msg}) exceeds the document's "
            f"total page count ({total_pages})."
        )
        sys.exit(1)

    # --- Extract + optionally strip images ---------------------------------
    images_removed: int | None = None  # None → not stripping; int → count

    if no_images and _fitz_available:
        # PyMuPDF path: extract and strip in a single pass
        try:
            images_removed = _strip_images_fitz(
                input_path, from_page, to_page, output_path
            )
        except Exception as exc:
            print(
                f"  Warning: PyMuPDF stripping failed ({exc}), "
                "falling back to pypdf.",
                file=sys.stderr,
            )
            # Fall through to pypdf path below
            images_removed = None

    if images_removed is None:
        # pypdf path: extract pages, then optionally strip images
        writer = PdfWriter()
        for page_index in range(from_page - 1, to_page):
            writer.add_page(reader.pages[page_index])

        if no_images:
            images_removed = 0
            for idx in range(len(writer.pages)):
                images_removed += _strip_images_from_page_pypdf(
                    writer.pages[idx], writer
                )

        with open(output_path, "wb") as out_file:
            writer.write(out_file)

    # --- Success message ---------------------------------------------------
    extracted = to_page - from_page + 1

    if no_images:
        img_note = (
            f", {images_removed} image(s) removed"
            if images_removed
            else ", no images found"
        )
    else:
        img_note = ""

    if offset:
        print(
            f"✓ Extracted {extracted} page(s) "
            f"(TOC pages {toc_from}–{toc_to}  →  PDF pages {from_page}–{to_page} "
            f"of {total_pages}, offset +{offset}{img_note}) "
            f"→ {output_path}"
        )
    else:
        print(
            f"✓ Extracted {extracted} page(s) "
            f"(pages {from_page}–{to_page} of {total_pages}{img_note}) "
            f"→ {output_path}"
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

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
            input_path, toc_from, toc_to,
            custom_name=args.name,
            out_dir=out_dir,
            no_images=args.no_images,
        )

    extract_pages(
        input_path,
        pdf_from,
        pdf_to,
        output_path,
        offset=args.offset,
        toc_from=toc_from,
        toc_to=toc_to,
        no_images=args.no_images,
    )


if __name__ == "__main__":
    main()
