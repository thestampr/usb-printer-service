"""Application-wide configuration for the USB receipt printer service."""

PRINTER = {
    "usb_port": "USB001",
    "usb_name": "XP-58 (copy 1)",
    "encoding": "utf-8",
    "line_width": 44,  # typical character width for 58mm thermal paper
    "pixel_width": 384,  # dot width for 58mm heads
}

LAYOUT = {
    "font_family": "Sarabun-SemiBold",
    "font_path": "assets/fonts/Sarabun/Sarabun-SemiBold.ttf",
    "font_size": 24,
    "font_size_small": 20,
    "line_spacing": 6,
    "currency": "บาท",
    "volume_unit": "ลิตร",
    "header_image": "",
    "header_title": "Your Gas Station",
    "header_description": "Your Address Here",
    "receipt_title": "ใบเสร็จน้ำมัน",
    "footer_label": "Thank you!",
    "footer_image": "",
}

SERVICE = {
    "host": "0.0.0.0",
    "port": 5000,
    "debug": True,
}
