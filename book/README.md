# book/

This folder holds the book the repo is built around: *Python Data Analysis, 4th Edition* by
Avinash Navlani and Cornellius Yudha Wijaya (Packt, 2026).

## Add your copy of the book

The PDF is not in the repo, because the book is copyrighted. To use the practice harness in
`PRACTICE/` at full strength:

1. Buy the book from Packt: https://www.packtpub.com/en-us/product/python-data-analysis-9781806022878
   (the print edition includes a free PDF; see the book's "Unlock Access" page).
2. Save the PDF in this folder. Any filename works; `.gitignore` ignores everything in `book/`
   except `README.md` and `outline.txt`, so no PDF here ever gets pushed.

Without the PDF, everything still works. Claude builds practice problems from your notes, your
notebooks, and Packt's code repo instead of from the book's own pages.

## Page numbers

One page number is used everywhere in this repo: **the number printed on the page**, which is
also the number a PDF reader shows, because the PDF carries page labels. Page 45 means the page
that says 45, in print and on screen. Notes, reading positions, skills, and `outline.txt` all use
it. The file's own page count is never used, because it is a number the reader cannot see.

The two differ. The body's printed numbers start again at 1 partway in, so a printed page in the
body sits 27 further into the file: printed page 45 is the 72nd page of the file. That matters
only when extracting text with a library, since `pypdf` indexes by position. Read the label
instead of adding 27, because the offset is not the same in the front matter:

```python
from pypdf import PdfReader
reader = PdfReader("book/<your file>.pdf")
labels = list(reader.page_labels)
index = labels.index("45")          # position in the file of printed page 45
text = reader.pages[index].extract_text()
```

## outline.txt

`outline.txt` is the book's table of contents: every chapter, section, and subsection, indented
by level, with the printed page each one starts on. `[p45]` means the page that has 45 printed on
it. Claude uses it to name the sections you finish and to find the pages to read when it writes
practice problems.

It is generated from the PDF's own bookmarks and page labels with `pypdf`, so it can be rebuilt
from any copy of the book. Ask Claude to regenerate it if your PDF's numbering differs.
