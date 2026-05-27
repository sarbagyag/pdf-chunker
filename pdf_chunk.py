#!/usr/bin/env python3
"""
pdf_chunk.py — Extract a page range from a PDF and save it as a new file.

Usage:
    python pdf_chunk.py -i input.pdf -f 3 -t 7
    python pdf_chunk.py -i report.pdf -f 1 -t 5 -n chapter_one
    python pdf_chunk.py --input report.pdf --from-page 1 --to-page 5 --name intro

Compress images to reduce file size (requires pymupdf):
    python pdf_chunk.py -i report.pdf -f 1 -t 5 --compress
    python pdf_chunk.py -i report.pdf -f 1 -t 5 --compress --quality 40
    python pdf_chunk.py -i report.pdf -f 1 -t 5 --compress --quality 20 --dpi 100
    # --quality: 1-100 (default 50). Lower = smaller file, worse image quality.
    # --dpi:     target DPI for downsampling (default 150). Lower = more aggressive.

Strip images entirely:
    python pdf_chunk.py -i report.pdf -f 1 -t 5 --no-images

Page-offset usage (when TOC page 1 != PDF page 1):
    python pdf_chunk.py -i book.pdf -f 1 -t 10 --offset 31
"""

import argparse
import io
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------

_pdf_generic_module = None

try:
    from pypdf import PdfReader, PdfWriter
    _pdf_generic_module = "pypdf"
except ImportError:
    try:
        from PyPDF2 import PdfReader, PdfWriter
        _pdf_generic_module = "PyPDF2"
    except ImportError:
        print("Error: PDF library not found.")
        print("Install it with:  pip install pypdf")
        sys.exit(1)

_fitz_available = False
try:
    import fitz
    _fitz_available = True
except ImportError:
    pass


