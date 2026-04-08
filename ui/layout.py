from __future__ import annotations

from typing import Any, Optional, Type, Union

FieldType = Union[
    Type[str], # Entry
    Type[int], # Slider
    Type[bool], # Toggle Switch / Checkbox
    Type[callable], # Button fields, pass function name to key
    None # non-editable
]
FieldSpec = tuple[
    str, # key in settings or function name
    str, # label to show in UI
    FieldType, # type of field
    Optional[int] # optional extra parameter (e.g. button primary flag)
]

# Component Helpers
def entry(label: str, key: str) -> FieldSpec:
    return (key, label, str)

def button(label: str, command: Union[callable, str], primary: bool = False) -> FieldSpec:
    if isinstance(command, str):
        command_name = command
    else:
        command_name = command.__name__
    return (command_name, label, callable, 1 if primary else 0)

def checkbox(label: str, key: str) -> FieldSpec:
    return (key, label, bool)

def slider(label: str, key: str) -> FieldSpec:
    return (key, label, int)

def section_header(label: str) -> FieldSpec:
    return ("-", label, None)

def separator() -> FieldSpec:
    return (" ", "", None)

FIELD_SPECS: dict[str, list[FieldSpec]] = {
    "LAYOUT": [
        entry("Header Image", "header_image"),
        slider("Image Scale (%)", "header_image_scale"),
        entry("Header Title", "header_title"),
        entry("Header Description", "header_description"),
        entry("Receipt Title", "receipt_title"),
        entry("Footer Label", "footer_label"),
        entry("Footer Image", "footer_image"),
        slider("Image Scale (%)", "footer_image_scale"),
        section_header("Advanced"),
        entry("Font Family", "font_family"),
        entry("Font Path", "font_path"),
        slider("Font Size", "font_size"),
        slider("Small Font Size", "font_size_small"),
        slider("Line Spacing", "line_spacing"),
        entry("Currency", "currency"),
        entry("Volume Unit", "volume_unit"),
    ],
    "PRINTER": [
        entry("USB Port", "usb_port"),
        entry("USB Name", "usb_name"),
        entry("Encoding", "encoding"),
        slider("Line Width", "line_width"),
        slider("Pixel Width", "pixel_width"),
        separator(),
        button("Download Printer Drivers", "open_driver_downloads_page", primary=True),
    ],
    "SERVICE": [
        entry("Host", "host"),
        entry("Port", "port"),
        separator(),
        checkbox("Debug Mode", "debug"),
    ],
}

FILE_PICKER_FIELDS: dict[tuple[str, str], dict[str, Any]] = {
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

IMAGE_FIELDS = {
    ("LAYOUT", "header_image"),
    ("LAYOUT", "footer_image"),
}

SCALE_FIELDS = {
    ("LAYOUT", "font_size"),
    ("LAYOUT", "font_size_small"),
    ("LAYOUT", "line_spacing"),
}

__all__ = [
    "FieldSpec",
    "FIELD_SPECS",
    "FILE_PICKER_FIELDS",
    "MULTILINE_FIELDS",
    "IMAGE_FIELDS",
    "SCALE_FIELDS",
]