# book/

This folder holds the book the repo is built around: *Python Data Analysis, 4th Edition* by
Avinash Navlani and Cornellius Yudha Wijaya (Packt, 2026).

## Add your copy of the book

The PDF is not in the repo, because the book is copyrighted. To use the practice routine in
`QUIZ/` at full strength:

1. Buy the book from Packt: https://www.packtpub.com/en-us/product/python-data-analysis-9781806022878
   (the print edition includes a free PDF; see the book's "Unlock Access" page).
2. Save the PDF in this folder as `Python Data Analysis - Fourth Edition.pdf`.

`.gitignore` keeps any PDF here out of git, so it never gets pushed.

Without the PDF, everything still works. Claude builds practice problems from your notes, your
notebooks, and Packt's code repo instead of from the book's own pages.

## outline.txt

`outline.txt` is the book's table of contents: every chapter, section, and subsection, indented
by level, with the PDF page each one starts on (`[p34]` means page 34 of the PDF file, not the
printed page number). Claude uses it to name the sections you finish and to find the pages to
read when it writes practice problems.

If your PDF's page numbers don't line up with the outline, ask Claude to regenerate
`outline.txt` from your copy. It's built from the PDF's bookmarks with the `pypdf` library.
