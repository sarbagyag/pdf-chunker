# pdf_chunk

A command-line tool to extract a range of pages from a PDF and save them as a new file.
Supports image compression (`--compress`) to hit a target file size, image stripping (`--no-images`), and page-offset handling for books where TOC page numbers don't match physical PDF pages.

---

## Quick Start

The full-featured command — covers every common case:

```bash
python3 pdf_chunk.py -i STM32.pdf -f 10 -t 20 -d stm32-chunks -n chapter-one-chunk --offset 31
```

| Part | What it does |
| ---- | ------------ |
| `-i STM32.pdf` | Source PDF to extract from |
| `-f 10 -t 20` | **TOC page numbers** — the printed page numbers you read in the Table of Contents |
| `--offset 31` | The front matter (cover, TOC, preface…) takes up 31 pages, so TOC page 10 is actually physical PDF page 41. The tool adds the offset for you |
| `-d stm32-chunks` | Save the output into this folder (created automatically if it doesn't exist) |
| `-n chapter-one-chunk` | Name the output file `chapter-one-chunk.pdf` |

**Output:** `stm32-chunks/chapter-one-chunk.pdf` — containing physical PDF pages 41–51.

**Success message:**
```
Extracted 11 page(s) (TOC pages 10-20  ->  PDF pages 41-51 of 1204, offset +31) -> stm32-chunks/chapter-one-chunk.pdf  [2.31 MB]
```

> **Why the offset matters:** Most scanned datasheets, textbooks, and reference manuals have front matter that shifts all the printed page numbers. Without `--offset` you'd have to do the arithmetic yourself every time. Pass `--offset <front-matter page count>` once and use your TOC numbers directly with `-f` and `-t`.

---

## Requirements

- Python 3
- [pypdf](https://pypi.org/project/pypdf/) (or PyPDF2)

```bash
pip install pypdf
```

For `--compress` and higher-quality `--no-images`, also install PyMuPDF and Pillow:

```bash
pip install pymupdf Pillow
```

Both are optional — the script falls back to pypdf automatically if they are not installed.

---

## Usage

```bash
python3 pdf_chunk.py -i <input.pdf> -f <from_page> -t <to_page> [options]
```

---

## Flags

| Flag     | Long form       | Required | Description |
| -------- | --------------- | -------- | ----------- |
| `-i`     | `--input`       | ✅       | Path to the source PDF file |
| `-f`     | `--from-page`   | ✅       | First page to extract — use **TOC page numbers** when `--offset` is set, otherwise the physical PDF page |
| `-t`     | `--to-page`     | ✅       | Last page to extract — same numbering as `-f` |
| `-n`     | `--name`        | ❌       | Custom output filename (no extension needed) |
| `-d`     | `--dir`         | ❌       | Output directory — created automatically if it doesn't exist |
| `-o`     | `--output`      | ❌       | Full output path including folder and filename — overrides `-n` and `-d` if given |
| _(none)_ | `--offset`      | ❌       | Integer added to `-f`/`-t` to convert TOC page numbers to physical PDF pages (default: `0`) |
| _(none)_ | `--no-images`   | ❌       | Strip all embedded images from the extracted pages. Figure labels and all other text are preserved |
| _(none)_ | `--compress`    | ❌       | Re-compress all embedded images at reduced JPEG quality to shrink file size. Requires PyMuPDF. Mutually exclusive with `--no-images` |
| _(none)_ | `--quality`     | ❌       | JPEG quality for `--compress` (default: `50`, range: `1–100`). Lower = smaller file, worse image quality |
| _(none)_ | `--dpi`         | ❌       | Target DPI for downsampling high-res images with `--compress` (default: `150`). Images already below this DPI are not upscaled |

---

## Examples

**Basic extraction** — output is auto-named `report_pages_3-7.pdf`:

```bash
python3 pdf_chunk.py -i report.pdf -f 3 -t 7
```

**Custom filename** — saves as `chapter_one.pdf` in the same folder as the input:

```bash
python3 pdf_chunk.py -i report.pdf -f 1 -t 5 -n chapter_one
```

**Custom directory** — saves as `chapter-one-chunk.pdf` inside `stm32-chunks/` (created if missing):

```bash
python3 pdf_chunk.py -i STM32.pdf -f 10 -t 20 -d stm32-chunks -n chapter-one-chunk
```

**Directory only, auto-named** — saves as `report_pages_10-20.pdf` inside `/tmp/chunks/`:

```bash
python3 pdf_chunk.py -i report.pdf -f 10 -t 20 -d /tmp/chunks
```

**Full output path** — saves to a specific folder with a specific name:

```bash
python3 pdf_chunk.py -i report.pdf -f 10 -t 20 -o /tmp/section.pdf
```

**Single page** — extracts just page 4:

```bash
python3 pdf_chunk.py -i report.pdf -f 4 -t 4
```

**With page offset** — TOC page 1 is physical PDF page 32 (offset = 31):

```bash
python3 pdf_chunk.py -i book.pdf -f 1 -t 10 --offset 31
# TOC pages 1–10  →  extracts PDF pages 32–41
# Output: book_pages_1-10.pdf  (named using your TOC numbers)
```

**Offset with custom name and directory:**

```bash
python3 pdf_chunk.py -i book.pdf -f 45 -t 60 --offset 31 -d chapters -n chapter_three
# TOC pages 45–60  →  extracts PDF pages 76–91
# Output: chapters/chapter_three.pdf
```

---

## Image compression

Add `--compress` to re-compress all embedded images as JPEG at reduced quality.
This is the recommended way to reduce file size to a target range (e.g. 1–2 MB per chunk).
Use `--quality` and `--dpi` to control aggressiveness.

```bash
# Default — quality 50, 150 DPI. Good starting point.
python3 pdf_chunk.py -i report.pdf -f 1 -t 30 --compress

# More aggressive — targets roughly 1–2 MB for typical STM32 chapters
python3 pdf_chunk.py -i report.pdf -f 1 -t 30 --compress --quality 30 --dpi 120

# Maximum squeeze — diagrams still readable, text stays sharp
python3 pdf_chunk.py -i report.pdf -f 1 -t 30 --compress --quality 20 --dpi 100
```

Combined with other flags:

```bash
python3 pdf_chunk.py -i STM32.pdf -f 10 -t 40 --offset 31 -d chunks -n ch2 --compress --quality 35
```

**Output naming with `--compress`:**

- Auto-name: `<stem>_pages_<from>-<to>_q<quality>.pdf` (e.g. `STM32_pages_1-30_q30.pdf`)
- When `-n` or `-o` is given: your name is used exactly (no suffix added)

**Success message with `--compress`:**

```
Extracted 30 page(s) (pages 1-30 of 1204, 18 image(s) recompressed (8.7 MB -> 1.2 MB image data, 86% saved)) -> STM32_pages_1-30_q30.pdf  [1.41 MB]
```

The final file size in MB is always printed so you know immediately whether you hit your target.

**DPI guide:**

| `--dpi` | Use when |
| ------- | -------- |
| `150` (default) | Technical diagrams, register maps — readable at normal zoom |
| `120` | More aggressive; block diagrams still clear |
| `100` | Maximum squeeze; fine detail may soften |

**How it works:**

The script extracts the pages, computes each image's effective DPI from its display rectangle on the page, downsamples any image that exceeds `--dpi`, then re-encodes everything as JPEG at `--quality`. Uses Pillow (LANCZOS resampling) if installed, otherwise falls back to PyMuPDF's built-in encoder. The final save runs `garbage=4` to purge orphaned objects from the PDF stream.

---

## Image removal

Add `--no-images` to strip all embedded images entirely. Figure labels, captions, and all other text are preserved. `--no-images` and `--compress` are mutually exclusive.

```bash
python3 pdf_chunk.py -i report.pdf -f 1 -t 5 --no-images
# Output: report_pages_1-5_no_images.pdf
```

Combined with other flags:

```bash
python3 pdf_chunk.py -i book.pdf -f 10 -t 20 --offset 31 -d chapters -n ch2 --no-images
```

**How it works:**

| Backend | Used when | Mechanism |
| ------- | --------- | --------- |
| **PyMuPDF** | `pymupdf` is installed | Locates each image's display rectangle, covers it with a white redaction annotation (`text=0` so overlapping text is never erased), then applies the redaction |
| **pypdf / PyPDF2** | fallback | Deletes each image's XObject entry from the page's resource dictionary and strips the corresponding `Do` draw commands from the content stream |

---

## Output naming

If no output flag is provided, the file is auto-named using the pattern:

```
<original_name>_pages_<from>-<to>[_q<quality>|_no_images].pdf
```

### Priority order

| Flags used             | Result |
| ---------------------- | ------ |
| `-o /path/to/file.pdf` | Saves to that exact path (overrides `-n` and `-d`) |
| `-d my_dir -n my_name` | Saves as `my_dir/my_name.pdf` |
| `-d my_dir`            | Saves as `my_dir/<input>_pages_<from>-<to>[_q<quality>\|_no_images].pdf` |
| `-n my_name`           | Saves as `my_name.pdf` in the same folder as the input |
| _(none)_               | Saves as `<input>_pages_<from>-<to>[_q<quality>\|_no_images].pdf` next to the input |

---

## Notes

- Page numbers are **1-based** — page 1 is the first page, matching what you see in any PDF viewer.
- The script validates the range before writing — it will error if `--from-page` is less than 1, `--to-page` is less than `--from-page`, or `--to-page` exceeds the document's total page count.
- If you pass `-n chapter.pdf` with an extension, it strips it automatically to avoid double extensions like `chapter.pdf.pdf`.
- The `-d` directory is created automatically (including nested folders) if it does not already exist.
- `--compress` and `--no-images` cannot be used together.

### Page offset (`--offset`)

Many scanned books or reference manuals have a gap between the **PDF's physical page numbers** and the **printed page numbers** shown in the Table of Contents. Pass `--offset <N>` to bridge that gap:

```
actual PDF page = TOC page + offset
```

- `-f` and `-t` always accept **TOC / printed page numbers** when `--offset` is set.
- Auto-generated filenames use the **TOC numbers** so the name stays meaningful.
- The success message prints both sets of numbers for verification:
  ```
  Extracted 10 page(s) (TOC pages 1-10  ->  PDF pages 32-41 of 512, offset +31) -> book_pages_1-10.pdf  [1.87 MB]
  ```
- Validation (bounds checking) is performed against the **actual PDF page numbers** after the offset is applied.
