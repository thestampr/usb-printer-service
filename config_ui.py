"""Tkinter configuration editor for printer settings."""
from __future__ import annotations

import ctypes
import math
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Tuple, Type

from config import settings
from PIL import Image, ImageDraw, ImageTk
from utils.winapi_utils import TitleBarColor, TitleBarTextColor, BorderColor

# Palette & sizing tuned for a clean layout that stays within the window
WINDOW_BG = "#f5f6fa"
WINDOW_BORDER = "#3b426e"
CARD_BG = "#ffffff"
NAV_BG = "#1f2432"
ACCENT = "#5565ff"
ACCENT_HOVER = "#6070fe"
NAV_TEXT = "#aeb4c8"
NAV_ACTIVE_TEXT = "#ffffff"
BORDER_COLOR = "#e4e7f2"
FIELD_BG = "#fbfbfe"
TEXT_COLOR = "#1b1d29"
FONT = ("Segoe UI", 12)
TITLE_FONT = ("Segoe UI", 16, "bold")
WINDOW_SIZE = "760x540"

FieldSpec = Tuple[str, str, Type[Any]]

FIELD_SPECS: Dict[str, List[FieldSpec]] = {
    "PRINTER": [
        ("usb_port", "USB Port", str),
        ("usb_name", "USB Name", str),
        ("encoding", "Encoding", str),
        ("line_width", "Line Width", int),
        ("pixel_width", "Pixel Width", int),
    ],
    "LAYOUT": [
        ("header_image", "Header Image", str),
        ("header_title", "Header Title", str),
        ("header_description", "Header Description", str),
        ("receipt_title", "Receipt Title", str),
        ("footer_label", "Footer Label", str),
        ("footer_image", "Footer Image", str),
        ("-", "Advanced", None),
        ("font_family", "Font Family", str),
        ("font_path", "Font Path", str),
        ("font_size", "Font Size", int),
        ("font_size_small", "Small Font Size", int),
        ("line_spacing", "Line Spacing", int),
        ("currency", "Currency", str),
        ("volume_unit", "Volume Unit", str),
    ],
    "SERVICE": [
        ("host", "Host", str),
        ("port", "Port", int),
        ("debug", "Debug Mode", bool),
    ],
}

FILE_PICKER_FIELDS: Dict[Tuple[str, str], Dict[str, Any]] = {
    ("LAYOUT", "font_path"): {
        "title": "Select font file",
        "filetypes": [
            ("Font Files", "*.ttf *.otf *.ttc"),
            ("All Files", "*.*"),
        ],
    },
    ("LAYOUT", "header_image"): {
        "title": "Select header image",
        "filetypes": [
            ("Image Files", "*.png *.jpg *.jpeg *.bmp"),
            ("All Files", "*.*"),
        ],
    },
    ("LAYOUT", "footer_image"): {
        "title": "Select footer image",
        "filetypes": [
            ("Image Files", "*.png *.jpg *.jpeg *.bmp"),
            ("All Files", "*.*"),
        ],
    },
}

def _get_icon(name: str = "") -> Image.Image:
    if not hasattr(_get_icon, "icon_cache"):
        _get_icon.icon_cache = {}

    if name and name in _get_icon.icon_cache:
        return _get_icon.icon_cache[name]

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    center = 32
    inner_radius = 16
    core_radius = 10
    outer_radius = 26
    tooth_width = 4
    body_color = ACCENT
    tooth_color = "#6d79ff"
    hole_color = CARD_BG
    shadow_color = "#121421"

    # Draw outer gear body
    draw.ellipse(
        (center - outer_radius, center - outer_radius, center + outer_radius, center + outer_radius),
        fill=body_color,
    )

    # Add teeth via small polygons around the rim
    for angle in range(0, 360, 30):
        rad = math.radians(angle)
        perp_angle = rad + math.pi / 2
        inner_x = center + math.cos(rad) * inner_radius
        inner_y = center + math.sin(rad) * inner_radius
        outer_x = center + math.cos(rad) * outer_radius
        outer_y = center + math.sin(rad) * outer_radius
        off_x = math.cos(perp_angle) * tooth_width
        off_y = math.sin(perp_angle) * tooth_width
        points = [
            (inner_x + off_x, inner_y + off_y),
            (inner_x - off_x, inner_y - off_y),
            (outer_x - off_x, outer_y - off_y),
            (outer_x + off_x, outer_y + off_y),
        ]
        draw.polygon(points, fill=tooth_color)

    # Slight inner shadow for depth
    draw.ellipse(
        (center - inner_radius, center - inner_radius, center + inner_radius, center + inner_radius),
        fill=shadow_color,
    )

    # Drill the center hole
    draw.ellipse(
        (center - core_radius, center - core_radius, center + core_radius, center + core_radius),
        fill=hole_color,
    )

    _get_icon.icon_cache[name] = img
    return img


