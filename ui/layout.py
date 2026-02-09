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

FIELD_SPECS: dict[str, list[FieldSpec]] = {
    "PRINTER": [
        ("usb_port", "USB Port", str),
        ("usb_name", "USB Name", str),
        ("encoding", "Encoding", str),
        ("line_width", "Line Width", int),
        ("pixel_width", "Pixel Width", int),
        (" ", "", None),
        ("open_driver_downloads_page", "Download Printer Drivers", callable, 1),
        # ^ name of function to call on button press
    ],
    "LAYOUT": [
        ("header_image", "Header Image", str),
        ("header_image_scale", "Image Scale (%)", int),
        ("header_title", "Header Title", str),
        ("header_description", "Header Description", str),
        ("receipt_title", "Receipt Title", str),
        ("footer_label", "Footer Label", str),
        ("footer_image", "Footer Image", str),
        ("footer_image_scale", "Image Scale (%)", int),
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
        (" ", "", None),
        ("debug", "Debug Mode", bool),
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
