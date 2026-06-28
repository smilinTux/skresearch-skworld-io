#!/usr/bin/env python3
"""Structure-sync check between each paper's index.html and paper.md.

Hard gate (fails the build):
  - every immediate subdirectory of papers/ MUST contain an index.html
  - any directory that has a paper.md MUST also have an index.html (and vice
    versa is allowed: an index.html-only landing page is fine)
  - where both exist, each must contain at least one section heading

Soft signal (GitHub Actions ::warning, does NOT fail the build):
  - the H2 section counts of paper.md ('## ') and index.html ('<h2') should
    match; a divergence is reported because some papers intentionally use
    index.html as a short landing page alongside a longer full.html.

This keeps the workflow green on current content while still surfacing drift.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS = os.path.join(ROOT, "papers")

H2_HTML = re.compile(r"<h2\b", re.IGNORECASE)
H2_MD = re.compile(r"^##\s+", re.MULTILINE)


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main():
    if not os.path.isdir(PAPERS):
        print(f"ERROR: {PAPERS} not found")
        return 1

    errors = []
    rows = []
    for name in sorted(os.listdir(PAPERS)):
        d = os.path.join(PAPERS, name)
        if not os.path.isdir(d):
            continue
        index_html = os.path.join(d, "index.html")
        paper_md = os.path.join(d, "paper.md")
        has_html = os.path.isfile(index_html)
        has_md = os.path.isfile(paper_md)

        if not has_html:
            errors.append(f"papers/{name}: missing index.html")
            continue
        if has_md and not has_html:
            errors.append(f"papers/{name}: has paper.md but missing index.html")
            continue

        html_h2 = len(H2_HTML.findall(read(index_html)))
        md_h2 = len(H2_MD.findall(read(paper_md))) if has_md else None

        if html_h2 == 0:
            errors.append(f"papers/{name}: index.html has no <h2> sections")
        if has_md and md_h2 == 0:
            errors.append(f"papers/{name}: paper.md has no '## ' sections")

        rows.append((name, has_md, md_h2, html_h2))

    print("paper                                   paper.md  index.html(h2)")
    warnings = []
    for name, has_md, md_h2, html_h2 in rows:
        md_disp = str(md_h2) if has_md else "-"
        flag = ""
        if has_md and md_h2 != html_h2:
            flag = "  (section counts differ)"
            warnings.append((name, md_h2, html_h2))
        print(f"  {name:<38} {md_disp:>5}     {html_h2:>5}{flag}")

    for name, md_h2, html_h2 in warnings:
        # GitHub Actions warning annotation (non-fatal)
        print(f"::warning title=Section drift::papers/{name} "
              f"paper.md has {md_h2} '## ' sections but index.html has "
              f"{html_h2} <h2> sections")

    if errors:
        print("\nSYNC ERRORS:")
        for e in errors:
            print(f"  {e}")
        return 1
    print("\nOK: every paper has index.html; markdown/html pairs are present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
