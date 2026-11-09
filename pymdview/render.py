"""Markdown → HTML. No GTK here, so everything in this module is unit-testable.

Pipeline:  load_text()  →  render_markdown()  →  build_page()

Renderer choice:
  * markdown-it-py (CommonMark + GitHub-style plugins) when installed — preferred.
  * Python-Markdown otherwise (always available: it is a hard dependency).
  * Plain <pre> as a last resort.
"""

import functools
import html
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

try:
    from markdown_it import MarkdownIt

    HAVE_MDIT = True
except ImportError:
    HAVE_MDIT = False
    log.debug("markdown-it-py not installed; using Python-Markdown")

try:
    import markdown
except ImportError:
    markdown = None
    log.debug("Python-Markdown not installed")

try:
    from pygments import highlight as _pyg_highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name
    from pygments.styles import get_all_styles
    from pygments.util import ClassNotFound

    HAVE_PYGMENTS = True
except ImportError:
    HAVE_PYGMENTS = False
    log.debug("Pygments not installed; code blocks will not be highlighted")

PAGE_CSS = (Path(__file__).parent / "style.css").read_text(encoding="utf-8")

WELCOME_HTML = """<div class="empty">
<h1>No document open</h1>
<p>Press <kbd>Ctrl</kbd>+<kbd>O</kbd>, or drop a Markdown file on this window.</p>
<p>The view refreshes automatically every time the file is saved.</p>
</div>"""


# ------------------------------------------------------------ syntax colours --


@functools.lru_cache(maxsize=1)
def pygments_css():
    """CSS for code highlighting, scoped so the light/dark body class picks one."""
    if not HAVE_PYGMENTS:
        return ""
    styles = set(get_all_styles())
    light = "friendly" if "friendly" in styles else "default"
    return "\n".join(
        (
            HtmlFormatter(style=light).get_style_defs(".light .highlight"),
            HtmlFormatter(style="monokai").get_style_defs(".dark .highlight"),
        )
    )


def _highlight(code, lang, _attrs=None):
    """markdown-it `highlight` hook. Returning "" lets markdown-it escape the block itself."""
    if not HAVE_PYGMENTS or not lang:
        return ""
    try:
        lexer = get_lexer_by_name(lang.split()[0])
    except (ClassNotFound, IndexError):
        return ""
    inner = _pyg_highlight(code, lexer, HtmlFormatter(nowrap=True))
    return f'<pre class="highlight"><code>{inner}</code></pre>\n'


# --------------------------------------------------------------- markdown-it --

# mdit-py-plugins is 0.3 on Ubuntu 22.04 and 0.4 on 24.04, and `admon` only exists
# in newer releases — so each plugin is loaded if present and skipped otherwise.
_MDIT_PLUGINS = (
    ("mdit_py_plugins.footnote", "footnote_plugin", {}),
    ("mdit_py_plugins.deflist", "deflist_plugin", {}),
    ("mdit_py_plugins.tasklists", "tasklists_plugin", {}),
    ("mdit_py_plugins.anchors", "anchors_plugin", {"max_level": 6}),
    ("mdit_py_plugins.admon", "admon_plugin", {}),
)


@functools.lru_cache(maxsize=1)
def _mdit():
    """Build the markdown-it parser once."""
    opts = {"html": True, "typographer": False, "highlight": _highlight}
    try:
        import linkify_it  # noqa: F401  (optional: auto-link bare URLs)

        opts["linkify"] = True
    except ImportError:
        log.debug("linkify-it not installed; bare URLs will not be auto-linked")
    md = MarkdownIt("commonmark", opts).enable(["table", "strikethrough"])
    if opts.get("linkify"):
        md.enable("linkify")
    for mod, fn, kw in _MDIT_PLUGINS:
        try:
            md.use(getattr(__import__(mod, fromlist=[fn]), fn), **kw)
        except Exception as e:  # ImportError, AttributeError, or an old plugin API
            log.debug("markdown-it plugin %s.%s not loaded: %s", mod, fn, e)
    return md


def _toc_html(tokens):
    """Build a nested <ul> table of contents from heading tokens that have an id.

    The shallowest heading level present becomes the top level, so a document
    that starts at h2 (or h3) does not get empty outer lists. `depth` tracks how
    many <ul> are currently open; moving deeper opens lists, moving shallower
    closes them, and a sibling just closes the previous <li>.
    """
    items = []
    for i, t in enumerate(tokens):
        if t.type == "heading_open" and t.attrGet("id"):
            title = tokens[i + 1].content if i + 1 < len(tokens) else ""
            items.append((int(t.tag[1]), t.attrGet("id"), title))
    if not items:
        return ""
    base = min(level for level, _, _ in items)
    out, depth = ['<nav class="toc">'], base - 1
    for level, hid, title in items:
        level = max(level, base)
        if level > depth:
            out.append("<ul><li>" * (level - depth))
        else:
            out.append("</li></ul>" * (depth - level) + "</li><li>")
        depth = level
        out.append(f'<a href="#{html.escape(hid)}">{html.escape(title)}</a>')
    out.append("</li></ul>" * (depth - base + 1) + "</nav>")
    return "".join(out)


# ---------------------------------------------------------------- pipeline --

_TASK_RE = re.compile(r"<li>(\s*<p>)?\s*\[( |x|X)\]\s+")
_TOC_RE = re.compile(r"<p>\s*\[TOC\]\s*</p>")
_FRONT_RE = re.compile(r"\A---\s*\n.*?\n(---|\.\.\.)\s*(\n|\Z)", re.S)


def _tasklists(body):
    """Turn `<li>[ ] item` / `<li>[x] item` into disabled checkboxes.

    Needed for the Python-Markdown fallback (and as a safety net for markdown-it
    when the tasklists plugin is missing).
    """

    def repl(m):
        checked = " checked" if m.group(2).lower() == "x" else ""
        return f'<li class="task">{m.group(1) or ""}<input type="checkbox" disabled{checked}>'

    return _TASK_RE.sub(repl, body)


def strip_front_matter(text):
    """Hide YAML front matter (Jekyll / Hugo / Obsidian style)."""
    return _FRONT_RE.sub("", text, count=1)


def load_text(raw):
    """Decode file bytes for rendering: UTF-8 (lenient), no BOM, no front matter."""
    text = raw.decode("utf-8", errors="replace")
    text = text.removeprefix("﻿")
    return strip_front_matter(text)


def render_markdown(text):
    """Render Markdown text to an HTML fragment (the contents of <main>)."""
    if HAVE_MDIT:
        md = _mdit()
        env = {}
        tokens = md.parse(text, env)
        body = md.renderer.render(tokens, md.options, env)
        if "[TOC]" in body:
            body = _TOC_RE.sub(lambda _m: _toc_html(tokens), body)
        return _tasklists(body)
    if markdown is None:
        return f"<pre>{html.escape(text)}</pre>"
    exts = ["extra", "toc", "sane_lists", "admonition"]
    cfg = {"toc": {"permalink": False}}
    if HAVE_PYGMENTS:
        exts.append("codehilite")
        cfg["codehilite"] = {"guess_lang": False, "css_class": "highlight"}
    md = markdown.Markdown(extensions=exts, extension_configs=cfg, output_format="html5")
    return _tasklists(md.convert(text))


def build_page(body_html, title, dark):
    """Wrap an HTML fragment in a complete page with styles for the chosen theme."""
    theme = "dark" if dark else "light"
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"<title>{html.escape(title)}</title><style>{PAGE_CSS}\n{pygments_css()}</style></head>"
        f'<body class="{theme}"><main>{body_html}</main></body></html>'
    )