class ConfigUI:
    def __init__(self) -> None:
        self._data = settings.get_all()
        self._root = tk.Tk()
        self._icon_image: tk.PhotoImage | None = None
        self._configure_window()
        self._active_section = next(iter(FIELD_SPECS))
        self._variables: Dict[Tuple[str, str], Tuple[tk.Variable, Type[Any]]] = {}
        self._nav_buttons: Dict[str, tk.Button] = {}
        self._scroll_canvas: tk.Canvas | None = None
        self._scroll_inner: ttk.Frame | None = None
        self._scrollbar: ttk.Scrollbar | None = None
        self._scroll_window: int | None = None
        self._section_title: ttk.Label | None = None
        self._init_variables()
        self._build_ui()

    def _configure_window(self) -> None:
        self._root.title("Printer Configuration")
        self._root.configure(bg=WINDOW_BG)
        self._root.geometry(WINDOW_SIZE)
        self._root.minsize(720, 500)
        self._root.resizable(True, True)
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)
        self._apply_dpi_awareness()
        self._icon_image = self._create_window_icon()
        if self._icon_image:
            self._root.iconphoto(True, self._icon_image)
        self._root.after(100, self._on_ready)
        self._root.bind("<Configure>", self._handle_window_configure)
        self._root.bind("<Map>", self._handle_window_state)
        self._root.bind("<Unmap>", self._handle_window_state)
        
    def _on_ready(self) -> None:
        self._apply_titlebar_theme()
        self._apply_border_color()

    def _apply_dpi_awareness(self) -> None:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    def _apply_titlebar_theme(self) -> None:
        if sys.platform != "win32":
            return
        try:
            TitleBarColor.set(self._root, NAV_BG)
            TitleBarTextColor.set(self._root, NAV_ACTIVE_TEXT)
        except Exception:
            pass
        
    def _apply_border_color(self) -> None:
        if sys.platform != "win32":
            return
        try:
            BorderColor.set(self._root, WINDOW_BORDER)
        except Exception:
            pass

    def _create_window_icon(self) -> tk.PhotoImage:
        icon = _get_icon("window_icon")
        return ImageTk.PhotoImage(icon)

    def _handle_window_configure(self, event: tk.Event) -> None:
        if event.widget is self._root:
            self._schedule_scrollbar_update()

    def _handle_window_state(self, _event: tk.Event) -> None:
        self._schedule_scrollbar_update()

    def _handle_scroll_inner_configure(self, _event: tk.Event) -> None:
        if self._scroll_canvas:
            self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))
        self._schedule_scrollbar_update()

    def _handle_canvas_configure(self, _event: tk.Event) -> None:
        if self._scroll_canvas and self._scroll_window is not None:
            self._scroll_canvas.itemconfigure(self._scroll_window, width=self._scroll_canvas.winfo_width())
        self._schedule_scrollbar_update()

    def _schedule_scrollbar_update(self) -> None:
        if self._root:
            self._root.after_idle(self._update_scrollbar_visibility)
        
    def _update_scrollbar_visibility(self) -> None:
        if not self._scroll_canvas or not self._scrollbar:
            return
        canvas_height = self._scroll_canvas.winfo_height()
        content_height = self._scroll_canvas.bbox("all")[3] if self._scroll_canvas.bbox("all") else 0
        if content_height <= canvas_height:
            self._scrollbar.configure(style="Hidden.Scrollbar")
        else:
            self._scrollbar.configure(style="Config.Vertical.TScrollbar")

    def _browse_file(self, target: tk.Variable, title: str, filetypes: List[Tuple[str, str]] | None) -> None:
        selection = filedialog.askopenfilename(
            parent=self._root,
            title=title,
            filetypes=filetypes or [("All Files", "*.*")],
        )
        if selection:
            target.set(selection)

    def _init_variables(self) -> None:
        for section, fields in FIELD_SPECS.items():
            for key, _label, field_type in fields:
                if key == "-": 
                    self._variables[(section, key)] = (tk.StringVar(value=""), type(None))
                    continue
                
                value = self._data.get(section, {}).get(key, "")
                if field_type is bool:
                    var: tk.Variable = tk.BooleanVar(value=bool(value))
                else:
                    var = tk.StringVar(value=str(value))
                self._variables[(section, key)] = (var, field_type)

    def _build_ui(self) -> None:
        self._configure_styles()

        container = ttk.Frame(self._root, padding=0, style="Config.Window.TFrame")
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        nav_frame = tk.Frame(container, bg=NAV_BG, width=190)
        nav_frame.grid(row=0, column=0, sticky="nsew")
        nav_frame.rowconfigure(1, weight=1)

        for section in FIELD_SPECS:
            btn = tk.Button(
                nav_frame,
                text=section.title(),
                font=("Segoe UI", 10),
                relief="sunken",
                bd=0,
                width=22,
                padx=12,
                pady=10,
                borderwidth=0,
                anchor="w",
                justify="left",
                fg=NAV_TEXT,
                bg=NAV_BG,
                activebackground=ACCENT,
                activeforeground=NAV_ACTIVE_TEXT,
                command=lambda s=section: self._select_section(s),
                cursor="hand2",
            )
            btn.pack(fill="x", pady=(0, 6))
            self._nav_buttons[section] = btn

        card = ttk.Frame(container, padding=0, style="Config.Card.TFrame")
        card.grid(row=0, column=1, sticky="nsew")
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)

        header = ttk.Frame(card, padding=(18, 8, 18, 10), style="Config.Card.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        self._section_title = ttk.Label(header, text="", style="Config.Title.TLabel")
        self._section_title.pack(anchor="w")

        scroll_container = ttk.Frame(card, padding=(18, 0, 0, 0), style="Config.Card.TFrame")
        scroll_container.grid(row=1, column=0, sticky="nsew")
        scroll_container.columnconfigure(0, weight=1)
        scroll_container.rowconfigure(0, weight=1)

        self._scroll_canvas = tk.Canvas(
            scroll_container,
            background=CARD_BG,
            highlightthickness=0,
            borderwidth=0,
        )
        self._scroll_canvas.grid(row=0, column=0, sticky="nsew")
        
        def yview(*args: Any) -> None:
            # Clamp top/bottom
            if (args[0] == "moveto" and ((float(args[1]) <= 0 and self._scroll_canvas.yview()[0] <= 0) or
               (float(args[1]) >= 1 and self._scroll_canvas.yview()[1] >= 1))) or \
               (args[0] == "scroll" and ((args[1] == "-1" and self._scroll_canvas.yview()[0] <= 0) or
               (args[1] == "1" and self._scroll_canvas.yview()[1] >= 1))):
                return
            self._scroll_canvas.yview(*args)

        self._scrollbar = ttk.Scrollbar(
            scroll_container,
            orient="vertical",
                command=yview,
            style="Config.Vertical.TScrollbar",
        )
        self._scrollbar.grid(row=0, column=1, sticky="ns", padx=(10, 0))
        self._scroll_canvas.configure(yscrollcommand=self._scrollbar.set)

        self._scroll_inner = ttk.Frame(self._scroll_canvas, style="Config.Card.TFrame")
        self._scroll_window = self._scroll_canvas.create_window((0, 0), window=self._scroll_inner, anchor="nw")
        self._scroll_inner.columnconfigure(1, weight=1)
        self._scroll_inner.bind("<Configure>", self._handle_scroll_inner_configure)
        self._scroll_canvas.bind("<Configure>", self._handle_canvas_configure)
        self._scroll_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        footer = ttk.Frame(card, padding=(20, 10, 20, 18), style="Config.Card.TFrame")
        footer.grid(row=2, column=0, sticky="ew")
        ttk.Button(
            footer,
            text="Reset Default",
            style="Config.TButton",
            command=self._reset_defaults,
            cursor="hand2"
        ).pack(side="left")
        ttk.Button(footer, text="Save", style="Config.Primary.TButton", command=self._save, cursor="hand2").pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Cancel", style="Config.TButton", command=self._root.destroy, cursor="hand2").pack(side="right")

        self._update_nav_styles()
        self._render_section(self._active_section)
        self._schedule_scrollbar_update()
        
    def _configure_styles(self) -> None:
        style = ttk.Style(self._root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Config.Window.TFrame", background=WINDOW_BG)
        style.configure("Config.Card.TFrame", background=CARD_BG)
        style.configure("Config.Title.TLabel", background=CARD_BG, foreground=TEXT_COLOR, font=TITLE_FONT)
        style.configure("Config.TLabel", background=CARD_BG, foreground=TEXT_COLOR, font=FONT)
        style.configure(
            "Config.TEntry",
            font=FONT,
            fieldbackground=FIELD_BG,
            bordercolor=BORDER_COLOR,
            padding=6,
        )
        style.map("Config.TEntry", bordercolor=[("focus", ACCENT)])
        style.configure(
            "Config.TButton",
            font=FONT,
            padding=(16, 6),
            relief="flat",
            borderwidth=0,
            cursor="hand2",
        )
        style.configure(
            "Config.Primary.TButton",
            font=FONT,
            padding=(16, 6),
            background=ACCENT,
            foreground="#ffffff",
            relief="flat",
            borderwidth=0,
            cursor="hand2",
        )
        style.map("Config.Primary.TButton", background=[("active", ACCENT_HOVER)], foreground=[("active", "#ffffff")])
        style.map("Config.Separator.TSeparator", background=[("!disabled", BORDER_COLOR)])
        style.configure("Config.TCheckbutton", background=CARD_BG, font=FONT, relief="flat", borderwidth=0)
        style.map("Config.TCheckbutton", background=[("active", CARD_BG)], foreground=[("active", TEXT_COLOR)])
        style.configure(
            "Config.Vertical.TScrollbar",
            gripcount=0,
            background="#c7cceb",
            troughcolor=CARD_BG,
            bordercolor=CARD_BG,
            darkcolor=CARD_BG,
            lightcolor=CARD_BG,
            arrowsize=10,
            relief="flat",
        )
        style.map("Config.Vertical.TScrollbar", background=[("active", ACCENT)])
        style.layout('Config.Vertical.TScrollbar', [(
            'Vertical.Scrollbar.trough', {
                'children': [(
                    'Vertical.Scrollbar.thumb', {
                        'expand': '1', 'sticky': 'nswe'
                    }
                )],
                'sticky': 'ns'
            }
        )])
        style.configure(
            "Hidden.Scrollbar",
            gripcount=0,
            background=CARD_BG,
            troughcolor=CARD_BG,
            bordercolor=CARD_BG,
            darkcolor=CARD_BG,
            lightcolor=CARD_BG,
            arrowsize=10,
            relief="flat",
        )
        style.map("Hidden.Scrollbar", background=[("active", CARD_BG)])
        style.layout('Hidden.Scrollbar', [(
            'Vertical.Scrollbar.trough', {
                'children': [(
                    'Vertical.Scrollbar.thumb', {
                        'expand': '1', 'sticky': 'nswe'
                    }
                )],
                'sticky': 'ns'
            }
        )])

    def _update_nav_styles(self) -> None:
        for section, btn in self._nav_buttons.items():
            if isinstance(btn, ttk.Button):
                if section == self._active_section:
                    btn.state(["!disabled"])
                    btn.configure(style="Config.Primary.TButton")
                else:
                    btn.state(["!disabled"])
                    btn.configure(style="Config.TButton")
            else:
                if section == self._active_section:
                    btn.configure(bg=ACCENT, fg=NAV_ACTIVE_TEXT)
                else:
                    btn.configure(bg=NAV_BG, fg=NAV_TEXT)

    def _select_section(self, section: str) -> None:
        if section == self._active_section:
            return
        self._active_section = section
        self._update_nav_styles()
        self._render_section(section)

    def _render_section(self, section: str) -> None:
        if not self._scroll_inner or not self._section_title:
            return
        for child in self._scroll_inner.winfo_children():
            child.destroy()

        self._section_title.configure(text=section.title())
        fields = FIELD_SPECS[section]

        for row, (key, label, field_type) in enumerate(fields):
            var, _ = self._variables[(section, key)]
            if field_type is bool:
                check = ttk.Checkbutton(self._scroll_inner, text=label, variable=var, style="Config.TCheckbutton", cursor="hand2")
                check.grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
            elif key == "-":
                sep_frame = ttk.Frame(self._scroll_inner, style="Config.Card.TFrame")
                sep_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(12, 8))
                label = ttk.Label(sep_frame, text=label, font=TITLE_FONT, style="Config.TLabel")
                label.pack(fill="x")
                sep = tk.Frame(sep_frame, height=1, bg=BORDER_COLOR)
                sep.pack(fill="x", pady=4)
            else:
                ttk.Label(self._scroll_inner, text=label, style="Config.TLabel", width=20).grid(row=row, column=0, sticky="w", pady=4)
                picker = FILE_PICKER_FIELDS.get((section, key))
                if picker:
                    field_frame = ttk.Frame(self._scroll_inner, style="Config.Card.TFrame")
                    field_frame.grid(row=row, column=1, sticky="ew", pady=4, padx=(12, 0))
                    field_frame.columnconfigure(0, weight=1)
                    entry = ttk.Entry(field_frame, textvariable=var, style="Config.TEntry", font=FONT, state="readonly", cursor="arrow")
                    entry.grid(row=0, column=0, sticky="ew")
                    browse_cmd = lambda v=var, cfg=picker: [self._browse_file(v, cfg.get("title", "Select File"), cfg.get("filetypes"))]
                    # clear_cmd = lambda v=var: [v.set("")]
                    ttk.Button(
                        field_frame,
                        text="Browse",
                        style="Config.TButton",
                        command=browse_cmd,
                        cursor="hand2",
                    ).grid(row=0, column=1, padx=(8, 0))
                else:
                    entry = ttk.Entry(self._scroll_inner, textvariable=var, style="Config.TEntry", font=FONT)
                    entry.grid(row=row, column=1, sticky="ew", pady=4, padx=(12, 0))

        self._schedule_scrollbar_update()

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self._scroll_canvas:
            # clamp top/bottom
            if (event.delta > 0 and self._scroll_canvas.yview()[0] <= 0) or \
               (event.delta < 0 and self._scroll_canvas.yview()[1] >= 1):
                return
            if event.state & 0x0001:  # Shift key for horizontal scroll
                self._scroll_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
            self._scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _reset_defaults(self) -> None:
        defaults = settings.get_defaults()
        for (section, key), (var, field_type) in self._variables.items():
            value = defaults.get(section, {}).get(key, "")
            if field_type is bool:
                var.set(bool(value))
            else:
                var.set("" if value is None else str(value))

    def _save(self) -> None:
        updated = settings.get_all()
        try:
            for (section, key), (var, field_type) in self._variables.items():
                if key == "-": continue
                value = var.get()
                if field_type is int:
                    value = int(value)
                elif field_type is bool:
                    value = bool(value)
                else:
                    value = str(value)
                updated[section][key] = value
        except ValueError as exc:
            messagebox.showerror("Invalid Value", f"Please enter valid values for all fields.\n{exc}")
            return

        settings.save_all(updated)
        messagebox.showinfo("Saved", "Configuration updated successfully.")
        self._root.destroy()

    def run(self) -> None:
        self._root.eval('tk::PlaceWindow . center')
        self._root.mainloop()


def launch_config_ui() -> None:
    """Launch the Tkinter configuration interface."""
    ui = ConfigUI()
    ui.run()


if __name__ == "__main__":
    launch_config_ui()
