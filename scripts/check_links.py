#!/usr/bin/env python3
"""Offline link checker for the skresearch papers site.

Validates *internal* relative/root-relative links in every .html and .md file
under the repo (papers/ + root). External links (http/https/mailto/tel/data)
are counted but not fetched, so the check is deterministic and network-free.

Resolution rules (mirror GitHub Pages root = repo root):
  - "#anchor"           -> skipped (same-page anchor, not validated here)
  - "/path"             -> resolved relative to repo root
  - "path"              -> resolved relative to the linking file's directory
  - trailing "/" or a directory target -> OK if the directory exists OR it
    contains index.html (static hosts commonly serve dir/index.html)
  - otherwise the resolved path must be an existing file

Exit 1 if any internal link is broken.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HTML_LINK = re.compile(r'(?:href|src)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
# Capture only the URL immediately after '](' , ignore optional "title".
MD_LINK = re.compile(r'\]\(\s*<?([^)\s>]+)>?(?:\s+["\'][^)]*["\'])?\s*\)')

EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "data:", "//", "javascript:")


def iter_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            if name.endswith((".html", ".md")):
                yield os.path.join(dirpath, name)


def extract_links(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if path.endswith(".html"):
        return HTML_LINK.findall(text)
    return MD_LINK.findall(text)


def resolve(src_file, link):
    # strip fragment and query
    target = link.split("#", 1)[0].split("?", 1)[0]
    if not target:
        return None  # pure anchor / query
    if target.startswith("/"):
        base = ROOT
        rel = target.lstrip("/")
    else:
        base = os.path.dirname(src_file)
        rel = target
    return os.path.normpath(os.path.join(base, rel))


def main():
    broken = []
    external = 0
    anchors = 0
    checked = 0
    for path in sorted(iter_files()):
        for link in extract_links(path):
            link = link.strip()
            if not link:
                continue
            if link.startswith(EXTERNAL_PREFIXES):
                external += 1
                continue
            if link.startswith("#"):
                anchors += 1
                continue
            resolved = resolve(path, link)
            if resolved is None:
                anchors += 1
                continue
            checked += 1
            ok = False
            if os.path.isdir(resolved):
                ok = True  # dir exists (host may serve index.html or autoindex)
            elif os.path.isfile(resolved):
                ok = True
            elif link.rstrip("/").endswith("/") or link.endswith("/"):
                ok = os.path.isdir(resolved)
            if not ok:
                broken.append((os.path.relpath(path, ROOT), link,
                               os.path.relpath(resolved, ROOT)))

    print(f"internal links checked: {checked}")
    print(f"external links (not fetched): {external}")
    print(f"anchors/empty (skipped): {anchors}")
    if broken:
        print("\nBROKEN INTERNAL LINKS:")
        for src, link, resolved in broken:
            print(f"  {src}: '{link}' -> missing {resolved}")
        return 1
    print("OK: no broken internal links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
