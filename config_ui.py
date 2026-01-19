"""Tkinter configuration editor for printer settings."""

from __future__ import annotations

import ctypes
import math
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Tuple, Type, Optional
import atexit

from config import settings
from PIL import Image, ImageDraw, ImageTk

from printer.driver import ReceiptPrinter
from printer.template import build_info_page, build_receipt_text

try:
    from utils.winapi_utils import (
        TitleBarColor, 
        TitleBarTextColor, 
        BorderColor, 
        WindowFrame,
        get_window_from_title
    )
except ImportError:
    print("[WARNING] winapi_utils could not be imported; Windows-specific features will be disabled.", file=sys.stderr)
    
    TitleBarColor = None
    TitleBarTextColor = None
    BorderColor = None
    WindowFrame = None
    def get_window_from_title(title: str) -> int:
        return 0

# Palette & sizing tuned for a clean layout that stays within the window
WINDOW_TITLE = "Printer Configuration"
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

MULTILINE_FIELDS = {
    ("LAYOUT", "header_title"),
    ("LAYOUT", "header_description"),
    ("LAYOUT", "receipt_title"),
    ("LAYOUT", "footer_label"),
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
        self._save_btn: ttk.Button | None = None
        self._cancel_btn: ttk.Button | None = None
        self._init_variables()
        self._build_ui()

    def _get_typed_value(self, value: Any, field_type: Type) -> Any:
        """Convert a string value to the specified type."""
        if field_type is bool:
            return bool(value)
        if field_type is int:
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
        return str(value)

    def _get_current_ui_config(self) -> Dict[str, Dict[str, Any]]:
        """Collect current values from all UI variables into a config dictionary."""
        config = {section: {} for section in FIELD_SPECS}
        for (section, key), (var, field_type) in self._variables.items():
            if key == "-": continue
            config[section][key] = self._get_typed_value(var.get(), field_type)
        return config

    def _apply_config_to_ui(self, config: Dict[str, Dict[str, Any]]) -> None:
        """Update UI variables with values from the provided config dictionary."""
        for (section, key), (var, field_type) in self._variables.items():
            if key == "-": continue
            val = config.get(section, {}).get(key, "")
            # Handle None or missing values gracefully
            if val is None:
                val = ""
            
            if field_type is bool:
                var.set(bool(val))
            else:
                var.set(str(val))

    def _check_dirty(self, *args) -> None:
        """Check if any variable differs from the saved data and enable/disable buttons."""
        if not self._save_btn:
            return

        is_dirty = False
        for (section, key), (var, field_type) in self._variables.items():
            if key == "-": continue
            
            current = self._get_typed_value(var.get(), field_type)
            original = self._get_typed_value(self._data.get(section, {}).get(key), field_type)
            
            if current != original:
                is_dirty = True
                break
        
        state = "!disabled" if is_dirty else "disabled"
        self._save_btn.state([state])
        if self._cancel_btn:
            self._cancel_btn.state([state])

    def _configure_window(self) -> None:
        self._root.title(WINDOW_TITLE)
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
        self._root.protocol("WM_DELETE_WINDOW", self._try_close_window)
        
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
                
                
                # key == "-" is skipped above, so we only bind actual fields
                var.trace_add("write", self._check_dirty)
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
            self._create_nav_button(nav_frame, section)

        # Print Test Button at the bottom of sidebar (ADDED)
        test_btn = tk.Button(
            nav_frame,
            text="Print Test",
            font=("Segoe UI", 10, "bold"),
            relief="sunken",
            bd=0,
            width=22,
            padx=12,
            pady=10,
            borderwidth=0,
            anchor="w",
            justify="left",
            fg=NAV_ACTIVE_TEXT,
            bg="#2c3e50",  # Slightly different bg to distinguish
            activebackground="#34495e", 
            activeforeground="#ffffff",
            command=self._print_test,
            cursor="hand2",
        )
        test_btn.pack(side="bottom", fill="x", pady=20)

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
        
        self._save_btn = ttk.Button(footer, text="Save", style="Config.Primary.TButton", command=self._save, cursor="hand2")
        self._save_btn.pack(side="right", padx=(6, 0))
        self._save_btn.state(["disabled"])  # Initially disabled

        self._cancel_btn = ttk.Button(footer, text="Cancel", style="Config.TButton", command=self._revert_changes, cursor="hand2")
        self._cancel_btn.pack(side="right")
        self._cancel_btn.state(["disabled"])  # Initially disabled

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
        style.map("Config.Primary.TButton", 
            background=[("disabled", "#e4e7f2"), ("active", ACCENT_HOVER)], 
            foreground=[("disabled", "#aeb4c8"), ("active", "#ffffff")]
        )
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
        for row, (key, label, field_type) in enumerate(FIELD_SPECS[section]):
            self._create_field_row(self._scroll_inner, section, key, label, field_type, row)

        self._schedule_scrollbar_update()

    def _create_field_row(self, parent: tk.Widget, section: str, key: str, label: str, field_type: Any, row: int) -> None:
        var, _ = self._variables[(section, key)]

        if field_type is bool:
            ttk.Checkbutton(parent, text=label, variable=var, style="Config.TCheckbutton", cursor="hand2") \
                .grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
            return

        if key == "-":
            frame = ttk.Frame(parent, style="Config.Card.TFrame")
            frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(12, 8))
            ttk.Label(frame, text=label, font=TITLE_FONT, style="Config.TLabel").pack(fill="x")
            tk.Frame(frame, height=1, bg=BORDER_COLOR).pack(fill="x", pady=4)
            return

        # Label for standard fields
        ttk.Label(parent, text=label, style="Config.TLabel", width=20, anchor="nw") \
            .grid(row=row, column=0, sticky="nw", pady=(8, 4))

        # 1. Multiline Text
        if (section, key) in MULTILINE_FIELDS:
            txt = tk.Text(
                parent, height=3, font=FONT, bg=FIELD_BG, fg=TEXT_COLOR,
                relief="flat", highlightthickness=1, highlightbackground=BORDER_COLOR,
                highlightcolor=ACCENT, padx=6, pady=6
            )
            txt.grid(row=row, column=1, sticky="ew", pady=4, padx=(12, 0))
            txt.insert("1.0", var.get())

            def on_text_change(event):
                var.set(txt.get("1.0", "end-1c"))
            
            def update_text_from_var(*args):
                if txt.get("1.0", "end-1c") != var.get():
                    txt.delete("1.0", "end")
                    txt.insert("1.0", var.get())

            txt.bind("<KeyRelease>", on_text_change)
            var.trace_add("write", update_text_from_var)
            return

        # 2. File Picker
        picker_cfg = FILE_PICKER_FIELDS.get((section, key))
        if picker_cfg:
            frame = ttk.Frame(parent, style="Config.Card.TFrame")
            frame.grid(row=row, column=1, sticky="ew", pady=4, padx=(12, 0))
            frame.columnconfigure(0, weight=1)
            
            ttk.Entry(frame, textvariable=var, style="Config.TEntry", font=FONT, state="readonly", cursor="arrow") \
                .grid(row=0, column=0, sticky="ew")
                
            cmd = lambda: self._browse_file(var, picker_cfg["title"], picker_cfg["filetypes"])
            ttk.Button(frame, text="Browse", style="Config.TButton", command=cmd, cursor="hand2") \
                .grid(row=0, column=1, padx=(8, 0))
            return

        # 3. Standard Entry
        ttk.Entry(parent, textvariable=var, style="Config.TEntry", font=FONT) \
            .grid(row=row, column=1, sticky="ew", pady=4, padx=(12, 0))

        self._schedule_scrollbar_update()

    def _create_nav_button(self, parent: tk.Widget, section: str) -> None:
        btn = tk.Button(
            parent,
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
        if not messagebox.askyesno("Reset Defaults", "Are you sure you want to reset all settings to defaults?\nThis cannot be undone."):
            return
        self._apply_config_to_ui(settings.get_defaults())

    def _revert_changes(self) -> None:
        """Revert changes to the last saved state."""
        self._apply_config_to_ui(self._data)

    def _save(self) -> None:
        try:
            updated = self._get_current_ui_config()
        except ValueError as exc:
            messagebox.showerror("Invalid Value", f"Please enter valid values for all fields.\n{exc}")
            return

        settings.save_all(updated)
        messagebox.showinfo("Saved", "Configuration updated successfully.")
        
        self._data = updated
        self._check_dirty()
        self._root.focus_set()

    def _try_close_window(self) -> None:
        """Handle window close request, checking for unsaved changes."""
        if self._save_btn and "disabled" not in self._save_btn.state():
            if not messagebox.askyesno("Unsaved Changes", "You have unsaved changes.\nAre you sure you want to exit without saving?"):
                return
        self._root.destroy()
    
    def _print_test(self) -> None:
        """Gather current settings and print a test page simulating a real receipt."""
        try:
            current_config = self._get_current_ui_config()
            printer_cfg = current_config.get("PRINTER", {})
            layout_cfg = current_config.get("LAYOUT", {})

            # Dummy payload simulating a transaction
            dummy_payload = {
                "items": [
                    {"name": "Gasoline 95", "amount": 40.5, "quantity": 30.0},
                    {"name": "Water Bottle", "amount": 10.0, "quantity": 1.0},
                ],
                "total": 1225.0,
                "customer": {
                    "name": "Test Customer",
                    "code": "CUST-0099"
                },
                "points": 120,
                "transection": "TXN-TEST-1234",
            }

            receipt_text = build_receipt_text(dummy_payload, layout_overrides=layout_cfg)

            # Print
            printer = ReceiptPrinter(printer_cfg)
            try:
                # 1. Header Image
                header_image_path = layout_cfg.get("header_image")
                if header_image_path:
                    try:
                        printer.print_image(header_image_path)
                    except Exception as e:
                        print(f"[WARN] Failed to print header image: {e}")

                # 2. Receipt Text
                printer.print_text(receipt_text)

                # 3. Footer Image
                footer_image_path = layout_cfg.get("footer_image")
                if footer_image_path:
                    try:
                        printer.print_image(footer_image_path)
                    except Exception as e:
                        print(f"[WARN] Failed to print footer image: {e}")

                printer.feed(2)
                printer.cut()
                messagebox.showinfo("Success", "Test receipt sent to printer.")
            except Exception as e:
                messagebox.showerror("Print Error", f"Failed to print:\n{e}")
            finally:
                printer.disconnect()
                
        except ValueError as e:
            messagebox.showerror("Configuration Error", f"Invalid printer settings:\n{e}")

    def run(self) -> None:
        self._root.eval('tk::PlaceWindow . center')
        self._root.mainloop()

def _acquire_single_instance_mutex(name: str = "Global\\PrinterConfigMutex") -> Optional[int]:
    """Create a named mutex; return handle if acquired, else None when already running or failed."""
    
    try:
        k32 = ctypes.windll.kernel32
        handle = k32.CreateMutexW(None, False, name)
        if not handle:
            return None
        # ERROR_ALREADY_EXISTS = 183
        already = k32.GetLastError() == 183
        if already:
            k32.CloseHandle(handle)
            return None
        return handle
    except Exception:
        return None
    
def _ensure_single_instance() -> bool:
    """Ensure only a single instance of the config UI is running."""
    
    mutex = _acquire_single_instance_mutex()
    if mutex is None:
        try:
            hwnd = get_window_from_title(WINDOW_TITLE)
            try:
                WindowFrame.foreground(hwnd)
            except Exception:
                pass
        except Exception:
            pass
        return False
    atexit.register(lambda: ctypes.windll.kernel32.ReleaseMutex(mutex) if mutex else None)
    return True

def launch_config_ui() -> None:
    """Launch the Tkinter configuration interface."""
    
    if _ensure_single_instance():
        ui = ConfigUI()
        ui.run()


if __name__ == "__main__":
    launch_config_ui()
