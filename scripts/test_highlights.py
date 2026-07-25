#!/usr/bin/env python3
"""Deterministic, offline tests for scripts/highlights.py.

Covers:
  - per-paper TL;DR derivation (normal, short/empty summary edge cases,
    dash sanitisation, over-long truncation)
  - the cross-paper "At a Glance" rollup (top-N, prefers NEW-flagged
    highlights, skips papers with no highlights)
  - parsing the real index.html into the paper data model
  - rendered output carries the markers and contains no em/en dashes

Run with:  python3 -m pytest scripts/test_highlights.py   (or plain python3)
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import highlights as H  # noqa: E402

LONG_DASHES = re.compile("[\u2014\u2013]")


# ---- fixtures (plain dicts = the paper data model) ----------------------

def _paper(title="A Paper", summary="", highlights=None, url="papers/x/"):
    return {
        "title": title,
        "url": url,
        "summary": summary,
        "highlights": highlights or [],
    }


# ---- per-paper TL;DR ----------------------------------------------------

def test_tldr_uses_first_sentence_of_summary():
    p = _paper(summary="This is the core claim. Then a second sentence adds detail.")
    assert H.derive_tldr(p) == "This is the core claim."


def test_tldr_empty_summary_falls_back_to_top_highlight():
    p = _paper(
        summary="",
        highlights=[{"text": "The headline highlight carries the point across.",
                     "is_new": False}],
    )
    tldr = H.derive_tldr(p)
    assert tldr == "The headline highlight carries the point across."


def test_tldr_short_summary_falls_back_to_top_highlight():
    # A too-short first sentence must not win over a real highlight.
    p = _paper(
        summary="Yes.",
        highlights=[{"text": "A substantive highlight sentence that is long enough.",
                     "is_new": False}],
    )
    assert H.derive_tldr(p) == "A substantive highlight sentence that is long enough."


def test_tldr_empty_when_nothing_to_summarise():
    assert H.derive_tldr(_paper(summary="", highlights=[])) == ""


def test_tldr_sanitises_em_and_en_dashes():
    p = _paper(summary="We built it surface by surface " + chr(0x2014) + " hybrid by construction. Rest.")
    out = H.derive_tldr(p)
    assert not LONG_DASHES.search(out), out


def test_tldr_truncates_over_long_first_sentence():
    long_sentence = "word " * 100  # ~500 chars, no sentence break
    out = H.derive_tldr(_paper(summary=long_sentence))
    assert len(out) <= H.TLDR_MAX_LEN
    assert out.endswith("...")


# ---- At a Glance rollup -------------------------------------------------

def test_at_a_glance_prefers_new_flagged_highlight():
    p = _paper(highlights=[
        {"text": "Older headline.", "is_new": False},
        {"text": "The shiny new result.", "is_new": True},
    ])
    picks = H.at_a_glance([p], top_n=5)
    assert len(picks) == 1
    assert picks[0]["text"] == "The shiny new result."
    assert picks[0]["is_new"] is True
    assert picks[0]["paper"] == "A Paper"


def test_at_a_glance_defaults_to_first_highlight_when_no_new():
    p = _paper(highlights=[
        {"text": "First and only headline.", "is_new": False},
        {"text": "Secondary point.", "is_new": False},
    ])
    picks = H.at_a_glance([p], top_n=5)
    assert picks[0]["text"] == "First and only headline."


def test_at_a_glance_skips_papers_without_highlights():
    papers = [
        _paper(title="Has one", highlights=[{"text": "Kept.", "is_new": False}]),
        _paper(title="Empty", highlights=[]),
    ]
    picks = H.at_a_glance(papers, top_n=5)
    assert [x["paper"] for x in picks] == ["Has one"]


def test_at_a_glance_respects_top_n():
    papers = [
        _paper(title=f"P{i}", highlights=[{"text": f"H{i}.", "is_new": False}])
        for i in range(6)
    ]
    picks = H.at_a_glance(papers, top_n=3)
    assert len(picks) == 3
    assert [x["paper"] for x in picks] == ["P0", "P1", "P2"]


def test_at_a_glance_sanitises_dashes():
    p = _paper(highlights=[{"text": "A " + chr(0x2013) + " B " + chr(0x2014) + " C.", "is_new": False}])
    picks = H.at_a_glance([p], top_n=5)
    assert not LONG_DASHES.search(picks[0]["text"])


# ---- parsing the real index.html ---------------------------------------

def test_parse_real_index_returns_expected_papers():
    papers = H.load_papers(ROOT)
    # Only cards that carry a `.glance` highlight block are real papers;
    # the dashed "Coming Soon" placeholder must be excluded.
    assert len(papers) == 6
    titles = [p["title"] for p in papers]
    assert titles[0].startswith("Built to Outlive the Algorithm")
    # every real paper yields at least one highlight and a non-empty TL;DR
    for p in papers:
        assert p["highlights"], p["title"]
        assert H.derive_tldr(p), p["title"]


def test_rollup_over_real_papers_is_dash_clean():
    papers = H.load_papers(ROOT)
    picks = H.at_a_glance(papers, top_n=H.TOP_N)
    assert 1 <= len(picks) <= H.TOP_N
    for pick in picks:
        assert not LONG_DASHES.search(pick["text"]), pick


def test_render_block_has_markers_and_no_long_dashes():
    papers = H.load_papers(ROOT)
    block = H.render_block(papers)
    assert H.MARK_START in block and H.MARK_END in block
    assert not LONG_DASHES.search(block), "render must never emit em/en dashes"


def _run_standalone():
    """Dependency-free runner so CI needs no pytest (mirrors check_*.py)."""
    tests = sorted(
        (name, obj)
        for name, obj in globals().items()
        if name.startswith("test_") and callable(obj)
    )
    failures = []
    for name, fn in tests:
        try:
            fn()
            print(f"  ok   {name}")
        except Exception as exc:  # noqa: BLE001
            failures.append((name, exc))
            print(f"  FAIL {name}: {exc}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        import pytest
    except ImportError:
        raise SystemExit(_run_standalone())
    raise SystemExit(pytest.main([__file__, "-v"]))
