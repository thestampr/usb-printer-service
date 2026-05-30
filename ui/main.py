"""Tkinter configuration editor for printer settings."""

from __future__ import annotations

import atexit
import ctypes
import math
import os
import subprocess
import sys
import threading
import tkinter as tk
from copy import deepcopy
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Any, Literal, Optional

from PIL import Image, ImageDraw, ImageTk

from common.interface import PayloadInfo
from common import updater
from config import settings
from config import dummy
from printer.driver import ReceiptPrinter
from printer.renderer import generate_receipt_image
from ui.layout import *
from ui.theme import *

from .components.slider import Slider
from l10n import LocaleEN, LocaleTH

try:
    from .utils.winapi import (BorderColor, TitleBarColor, TitleBarTextColor,
                               WindowFrame, get_window_from_title)
except ImportError:
    print("[WARNING] winapi_utils could not be imported; Windows-specific features will be disabled.", file=sys.stderr)
    
    BorderColor = None
    TitleBarColor = None
    TitleBarTextColor = None
    WindowFrame = None
    def get_window_from_title(title: str) -> int: return 0

if TYPE_CHECKING:
    from config.settings import Config
    from l10n.abc import Locale

WINDOW_TITLE = "Printer Configuration"


class UI:
    def __init__(self) -> None:
        self._root = tk.Tk()

        self._icon_image: Optional[tk.PhotoImage] = None
        self._variables: dict[tuple[str, str], tuple[tk.Variable, type[Any]]] = {}
        self._image_refs: dict[str, ImageTk.PhotoImage] = {}
        self._nav_buttons: dict[str, tk.Button] = {}
        self._scroll_canvas: Optional[tk.Canvas] = None
        self._scroll_inner: Optional[ttk.Frame] = None
        self._scrollbar: Optional[ttk.Scrollbar] = None
        self._scroll_window: Optional[int] = None
        self._section_title: Optional[ttk.Label] = None
        self._preview_frame: Optional[ttk.Frame] = None
        self._preview_label: Optional[ttk.Label] = None
        self._preview_canvas: Optional[tk.Canvas] = None
        self._preview_scrollbar: Optional[ttk.Scrollbar] = None
        self._preview_scroll_inner: Optional[ttk.Frame] = None
        self._preview_scroll_window: Optional[int] = None
        self._preview_scroll_container: Optional[ttk.Frame] = None
        # When on the DUMMY tab, returns the current (possibly unsaved) editor
        # payload so the preview reflects edits live; None elsewhere.
        self._dummy_preview_payload: Optional[Any] = None
        self._preview_visible_at = 1280
        self._preview_content_width = 440
        self._preview_scrollbar_width = 12
        self._preview_scrollbar_gap = 10
        # Receipt preview locale code: 'en' or 'th'
        self._receipt_locale_var: tk.StringVar = tk.StringVar()
        self._save_btn: Optional[ttk.Button] = None
        self._cancel_btn: Optional[ttk.Button] = None

        self._resize_event_id: Optional[int] = None
        self._cache: dict[str, Any] = {}

        self._data = settings.get_all()
        # Initialize receipt locale from saved settings (persisted in LAYOUT.receipt_locale)
        try:
            saved = self._data.get("LAYOUT", {}).get("receipt_locale", "en")
        except Exception:
            saved = "en"
        self._receipt_locale_var.set(saved)
        self._active_section = next(iter(FIELD_SPECS))
        self._prepare_window()
        self._init_variables()
        self._build()

    @property
    def has_changes(self) -> bool: return self._save_btn and "disabled" not in self._save_btn.state()

    @property
    def section(self) -> str: return self._active_section

    @section.setter
    def section(self, section: str):
        if section == self._active_section: return

        self._active_section = section
        self._update_nav_styles()
        self._build_section(section)


    def _on_ready(self) -> None:
        self._apply_titlebar_theme()
        self._apply_border_color()

    def _on_resize(self, event: tk.Event) -> None:
        if event.widget is not self._root: return
        
        if self._resize_event_id:
            self._root.after_cancel(self._resize_event_id)
        self._resize_event_id = self._root.after(100, self._check_responsive_layout, event)
            
    def _on_state_changes(self, _: tk.Event) -> None:
        self._update_scrollbar_visibility()
        self._check_responsive_layout()

    def _on_closing(self) -> None:
        if self.has_changes:
            confirm = messagebox.askyesno(
                "Unsaved Changes", 
                """
                    You have unsaved changes.
                    Are you sure you want to exit without saving?
                """
            )
            if not confirm: return
        self._root.destroy()


    def _build(self) -> None:
        self._prepare_styles()
        
        def yview(*args: Any) -> None:
            if (args[0] == "moveto" and ((float(args[1]) <= 0 and self._scroll_canvas.yview()[0] <= 0) or
               (float(args[1]) >= 1 and self._scroll_canvas.yview()[1] >= 1))) or \
               (args[0] == "scroll" and ((args[1] == "-1" and self._scroll_canvas.yview()[0] <= 0) or
               (args[1] == "1" and self._scroll_canvas.yview()[1] >= 1))):
                return
            self._scroll_canvas.yview(*args)

        def on_scroll_configure(_: tk.Event) -> None:
            if self._scroll_canvas:
                self._scroll_canvas.configure(scrollregion=self._scroll_canvas.bbox("all"))
            self._update_scrollbar_visibility()

        def on_canvas_configure(_: tk.Event) -> None:
            if self._scroll_canvas and self._scroll_window is not None:
                self._scroll_canvas.itemconfigure(self._scroll_window, width=self._scroll_canvas.winfo_width())
            self._update_scrollbar_visibility()

        def on_mousewheel(event: tk.Event) -> None:
            if self._scroll_canvas:
                if self._is_widget_in_preview(event.widget):
                    return
                if (event.delta > 0 and self._scroll_canvas.yview()[0] <= 0) or \
                (event.delta < 0 and self._scroll_canvas.yview()[1] >= 1):
                    return
                if event.state & 0x0001:  # Shift key
                    return self._scroll_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
                self._scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        container = ttk.Frame(
            self._root, 
            padding=0, 
            style="Config.Window.TFrame"
        )
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        nav_frame = tk.Frame(
            container, 
            bg=NAV_BG, 
            width=190
        )
        nav_frame.grid(row=0, column=0, sticky="nsew")
        nav_frame.rowconfigure(1, weight=1)

        self._build_navbar(nav_frame)

        card = ttk.Frame(
            container, 
            padding=0, 
            style="Config.Card.TFrame"
        )
        card.grid(row=0, column=1, sticky="nsew")
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)

        main_content = ttk.Frame(
            card, 
            style="Config.Card.TFrame"
        )
        main_content.grid(row=0, column=0, sticky="nsew")
        main_content.columnconfigure(0, weight=1)
        main_content.rowconfigure(0, weight=1)

        scroll_container = ttk.Frame(
            main_content, 
            padding=(18, 0, 0, 0), 
            style="Config.Card.TFrame"
        )
        scroll_container.grid(row=0, column=0, sticky="nsew")
        scroll_container.columnconfigure(0, weight=1)
        scroll_container.rowconfigure(1, weight=1)
        
        self._section_title = ttk.Label(
            scroll_container, 
            text="", 
            style="Config.Title.TLabel"
        )
        self._section_title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self._scroll_canvas = tk.Canvas(
            scroll_container,
            background=CARD_BG,
            highlightthickness=0,
            borderwidth=0,
        )
        self._scroll_canvas.grid(row=1, column=0, sticky="nsew")

        self._scrollbar = ttk.Scrollbar(
            scroll_container,
            orient="vertical",
            command=yview,
            style="Config.Vertical.TScrollbar",
        )
        self._scrollbar.grid(row=1, column=1, sticky="ns", padx=(10, 0))
        self._scroll_canvas.configure(yscrollcommand=self._scrollbar.set)

        self._scroll_inner = ttk.Frame(
            self._scroll_canvas, 
            style="Config.Card.TFrame"
        )
        self._scroll_window = self._scroll_canvas.create_window((0, 0), window=self._scroll_inner, anchor="nw")
        self._scroll_inner.columnconfigure(1, weight=1)
        self._scroll_inner.bind("<Configure>", on_scroll_configure)
        self._scroll_canvas.bind("<Configure>", on_canvas_configure)
        self._scroll_canvas.bind_all("<MouseWheel>", on_mousewheel)

        self._right_panel = ttk.Frame(
            main_content, 
            padding=(20, 10, 20, 0), 
            style="Config.Card.TFrame"
        )
        self._right_panel.grid(row=0, column=1, sticky="nsew")
        self._right_panel.grid_columnconfigure(0, weight=1)
        self._right_panel.grid_rowconfigure(1, weight=1)

        footer = ttk.Frame(
            card, 
            padding=(20, 10, 20, 18), 
            style="Config.Card.TFrame"
        )
        footer.grid(row=1, column=0, sticky="ew")
        ttk.Button(
            footer,
            text="Reset Default",
            style="Config.TButton",
            command=self._reset_defaults,
            cursor="hand2"
        ).pack(side="left")
        
        self._save_btn = ttk.Button(
            footer, 
            text="Save", 
            style="Config.Primary.TButton", 
            command=self._save, 
            cursor="hand2"
        )
        self._save_btn.pack(side="right", padx=(6, 0))
        self._save_btn.state(["disabled"])

        self._cancel_btn = ttk.Button(
            footer, 
            text="Cancel", 
            style="Config.TButton", 
            command=self._revert_changes, 
            cursor="hand2"
        )
        self._cancel_btn.pack(side="right")
        self._cancel_btn.state(["disabled"])

        self._update_nav_styles()
        self._build_section(self._active_section)
        self._update_scrollbar_visibility()
        
    def _build_section(self, section: str) -> None:
        if not self._scroll_inner or not self._section_title:
            return

        # Reset any live dummy-preview draft; re-set by _build_dummy_section.
        self._dummy_preview_payload = None

        for child in self._scroll_inner.winfo_children():
            child.destroy()
        
        for child in self._right_panel.winfo_children():
            child.destroy()
            
        self._preview_label = None 
        self._preview_frame = None
        self._preview_canvas = None
        self._preview_scrollbar = None
        self._preview_scroll_inner = None
        self._preview_scroll_window = None
        self._preview_scroll_container = None

        self._section_title.configure(text=section.title())
        for row, (key, label, field_type, *rest) in enumerate(FIELD_SPECS[section]):
            state = rest[0] if rest else None
            self._build_field_row(self._scroll_inner, section, key, label, field_type, state, row)

        if section in ("LAYOUT", "DUMMY"):
            if section == "DUMMY":
                self._build_dummy_section(self._scroll_inner)
            self._build_preview_panel()
            self._root.after_idle(self._update_preview_widget)
        else:
            if self._right_panel.winfo_ismapped():
                self._right_panel.grid_remove()

        self._root.after_idle(self._check_responsive_layout)

    def _build_preview_panel(self) -> None:
        """Build the receipt preview panel (header, locale buttons, scrollable
        canvas, Print Test) into the fixed right panel. Shared by LAYOUT and DUMMY."""

        # Create Preview header and content in Fixed Right Panel
        header_frame = ttk.Frame(self._right_panel, style="Config.Card.TFrame")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(
            header_frame,
            text="Preview",
            font=TITLE_FONT,
            style="Config.Title.TLabel"
        ).grid(row=0, column=0, sticky="w")

        # Receipt language selector (two buttons) to the right of the Preview header
        def _apply_locale_button_styles():
            code = self._receipt_locale_var.get()
            en_style = "Config.Primary.TButton" if code == "en" else "Config.TButton"
            th_style = "Config.Primary.TButton" if code == "th" else "Config.TButton"
            try:
                en_btn.configure(style=en_style)
                th_btn.configure(style=th_style)
            except Exception:
                pass

        def _set_preview_locale(code: str) -> None:
            self._receipt_locale_var.set(code)
            # Persist immediately to settings
            try:
                settings.update_section("LAYOUT", {"receipt_locale": code})
            except Exception:
                pass
            _apply_locale_button_styles()
            self._update_preview_widget()

        en_btn = ttk.Button(
            header_frame,
            text="English",
            style=("Config.Primary.TButton" if self._receipt_locale_var.get() == "en" else "Config.TButton"),
            command=lambda: _set_preview_locale("en"),
            cursor="hand2",
            width=10
        )
        en_btn.grid(row=0, column=1, sticky="e", padx=(8, 4))

        th_btn = ttk.Button(
            header_frame,
            text="ภาษาไทย",
            style=("Config.Primary.TButton" if self._receipt_locale_var.get() == "th" else "Config.TButton"),
            command=lambda: _set_preview_locale("th"),
            cursor="hand2",
            width=10
        )
        th_btn.grid(row=0, column=2, sticky="e")

        self._preview_frame = ttk.Frame(
            self._right_panel,
            style="Config.Card.TFrame"
        )
        self._preview_frame.grid(row=1, column=0, sticky="nsew")
        self._preview_frame.configure(
            width=self._preview_content_width + self._preview_scrollbar_gap + self._preview_scrollbar_width
        )
        self._preview_frame.grid_columnconfigure(0, weight=1)
        self._preview_frame.grid_rowconfigure(0, weight=1)

        preview_scroll_container = ttk.Frame(
            self._preview_frame,
            style="Config.Card.TFrame"
        )
        self._preview_scroll_container = preview_scroll_container
        preview_scroll_container.grid(row=0, column=0, sticky="nsew")
        preview_scroll_container.grid_columnconfigure(0, minsize=self._preview_content_width)
        preview_scroll_container.grid_columnconfigure(1, minsize=self._preview_scrollbar_width)
        preview_scroll_container.grid_rowconfigure(0, weight=1)

        self._preview_canvas = tk.Canvas(
            preview_scroll_container,
            background=CARD_BG,
            highlightthickness=0,
            borderwidth=0,
            width=self._preview_content_width,
        )
        self._preview_canvas.grid(row=0, column=0, sticky="nsew")

        self._preview_scrollbar = ttk.Scrollbar(
            preview_scroll_container,
            orient="vertical",
            command=self._preview_canvas.yview,
            style="Config.Vertical.TScrollbar",
        )
        self._preview_scrollbar.grid(row=0, column=1, sticky="ns", padx=(self._preview_scrollbar_gap, 0))
        self._preview_canvas.configure(yscrollcommand=self._preview_scrollbar.set)

        self._right_panel.grid_columnconfigure(
            0,
            minsize=self._preview_content_width + self._preview_scrollbar_gap + self._preview_scrollbar_width
        )

        self._preview_scroll_inner = ttk.Frame(
            self._preview_canvas,
            style="Config.Card.TFrame"
        )
        self._preview_scroll_window = self._preview_canvas.create_window(
            (0, 0),
            window=self._preview_scroll_inner,
            anchor="nw"
        )

        def on_preview_inner_configure(_: tk.Event) -> None:
            if self._preview_canvas:
                self._preview_canvas.configure(scrollregion=self._preview_canvas.bbox("all"))
            self._update_preview_scrollbar_visibility()

        def on_preview_canvas_configure(_: tk.Event) -> None:
            self._update_preview_scrollbar_visibility()

        def on_preview_mousewheel(event: tk.Event) -> None:
            if not self._preview_canvas:
                return
            delta = int(-1 * (event.delta / 120))
            if delta == 0:
                return

            y0, y1 = self._preview_canvas.yview()
            if (delta < 0 and y0 <= 0) or (delta > 0 and y1 >= 1):
                return

            self._preview_canvas.yview_scroll(delta, "units")

        self._preview_scroll_inner.bind("<Configure>", on_preview_inner_configure)
        self._preview_canvas.bind("<Configure>", on_preview_canvas_configure)
        self._preview_canvas.bind("<MouseWheel>", on_preview_mousewheel)

        self._preview_label = ttk.Label(
            self._preview_scroll_inner,
            text="Loading Preview...",
            style="Config.TLabel",
            background=CARD_BG
        )
        self._preview_label.pack(anchor="n", pady=(0, 50))
        self._preview_label.bind("<MouseWheel>", on_preview_mousewheel)

        btn = ttk.Button(
            self._preview_frame,
            text="Print Test",
            style="Config.Primary.TButton",
            command=self._print_preview,
            cursor="hand2"
        )
        btn.grid(row=1, column=0, sticky="ew", pady=(10, 0))

    # Column sizing shared by the dummy editor's header rows and value rows so
    # the columns line up like a Postman key/value table.
    _DUMMY_KEY_COL = 220
    _DUMMY_NUM_COL = 120
    _DUMMY_REMOVE_COL = 28

    def _build_dummy_section(self, parent: tk.Widget) -> None:
        """Structured (Postman-style) editor for the example payload, section by section."""

        holder = ttk.Frame(parent, style="Config.Card.TFrame")
        holder.grid(row=0, column=0, columnspan=2, sticky="ew", padx=(0, 20))
        holder.columnconfigure(0, weight=1)

        def render(data: dict[str, Any], message: str = "", ok: bool = True) -> None:
            for child in holder.winfo_children():
                child.destroy()

            ttk.Label(
                holder,
                text=(
                    "Edit the example payload used for the live preview and the "
                    "“Print Test” button. Saved to config/temp.dummy.json."
                ),
                style="Config.TLabel",
                wraplength=660,
                justify="left",
            ).pack(anchor="w", pady=(0, 14))

            def refresh_preview(*_) -> None:
                self._update_preview_widget()

            def section_card(title: str, hint: str = "") -> ttk.Frame:
                card = tk.Frame(
                    holder, bg=CARD_BG, highlightthickness=1,
                    highlightbackground=BORDER_COLOR, bd=0,
                )
                card.pack(fill="x", pady=(0, 14))
                inner = ttk.Frame(card, style="Config.Card.TFrame")
                inner.pack(fill="x", padx=14, pady=12)
                top = ttk.Frame(inner, style="Config.Card.TFrame")
                top.pack(fill="x", pady=(0, 2))
                ttk.Label(
                    top, text=title, font=("Segoe UI", 13, "bold"),
                    style="Config.Title.TLabel",
                ).pack(side="left")
                if hint:
                    ttk.Label(
                        top, text=hint, style="Config.TLabel",
                        foreground=NAV_TEXT, font=("Segoe UI", 9),
                    ).pack(side="left", padx=(10, 0))
                return inner

            def remove_control(row_frame: ttk.Frame, column: int, on_click) -> None:
                btn = tk.Label(
                    row_frame, text="✕", bg=CARD_BG, fg=NAV_TEXT,
                    font=("Segoe UI", 10), cursor="hand2",
                )
                btn.grid(row=0, column=column, padx=(8, 0))
                btn.bind("<Enter>", lambda e: btn.configure(fg="#c62828"))
                btn.bind("<Leave>", lambda e: btn.configure(fg=NAV_TEXT))
                btn.bind("<Button-1>", lambda e: on_click())

            # ---- Key/Value table (header_info / footer_info) ----
            def kv_card(title: str, hint: str, initial: dict[str, Any]):
                inner = section_card(title, hint)
                rows: list[tuple[ttk.Frame, tk.StringVar, tk.StringVar]] = []

                hdr = ttk.Frame(inner, style="Config.Card.TFrame")
                hdr.pack(fill="x", pady=(8, 2))
                hdr.columnconfigure(0, minsize=self._DUMMY_KEY_COL)
                hdr.columnconfigure(1, weight=1)
                hdr.columnconfigure(2, minsize=self._DUMMY_REMOVE_COL)
                ttk.Label(hdr, text="KEY", style="Config.TLabel", foreground=NAV_TEXT,
                          font=("Segoe UI", 8)).grid(row=0, column=0, sticky="w")
                ttk.Label(hdr, text="VALUE", style="Config.TLabel", foreground=NAV_TEXT,
                          font=("Segoe UI", 8)).grid(row=0, column=1, sticky="w")

                body = ttk.Frame(inner, style="Config.Card.TFrame")
                body.pack(fill="x")

                def add_row(key: str = "", value: str = "") -> None:
                    rf = ttk.Frame(body, style="Config.Card.TFrame")
                    rf.pack(fill="x", pady=2)
                    rf.columnconfigure(0, minsize=self._DUMMY_KEY_COL)
                    rf.columnconfigure(1, weight=1)
                    rf.columnconfigure(2, minsize=self._DUMMY_REMOVE_COL)
                    kvar = tk.StringVar(value=key)
                    vvar = tk.StringVar(value=value)
                    ttk.Entry(rf, textvariable=kvar, style="Config.TEntry", font=FONT).grid(
                        row=0, column=0, sticky="ew", padx=(0, 8))
                    ttk.Entry(rf, textvariable=vvar, style="Config.TEntry", font=FONT).grid(
                        row=0, column=1, sticky="ew")
                    kvar.trace_add("write", refresh_preview)
                    vvar.trace_add("write", refresh_preview)
                    entry = (rf, kvar, vvar)
                    rows.append(entry)

                    def remove() -> None:
                        if entry in rows:
                            rows.remove(entry)
                        rf.destroy()
                        refresh_preview()

                    remove_control(rf, 2, remove)

                for k, v in initial.items():
                    add_row(str(k), str(v))

                ttk.Button(inner, text="+ Add Field", style="Config.TButton",
                           command=lambda: add_row(), cursor="hand2").pack(anchor="w", pady=(8, 0))

                def collect() -> dict[str, str]:
                    out: dict[str, str] = {}
                    for _, kvar, vvar in rows:
                        key = kvar.get().strip()
                        if key:
                            out[key] = vvar.get()
                    return out

                return collect

            # ---- Items table ----
            def items_card(initial_items: list[dict[str, Any]]):
                inner = section_card("Items", "name · price/unit · quantity")
                rows: list[tuple[ttk.Frame, tk.StringVar, tk.StringVar, tk.StringVar]] = []

                hdr = ttk.Frame(inner, style="Config.Card.TFrame")
                hdr.pack(fill="x", pady=(8, 2))
                hdr.columnconfigure(0, weight=1)
                hdr.columnconfigure(1, minsize=self._DUMMY_NUM_COL)
                hdr.columnconfigure(2, minsize=self._DUMMY_NUM_COL)
                hdr.columnconfigure(3, minsize=self._DUMMY_REMOVE_COL)
                ttk.Label(hdr, text="NAME", style="Config.TLabel", foreground=NAV_TEXT,
                          font=("Segoe UI", 8)).grid(row=0, column=0, sticky="w")
                ttk.Label(hdr, text="AMOUNT", style="Config.TLabel", foreground=NAV_TEXT,
                          font=("Segoe UI", 8)).grid(row=0, column=1, sticky="w", padx=(8, 0))
                ttk.Label(hdr, text="QTY", style="Config.TLabel", foreground=NAV_TEXT,
                          font=("Segoe UI", 8)).grid(row=0, column=2, sticky="w", padx=(8, 0))

                body = ttk.Frame(inner, style="Config.Card.TFrame")
                body.pack(fill="x")

                def add_item(name: str = "", amount: str = "", quantity: str = "") -> None:
                    rf = ttk.Frame(body, style="Config.Card.TFrame")
                    rf.pack(fill="x", pady=2)
                    rf.columnconfigure(0, weight=1)
                    rf.columnconfigure(1, minsize=self._DUMMY_NUM_COL)
                    rf.columnconfigure(2, minsize=self._DUMMY_NUM_COL)
                    rf.columnconfigure(3, minsize=self._DUMMY_REMOVE_COL)
                    nvar = tk.StringVar(value=name)
                    avar = tk.StringVar(value=amount)
                    qvar = tk.StringVar(value=quantity)
                    ttk.Entry(rf, textvariable=nvar, style="Config.TEntry", font=FONT).grid(
                        row=0, column=0, sticky="ew")
                    ttk.Entry(rf, textvariable=avar, style="Config.TEntry", font=FONT,
                              justify="right").grid(row=0, column=1, sticky="ew", padx=(8, 0))
                    ttk.Entry(rf, textvariable=qvar, style="Config.TEntry", font=FONT,
                              justify="right").grid(row=0, column=2, sticky="ew", padx=(8, 0))
                    nvar.trace_add("write", refresh_preview)
                    avar.trace_add("write", refresh_preview)
                    qvar.trace_add("write", refresh_preview)
                    entry = (rf, nvar, avar, qvar)
                    rows.append(entry)

                    def remove() -> None:
                        if entry in rows:
                            rows.remove(entry)
                        rf.destroy()
                        refresh_preview()

                    remove_control(rf, 3, remove)

                for item in initial_items:
                    add_item(
                        str(item.get("name", "")),
                        _num_str(item.get("amount")),
                        _num_str(item.get("quantity")),
                    )

                ttk.Button(inner, text="+ Add Item", style="Config.TButton",
                           command=lambda: add_item(), cursor="hand2").pack(anchor="w", pady=(8, 0))

                def collect() -> list[dict[str, str]]:
                    out: list[dict[str, str]] = []
                    for _, nvar, avar, qvar in rows:
                        name = nvar.get().strip()
                        if not name:
                            continue
                        out.append({
                            "name": name,
                            "amount": avar.get().strip(),
                            "quantity": qvar.get().strip(),
                        })
                    return out

                return collect

            # ---- Transaction info (fixed numeric keys) ----
            def transaction_card(initial: dict[str, Any]):
                inner = section_card("Transaction Info", "leave blank to auto-calculate")
                tvars: dict[str, tk.StringVar] = {}
                body = ttk.Frame(inner, style="Config.Card.TFrame")
                body.pack(fill="x", pady=(8, 0))
                for key, label in (("received", "Received"), ("change", "Change"),
                                   ("discount", "Discount"), ("total", "Total")):
                    rf = ttk.Frame(body, style="Config.Card.TFrame")
                    rf.pack(fill="x", pady=2)
                    rf.columnconfigure(0, minsize=self._DUMMY_KEY_COL)
                    rf.columnconfigure(1, weight=1)
                    ttk.Label(rf, text=label, style="Config.TLabel", font=FONT).grid(
                        row=0, column=0, sticky="w")
                    var = tk.StringVar(value=_num_str(initial.get(key)))
                    ttk.Entry(rf, textvariable=var, style="Config.TEntry", font=FONT,
                              justify="right").grid(row=0, column=1, sticky="ew")
                    var.trace_add("write", refresh_preview)
                    tvars[key] = var

                def collect() -> dict[str, str]:
                    out: dict[str, str] = {}
                    for key, var in tvars.items():
                        val = var.get().strip()
                        if val:
                            out[key] = val
                    return out

                return collect

            # ---- Top-level receipt fields (rfid / info-title) ----
            def receipt_card(rfid_value: str, info_title_value: str):
                inner = section_card("Receipt", "RFID (top-left) · info title (after header)")
                fields: dict[str, tk.StringVar] = {}
                body = ttk.Frame(inner, style="Config.Card.TFrame")
                body.pack(fill="x", pady=(8, 0))
                for key, label, value in (("rfid", "RFID", rfid_value),
                                          ("info-title", "Info Title", info_title_value)):
                    rf = ttk.Frame(body, style="Config.Card.TFrame")
                    rf.pack(fill="x", pady=2)
                    rf.columnconfigure(0, minsize=self._DUMMY_KEY_COL)
                    rf.columnconfigure(1, weight=1)
                    ttk.Label(rf, text=label, style="Config.TLabel", font=FONT).grid(
                        row=0, column=0, sticky="w")
                    var = tk.StringVar(value=value)
                    ttk.Entry(rf, textvariable=var, style="Config.TEntry", font=FONT).grid(
                        row=0, column=1, sticky="ew")
                    var.trace_add("write", refresh_preview)
                    fields[key] = var

                def collect() -> dict[str, str]:
                    out: dict[str, str] = {}
                    for key, var in fields.items():
                        if var.get().strip():
                            out[key] = var.get()
                    return out

                return collect

            receipt_collect = receipt_card(
                str(data.get("rfid", "") or ""),
                str(data.get("info-title", "") or ""),
            )
            header_collect = kv_card("Header Info", "printed above the items", data.get("header_info", {}) or {})
            items_collect = items_card(data.get("items", []) or [])
            footer_collect = kv_card("Footer Info", "printed below the total", data.get("footer_info", {}) or {})
            tx_collect = transaction_card(data.get("transaction_info", {}) or {})

            def build_draft_payload() -> dict[str, Any]:
                """Best-effort payload from the current editor state for live preview.

                Tolerant of partial input: rows with non-numeric amount/quantity (or
                blank name) are skipped so the preview never errors mid-edit.
                """
                payload: dict[str, Any] = dict(receipt_collect())
                header = header_collect()
                if header:
                    payload["header_info"] = header
                items: list[dict[str, Any]] = []
                for raw in items_collect():
                    try:
                        items.append({
                            "name": raw["name"],
                            "amount": float(raw["amount"]),
                            "quantity": float(raw["quantity"]),
                        })
                    except ValueError:
                        continue
                payload["items"] = items
                footer = footer_collect()
                if footer:
                    payload["footer_info"] = footer
                transaction: dict[str, float] = {}
                for key, val in tx_collect().items():
                    try:
                        transaction[key] = float(val)
                    except ValueError:
                        continue
                if transaction:
                    payload["transaction_info"] = transaction
                return payload

            # Expose the live draft so the preview reflects unsaved edits.
            self._dummy_preview_payload = build_draft_payload

            status = ttk.Label(holder, text=message, style="Config.TLabel", font=("Segoe UI", 9))
            status.pack(anchor="w", pady=(4, 4))
            if message:
                status.configure(foreground=("#2e7d32" if ok else "#c62828"))

            def set_status(msg: str, is_ok: bool) -> None:
                status.configure(text=msg, foreground=("#2e7d32" if is_ok else "#c62828"))

            def on_save() -> None:
                payload: dict[str, Any] = dict(receipt_collect())

                header = header_collect()
                if header:
                    payload["header_info"] = header

                items: list[dict[str, Any]] = []
                for raw in items_collect():
                    try:
                        amount = float(raw["amount"])
                        quantity = float(raw["quantity"])
                    except ValueError:
                        set_status(f"Item “{raw['name']}” needs a numeric amount and quantity.", False)
                        return
                    items.append({"name": raw["name"], "amount": amount, "quantity": quantity})
                if not items:
                    set_status("Add at least one item with a name, amount and quantity.", False)
                    return
                payload["items"] = items

                footer = footer_collect()
                if footer:
                    payload["footer_info"] = footer

                transaction: dict[str, float] = {}
                for key, val in tx_collect().items():
                    try:
                        transaction[key] = float(val)
                    except ValueError:
                        set_status(f"Transaction “{key}” must be a number.", False)
                        return
                if transaction:
                    payload["transaction_info"] = transaction

                try:
                    PayloadInfo.from_dict(deepcopy(payload))
                except Exception as exc:
                    set_status(f"Invalid payload: {exc}", False)
                    return
                try:
                    dummy.save(payload)
                except OSError as exc:
                    set_status(f"Could not save: {exc}", False)
                    return
                set_status("Saved to config/temp.dummy.json.", True)
                # Refresh the receipt preview with the newly saved payload.
                self._update_preview_widget()

            btns = ttk.Frame(holder, style="Config.Card.TFrame")
            btns.pack(anchor="w", pady=(4, 0))
            ttk.Button(btns, text="Save Dummy", style="Config.Primary.TButton",
                       command=on_save, cursor="hand2").pack(side="left")
            ttk.Button(btns, text="Reset to Default", style="Config.TButton",
                       command=lambda: render(dummy.get_defaults(),
                                              "Loaded defaults — click Save Dummy to apply.", True),
                       cursor="hand2").pack(side="left", padx=(8, 0))
            ttk.Button(btns, text="Reload from File", style="Config.TButton",
                       command=lambda: render(dummy.load(), "Reloaded from file.", True),
                       cursor="hand2").pack(side="left", padx=(8, 0))

            # Reflect the (re)rendered editor state in the preview. No-op on the
            # initial build (the preview label is created afterwards); meaningful
            # for Reset/Reload which re-render while the preview already exists.
            self._update_preview_widget()

        render(dummy.load())

    def _build_field_row(
        self, 
        parent: tk.Widget, 
        section: str, 
        key: str, 
        label: str, 
        field_type: Any, 
        state: Optional[int],
        row: int
    ) -> None:
        var, _ = self._variables[(section, key)]

        # build toggle switch
        if field_type is bool:
            ttk.Checkbutton(
                parent, 
                text=f"  {label}", 
                variable=var, 
                style="Custom.TCheckbutton", 
                cursor="hand2"
            ).grid(row=row, column=1, columnspan=2, sticky="w", padx=(12, 0))
            return

        if key.endswith("_scale"): return

        # build button
        if field_type is callable:
            # get gobal function by name
            cmd = globals().get(key)

            is_primary = False
            if state is not None:
                is_primary = (state == 1)

            ttk.Button(
                parent, 
                text=label, 
                style="Config.Primary.TButton" if is_primary else "Config.TButton", 
                command=cmd, 
                cursor="hand2"
            ).grid(row=row, column=1, sticky="w", pady=4, padx=(12, 0))
            return

        # build separator or spacer
        if key == "-":
            frame = ttk.Frame(
                parent, 
                style="Config.Card.TFrame"
            )
            frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(12, 8))
            if label: 
                ttk.Label(
                    frame, 
                    text=label, 
                    font=TITLE_FONT, 
                    style="Config.TLabel"
                ).pack(fill="x")
            tk.Frame(
                frame, 
                height=1, 
                bg=BORDER_COLOR
            ).pack(fill="x", pady=4)
            return
        
        # build empty spacer
        if key == " ":
            tk.Frame(
                parent, 
                height=40, 
                bg=CARD_BG
            ).grid(row=row, column=0, columnspan=2)
            return

        # build label + input
        ttk.Label(
            parent, 
            text=label, 
            style="Config.TLabel", 
            width=20, 
            anchor="nw"
        ).grid(row=row, column=0, sticky="nw", pady=(8, 4))
            
        if (section, key) in IMAGE_FIELDS:
            self._build_image_input(parent, section, key, row)
            return
            
        if (section, key) in SCALE_FIELDS:
            f_min, f_max = 8, 80
            if key == "line_spacing": f_min, f_max = 0, 100
                
            self._build_slider_input(parent, var, row, from_=f_min, to=f_max)
            return

        if (section, key) in CHOICE_FIELDS:
            self._build_choice_input(parent, section, key, var, row)
            return

        if (section, key) in MULTILINE_FIELDS:
            lines = str(var.get()).splitlines()

            txt_container = ttk.Frame(parent, style="Config.Card.TFrame")
            txt_container.grid(row=row, column=1, sticky="ew", pady=4, padx=(12, 0))
            txt_container.columnconfigure(0, weight=1)

            txt = tk.Text(
                txt_container,
                height=max(3, len(lines)),
                font=FONT,
                bg=FIELD_BG,
                fg=TEXT_COLOR,
                relief="flat",
                highlightthickness=1,
                highlightbackground=BORDER_COLOR,
                highlightcolor=ACCENT,
                padx=6,
                pady=6,
                wrap="word",
            )
            txt.grid(row=0, column=0, sticky="ew")
            txt.insert("1.0", var.get())

            # Resize grip
            _grip_drag: dict[str, Any] = {}
            grip = tk.Canvas(
                txt_container,
                width=16,
                height=10,
                bg=CARD_BG,
                highlightthickness=0,
                cursor="sb_v_double_arrow",
            )
            grip.grid(row=1, column=0, sticky="e")
            for gy in (3, 6):
                grip.create_line(4, gy, 13, gy, fill=BORDER_COLOR, width=1)

            def on_grip_press(e: tk.Event) -> None:
                _grip_drag["start_y"] = e.y_root
                _grip_drag["start_h"] = int(txt.cget("height"))
                # Capture line height once at press time so it stays stable during drag
                _grip_drag["line_h"] = txt.winfo_reqheight() / max(int(txt.cget("height")), 1)

            def on_grip_drag(e: tk.Event) -> None:
                line_h = _grip_drag.get("line_h", 0)
                if line_h <= 0:
                    return
                dy = e.y_root - _grip_drag["start_y"]
                new_h = max(1, round(_grip_drag["start_h"] + dy / line_h))
                if new_h != int(txt.cget("height")):
                    txt.configure(height=new_h)

            grip.bind("<ButtonPress-1>", on_grip_press)
            grip.bind("<B1-Motion>", on_grip_drag)

            def on_text_change(event):
                var.set(txt.get("1.0", "end-1c"))

            def update_text_from_var(*args):
                try:
                    if not txt.winfo_exists():
                        return
                    if txt.get("1.0", "end-1c") != var.get():
                        txt.delete("1.0", "end")
                        txt.insert("1.0", var.get())
                except Exception:
                    pass

            txt.bind("<KeyRelease>", on_text_change)
            var.trace_add("write", update_text_from_var)
            return

        picker_cfg = FILE_PICKER_FIELDS.get((section, key))
        if picker_cfg:
            frame = ttk.Frame(
                parent, 
                style="Config.Card.TFrame"
            )
            frame.grid(row=row, column=1, sticky="ew", pady=4, padx=(12, 0))
            frame.columnconfigure(0, weight=1)
            
            ttk.Entry(
                frame, 
                textvariable=var, 
                style="Config.TEntry", 
                font=FONT, 
                state="readonly", 
                cursor="arrow"
            ).grid(row=0, column=0, sticky="ew")
                
            cmd = lambda: self._browse_file(var, picker_cfg["title"], picker_cfg["filetypes"])
            ttk.Button(
                frame, 
                text="Browse", 
                style="Config.TButton", 
                command=cmd, 
                cursor="hand2"
            ).grid(row=0, column=1, padx=(8, 0))
            return

        ttk.Entry( # Fallback Text input
            parent, 
            textvariable=var, 
            style="Config.TEntry", 
            font=FONT
        ).grid(row=row, column=1, sticky="ew", pady=4, padx=(12, 0))

    def _build_image_input(
        self, 
        parent: tk.Widget, 
        section: str, 
        key: str, 
        row: int
    ) -> None:
        """Create a visual image picker with responsive 1:1 preview (max 300px)."""
        
        var, _ = self._variables[(section, key)]
        
        container = ttk.Frame(
            parent, 
            style="Config.Card.TFrame"
        )
        container.grid(row=row, column=1, sticky="ew", pady=4, padx=(12, 0))
        
        init_size = 120
        MAX_PREVIEW_SIZE = 300
        
        canvas = tk.Canvas(
            container, 
            width=init_size, 
            height=init_size, 
            bg=FIELD_BG, 
            highlightthickness=1, 
            highlightbackground=BORDER_COLOR,
            cursor="hand2"
        )
        canvas.pack(side="left", anchor="n")
        
        controls_frame = ttk.Frame(
            container, 
            style="Config.Card.TFrame"
        )
        controls_frame.pack(side="left", fill="both", expand=True, padx=(12, 0), anchor="n")

        btns_frame = ttk.Frame(
            controls_frame, 
            style="Config.Card.TFrame"
        )
        btns_frame.pack(side="top", fill="x", anchor="n")

        def on_browse():
            picker_cfg = FILE_PICKER_FIELDS.get((section, key))
            if picker_cfg:
                self._browse_file(var, picker_cfg["title"], picker_cfg["filetypes"])

        ttk.Button(
            btns_frame, 
            text="Browse...", 
            style="Config.TButton", 
            command=on_browse, 
            cursor="hand2", 
            width=12
        ).pack(anchor="w", pady=(0, 4))
        ttk.Button(
            btns_frame, 
            text="Clear", 
            style="Config.TButton", 
            command=lambda: var.set(""), 
            cursor="hand2", width=12
        ).pack(anchor="w", pady=(0, 8))
            
        scale_key = f"{key}_scale"
        if (section, scale_key) in self._variables:
            scale_var, _ = self._variables[(section, scale_key)]
            
            scale_frame = ttk.Frame(
                controls_frame, 
                style="Config.Card.TFrame"
            )
            scale_frame.pack(side="bottom", fill="x", anchor="s", pady=(8, 0))
            
            ttk.Label(
                scale_frame, 
                text="Image Scale", 
                style="Config.TLabel", 
                font=FONT
            ).pack(anchor="w", pady=(0, 2))
            
            s_row = ttk.Frame(
                scale_frame, 
                style="Config.Card.TFrame"
            )
            s_row.pack(fill="x")
            
            ttk.Label(
                s_row, 
                text="%", 
                style="Config.TLabel"
            ).pack(side="right", padx=(4, 0))
            
            vcmd = (s_row.register(_validate_digits), "%P")
            entry = ttk.Entry(
                s_row, 
                textvariable=scale_var, 
                width=4, 
                justify="center", 
                font=FONT,
                style="Config.TEntry", 
                validate="key", 
                validatecommand=vcmd
            )
            entry.pack(side="right")

            try:
                curr = int(scale_var.get())
            except (ValueError, TypeError):
                curr = 100
                scale_var.set(100)

            scale = Slider(
                s_row, 
                from_=0, 
                to=100, 
                variable=scale_var, 
                height=30, 
                bg=CARD_BG,
                cursor="hand2"
            )
            scale.pack(side="left", fill="x", expand=True, padx=(0, 10))
            
            def validate_img_scale(event=None):
                try:
                    val_str = entry.get().strip()
                    if not val_str:
                        val = 100
                    else:
                        val = int(val_str)
                    
                    if val > 100: val = 100
                    elif val < 0: val = 0
                    
                    if scale_var.get() != str(val):
                        scale_var.set(val)
                    else:
                        entry.delete(0, "end")
                        entry.insert(0, str(val))
                        
                    self._update_preview_widget()
                except (ValueError, TypeError):
                    entry.delete(0, "end")
                    entry.insert(0, str(scale_var.get()))

            entry.bind("<FocusOut>", validate_img_scale)
            entry.bind("<Return>", validate_img_scale)
            
        path_frame = ttk.Frame(
            controls_frame, 
            style="Config.Card.TFrame"
        )
        path_frame.pack(anchor="w", pady=(4, 0))
        
        lbl_path = ttk.Label(
            path_frame, 
            text="", 
            style="Config.TLabel", 
            foreground="#a0a0a0",
            font=("Segoe UI", 8)
        )
        lbl_path.pack(anchor="w")
        
        btn_open_folder = ttk.Label(
            path_frame,
            text="Open in folder",
            style="Config.TLabel",
            foreground=ACCENT,
            font=("Segoe UI", 8),
            cursor="hand2"
        )
        
        def open_folder(e):
            path = var.get()
            if path and os.path.exists(path):
                try:
                    full_path = os.path.abspath(path)
                    subprocess.Popen(f'explorer /select,"{full_path}"')
                except Exception:
                    pass

        
        def on_enter(e):
            btn_open_folder.configure(font=("Segoe UI", 8, "underline"))
        
        def on_leave(e):
            btn_open_folder.configure(font=("Segoe UI", 8))
        
        btn_open_folder.bind("<Enter>", on_enter)
        btn_open_folder.bind("<Leave>", on_leave)
        btn_open_folder.bind("<Button-1>", open_folder)
            
        lbl_hint = ttk.Label(
            controls_frame, 
            text="No image selected", 
            style="Config.TLabel", 
            foreground=NAV_TEXT,
            font=("Segoe UI", 9)
        )
        lbl_hint.pack(anchor="w", pady=(24, 0))

        def update_preview(*args) -> None:
            try:
                if not canvas.winfo_exists(): return
            except Exception:
                return

            path = var.get()
            self._image_refs.pop(key, None)
            canvas.delete("all")
            
            if path:
                display_path = path
                if len(path) > 80:
                    display_path = "..." + path[-37:]
                lbl_path.configure(text=display_path)
                btn_open_folder.pack(anchor="w", pady=(2, 0))
            else:
                lbl_path.configure(text="")
                btn_open_folder.pack_forget()
            
            w = int(canvas.cget("width"))
            h = int(canvas.cget("height"))
            
            if not path:
                canvas.create_text(
                    w//2, h//2, 
                    text="No Image", 
                    fill=NAV_TEXT, 
                    font=("Segoe UI", 10)
                )
                lbl_hint.configure(text="No image selected")
                return
            
            try:
                img = Image.open(path)
                orig_w, orig_h = img.size
                
                img.thumbnail((w, h), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._image_refs[key] = photo
                
                x = (w - photo.width()) // 2
                y = (h - photo.height()) // 2
                canvas.create_image(x, y, image=photo, anchor="nw")
                lbl_hint.configure(text=f"{orig_w}x{orig_h} px")
            except Exception:
                canvas.create_text(
                    w//2, h//2, 
                    text="Invalid\nImage", 
                    justify="center",
                    fill="red", 
                    font=("Segoe UI", 10)
                )
                lbl_hint.configure(text="Error loading image")

        update_preview()
        var.trace_add("write", update_preview)
        canvas.bind("<Button-1>", lambda e: on_browse())

        def on_resize(event: tk.Event) -> None:
            available_w = event.width - 150 
            new_size = max(120, min(available_w, MAX_PREVIEW_SIZE)) # Clamp size 120 to 300
            
            current_w = int(canvas.cget("width"))
            if abs(new_size - current_w) > 5:
                canvas.configure(width=new_size, height=new_size)
                update_preview()

        container.bind("<Configure>", on_resize)

    def _build_navbar(self, parent: tk.Widget) -> None:
        for section in FIELD_SPECS:
            self._build_nav_button(parent, section)

        # Divider + "Check for Updates" directly under the section nav
        tk.Frame(parent, bg="#333a4d", height=1).pack(fill="x", padx=16, pady=(6, 8))
        self._build_update_button(parent)

        # Spacer
        tk.Frame(parent, bg=NAV_BG).pack(fill="both", expand=True)

        # Version label (bottom-most)
        self._build_version_label(parent)

        # Inline "Docs • Github" links with a divider above (separates footer from nav)
        self._build_footer_links(parent)

    def _build_version_label(self, parent: tk.Widget) -> None:
        """Tiny, grey current-version label pinned to the very bottom of the nav."""
        try:
            version = updater.get_current_version()
        except Exception:
            version = ""

        tk.Label(
            parent,
            text=f"v{version}" if version else "",
            font=("Segoe UI", 8),
            fg=NAV_TEXT,
            bg=NAV_BG,
        ).pack(side="bottom", pady=(0, 8))

    def _build_nav_button(
        self, 
        parent: tk.Widget, 
        section: str
    ) -> None:
        def set_section() -> None: self.section = section

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
            command=lambda: set_section(),
            cursor="hand2",
        )
        btn.pack(fill="x", pady=(0, 6))
        self._nav_buttons[section] = btn

    def _build_footer_links(self, parent: tk.Widget) -> None:
        """Inline 'Docs • Github' hover-underline links with a divider above."""

        container = tk.Frame(parent, bg=NAV_BG)
        container.pack(side="bottom", fill="x", pady=(0, 12))

        # Divider to visually separate the footer links from the nav above.
        tk.Frame(container, bg="#333a4d", height=1).pack(fill="x", padx=16, pady=(0, 10))

        row = tk.Frame(container, bg=NAV_BG)
        row.pack()  # centered horizontally

        self._build_text_link(row, "Docs", open_docs)
        tk.Label(
            row, text="•", font=("Segoe UI", 9), fg=NAV_TEXT, bg=NAV_BG,
        ).pack(side="left", padx=8)
        self._build_text_link(row, "Github", open_github_repo)

    def _build_text_link(self, parent: tk.Widget, text: str, command) -> None:
        """A small grey hover-underline clickable text link for the nav footer."""

        lbl = tk.Label(
            parent, text=text, font=("Segoe UI", 9),
            fg=NAV_TEXT, bg=NAV_BG, cursor="hand2",
        )
        lbl.pack(side="left")
        lbl.bind("<Enter>", lambda e: lbl.configure(font=("Segoe UI", 9, "underline"), fg=NAV_ACTIVE_TEXT))
        lbl.bind("<Leave>", lambda e: lbl.configure(font=("Segoe UI", 9), fg=NAV_TEXT))
        lbl.bind("<ButtonRelease-1>", lambda e: command())

    def _build_update_button(
        self,
        parent: tk.Widget
    ) -> None:
        """Create a 'Check for Updates' nav button matching the main nav style."""

        btn = tk.Button(
            parent,
            text="Check for Updates",
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
            command=self._check_for_updates,
            cursor="hand2",
        )

        btn.pack(
            fill="x",
            pady=(0, 6)
        )
        self._update_button = btn

    def _check_for_updates(self) -> None:
        """Check GitHub for a newer version (off the UI thread)."""

        btn = getattr(self, "_update_button", None)
        if btn is not None:
            btn.configure(text="Checking...", state="disabled")

        def worker() -> None:
            try:
                result, err = updater.check_for_update(), None
            except Exception as exc:  # network / parse / HTTP errors
                result, err = None, exc
            self._root.after(0, lambda: self._on_update_checked(result, err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_checked(self, result: Optional[dict], err: Optional[Exception]) -> None:
        """Handle the update-check result back on the UI thread."""

        btn = getattr(self, "_update_button", None)
        if btn is not None:
            btn.configure(text="Check for Updates", state="normal")

        if err is not None:
            messagebox.showwarning("Update check failed", f"Could not check for updates.\n\n{err}")
            return

        if not result or not result.get("available"):
            current = result.get("current") if result else updater.get_current_version()
            messagebox.showinfo("Up to date", f"You are running the latest version ({current}).")
            return

        warning = ""
        if updater.is_dev_checkout():
            warning = (
                "\n\nWARNING: This looks like a git working copy. Updating will "
                "overwrite local changes with the published version."
            )

        proceed = messagebox.askyesno(
            "Update available",
            f"A new version is available.\n\n"
            f"Current: {result['current']}\n"
            f"Latest: {result['latest']}\n\n"
            "The app will close, install the update, refresh dependencies, "
            f"and reopen automatically. Continue?{warning}"
        )
        if not proceed:
            return

        try:
            updater.launch_updater("ui")
        except Exception as exc:
            messagebox.showerror("Update failed", f"Could not start the updater.\n\n{exc}")
            return

        messagebox.showinfo(
            "Updating",
            "The updater is running in a new window.\n"
            "This app will now close and reopen when the update finishes."
        )
        self._root.destroy()

    def _build_slider_input(
        self, 
        parent: tk.Widget, 
        variable: Any, 
        row: int,
        from_: int = 0, 
        to: int = 100, 
        label: Optional[str] = None
    ) -> None:
        """Helper to create a standard Slider + Entry row."""

        container = ttk.Frame(parent, style="Config.Card.TFrame")
        if label:
            ttk.Label(
                container, 
                text=label, 
                style="Config.TLabel", 
                font=FONT
            ).pack(anchor="w", pady=(0, 2))
            
        s_row = ttk.Frame(container, style="Config.Card.TFrame")
        s_row.pack(fill="x")
        
        vcmd = (s_row.register(_validate_digits), "%P")
        entry = ttk.Entry(
            s_row, 
            textvariable=variable, 
            width=4, 
            justify="center", 
            font=FONT,
            style="Config.TEntry", 
            validate="key", 
            validatecommand=vcmd
        )
        entry.pack(side="right")

        try:
            curr = int(variable.get())
        except (ValueError, TypeError):
            curr = from_
            variable.set(from_)

        scale = Slider(s_row, from_=from_, to=to, variable=variable, height=30, bg=CARD_BG, cursor="hand2")
        scale.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        def validate_and_clamp(event=None):
            try:
                val_str = entry.get().strip()
                if not val_str:
                    val = from_
                else:
                    val = int(val_str)
                
                if val > to:
                    val = to
                elif val < from_:
                    val = from_
                
                if variable.get() != str(val):
                    variable.set(val)
                else:
                    entry.delete(0, "end")
                    entry.insert(0, str(val))

                self._root.after_idle(self._check_dirty)
                self._root.after_idle(self._update_preview_widget)
                
            except (ValueError, TypeError):
                entry.delete(0, "end")
                entry.insert(0, str(variable.get()))

        entry.bind("<FocusOut>", validate_and_clamp)
        entry.bind("<Return>", validate_and_clamp)
        
        container.grid(row=row, column=1, sticky="ew", pady=4, padx=(0, 20))

    def _build_choice_input(
        self, 
        parent: tk.Widget, 
        section: str, 
        key: str, 
        variable: Any, 
        row: int
    ) -> None:
        """Helper to create a button-based choice selector."""
        
        # Get available options based on the field
        options = []
        if section == "PRINTER" and key == "paper_width":
            options = settings.get_paper_width_options()
        
        if not options:
            # Fallback to text entry if no options available
            ttk.Entry(
                parent, 
                textvariable=variable, 
                style="Config.TEntry", 
                font=FONT
            ).grid(row=row, column=1, sticky="ew", pady=4, padx=(12, 0))
            return
        
        # Create button-based choice selector
        container = ttk.Frame(parent, style="Config.Card.TFrame")
        container.grid(row=row, column=1, sticky="ew", pady=4, padx=(12, 0))
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)
        
        buttons = {}
        
        def create_button_click_handler(option_value):
            def on_click():
                variable.set(option_value)
                # Update button styles
                for opt, btn in buttons.items():
                    if opt == option_value:
                        btn.configure(style="Config.Primary.TButton")
                    else:
                        btn.configure(style="Config.TButton")
                # Apply paper width mapping
                current_config = self._get_current_ui_config()
                settings.apply_paper_width(current_config, option_value)
                self._check_dirty()
            return on_click
        
        # Create buttons for each option
        for idx, option in enumerate(options):
            btn = ttk.Button(
                container,
                text=option,
                style="Config.Primary.TButton" if variable.get() == option else "Config.TButton",
                command=create_button_click_handler(option),
                cursor="hand2"
            )
            btn.grid(row=0, column=idx, sticky="ew", padx=4)
            buttons[option] = btn

    def _prepare_window(self) -> None:
        self._root.title(WINDOW_TITLE)
        self._root.configure(bg=WINDOW_BG)
        self._root.geometry(WINDOW_SIZE)
        self._root.minsize(1000, 500)
        self._root.resizable(True, True)
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)
        self._apply_dpi_awareness()
        self._icon_image = self._create_window_icon()
        if self._icon_image:
            self._root.iconphoto(True, self._icon_image)
        self._root.after(100, self._on_ready)
        self._root.bind("<Configure>", self._on_resize)
        self._root.bind("<Map>", self._on_state_changes)
        self._root.bind("<Unmap>", self._on_state_changes)
        self._root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
    def _prepare_styles(self) -> None:
        style = ttk.Style(self._root)

        if "clam" in style.theme_names(): style.theme_use("clam")

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

        self._build_custom_checkbox_indicator(style, CARD_BG, TEXT_COLOR, ACCENT)

    def _build_custom_checkbox_indicator(self, style: ttk.Style, bg: str, fg: str, border: str) -> None:
        """Create a custom checkbox indicator (checked/unchecked) that matches theme colors."""
        size = 16

        def make_base():
            img = tk.PhotoImage(width=size, height=size)
            # border rectangle
            for x in range(size):
                img.put(border, to=(x, 0))
                img.put(border, to=(x, size - 1))
            for y in range(size):
                img.put(border, to=(0, y))
                img.put(border, to=(size - 1, y))
            return img

        def fill_square(img: tk.PhotoImage, padding: int, color: str):
            for x in range(padding, size - padding):
                for y in range(padding, size - padding):
                    img.put(color, to=(x, y))

        if len(self._cache) == 0:
            # create unchecked and checked images only once and cache them
            unchecked = make_base()
            checked = make_base()
            fill_square(checked, 3, ACCENT)

            # keep refs
            self._cache["unchecked"] = unchecked
            self._cache["checked"] = checked

            # create a custom indicator element and layout
            try:
                style.element_create("Custom.Check.indicator", "image", unchecked,
                                        ("selected", checked), ("!selected", unchecked),
                                        ("alternate", unchecked))
            except tk.TclError:
                # element may already exist; update images by recreating layout
                pass

            style.layout(
                "Custom.TCheckbutton",
                [
                    (
                        "Checkbutton.padding",
                        {
                            "sticky": "nswe",
                            "children": [
                                ("Custom.Check.indicator", {"side": "left", "sticky": ""}),
                                ("Checkbutton.label", {"side": "right", "sticky": "w"}),
                            ],
                        },
                    )
                ],
            )
        
        # fix background/foreground and disable hover background changes
        style.configure("Custom.TCheckbutton", background=bg, foreground=fg, padding=2)
        style.map(
            "Custom.TCheckbutton",
            background=[("active", bg), ("selected", bg), ("disabled", bg)],
            foreground=[("active", fg), ("selected", fg), ("disabled", "#97a6b5")],
        )

    def _apply_dpi_awareness(self) -> None:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    def _apply_titlebar_theme(self) -> None:
        if sys.platform != "win32": return
        try:
            TitleBarColor.set(self._root, NAV_BG)
            TitleBarTextColor.set(self._root, NAV_ACTIVE_TEXT)
        except Exception:
            pass
        
    def _apply_border_color(self) -> None:
        if sys.platform != "win32": return
        try:
            BorderColor.set(self._root, WINDOW_BORDER)
        except Exception:
            pass


    def _get_typed_value(self, value: Any, field_type: type) -> Any:
        """Convert a string value to the specified type."""

        if field_type is bool:
            return bool(value)
        if field_type is int:
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
        if field_type is dict:
            # For choice fields, return the string value as-is
            return str(value)
        return str(value)

    def _get_current_ui_config(self) -> Config:
        """Collect current values from all UI variables into a config dictionary."""

        config = {section: {} for section in FIELD_SPECS}
        for (section, key), (var, field_type) in self._variables.items():
            if self._check_ignore_key(key, field_type): continue
            config[section][key] = self._get_typed_value(var.get(), field_type)

        # inject receipt_locale to LAYOUT section for preview rendering
        code = self._receipt_locale_var.get() if hasattr(self, "_receipt_locale_var") else "en"
        config["LAYOUT"]["receipt_locale"] = code
        
        # Apply paper_width mapping to set line_width and pixel_width
        if "PRINTER" in config and "paper_width" in config["PRINTER"]:
            settings.apply_paper_width(config, config["PRINTER"]["paper_width"])

        return config

    def _set_config(self, config: Config) -> None:
        """Update UI variables with values from the provided config dictionary."""

        for (section, key), (var, field_type) in self._variables.items():
            if self._check_ignore_key(key, field_type): continue
            val = config.get(section, {}).get(key, "")
            if val is None: val = ""
            
            if field_type is bool:
                var.set(bool(val))
            else:
                var.set(str(val))

    def _check_dirty(self, *args) -> None:
        """Check if any variable differs from the saved data and enable/disable buttons."""

        if not self._save_btn: return

        is_dirty = False
        for (section, key), (var, field_type) in self._variables.items():
            if self._check_ignore_key(key, field_type): continue
            
            current = self._get_typed_value(var.get(), field_type)
            original = self._get_typed_value(self._data.get(section, {}).get(key), field_type)
            
            if current != original:
                is_dirty = True
                break
        
        state = "!disabled" if is_dirty else "disabled"
        self._save_btn.state([state])
        if self._cancel_btn:
            self._cancel_btn.state([state])

    def _check_ignore_key(self, key: str, field_type: type) -> bool:
        if field_type is callable: return True
        return key in ["-", " "]

    def _create_window_icon(self) -> tk.PhotoImage:
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
        return ImageTk.PhotoImage(img)

    def _check_responsive_layout(self, event: tk.Event = None) -> None:
        self._update_scrollbar_visibility()
        self._update_preview_visibility()

    def _update_scrollbar_visibility(self) -> None:
        def update_scrollbar_visibility() -> None:
            if not self._scroll_canvas or not self._scrollbar:
                return
            canvas_height = self._scroll_canvas.winfo_height()
            content_height = self._scroll_canvas.bbox("all")[3] if self._scroll_canvas.bbox("all") else 0
            if content_height <= canvas_height:
                self._scrollbar.configure(style="Hidden.Scrollbar")
            else:
                self._scrollbar.configure(style="Config.Vertical.TScrollbar")

        if self._root:
            self._root.after_idle(update_scrollbar_visibility)

    def _update_preview_visibility(self) -> None:
        """Toggle preview panel visibility based on window width."""

        if self.section not in ("LAYOUT", "DUMMY"): return

        width = self._root.winfo_width()
        if width < self._preview_visible_at:
            if self._right_panel.winfo_ismapped():
                self._right_panel.grid_remove()
        else:
            if len(self._right_panel.winfo_children()) > 0 and not self._right_panel.winfo_ismapped():
                self._right_panel.grid()

    def _is_widget_in_preview(self, widget: Any) -> bool:
        """Return True when widget belongs to the preview panel subtree."""

        if not widget or not self._preview_frame:
            return False

        try:
            current = widget
            preview_path = str(self._preview_frame)
            while current:
                if str(current) == preview_path:
                    return True
                parent_path = current.winfo_parent()
                if not parent_path:
                    break
                current = current._nametowidget(parent_path)
        except Exception:
            return False

        return False

    def _update_preview_scrollbar_visibility(self) -> None:
        def update_preview_scrollbar_visibility() -> None:
            if not self._preview_canvas or not self._preview_scrollbar:
                return

            canvas_height = self._preview_canvas.winfo_height()
            content_bbox = self._preview_canvas.bbox("all")
            content_height = content_bbox[3] if content_bbox else 0

            if content_height <= canvas_height:
                self._preview_scrollbar.grid_remove()
            else:
                self._preview_scrollbar.grid()

        if self._root:
            self._root.after_idle(update_preview_scrollbar_visibility)

    def _browse_file(
        self, 
        target: tk.Variable, 
        title: str, 
        filetypes: Optional[list[tuple[str, str]]]
    ) -> None:
        selection = filedialog.askopenfilename(
            parent=self._root,
            title=title,
            filetypes=filetypes or [("All Files", "*.*")],
        )
        if selection: target.set(selection)

    def _init_variables(self) -> None:
        for section, fields in FIELD_SPECS.items():
            for (key, _label, field_type, *rest) in fields:
                if key == "-": 
                    self._variables[(section, key)] = (tk.StringVar(value=""), type(None))
                    continue
                
                value = self._data.get(section, {}).get(key, "")
                if field_type is bool:
                    var: tk.Variable = tk.BooleanVar(value=bool(value))
                else:
                    var = tk.StringVar(value=str(value))
                
                var.trace_add("write", self._check_dirty)
                if section == "LAYOUT":
                    var.trace_add("write", self._update_preview_widget)
                    
                self._variables[(section, key)] = (var, field_type)

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

    def _reset_defaults(self) -> None:
        confirm = messagebox.askyesno(
            "Reset Defaults", 
            """
                Are you sure you want to reset all settings to defaults?
                This cannot be undone.
            """
        )
        if confirm: self._set_config(settings.get_defaults())

    def _revert_changes(self) -> None:
        """Revert changes to the last saved state."""
        self._set_config(self._data)

    def _save(self) -> None:
        try:
            updated = self._get_current_ui_config()
        except ValueError as exc:
            return messagebox.showerror(
                "Invalid Value", 
                f"""
                    Please enter valid values for all fields.
                    {exc}
                """
            )

        settings.save_all(updated)
        
        self._data = updated
        self._check_dirty()
        self._root.focus_set()
    
    def _print_preview(self) -> None:
        """Gather current settings and print a preview page simulating a real receipt."""
        
        try:
            try:
                print_preview(self._get_current_ui_config())
                messagebox.showinfo("Success", "Test receipt sent to printer.")
            except Exception as e:
                messagebox.showerror("Print Error", f"Failed to print:\n{e}")
                
        except ValueError as e:
            messagebox.showerror("Configuration Error", f"Invalid printer settings:\n{e}")

    def _generate_preview_image(self) -> Optional[ImageTk.PhotoImage]:
        """Generate a grayscale preview of the receipt layout."""

        try:
            cfg = self._get_current_ui_config().get("LAYOUT", {})

            # On the Dummy tab show the live (unsaved) editor payload; elsewhere
            # use the saved dummy on disk.
            if self._active_section == "DUMMY" and self._dummy_preview_payload:
                payload = self._dummy_preview_payload()
            else:
                payload = dummy.load()
            info = PayloadInfo.from_dict(payload)
            
            code = self._receipt_locale_var.get() if hasattr(self, "_receipt_locale_var") else "en"
            locale = LocaleTH() if code == "th" else LocaleEN()

            img = generate_receipt_image(
                cfg,
                info,
                locale=locale
            )
            
            preview_img = self._apply_paper_effect(img)
            return ImageTk.PhotoImage(preview_img)

        except Exception as e:
            print(f"Preview generation failed: {e}")
            return None

    def _apply_paper_effect(self, content_img: Image.Image) -> Image.Image:
        """Add margins, jagged edges, and border to simulate a paper receipt."""
        
        tooth_w = 10
        tooth_h = 6
        
        PADDING = 20
        V_PADDING = 30
        BOTTOM_PADDING = 80
        
        base_w = content_img.width + (2 * PADDING)
        remainder = base_w % tooth_w
        if remainder != 0:
            base_w += (tooth_w - remainder)
            
        target_w = int(base_w)
        target_h = content_img.height + V_PADDING + BOTTOM_PADDING
        
        final_im = Image.new("RGBA", (target_w + 1, target_h), (0, 0, 0, 0))
        
        points = []
        points.append((0, 0))
        for i in range(0, target_w, tooth_w):
            points.append((i + tooth_w/2, tooth_h))
            points.append((i + tooth_w, 0))
            
        points.append((target_w, target_h))
        for i in range(target_w, 0, -tooth_w):
            points.append((i - tooth_w/2, target_h - tooth_h))
            points.append((i - tooth_w, target_h))
        points.append((0, 0))
        
        mask = Image.new("L", (target_w + 1, target_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.polygon(points, fill=255)
        
        white_paper = Image.new("RGBA", (target_w + 1, target_h), (255, 255, 255, 255))
        final_im.paste(white_paper, (0, 0), mask)
        
        content_rgba = content_img.convert("RGBA")
        content_x = (target_w - content_img.width) // 2
        final_im.paste(content_rgba, (content_x, V_PADDING), content_rgba)
        
        outline_layer = Image.new("RGBA", (target_w + 1, target_h), (0, 0, 0, 0))
        outline_draw = ImageDraw.Draw(outline_layer)
        edge_color = (200, 200, 200, 255)
        right_edge_x = target_w - 3
        top_edge_y = tooth_h
        bottom_edge_y = target_h - tooth_h
        
        outline_draw.line(points, fill=edge_color, width=2)
        outline_draw.line([(right_edge_x, top_edge_y), (right_edge_x, bottom_edge_y)], fill=edge_color, width=2)
        
        final_im.alpha_composite(outline_layer)
        return final_im

    def _update_preview_widget(self, *args) -> None:
        """Refresh the preview label if it exists."""

        if not self._preview_label: return
        if self._active_section not in ("LAYOUT", "DUMMY"): return

        photo = self._generate_preview_image()
        if photo:
            self._preview_content_width = photo.width()
            self._preview_label.configure(image=photo, text="")
            self._preview_label.image = photo # Keep ref
            total_preview_width = self._preview_content_width + self._preview_scrollbar_gap + self._preview_scrollbar_width
            self._right_panel.grid_columnconfigure(0, minsize=total_preview_width)
            if self._preview_frame:
                self._preview_frame.configure(width=total_preview_width)
            if self._preview_scroll_container:
                self._preview_scroll_container.grid_columnconfigure(0, minsize=self._preview_content_width)
            if self._preview_canvas:
                self._preview_canvas.configure(width=self._preview_content_width)
            if self._preview_scroll_window is not None:
                self._preview_canvas.itemconfigure(self._preview_scroll_window, width=photo.width())
        else:
            self._preview_label.configure(image="", text="Preview Error")
            if self._preview_scroll_window is not None and self._preview_canvas:
                self._preview_canvas.configure(width=self._preview_content_width)
                self._preview_canvas.itemconfigure(self._preview_scroll_window, width=self._preview_content_width)

        self._update_preview_scrollbar_visibility()

    def run(self) -> None:
        self._root.eval("tk::PlaceWindow . center")
        self._root.mainloop()
    

def _validate_digits(P: str) -> bool:
    if P == "": return True
    return P.isdigit()

def _num_str(value: Any) -> str:
    """Format a payload number for an entry field, dropping a trailing .0."""
    if value is None or value == "":
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)

def _acquire_single_instance_mutex() -> Optional[int]:
    """Create a named mutex; return handle if acquired, else None when already running or failed."""
    
    try:
        k32 = ctypes.windll.kernel32
        handle = k32.CreateMutexW(None, False, "Global\\PrinterConfigMutex")
        if not handle:
            return None
        already = k32.GetLastError() == 183 # ERROR_ALREADY_EXISTS
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
            WindowFrame.foreground(hwnd)
        except Exception:
            pass
        return False
    atexit.register(lambda: ctypes.windll.kernel32.ReleaseMutex(mutex) if mutex else None)
    return True


def print_preview(config: Optional[Config]=None, locale: Optional[Locale]=None) -> None:
    """Print preview of receipt based on [config]"""

    current_config = config or settings.get_all()
    printer_cfg = current_config.get("PRINTER", {})
    layout_cfg = current_config.get("LAYOUT", {})

    info = PayloadInfo.from_dict(dummy.load())
    if locale is None:
        rc = layout_cfg.get("receipt_locale", "en")
        locale = LocaleTH() if rc == "th" else LocaleEN()

    img = generate_receipt_image(
        layout_cfg,
        info,
        locale=locale
    )

    printer = ReceiptPrinter(printer_cfg)
    try:
        printer.print_image(img)
        printer.cut()
    except Exception as e:
        raise Exception(f"Print Error: {e}")
    finally:
        printer.disconnect()

def open_url(url: str) -> None:
    """Open the specified URL in the default web browser."""

    if sys.platform == "win32":
        os.startfile(url)
    else:
        # Not implemented yet
        ...

def open_driver_downloads_page() -> None:
    """Open the printer driver downloads page in the default browser."""
    
    from pathlib import Path
    
    # Get the path to the printer drivers HTML file
    drivers_html = Path(__file__).parent.parent / "assets" / "printer_drivers.html"
    
    if drivers_html.exists():
        # Convert to file:// URL for cross-platform compatibility
        file_url = drivers_html.as_uri()
        if sys.platform == "win32":
            os.startfile(str(drivers_html))
        else:
            import webbrowser
            webbrowser.open(file_url)
    else:
        # Fallback to online page if file doesn't exist
        url = "https://www.xprinter.co.th/en/pages/45381-Download%20Driver"
        open_url(url)

def open_github_repo() -> None:
    """Open the GitHub repository page in the default browser."""

    url = "https://github.com/thestampr/usb-printer-service"
    open_url(url)

def open_docs() -> None:
    """Open the developer documentation in the default browser."""
    
    from pathlib import Path
    
    docs_html = Path(__file__).parent.parent / "assets" / "docs.html"
    
    if docs_html.exists():
        if sys.platform == "win32":
            os.startfile(str(docs_html))
        else:
            import webbrowser
            webbrowser.open(docs_html.as_uri())
    else:
        # Fallback if not found
        messagebox.showerror("Error", "Documentation file not found.")

def main() -> None:
    """Launch the Tkinter configuration interface."""
    
    if _ensure_single_instance():
        ui = UI()
        ui.run()


if __name__ == "__main__":
    main()
