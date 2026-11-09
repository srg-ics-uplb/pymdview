"""Version shims for the GTK / WebKitGTK stacks shipped by Ubuntu 22.04 and 24.04.

Keep every "which API does this system have?" check in this module so the rest
of the code can be written against one API.

Other modules import GTK names from here (not from gi.repository) so the
versions pinned below are always in place before anything loads.

  * WebKit2 4.1 (libsoup 3) is the norm on 24.04; 22.04 may only have 4.0.
  * WebKitGTK ≥ 2.40 adds `evaluate_javascript` and `set_enable_javascript_markup`;
    older versions only have `run_javascript` and `set_enable_javascript`.
"""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
try:
    gi.require_version("WebKit2", "4.1")
except ValueError:
    gi.require_version("WebKit2", "4.0")

from gi.repository import Gdk, Gio, GLib, Gtk, Pango, WebKit2  # noqa: E402


def disable_page_scripts(settings):
    """Stop scripts embedded in Markdown from running.

    Markdown may contain raw HTML, so page JavaScript is always off. Our own
    calls through run_js() still work because they go through the WebKit API.
    """
    if hasattr(settings, "set_enable_javascript_markup"):
        settings.set_enable_javascript_markup(False)
    else:
        settings.set_enable_javascript(False)


def run_js(webview, script, callback=None):
    """Evaluate `script` in the page; call `callback(number_or_None)` with the result."""

    def done(wv, res, _data=None):
        if callback is None:
            return
        try:
            if hasattr(wv, "evaluate_javascript_finish"):
                jsv = wv.evaluate_javascript_finish(res)
            else:
                jsv = wv.run_javascript_finish(res).get_js_value()
            val = jsv.to_double() if jsv is not None and jsv.is_number() else None
        except Exception:
            val = None
        callback(val)

    if hasattr(webview, "evaluate_javascript"):
        webview.evaluate_javascript(script, -1, None, None, None, done, None)
    else:
        webview.run_javascript(script, None, done, None)


def system_prefers_dark():
    """True if the desktop asks for a dark theme (GNOME 42+ first, then GTK settings)."""
    try:
        src = Gio.SettingsSchemaSource.get_default()
        schema = src.lookup("org.gnome.desktop.interface", True) if src else None
        if schema and schema.has_key("color-scheme"):
            scheme = Gio.Settings.new("org.gnome.desktop.interface").get_string("color-scheme")
            if scheme == "prefer-dark":
                return True
    except Exception:
        pass
    s = Gtk.Settings.get_default()
    if s is None:
        return False
    if s.get_property("gtk-application-prefer-dark-theme"):
        return True
    return "dark" in (s.get_property("gtk-theme-name") or "").lower()


__all__ = [
    "Gdk",
    "Gio",
    "GLib",
    "Gtk",
    "Pango",
    "WebKit2",
    "disable_page_scripts",
    "run_js",
    "system_prefers_dark",
]
