"""Tests for pymdview.render (no GTK needed)."""

import re

import pytest

from pymdview import render


@pytest.fixture(params=["markdown-it", "python-markdown"])
def renderer(request, monkeypatch):
    """Run a test with each available renderer."""
    if request.param == "markdown-it":
        if not render.HAVE_MDIT:
            pytest.skip("markdown-it-py not installed")
    else:
        if render.markdown is None:
            pytest.skip("Python-Markdown not installed")
        monkeypatch.setattr(render, "HAVE_MDIT", False)
    return request.param


needs_mdit = pytest.mark.skipif(not render.HAVE_MDIT, reason="markdown-it-py not installed")


def _has_mdit_plugin(name):
    try:
        __import__(f"mdit_py_plugins.{name}")
        return True
    except ImportError:
        return False


needs_pygments = pytest.mark.skipif(not render.HAVE_PYGMENTS, reason="Pygments not installed")


# ---- both renderers ----


def test_heading_and_paragraph(renderer):
    out = render.render_markdown("# Title\n\nHello *world*.")
    assert "<h1" in out and "Title</h1>" in out
    assert "<em>world</em>" in out


def test_table(renderer):
    out = render.render_markdown("| a | b |\n|---|---|\n| 1 | 2 |\n")
    assert "<table>" in out and "<td>1</td>" in out


def test_task_list(renderer):
    out = render.render_markdown("- [ ] todo\n- [x] done\n")
    boxes = re.findall(r"<input[^>]*>", out)
    assert len(boxes) == 2
    assert "checked" not in boxes[0]
    assert "checked" in boxes[1]
    assert all("disabled" in b for b in boxes)


def test_footnote(renderer):
    if renderer == "markdown-it" and not _has_mdit_plugin("footnote"):
        pytest.skip("mdit-py-plugins not installed")
    out = render.render_markdown("Text[^1].\n\n[^1]: The note.\n")
    assert "The note." in out
    assert 'href="#fn' in out


def test_fenced_code_is_escaped(renderer):
    out = render.render_markdown("```\n<b>not bold</b>\n```\n")
    assert "&lt;b&gt;" in out
    assert "<b>not bold</b>" not in out


# ---- markdown-it specifics ----


@needs_mdit
def test_strikethrough():
    assert "<s>gone</s>" in render.render_markdown("~~gone~~")


@needs_mdit
@needs_pygments
def test_known_language_is_highlighted():
    out = render.render_markdown("```python\ndef f(): pass\n```\n")
    assert '<pre class="highlight">' in out
    assert '<span class="k">def</span>' in out


@needs_mdit
def test_unknown_language_falls_back_to_plain_block():
    out = render.render_markdown("```nosuchlang\nx < y\n```\n")
    assert "<pre><code" in out
    assert "x &lt; y" in out


def _toc_links(out):
    nav = re.search(r'<nav class="toc">(.*?)</nav>', out, re.S)
    assert nav, out
    return nav.group(1)


def _anchors_available():
    return render.HAVE_MDIT and 'id="' in render.render_markdown("# x")


needs_anchors = pytest.mark.skipif(not _anchors_available(), reason="mdit anchors plugin unavailable")


@needs_anchors
def test_toc_nesting():
    out = render.render_markdown("[TOC]\n\n## A\n\n### A1\n\n## B\n")
    toc = _toc_links(out)
    assert "[TOC]" not in out
    # A1 is nested in a list inside A; B is A's sibling at the top level.
    assert re.fullmatch(
        r'<ul><li><a href="#a">A</a><ul><li><a href="#a1">A1</a></li></ul></li>'
        r'<li><a href="#b">B</a></li></ul>',
        toc,
    ), toc


@needs_anchors
def test_toc_starting_at_h3_has_no_empty_outer_lists():
    toc = _toc_links(render.render_markdown("[TOC]\n\n### Deep\n\n### Also\n"))
    assert toc.startswith('<ul><li><a href="#deep">')
    assert toc.count("<ul>") == 1


@needs_mdit
def test_toc_with_no_headings_is_empty():
    assert "<nav" not in render.render_markdown("[TOC]\n\nJust text.\n")


# ---- input handling and page ----


def test_front_matter_is_hidden():
    text = render.strip_front_matter("---\ntitle: x\n---\n# Body\n")
    assert text == "# Body\n"


def test_front_matter_only_at_start():
    text = "# Body\n\n---\nnot: front\n---\n"
    assert render.strip_front_matter(text) == text


def test_load_text_strips_bom_and_front_matter():
    raw = "﻿---\na: 1\n...\nHi".encode()
    assert render.load_text(raw) == "Hi"


def test_load_text_tolerates_bad_utf8():
    assert render.load_text(b"caf\xe9") == "caf�"


def test_build_page_theme_and_title_escaping():
    page = render.build_page("<p>x</p>", "a<b>.md", dark=True)
    assert '<body class="dark">' in page
    assert "<title>a&lt;b&gt;.md</title>" in page
    assert "<main><p>x</p></main>" in page
    assert "--link" in page  # style.css was loaded
