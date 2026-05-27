# pdf_chunk

A command-line tool to extract a range of pages from a PDF and save them as a new file.

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
✓ Extracted 11 page(s) (TOC pages 10–20  →  PDF pages 41–51 of 1204, offset +31) → stm32-chunks/chapter-one-chunk.pdf
```

> **Why the offset matters:** Most scanned datasheets, textbooks, and reference manuals have front matter that shifts all the printed page numbers. Without `--offset` you'd have to do the arithmetic yourself every time. Pass `--offset <front-matter page count>` once and use your TOC numbers directly with `-f` and `-t`.

---

## Requirements

- Python 3
- [pypdf](https://pypi.org/project/pypdf/)

Install the dependency:

```bash
pip install pypdf
```

---

## Usage

```bash
python3 pdf_chunk.py -i <input.pdf> -f <from_page> -t <to_page> [options]
```

---

## Flags

| Flag       | Long form     | Required | Description                                                                                                                                    |
| ---------- | ------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `-i`       | `--input`     | ✅       | Path to the source PDF file                                                                                                                    |
| `-f`       | `--from-page` | ✅       | First page to extract — use **TOC page numbers** when `--offset` is set, otherwise the physical PDF page                                      |
| `-t`       | `--to-page`   | ✅       | Last page to extract — same numbering as `-f`                                                                                                  |
| `-n`       | `--name`      | ❌       | Custom output filename (no extension needed)                                                                                                   |
| `-d`       | `--dir`       | ❌       | Output directory — created automatically if it doesn't exist                                                                                   |
| `-o`       | `--output`    | ❌       | Full output path including folder and filename — overrides `-n` and `-d` if given                                                              |
| _(none)_   | `--offset`    | ❌       | Integer added to `-f`/`-t` to convert TOC page numbers to physical PDF pages. Use when the book's page 1 is not the PDF's first page (default: `0`) |

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

**_Custom directory — saves as `chapter-one-chunk.pdf` inside `stm32-chunks/` (created if missing):_**

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

**Using long-form flags:**

```bash
python3 pdf_chunk.py --input report.pdf --from-page 1 --to-page 5 --name intro
```

**With page offset** — the book's Table of Contents starts at page 1, but the actual PDF page that maps to TOC page 1 is physical page 32 (offset = 31). Supply TOC page numbers and the tool translates them automatically:

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

## Output Naming

If no output flag is provided, the file is auto-named using the pattern:

```
<original_name>_pages_<from>-<to>.pdf
```

For example, running on `report.pdf` with `-f 3 -t 7` produces:

```
report_pages_3-7.pdf
```

### Priority order

| Flags used             | Result                                                                   |
| ---------------------- | ------------------------------------------------------------------------ |
| `-o /path/to/file.pdf` | Saves to that exact path (overrides `-n` and `-d`)                       |
| `-d my_dir -n my_name` | Saves as `my_dir/my_name.pdf`                                            |
| `-d my_dir`            | Saves as `my_dir/<input>_pages_<from>-<to>.pdf`                          |
| `-n my_name`           | Saves as `my_name.pdf` in the same folder as the input                   |
| _(none)_               | Saves as `<input>_pages_<from>-<to>.pdf` in the same folder as the input |

---

## Notes

- Page numbers are **1-based** — page 1 is the first page, matching what you see in any PDF viewer.
- The script validates the range before writing — it will error if `--from-page` is less than 1, `--to-page` is less than `--from-page`, or `--to-page` exceeds the document's total page count.
- If you pass `-n chapter.pdf` with an extension, it strips it automatically to avoid double extensions like `chapter.pdf.pdf`.
- The `-d` directory is created automatically (including nested folders) if it does not already exist.

### Page offset (`--offset`)

Many scanned books or reference manuals have a gap between the **PDF's physical page numbers** and the **printed page numbers** shown in the Table of Contents. For example, the front matter (cover, TOC, preface) may occupy 31 pages before the book's "page 1" begins.

Pass `--offset <N>` to bridge that gap:

```
actual PDF page = TOC page + offset
```

- `-f` and `-t` always accept **TOC / printed page numbers** when `--offset` is set.
- Auto-generated filenames use the **TOC numbers** so the name stays meaningful.
- The success message prints both sets of numbers for verification:
  ```
  ✓ Extracted 10 page(s) (TOC pages 1–10  →  PDF pages 32–41 of 512, offset +31) → book_pages_1-10.pdf
  ```
- Validation (bounds checking) is performed against the **actual PDF page numbers** after the offset is applied.
