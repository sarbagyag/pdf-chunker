# pdf_chunk

A simple command-line tool to extract a range of pages from a PDF and save them as a new file.

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

| Flag | Long form     | Required | Description                                                                       |
| ---- | ------------- | -------- | --------------------------------------------------------------------------------- |
| `-i` | `--input`     | ✅       | Path to the source PDF file                                                       |
| `-f` | `--from-page` | ✅       | First page to extract (1-based, inclusive)                                        |
| `-t` | `--to-page`   | ✅       | Last page to extract (1-based, inclusive)                                         |
| `-n` | `--name`      | ❌       | Custom output filename (no extension needed)                                      |
| `-d` | `--dir`       | ❌       | Output directory — created automatically if it doesn't exist                      |
| `-o` | `--output`    | ❌       | Full output path including folder and filename — overrides `-n` and `-d` if given |

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
