"""Render the paper-receipt frame around a rendered receipt image.

Ported verbatim (behaviour-for-behaviour) from the legacy Tkinter UI's
``UI._apply_paper_effect`` so the web preview looks identical: white paper with
jagged top/bottom edges, centered content, and a soft grey outline.
"""

from __future__ import annotations

from PIL import Image, ImageDraw


def apply_paper_effect(content_img: Image.Image) -> Image.Image:
    """Add margins, jagged edges, and a border to simulate a paper receipt."""

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
        points.append((i + tooth_w / 2, tooth_h))
        points.append((i + tooth_w, 0))

    points.append((target_w, target_h))
    for i in range(target_w, 0, -tooth_w):
        points.append((i - tooth_w / 2, target_h - tooth_h))
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

    outline_draw.line(points, fill=edge_color, width=2)

    final_im.alpha_composite(outline_layer)
    return final_im