def _import_generic(name):
    import importlib
    mod = importlib.import_module(f"{_pdf_generic_module}.generic")
    return getattr(mod, name)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract a page range from a PDF file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pdf_chunk.py -i report.pdf -f 1 -t 5
  python pdf_chunk.py -i report.pdf -f 10 -t 20 -n chapter_two

  # Compress images to reduce file size (requires pymupdf):
  python pdf_chunk.py -i report.pdf -f 1 -t 5 --compress
  python pdf_chunk.py -i report.pdf -f 1 -t 5 --compress --quality 40
  python pdf_chunk.py -i report.pdf -f 1 -t 5 --compress --quality 20 --dpi 100
  python pdf_chunk.py -i report.pdf -f 1 -t 5 --compress --quality 30 -n chapter_small

  # Strip images entirely:
  python pdf_chunk.py -i report.pdf -f 1 -t 5 --no-images

  # Page offset (TOC page 1 = PDF page 32):
  python pdf_chunk.py -i book.pdf -f 1 -t 10 --offset 31
        """,
    )

    parser.add_argument("-i", "--input", required=True, metavar="FILE",
                        help="Path to the source PDF file")
    parser.add_argument("-f", "--from-page", required=True, type=int,
                        metavar="N", dest="from_page",
                        help="First page to extract (1-based, inclusive)")
    parser.add_argument("-t", "--to-page", required=True, type=int,
                        metavar="N", dest="to_page",
                        help="Last page to extract (1-based, inclusive)")
    parser.add_argument("-o", "--output", metavar="FILE",
                        help="Full path for the output PDF")
    parser.add_argument("-n", "--name", metavar="NAME",
                        help="Custom filename stem (no extension)")
    parser.add_argument("-d", "--dir", metavar="DIR",
                        help="Output directory (created if missing)")
    parser.add_argument("--offset", type=int, default=0, metavar="N",
                        help="Page offset added to --from-page and --to-page")
    parser.add_argument("--no-images", action="store_true", dest="no_images",
                        help="Strip all embedded images from extracted pages")

    parser.add_argument(
        "--compress", action="store_true",
        help=(
            "Re-compress all embedded images at reduced quality to shrink file size. "
            "Requires pymupdf (pip install pymupdf). "
            "Control aggressiveness with --quality and --dpi."
        ),
    )
    parser.add_argument(
        "--quality", type=int, default=50, metavar="1-100",
        help=(
            "JPEG quality for recompressed images (default: 50). "
            "Lower = smaller file, worse quality. "
            "Typical useful range: 20-60. Only used with --compress."
        ),
    )
    parser.add_argument(
        "--dpi", type=int, default=150, metavar="DPI",
        help=(
            "Target DPI when downsampling high-resolution images (default: 150). "
            "Images already below this DPI are not upscaled. "
            "Use 100-120 for aggressive size reduction, 150-200 for readable diagrams. "
            "Only used with --compress."
        ),
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------

def build_output_path(input_path, from_page, to_page,
                      custom_name=None, out_dir=None, suffix_tag=""):
    ext = input_path.suffix or ".pdf"
    base_dir = out_dir if out_dir else input_path.parent

    if custom_name:
        stem = Path(custom_name).stem
        return base_dir / f"{stem}{ext}"

    stem = input_path.stem
    tag = f"_{suffix_tag}" if suffix_tag else ""
    return base_dir / f"{stem}_pages_{from_page}-{to_page}{tag}{ext}"


# ---------------------------------------------------------------------------
# Image-stripping helpers  (--no-images)
# ---------------------------------------------------------------------------

def _strip_images_from_page_pypdf(page, writer):
    NameObject = _import_generic("NameObject")
    image_names = set()
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
        keys_to_del = []
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

    try:
        ContentStream = _import_generic("ContentStream")
        contents = page.get("/Contents")
        if contents is None:
            return len(image_names)
        content_obj = contents.get_object()
        cs = ContentStream(content_obj, writer)
        cs.operations = [
            (ops, op) for ops, op in cs.operations
            if not (op == b"Do" and ops and str(ops[0]).lstrip("/") in image_names)
        ]
        page[NameObject("/Contents")] = writer._add_object(cs)
    except Exception as exc:
        print(f"  Warning: content stream rewrite failed ({exc}).", file=sys.stderr)

    return len(image_names)


def _strip_images_fitz(input_path, from_page, to_page, output_path):
    """
    Extract pages and truly remove all images from the output so they are
    not counted against Claude's per-conversation image budget.

    Strategy: zero the image stream AND change /Subtype from /Image to /Form
    with a 1x1 BBox. This makes the xref invisible to image-counting code
    while keeping the PDF structurally valid. garbage=4 + clean=True on save
    purges orphaned objects and normalises the file.
    """
    src = fitz.open(str(input_path))
    dst = fitz.open()
    dst.insert_pdf(src, from_page=from_page - 1, to_page=to_page - 1)
    src.close()

    total_removed = 0
    seen_xrefs = set()

    for page in dst:
        for img in page.get_images(full=True):
            xref = img[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            try:
                dst.update_stream(xref, b"")
                dst.xref_set_key(xref, "Subtype", "/Form")
                dst.xref_set_key(xref, "BBox", "[0 0 1 1]")
                total_removed += 1
            except Exception:
                pass

    dst.save(str(output_path), garbage=4, deflate=True, clean=True)
    dst.close()
    return total_removed


# ---------------------------------------------------------------------------
# Image-compression helper  (--compress, requires fitz)
# ---------------------------------------------------------------------------

def _compress_images_fitz(input_path, from_page, to_page, output_path,
                           quality=50, target_dpi=150):
    """
    Extract pages and re-compress every embedded image as JPEG at *quality*.
    Images whose effective DPI exceeds *target_dpi* are downsampled first.

    Returns (images_processed, original_bytes, compressed_bytes).
    """
    try:
        from PIL import Image as PILImage
        pil_available = True
    except ImportError:
        pil_available = False

    src = fitz.open(str(input_path))
    dst = fitz.open()
    dst.insert_pdf(src, from_page=from_page - 1, to_page=to_page - 1)
    src.close()

    images_processed = 0
    original_bytes = 0
    compressed_bytes = 0

    for page in dst:
        imgs = page.get_images(full=True)
        for img_info in imgs:
            xref = img_info[0]
            try:
                base_img = dst.extract_image(xref)
            except Exception:
                continue

            img_bytes = base_img["image"]
            original_bytes += len(img_bytes)
            colorspace = base_img.get("colorspace", 3)
            width = base_img.get("width", 0)
            height = base_img.get("height", 0)

            # Compute effective DPI from the image's display rect on the page
            try:
                rects = page.get_image_rects(xref, transform=False)
                if rects:
                    r = rects[0]
                    display_w_pts = abs(r.x1 - r.x0)
                    display_h_pts = abs(r.y1 - r.y0)
                    dpi_x = width  / (display_w_pts / 72) if display_w_pts > 0 else 0
                    dpi_y = height / (display_h_pts / 72) if display_h_pts > 0 else 0
                    effective_dpi = max(dpi_x, dpi_y)
                else:
                    effective_dpi = 999
            except Exception:
                effective_dpi = 999

            needs_downsample = effective_dpi > target_dpi and (width > 0 and height > 0)

            new_bytes = None

            if pil_available:
                try:
                    pil_img = PILImage.open(io.BytesIO(img_bytes))
                    if pil_img.mode not in ("RGB", "L"):
                        pil_img = pil_img.convert("RGB")

                    if needs_downsample:
                        scale = target_dpi / effective_dpi
                        new_w = max(1, int(width * scale))
                        new_h = max(1, int(height * scale))
                        pil_img = pil_img.resize((new_w, new_h), PILImage.LANCZOS)

                    buf = io.BytesIO()
                    pil_img.save(buf, format="JPEG", quality=quality, optimize=True)
                    new_bytes = buf.getvalue()
                except Exception:
                    new_bytes = None

            if new_bytes is None:
                # fitz-only fallback
                try:
                    if needs_downsample:
                        scale = target_dpi / effective_dpi
                        new_w = max(1, int(width * scale))
                        new_h = max(1, int(height * scale))
                        pix = fitz.Pixmap(img_bytes)
                        pix = pix.scale(new_w, new_h)
                    else:
                        pix = fitz.Pixmap(img_bytes)

                    if pix.n > 3:
                        pix = fitz.Pixmap(fitz.csRGB, pix)

                    new_bytes = pix.tobytes("jpeg", jpg_quality=quality)
                except Exception:
                    compressed_bytes += len(img_bytes)
                    continue

            compressed_bytes += len(new_bytes)
            images_processed += 1

            try:
                dst.update_stream(xref, new_bytes, new_dict={
                    "/Filter": "/DCTDecode",
                    "/ColorSpace": "/DeviceRGB" if colorspace == 3 else "/DeviceGray",
                })
            except Exception:
                pass

    dst.save(str(output_path), garbage=4, deflate=True)
    dst.close()
    return images_processed, original_bytes, compressed_bytes


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def extract_pages(input_path, from_page, to_page, output_path,
                  offset=0, toc_from=None, toc_to=None,
                  no_images=False, compress=False, quality=50, target_dpi=150):

    reader = PdfReader(str(input_path))
    total_pages = len(reader.pages)

    if from_page < 1:
        toc_msg = f" (TOC page {toc_from})" if toc_from is not None and offset else ""
        print(f"Error: --from-page must be >= 1 (got PDF page {from_page}{toc_msg}).")
        sys.exit(1)
    if to_page < from_page:
        print(f"Error: --to-page ({to_page}) must be >= --from-page ({from_page}).")
        sys.exit(1)
    if to_page > total_pages:
        toc_msg = f" (TOC page {toc_to})" if toc_to is not None and offset else ""
        print(f"Error: --to-page ({to_page}{toc_msg}) exceeds total page count ({total_pages}).")
        sys.exit(1)

    images_removed = None
    compress_stats = None

    # ---- --compress -------------------------------------------------------
    if compress:
        if not _fitz_available:
            print("Error: --compress requires pymupdf. Install with:  pip install pymupdf")
            sys.exit(1)
        try:
            compress_stats = _compress_images_fitz(
                input_path, from_page, to_page, output_path,
                quality=quality, target_dpi=target_dpi,
            )
        except Exception as exc:
            print(f"Error during compression: {exc}", file=sys.stderr)
            sys.exit(1)

    # ---- --no-images ------------------------------------------------------
    elif no_images:
        if _fitz_available:
            try:
                images_removed = _strip_images_fitz(
                    input_path, from_page, to_page, output_path
                )
            except Exception as exc:
                print(f"  Warning: PyMuPDF stripping failed ({exc}), falling back to pypdf.",
                      file=sys.stderr)
                images_removed = None

        if images_removed is None:
            writer = PdfWriter()
            for i in range(from_page - 1, to_page):
                writer.add_page(reader.pages[i])
            images_removed = 0
            for idx in range(len(writer.pages)):
                images_removed += _strip_images_from_page_pypdf(writer.pages[idx], writer)
            with open(output_path, "wb") as f:
                writer.write(f)

    # ---- plain extraction -------------------------------------------------
    else:
        writer = PdfWriter()
        for i in range(from_page - 1, to_page):
            writer.add_page(reader.pages[i])
        with open(output_path, "wb") as f:
            writer.write(f)

    # ---- success message --------------------------------------------------
    extracted = to_page - from_page + 1
    out_size_mb = output_path.stat().st_size / 1_048_576

    if compress_stats is not None:
        n_imgs, orig_b, comp_b = compress_stats
        saved_pct = (1 - comp_b / orig_b) * 100 if orig_b > 0 else 0
        extra = (
            f", {n_imgs} image(s) recompressed "
            f"({orig_b / 1_048_576:.1f} MB -> {comp_b / 1_048_576:.1f} MB image data, "
            f"{saved_pct:.0f}% saved)"
        )
    elif no_images:
        extra = f", {images_removed} image(s) removed" if images_removed else ", no images found"
    else:
        extra = ""

    loc = f"TOC pages {toc_from}-{toc_to}  ->  PDF pages" if offset else "pages"
    print(
        f"Extracted {extracted} page(s) "
        f"({loc} {from_page}-{to_page} of {total_pages}{extra}) "
        f"-> {output_path}  [{out_size_mb:.2f} MB]"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    if args.compress and args.no_images:
        print("Error: --compress and --no-images are mutually exclusive.")
        sys.exit(1)

    if not 1 <= args.quality <= 100:
        print(f"Error: --quality must be between 1 and 100 (got {args.quality}).")
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    toc_from = args.from_page
    toc_to   = args.to_page
    pdf_from = args.from_page + args.offset
    pdf_to   = args.to_page   + args.offset

    if args.output:
        output_path = Path(args.output)
    else:
        out_dir = Path(args.dir) if args.dir else None
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)

        if args.compress:
            tag = f"q{args.quality}"
        elif args.no_images:
            tag = "no_images"
        else:
            tag = ""

        output_path = build_output_path(
            input_path, toc_from, toc_to,
            custom_name=args.name,
            out_dir=out_dir,
            suffix_tag=tag,
        )

    extract_pages(
        input_path, pdf_from, pdf_to, output_path,
        offset=args.offset,
        toc_from=toc_from,
        toc_to=toc_to,
        no_images=args.no_images,
        compress=args.compress,
        quality=args.quality,
        target_dpi=args.dpi,
    )


if __name__ == "__main__":
    main()
