"""The viewer window: header bar, WebKit view, find bar, link status line.

Data flow for a document:
    file monitor event ─► _schedule_reload() ─► render() ─► render.render_markdown()
        ─► render.build_page() ─► WebView.load_html() ─► on_load_changed()
           (restores scroll position, pending #anchor, find highlights, …)
"""

import html
import os

from pymdview import APP_NAME, PRG_NAME, render
from pymdview.compat import (
    Gdk,
    Gio,
    GLib,
    Gtk,
    Pango,
    WebKit2,
    disable_page_scripts,
    run_js,
    system_prefers_dark,
)
from pymdview.shortcuts import SHORTCUTS, accels, detailed_name
from pymdview.util import js_str, pretty_path

MD_EXTENSIONS = (".md", ".markdown", ".mdown", ".mkd", ".mkdn", ".mdx", ".txt")

RELOAD_DEBOUNCE_MS = 150  # editors often emit several events per save
FLASH_SECONDS = 3
ZOOM_STEP = 1.1
ZOOM_MIN, ZOOM_MAX = 0.3, 4.0
FIND_MAX_MATCHES = 10000
PDF_PRINTER = "Print to File"  # GTK's built-in file backend; writes PDF without a dialog

# Every event that can mean "the file now has different contents".
_RELOAD_EVENTS = (
    Gio.FileMonitorEvent.CHANGES_DONE_HINT,
    Gio.FileMonitorEvent.CHANGED,
    Gio.FileMonitorEvent.CREATED,
    Gio.FileMonitorEvent.MOVED_IN,
    Gio.FileMonitorEvent.RENAMED,
    Gio.FileMonitorEvent.DELETED,
    Gio.FileMonitorEvent.MOVED_OUT,
)

# Context-menu entries to keep; everything browser-like is removed.
_CONTEXT_MENU_KEEP = {
    WebKit2.ContextMenuAction.COPY,
    WebKit2.ContextMenuAction.COPY_LINK_TO_CLIPBOARD,
    WebKit2.ContextMenuAction.COPY_IMAGE_TO_CLIPBOARD,
    WebKit2.ContextMenuAction.COPY_IMAGE_URL_TO_CLIPBOARD,
    WebKit2.ContextMenuAction.SELECT_ALL,
    WebKit2.ContextMenuAction.OPEN_LINK,
}

# Header-bar menu: sections of (label, action).
_MENU = (
    (("Find…", "win.find"), ("Dark Theme", "win.dark")),
    (("Zoom In", "win.zoom-in"), ("Zoom Out", "win.zoom-out"), ("Reset Zoom", "win.zoom-reset")),
    (
        ("Print…", "win.print"),
        ("Export as PDF…", "win.export-pdf"),
        ("Open in Text Editor", "win.edit"),
        ("Show in Folder", "win.folder"),
    ),
    (("Keyboard Shortcuts", "win.shortcuts"), (f"About {APP_NAME}", "app.about")),
)

# Actions that only make sense with a file open.
_FILE_ACTIONS = ("reload", "print", "export-pdf", "edit", "folder")


class ViewerWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.set_default_size(980, 760)
        self.set_icon_name(PRG_NAME)

        self.gfile = None  # the open document (Gio.File) or None
        self.monitor = None  # Gio.FileMonitor on the document's folder
        self.reload_source = 0  # GLib source id of a pending debounced reload
        self.pending_scroll = None  # scrollY to restore after the next load
        self.pending_anchor = None  # #fragment to jump to after the next load
        self.pending_after_load = None  # one-shot callable run after the next load
        self.dark = system_prefers_dark()

        self._build_header()
        self._build_webview()
        self._build_findbar()
        self._build_status()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.pack_start(self.searchbar, False, False, 0)
        box.pack_start(self.overlay, True, True, 0)
        self.add(box)

        # Drag & drop onto the window (not the web view, which would navigate).
        self.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.drag_dest_add_uri_targets()
        self.connect("drag-data-received", self.on_drop)
        self.webview.drag_dest_unset()

        self._install_actions()
        self.render()

    # ---- UI construction ----
    def _build_header(self):
        hb = Gtk.HeaderBar(show_close_button=True, title=APP_NAME)
        self.set_titlebar(hb)
        self.header = hb

        for icon, tip, action in (
            ("document-open-symbolic", "Open… (Ctrl+O)", "win.open"),
            ("view-refresh-symbolic", "Reload (Ctrl+R)", "win.reload"),
        ):
            btn = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
            btn.set_tooltip_text(tip)
            btn.set_action_name(action)
            hb.pack_start(btn)

        menu = Gio.Menu()
        for section in _MENU:
            sec = Gio.Menu()
            for label, action in section:
                sec.append(label, action)
            menu.append_section(None, sec)
        menu_btn = Gtk.MenuButton(menu_model=menu)
        menu_btn.add(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
        hb.pack_end(menu_btn)

    def _build_webview(self):
        settings = WebKit2.Settings()
        disable_page_scripts(settings)
        settings.set_allow_file_access_from_file_urls(True)  # relative images
        settings.set_enable_developer_extras(False)
        self.webview = WebKit2.WebView(settings=settings)
        self.webview.connect("decide-policy", self.on_decide_policy)
        self.webview.connect("load-changed", self.on_load_changed)
        self.webview.connect("context-menu", self.on_context_menu)
        self.webview.connect("mouse-target-changed", self.on_hover)

    def _build_findbar(self):
        self.find_entry = Gtk.SearchEntry(width_chars=32)
        self.find_entry.connect("search-changed", self.on_find_changed)
        self.find_entry.connect("activate", lambda *_: self.find_ctl().search_next())
        self.find_entry.connect("stop-search", lambda *_: self.searchbar.set_search_mode(False))
        prev_b = Gtk.Button.new_from_icon_name("go-up-symbolic", Gtk.IconSize.BUTTON)
        prev_b.connect("clicked", lambda *_: self.find_ctl().search_previous())
        next_b = Gtk.Button.new_from_icon_name("go-down-symbolic", Gtk.IconSize.BUTTON)
        next_b.connect("clicked", lambda *_: self.find_ctl().search_next())
        self.find_label = Gtk.Label()
        self.find_label.get_style_context().add_class("dim-label")

        linked = Gtk.Box()
        linked.get_style_context().add_class("linked")
        for w in (self.find_entry, prev_b, next_b):
            linked.pack_start(w, False, False, 0)
        fbox = Gtk.Box(spacing=6)
        fbox.pack_start(linked, False, False, 0)
        fbox.pack_start(self.find_label, False, False, 0)

        self.searchbar = Gtk.SearchBar()
        self.searchbar.add(fbox)
        self.searchbar.connect_entry(self.find_entry)
        self.searchbar.connect("notify::search-mode-enabled", self.on_search_mode)

        fc = self.find_ctl()
        fc.connect("counted-matches", self.on_counted_matches)
        fc.connect("failed-to-find-text", lambda *_: self.find_label.set_text("No matches"))

    def _build_status(self):
        """Bottom-left overlay showing hovered link targets and short messages."""
        self.status = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.status.get_style_context().add_class("dim-label")
        self.status.set_margin_start(8)
        self.status.set_margin_end(8)
        self.status_rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.CROSSFADE)
        self.status_rev.add(self.status)
        self.status_rev.set_halign(Gtk.Align.START)
        self.status_rev.set_valign(Gtk.Align.END)

        self.overlay = Gtk.Overlay()
        self.overlay.add(self.webview)
        self.overlay.add_overlay(self.status_rev)

    # ---- actions ----
    def _install_actions(self):
        handlers = {
            "open": self.choose_file,
            "reload": lambda: self.render(keep_scroll=True),
            "find": lambda: self.searchbar.set_search_mode(True),
            "zoom-in": lambda: self.zoom(ZOOM_STEP),
            "zoom-out": lambda: self.zoom(1 / ZOOM_STEP),
            "zoom-reset": lambda: self.webview.set_zoom_level(1.0),
            "print": self.print_doc,
            "export-pdf": self.export_pdf,
            "edit": lambda: self.open_external(self.gfile),
            "folder": self.show_in_folder,
            "shortcuts": self.show_shortcuts,
            "close": self.close,
        }
        app = self.get_application()
        for name, handler in handlers.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, h=handler: h())
            self.add_action(action)
            if accels(name):
                app.set_accels_for_action(detailed_name(name), accels(name))

        dark = Gio.SimpleAction.new_stateful("dark", None, GLib.Variant.new_boolean(self.dark))
        dark.connect("activate", self.on_toggle_dark)
        self.add_action(dark)
        app.set_accels_for_action("win.dark", accels("dark"))
        self._update_file_actions()

    def _update_file_actions(self):
        for name in _FILE_ACTIONS:
            self.lookup_action(name).set_enabled(self.gfile is not None)

    # ---- file handling ----
    def open_gfile(self, gfile):
        """Show `gfile` in this window and start watching it for changes."""
        if self.monitor:
            self.monitor.cancel()
            self.monitor = None
        self.gfile = gfile
        # Watch the folder, not the file: many editors (Vim, VS Code, gedit) save by
        # writing a temp file and renaming it over the original, which ends a
        # file-level monitor. A folder monitor sees the rename and keeps working.
        try:
            self.monitor = gfile.get_parent().monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
            self.monitor.connect("changed", self.on_dir_changed)
        except GLib.Error:
            self.monitor = None
        self._update_file_actions()
        self.render()
        if self.gfile.get_path():
            Gtk.RecentManager.get_default().add_item(self.gfile.get_uri())

    def on_dir_changed(self, _mon, f, other, event):
        target = self.gfile
        if target is None:
            return
        hit = (f and f.equal(target)) or (other and other.equal(target))
        if hit and event in _RELOAD_EVENTS:
            self._schedule_reload()

    def _schedule_reload(self):
        """Debounce: restart the timer on every event, reload once things settle."""
        if self.reload_source:
            GLib.source_remove(self.reload_source)
        self.reload_source = GLib.timeout_add(RELOAD_DEBOUNCE_MS, self._debounced_reload)

    def _debounced_reload(self):
        self.reload_source = 0
        self.render(keep_scroll=True)
        return GLib.SOURCE_REMOVE

    def choose_file(self):
        dlg = Gtk.FileChooserNative.new(
            "Open Markdown File", self, Gtk.FileChooserAction.OPEN, "_Open", "_Cancel"
        )
        flt = Gtk.FileFilter()
        flt.set_name("Markdown files")
        for ext in MD_EXTENSIONS:
            flt.add_pattern("*" + ext)
            flt.add_pattern("*" + ext.upper())
        flt.add_mime_type("text/markdown")
        flt.add_mime_type("text/x-markdown")
        dlg.add_filter(flt)
        allf = Gtk.FileFilter()
        allf.set_name("All files")
        allf.add_pattern("*")
        dlg.add_filter(allf)
        if self.gfile and self.gfile.get_parent():
            dlg.set_current_folder_file(self.gfile.get_parent())
        if dlg.run() == Gtk.ResponseType.ACCEPT:
            self.open_gfile(dlg.get_file())
        dlg.destroy()

    def on_drop(self, _w, _ctx, _x, _y, data, _info, _time):
        uris = data.get_uris()
        if uris:
            self.open_gfile(Gio.File.new_for_uri(uris[0]))
            for extra in uris[1:]:
                self.get_application().open_in_new_window(Gio.File.new_for_uri(extra))

    # ---- rendering ----
    def render(self, keep_scroll=False):
        """Re-read the file and show it. `keep_scroll` preserves the scroll position."""
        if self.gfile is None:
            self.header.set_title(APP_NAME)
            self.header.set_subtitle(None)
            self.set_title(APP_NAME)
            self.webview.load_html(render.build_page(render.WELCOME_HTML, APP_NAME, self.dark), "file:///")
            return

        name = self.gfile.get_basename()
        parent = self.gfile.get_parent()
        self.header.set_title(name)
        if parent and parent.get_path():
            self.header.set_subtitle(pretty_path(parent.get_path()))
        else:
            self.header.set_subtitle(self.gfile.get_uri())
        self.set_title(f"{name} — {APP_NAME}")

        try:
            _ok, raw, _etag = self.gfile.load_contents(None)
            body = render.render_markdown(render.load_text(raw))
        except GLib.Error as e:
            if keep_scroll:  # mid-save the file can vanish briefly; keep the last version
                return
            body = f'<div class="empty"><h1>Can’t open file</h1><p>{html.escape(e.message)}</p></div>'

        page = render.build_page(body, name, self.dark)
        base = self.gfile.get_uri()  # makes relative links and images resolve
        if keep_scroll:
            self._js("window.scrollY", lambda y: self._load(page, base, y))
        else:
            self._load(page, base, None)

    def _load(self, page, base, scroll_y):
        self.pending_scroll = scroll_y
        self.webview.load_html(page, base)

    def scroll_to_anchor(self, frag):
        frag = GLib.uri_unescape_string(frag, None) or frag
        self._js(
            "(function(i){var e=document.getElementById(i)||document.getElementsByName(i)[0];"
            f"if(e)e.scrollIntoView();}})({js_str(frag)})"
        )

    def on_load_changed(self, _wv, event):
        """After a page finishes loading, re-apply per-window state to it."""
        if event != WebKit2.LoadEvent.FINISHED:
            return
        if self.pending_anchor:
            frag, self.pending_anchor = self.pending_anchor, None
            self.scroll_to_anchor(frag)
        if self.pending_scroll:
            y, self.pending_scroll = self.pending_scroll, None
            self._js(f"window.scrollTo(0, {int(y)})")
        if self.searchbar.get_search_mode():
            self.on_find_changed(self.find_entry)
        if self.pending_after_load:
            callback, self.pending_after_load = self.pending_after_load, None
            callback()

    def _js(self, script, callback=None):
        run_js(self.webview, script, callback)

    # ---- navigation ----
    def on_decide_policy(self, _wv, decision, dtype):
        """Handle link clicks ourselves instead of letting the web view navigate."""
        if dtype == WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION:
            uri = decision.get_navigation_action().get_request().get_uri()
            decision.ignore()
            self.follow_link(uri)
            return True
        if dtype != WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            return False
        action = decision.get_navigation_action()
        if action.get_navigation_type() == WebKit2.NavigationType.OTHER:
            return False  # our own load_html() calls
        uri = action.get_request().get_uri()
        decision.ignore()
        self.follow_link(uri)
        return True

    def follow_link(self, uri):
        """#anchor → scroll; local .md → open here; anything else → default app."""
        base, _, frag = uri.partition("#")
        current = self.gfile.get_uri() if self.gfile else None
        if frag and (base == current or base in ("", "file:///")):
            self.scroll_to_anchor(frag)
            return
        if base.startswith("file://"):
            target = Gio.File.new_for_uri(base)
            if not target.query_exists(None):
                self.flash(f"Not found: {target.get_path()}")
                return
            if target.get_basename().lower().endswith(MD_EXTENSIONS):
                self.open_gfile(target)
                self.pending_anchor = frag or None
                return
        try:
            Gtk.show_uri_on_window(self, uri, Gdk.CURRENT_TIME)
        except GLib.Error as e:
            self.flash(e.message)

    def on_hover(self, _wv, hit, _mods):
        if hit.context_is_link():
            self.status.set_text(hit.get_link_uri())
            self.status_rev.set_reveal_child(True)
        else:
            self.status_rev.set_reveal_child(False)

    def flash(self, msg):
        """Show a short message in the status line for a few seconds."""
        self.status.set_text(msg)
        self.status_rev.set_reveal_child(True)
        GLib.timeout_add_seconds(FLASH_SECONDS, self._hide_status)

    def _hide_status(self):
        self.status_rev.set_reveal_child(False)
        return GLib.SOURCE_REMOVE

    def on_context_menu(self, _wv, menu, _event, _hit):
        for item in list(menu.get_items()):
            if item.get_stock_action() not in _CONTEXT_MENU_KEEP:
                menu.remove(item)
        return False

    # ---- find ----
    def find_ctl(self):
        return self.webview.get_find_controller()

    def on_find_changed(self, entry):
        text = entry.get_text()
        fc = self.find_ctl()
        if not text:
            fc.search_finish()
            self.find_label.set_text("")
            return
        opts = WebKit2.FindOptions.CASE_INSENSITIVE | WebKit2.FindOptions.WRAP_AROUND
        fc.count_matches(text, opts, FIND_MAX_MATCHES)
        fc.search(text, opts, FIND_MAX_MATCHES)

    def on_counted_matches(self, _ctl, n):
        self.find_label.set_text(f"{n} match" if n == 1 else f"{n} matches")

    def on_search_mode(self, bar, _p):
        if not bar.get_search_mode():
            self.find_ctl().search_finish()
            self.find_label.set_text("")
            self.webview.grab_focus()

    # ---- misc ----
    def zoom(self, factor):
        z = self.webview.get_zoom_level() * factor
        self.webview.set_zoom_level(max(ZOOM_MIN, min(ZOOM_MAX, z)))

    def on_toggle_dark(self, action, _p):
        self.dark = not action.get_state().get_boolean()
        action.set_state(GLib.Variant.new_boolean(self.dark))
        self.render(keep_scroll=True)

    def _on_light_page(self, job):
        """Run `job(done)` while the light theme is showing, for printing on white paper.

        In dark mode the page is re-rendered light first, `job` runs once that page
        has loaded, and dark mode comes back when `job` calls `done()`.
        """
        if not self.dark:
            job(lambda: None)
            return

        def restore_dark():
            self.dark = True
            self.render(keep_scroll=True)

        self.dark = False
        self.pending_after_load = lambda: job(restore_dark)
        self.render(keep_scroll=True)

    def print_doc(self):
        """Show the print dialog (which can also print to a file)."""

        def job(done):
            WebKit2.PrintOperation.new(self.webview).run_dialog(self)
            done()

        self._on_light_page(job)

    def export_pdf(self):
        """Ask where to save, then write the document as a PDF without a print dialog."""
        if self.gfile is None:
            return
        dlg = Gtk.FileChooserNative.new(
            "Export as PDF", self, Gtk.FileChooserAction.SAVE, "_Export", "_Cancel"
        )
        dlg.set_do_overwrite_confirmation(True)
        stem = os.path.splitext(self.gfile.get_basename())[0]
        dlg.set_current_name(stem + ".pdf")
        parent = self.gfile.get_parent()
        if parent and parent.get_path():
            dlg.set_current_folder_file(parent)
        flt = Gtk.FileFilter()
        flt.set_name("PDF documents")
        flt.add_mime_type("application/pdf")
        flt.add_pattern("*.pdf")
        dlg.add_filter(flt)
        target = dlg.get_file() if dlg.run() == Gtk.ResponseType.ACCEPT else None
        dlg.destroy()
        if target is not None:
            self.write_pdf(target)

    def write_pdf(self, target):
        """Write the current document to `target` (a Gio.File) as PDF."""
        path = target.get_path()
        if path and not path.lower().endswith(".pdf"):
            target = Gio.File.new_for_path(path + ".pdf")

        def job(done):
            settings = Gtk.PrintSettings()
            settings.set_printer(PDF_PRINTER)
            settings.set(Gtk.PRINT_SETTINGS_OUTPUT_FILE_FORMAT, "pdf")
            settings.set(Gtk.PRINT_SETTINGS_OUTPUT_URI, target.get_uri())
            op = WebKit2.PrintOperation.new(self.webview)
            op.set_print_settings(settings)
            op.set_page_setup(Gtk.PageSetup())  # locale default paper size
            op.connect("finished", lambda _op: (done(), self.flash(f"Exported {target.get_basename()}")))
            op.connect("failed", lambda _op, err: (done(), self.flash(f"PDF export failed: {err.message}")))
            op.print_()

        self._on_light_page(job)

    def open_external(self, gfile):
        if gfile is None:
            return
        try:
            Gio.AppInfo.launch_default_for_uri(gfile.get_uri(), None)
        except GLib.Error:
            app = Gio.AppInfo.get_default_for_type("text/plain", False)
            if app:
                app.launch([gfile], None)

    def show_in_folder(self):
        if self.gfile is None:
            return
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            bus.call_sync(
                "org.freedesktop.FileManager1",
                "/org/freedesktop/FileManager1",
                "org.freedesktop.FileManager1",
                "ShowItems",
                GLib.Variant("(ass)", ([self.gfile.get_uri()], "")),
                None,
                Gio.DBusCallFlags.NONE,
                2000,
                None,
            )
        except GLib.Error:
            Gio.AppInfo.launch_default_for_uri(self.gfile.get_parent().get_uri(), None)

    def show_shortcuts(self):
        dlg = Gtk.Dialog(title="Keyboard Shortcuts", transient_for=self, modal=True, use_header_bar=True)
        grid = Gtk.Grid(column_spacing=24, row_spacing=8, margin=18)
        for row, (_name, keys, label) in enumerate(SHORTCUTS):
            key_label = Gtk.Label(xalign=0)
            key_label.set_markup(f"<b>{GLib.markup_escape_text(_accel_text(keys))}</b>")
            grid.attach(key_label, 0, row, 1, 1)
            grid.attach(Gtk.Label(label=label, xalign=0), 1, row, 1, 1)
        dlg.get_content_area().add(grid)
        dlg.show_all()
        dlg.connect("response", lambda d, _r: d.destroy())


def _accel_text(keys):
    """Human-readable accelerators, e.g. ['<Ctrl>r', 'F5'] → 'Ctrl+R / F5'.

    Keypad duplicates are skipped since they are just alternative keys.
    """
    labels = []
    for k in keys:
        if "KP_" in k:
            continue
        key, mods = Gtk.accelerator_parse(k)
        text = Gtk.accelerator_get_label(key, mods)
        if text not in labels:
            labels.append(text)
    return " / ".join(labels)
