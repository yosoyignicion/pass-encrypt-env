"""Interfaz GTK3: pop-up compacto de desbloqueo y bandeja del sistema."""

from __future__ import annotations

from pathlib import Path

try:  # PyGObject/GTK es opcional: permite importar y testear el núcleo sin GUI.
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk

    HAS_GTK = True
except (ImportError, ValueError):  # pragma: no cover - depende del entorno
    Gdk = GLib = Gtk = None  # type: ignore[assignment]
    HAS_GTK = False

_Base = Gtk.Window if HAS_GTK else object

CSS = b"""
.passenv-card { background: #1e1e2e; }
.passenv-title { color: #cdd6f4; font-weight: 700; font-size: 15px; }
.passenv-sub { color: #9399b2; font-size: 11px; }
.passenv-entry { background: #313244; color: #cdd6f4; border-radius: 8px;
                 border: 1px solid #45475a; padding: 8px 10px; }
.passenv-entry:focus { border-color: #89b4fa; }
.passenv-error { color: #f38ba8; font-size: 11px; }
.passenv-btn { background: #89b4fa; color: #1e1e2e; font-weight: 700;
               border-radius: 8px; padding: 8px 14px; border: none; }
.passenv-btn.secondary { background: #45475a; color: #cdd6f4; font-weight: 500; }
button.passenv-btn:hover { background: #74a0e6; }
"""


def _install_css() -> None:
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    screen = Gdk.Screen.get_default()
    if screen is not None:
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


class UnlockWindow(_Base):
    """Ventana de desbloqueo, no modal y descartable."""

    def __init__(self, on_submit, on_quit):
        super().__init__(title="passenv — desbloquear")
        self._on_submit = on_submit
        self._on_quit = on_quit
        self._busy = False

        self.set_default_size(360, -1)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_keep_above(True)
        self.set_border_width(18)
        self.get_style_context().add_class("passenv-card")
        _install_css()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(box)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.pack_start(header, False, False, 0)

        logo = self._load_logo()
        if logo is not None:
            header.pack_start(logo, False, False, 0)

        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        header.pack_start(titles, True, True, 0)

        title = Gtk.Label(xalign=0)
        title.set_markup("Desbloquear bóveda")
        title.get_style_context().add_class("passenv-title")
        titles.pack_start(title, False, False, 0)

        sub = Gtk.Label(xalign=0)
        sub.set_markup("passencryptenv · contraseña maestra + TOTP")
        sub.get_style_context().add_class("passenv-sub")
        titles.pack_start(sub, False, False, 0)

        self.master = Gtk.Entry()
        self.master.set_visibility(False)
        self.master.set_placeholder_text("Contraseña maestra")
        self.master.get_style_context().add_class("passenv-entry")
        self.master.connect("activate", self._focus_totp)
        box.pack_start(self.master, False, False, 0)

        self.totp = Gtk.Entry()
        self.totp.set_placeholder_text("Código TOTP (6 dígitos)")
        self.totp.set_max_length(6)
        self.totp.get_style_context().add_class("passenv-entry")
        self.totp.connect("activate", lambda _e: self._submit())
        box.pack_start(self.totp, False, False, 0)

        self.error = Gtk.Label(xalign=0)
        self.error.get_style_context().add_class("passenv-error")
        box.pack_start(self.error, False, False, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_halign(Gtk.Align.END)
        box.pack_start(actions, False, False, 0)

        quit_btn = Gtk.Button(label="Más tarde")
        quit_btn.get_style_context().add_class("passenv-btn")
        quit_btn.get_style_context().add_class("secondary")
        quit_btn.connect("clicked", lambda _b: self.hide())
        actions.pack_start(quit_btn, False, False, 0)

        self.unlock_btn = Gtk.Button(label="Desbloquear")
        self.unlock_btn.get_style_context().add_class("passenv-btn")
        self.unlock_btn.connect("clicked", lambda _b: self._submit())
        actions.pack_start(self.unlock_btn, False, False, 0)

        self.connect("delete-event", self._on_delete)

    @staticmethod
    def _load_logo():
        """Carga el logo SVG si está disponible (degrada sin ruido si no)."""
        path = Path(__file__).resolve().parents[2] / "assets" / "logo.svg"
        if not path.exists():
            return None
        try:
            image = Gtk.Image.new_from_file(str(path))
            image.set_pixel_size(44)
            return image
        except Exception:  # noqa: BLE001
            return None

    def _focus_totp(self, _entry=None):
        self.totp.grab_focus()

    def _on_delete(self, *_args):
        self.hide()
        return True

    def show_prompt(self):
        self.flash_error("")
        self.master.set_text("")
        self.totp.set_text("")
        self.show_all()
        self.present_with_time(Gtk.get_current_event_time())
        self.master.grab_focus()

    def flash_error(self, message: str):
        self.error.set_text(message)

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.unlock_btn.set_sensitive(not busy)
        self.master.set_sensitive(not busy)
        self.totp.set_sensitive(not busy)

    def _submit(self):
        if self._busy:
            return
        # Saneamos: el portapapeles suele arrastrar \n/espacios y el Entry los conserva.
        master = self.master.get_text().strip()
        code = "".join(ch for ch in self.totp.get_text() if ch.isdigit())
        if not master:
            self.flash_error("Introduce la contraseña maestra.")
            return
        self._set_busy(True)
        self.flash_error("")

        def work():
            try:
                self._on_submit(master, code)
            except Exception as exc:  # noqa: BLE001
                GLib.idle_add(self._fail, str(exc))
            else:
                GLib.idle_add(self._ok)
            return False

        # El KDF es costoso: lo hacemos fuera del hilo de UI.
        import threading

        threading.Thread(target=work, daemon=True).start()

    def _fail(self, message: str):
        self._set_busy(False)
        self.flash_error(message)
        return False

    def _ok(self):
        self._set_busy(False)
        self.hide()
        return False


def make_indicator(on_lock, on_unlock, on_quit):
    """Indicador de bandeja. Devuelve None si no hay soporte."""
    if not HAS_GTK:
        return None
    try:
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3 as AppIndicator
    except (ValueError, ImportError):
        return None

    indicator = AppIndicator.Indicator.new(
        "passenv", "dialog-password", AppIndicator.IndicatorCategory.APPLICATION_STATUS
    )
    indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)

    menu = Gtk.Menu()
    item_unlock = Gtk.MenuItem(label="Desbloquear…")
    item_unlock.connect("activate", lambda _i: on_unlock())
    item_lock = Gtk.MenuItem(label="Bloquear")
    item_lock.connect("activate", lambda _i: on_lock())
    item_quit = Gtk.MenuItem(label="Salir")
    item_quit.connect("activate", lambda _i: on_quit())
    for item in (item_unlock, item_lock, Gtk.SeparatorMenuItem(), item_quit):
        menu.append(item)
    menu.show_all()
    indicator.set_menu(menu)
    return indicator
