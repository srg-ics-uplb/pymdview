"""Application object and command-line entry point."""

import argparse
import logging
import os
import sys

from pymdview import APP_ID, APP_NAME, PRG_NAME, VERSION


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog=PRG_NAME,
        description="Opens Markdown files in a live-reloading viewer.",
    )
    parser.add_argument("files", nargs="*", metavar="FILE.md")
    parser.add_argument("-v", "--version", action="version", version=f"{PRG_NAME} {VERSION}")
    parser.add_argument("--debug", action="store_true", help="log diagnostics (also: MDVIEW_DEBUG=1)")
    args = parser.parse_args(argv[1:])

    debug = args.debug or os.environ.get("MDVIEW_DEBUG") == "1"
    logging.basicConfig(level=logging.DEBUG if debug else logging.WARNING, format="%(name)s: %(message)s")

    # GTK is imported only now, so --help/--version work without a display and the
    # logging set up above already captures import-time messages from render.py.
    app = _make_app()
    return app.run([argv[0], *args.files])


def _make_app():
    from pymdview.compat import Gio, GLib, Gtk
    from pymdview.shortcuts import accels
    from pymdview.window import ViewerWindow

    class MdViewApp(Gtk.Application):
        def __init__(self):
            super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
            GLib.set_application_name(APP_NAME)
            GLib.set_prgname(PRG_NAME)

        def do_startup(self):
            Gtk.Application.do_startup(self)
            for name, handler in (
                ("quit", self.quit),
                ("new-window", lambda: self.open_in_new_window(None)),
                ("about", self.show_about),
            ):
                action = Gio.SimpleAction.new(name, None)
                action.connect("activate", lambda _a, _p, h=handler: h())
                self.add_action(action)
                keys = accels("app." + name)
                if keys:
                    self.set_accels_for_action("app." + name, keys)

        def do_activate(self):
            win = self.get_active_window()
            if win is None:
                win = ViewerWindow(self)
                win.show_all()
            win.present()

        def do_open(self, files, _n, _hint):
            for f in files:
                self.open_in_new_window(f)

        def open_in_new_window(self, gfile):
            """Open `gfile` in an empty window if there is one, else a new window."""
            if gfile is not None:
                for w in self.get_windows():
                    if isinstance(w, ViewerWindow) and w.gfile is None:
                        w.open_gfile(gfile)
                        w.present()
                        return w
            w = ViewerWindow(self)
            w.show_all()
            if gfile is not None:
                w.open_gfile(gfile)
            w.present()
            return w

        def show_about(self):
            Gtk.AboutDialog(
                transient_for=self.get_active_window(),
                modal=True,
                program_name=APP_NAME,
                version=VERSION,
                logo_icon_name=PRG_NAME,
                comments="A simple Markdown viewer that refreshes as you save.",
                license_type=Gtk.License.MIT_X11,
            ).present()

    return MdViewApp()
