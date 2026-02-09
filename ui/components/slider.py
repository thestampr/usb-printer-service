from __future__ import annotations

import tkinter as tk
from typing import Optional

from ..theme import *
from ._typing import *


class Slider(tk.Canvas):
    """A custom slider widget drawn on a Canvas to ensure specific styling."""

    def __init__(
        self, 
        parent: tk.Widget, 
        from_: int = 0, 
        to: int = 100, 
        variable: tk.IntVar = None, 
        command: Optional[Command] =None, 
        width: int = 200, 
        height: int = 24, 
        bg: Color = CARD_BG, 
        trough_color: Color = "#e5e7eb", 
        active_color: Color = ACCENT, 
        handle_color: Color = ACCENT,
        **kwargs
    ) -> None:
        super().__init__(
            parent, 
            width=width, 
            height=height, 
            bg=bg, 
            highlightthickness=0, 
            **kwargs
        )
        self._from = from_
        self._to = to
        self._variable = variable or tk.IntVar(value=from_)
        self._command = command
        
        self._trough_color = trough_color
        self._active_color = active_color
        self._handle_color = handle_color
        
        try:
            self._value = int(float(self._variable.get()))
        except (ValueError, TypeError):
            self._value = from_
            
        self._dragging = False
        
        self.bind("<Configure>", self._on_update)
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Destroy>", self._on_destroy)
        
        self._trace_id = None
        if self._variable:
            self._trace_id = self._variable.trace_add("write", self._on_change)

    def _on_destroy(self, _: tk.Event) -> None:
        if self._variable and self._trace_id:
            try:
                self._variable.trace_remove("write", self._trace_id)
            except Exception:
                pass
        self._trace_id = None

    def _on_update(self, _: tk.Event) -> None:
        self._paint()

    def _on_click(self, event: tk.Event) -> None:
        self._dragging = True
        self._update_value(event.x)

    def _on_drag(self, event: tk.Event) -> None:
        if self._dragging:
            self._update_value(event.x)

    def _on_release(self, _: tk.Event) -> None:
        self._dragging = False

    def _on_change(self, *_) -> None:
        try:
            new_val = int(self._variable.get())
            if new_val != self._value:
                self._value = new_val
                self._paint()
        except (ValueError, TypeError):
            pass


    def _paint(self) -> None:
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        cy = h // 2

        # Draw Track
        padding = 10
        self.create_line(
            padding, 
            cy, 
            w - padding, 
            cy, 
            fill=self._trough_color, 
            width=6, 
            capstyle="round", 
            joinstyle="bevel", 
            smooth=True
        )
        
        # Draw Active Progress
        x_val = self._coord_from_value(self._value)
        if x_val > padding:
            self.create_line(
                padding, 
                cy, 
                x_val, 
                cy, 
                fill=self._active_color, 
                width=6, 
                capstyle="round", 
                joinstyle="bevel", 
                smooth=True
            )
        
        # Draw Handle
        radius = 8
        self.create_oval(
            x_val - radius, 
            cy - radius, 
            x_val + radius, 
            cy + radius, 
            fill=self._handle_color, 
            outline=self._handle_color, 
            width=1,
        )

    def _coord_from_value(self, value: int) -> int:
        w = self.winfo_width()
        if w <= 1: w = int(self["width"])
        padding = 10
        usable_w = w - 2 * padding
        
        try:
            val = float(value)
        except (ValueError, TypeError):
            val = float(self._from)
            
        normalized = (val - self._from) / (self._to - self._from)
        return padding + (normalized * usable_w)

    def _value_from_coord(self, x: int) -> int:
        w = self.winfo_width()
        padding = 10
        usable_w = w - 2 * padding
        if usable_w <= 0: return self._from
        
        rel_x = x - padding
        normalized = max(0.0, min(1.0, rel_x / usable_w))
        return int(self._from + (normalized * (self._to - self._from)))
    
    def _update_value(self, x: int) -> None:
        val = self._value_from_coord(x)
        if val != self._value:
            self._value = val
            self._variable.set(val)
            self._paint()
            if self._command:
                self._command(val)