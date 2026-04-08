from __future__ import annotations

import logging
import math
from typing import Any, Optional, TYPE_CHECKING
from PIL import Image, ImageDraw, ImageFont
from printer.utils import get_real_path
from l10n import LocaleEN, LocaleTH

if TYPE_CHECKING:
    from common.interface import PayloadInfo
    from l10n import Locale

LOGGER = logging.getLogger(__name__)

class DashedImageDraw(ImageDraw.ImageDraw):
    """Helper for drawing dashed lines."""

    def thick_line(self, xy: list[tuple[float, float]], direction: list[tuple[float, float]], fill=None, width=0):
        if xy[0] != xy[1]:
            self.line(xy, fill=fill, width=width)
        else:
            x1, y1 = xy[0]
            dx1, dy1 = direction[0]
            dx2, dy2 = direction[1]
            if dy2 - dy1 < 0:
                x1 -= 1
            if dx2 - dx1 < 0:
                y1 -= 1
            
            if dy2 - dy1 != 0:
                if dx2 - dx1 != 0:
                    k = -(dx2 - dx1) / (dy2 - dy1)
                    a = 1 / math.sqrt(1 + k**2)
                    b = (width * a - 1) / 2
                else:
                    k = 0
                    b = (width - 1) / 2
                x3 = x1 - math.floor(b)
                y3 = y1 - int(k * b)
                x4 = x1 + math.ceil(b)
                y4 = y1 + int(k * b)
            else:
                x3 = x1
                y3 = y1 - math.floor((width - 1) / 2)
                x4 = x1
                y4 = y1 + math.ceil((width - 1) / 2)
            self.line([(x3, y3), (x4, y4)], fill=fill, width=1)

    def dashed_line(self, xy: list[tuple[float, float]], dash=(6, 4), fill=None, width=0):
        for i in range(len(xy) - 1):
            x1, y1 = xy[i]
            x2, y2 = xy[i + 1]
            x_length = x2 - x1
            y_length = y2 - y1
            length = math.sqrt(x_length**2 + y_length**2)
            dash_enabled = True
            position = 0
            while position <= length:
                for dash_step in dash:
                    if position > length:
                        break
                    if dash_enabled:
                        start = position / length
                        end = min((position + dash_step - 1) / length, 1)
                        self.thick_line(
                            [
                                (round(x1 + start * x_length), round(y1 + start * y_length)),
                                (round(x1 + end * x_length), round(y1 + end * y_length))
                            ],
                            xy, fill, width
                        )
                    dash_enabled = not dash_enabled
                    position += dash_step

class ReceiptRenderer:
    """Handles the generation of receipt images."""

    PADDING = 0
    V_PADDING = 0
    BOTTOM_PADDING = 10
    SCALE_FACTOR = 0.8

    def __init__(self, config: dict[str, Any], width: int = 384):
        self.config = config
        self.target_width = width
        self.font_path = get_real_path(config.get("font_path", "arial.ttf"))
        self.line_spacing = int(config.get("line_spacing", 4)) * 2
        
        # Initialize fonts
        p_font_size = max(10, int(config.get("font_size", 24) * self.SCALE_FACTOR))
        p_font_small = max(8, int(config.get("font_size_small", 20) * self.SCALE_FACTOR))
        self.title_font = self._load_font(self.font_path, p_font_size)
        self.body_font = self._load_font(self.font_path, p_font_small)

        # Initialize canvas
        # Determine height dynamically - start large
        self.temp_h = 2000
        self.im = Image.new("L", (self.target_width, self.temp_h), 255)
        self.draw = DashedImageDraw(self.im)
        self.y = self.V_PADDING

    def _load_font(self, path: str, size: int) -> ImageFont.ImageFont:
        try:
            return ImageFont.truetype(path, size)
        except IOError:
            return ImageFont.load_default()

    def wrap_text(self, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
        """Wrap text to fit max_width, respecting explicit newlines."""
        if not text:
            return []

        lines = []
        paragraphs = text.split("\n")

        for paragraph in paragraphs:
            if font.getlength(paragraph) <= max_width:
                lines.append(paragraph)
                continue

            words = paragraph.split(" ")
            current_line = []

            for word in words:
                test_line = " ".join(current_line + [word])
                if font.getlength(test_line) <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word)
                        current_line = []

            if current_line:
                lines.append(" ".join(current_line))

        return lines

    def draw_centered_text(self, text: str, font: ImageFont.ImageFont) -> None:
        if not text:
            return

        max_w = self.target_width - (2 * self.PADDING)
        lines = self.wrap_text(text, font, max_w)

        for line in lines:
            length = font.getlength(line)
            x = (self.target_width - length) // 2
            self.draw.text((x, self.y), line, font=font, fill=0)
            
            bbox = font.getbbox("ผู้")
            h = bbox[3] - bbox[1]
            
            self.y += h + 6

    def draw_keyvalue_text(self, key: str, value: Any) -> None:
        if not key or not value: return
        self.draw.text((self.PADDING, self.y), key, font=self.body_font, fill=0)
        value_str = str(value)
        bbox = self.draw.textbbox((0, 0), value_str, font=self.body_font)
        th = bbox[3] - bbox[1]
        tw = bbox[2] - bbox[0]
        self.draw.text((self.target_width - self.PADDING - tw, self.y), value_str, font=self.body_font, fill=0)
        self.y += th + 10

    def draw_3_columns(self, col1: str, col2: str, col3: str, font: Optional[ImageFont.ImageFont] = None) -> None:
        """Draw text in 3 columns with 5:1:2 ratio."""
        if font is None:
            font = self.body_font

        # Calculate column widths
        available_width = self.target_width - (2 * self.PADDING)
        col1_w = int(available_width * (5 / 8))
        col2_w = int(available_width * (1 / 8))
        # col3 gets the remaining to avoid rounding gaps
        col3_w = available_width - col1_w - col2_w

        # Wrap text for each column
        col1_lines = self.wrap_text(str(col1), font, col1_w)
        col2_lines = self.wrap_text(str(col2), font, col2_w)
        col3_lines = self.wrap_text(str(col3), font, col3_w)

        max_lines = max(len(col1_lines), len(col2_lines), len(col3_lines))
        
        # Calculate line height
        bbox_a = font.getbbox("A")
        line_height = (bbox_a[3] - bbox_a[1]) + 4 if bbox_a else 19

        for i in range(max_lines):
            cur_y = self.y + (i * line_height)
            
            # Column 1 (Left aligned)
            if i < len(col1_lines):
                self.draw.text((self.PADDING, cur_y), col1_lines[i], font=font, fill=0)
            
            # Column 2 (Center aligned in its box)
            if i < len(col2_lines):
                c2_text = col2_lines[i]
                c2_bbox = font.getbbox(c2_text)
                c2_text_w = c2_bbox[2] - c2_bbox[0]
                # Center position: Start of Col2 + (Col2 Width - Text Width) / 2
                c2_x = self.PADDING + col1_w + (col2_w - c2_text_w) // 2
                self.draw.text((c2_x, cur_y), c2_text, font=font, fill=0)

            # Column 3 (Right aligned in its box)
            if i < len(col3_lines):
                c3_text = col3_lines[i]
                c3_bbox = font.getbbox(c3_text)
                c3_text_w = c3_bbox[2] - c3_bbox[0]
                # Right position: End of Col3 - Text Width
                c3_x = self.target_width - self.PADDING - c3_text_w
                self.draw.text((c3_x, cur_y), c3_text, font=font, fill=0)

        self.y += max_lines * line_height

    def draw_4_columns(self, col1: str, col2: str, col3: str, col4: str, font: Optional[ImageFont.ImageFont] = None) -> None:
        """Draw text in 4 columns with 3:1.5:1.5:2 ratio."""
        if font is None:
            font = self.body_font

        # Calculate column widths (total 8 units)
        available_width = self.target_width - (2 * self.PADDING)
        col1_w = int(available_width * (3 / 8))
        col2_w = int(available_width * (1.5 / 8))
        col3_w = int(available_width * (1.5 / 8))
        # col4 gets the remaining to avoid rounding gaps
        col4_w = available_width - col1_w - col2_w - col3_w

        # Wrap text for each column
        col1_lines = self.wrap_text(str(col1), font, col1_w)
        col2_lines = self.wrap_text(str(col2), font, col2_w)
        col3_lines = self.wrap_text(str(col3), font, col3_w)
        col4_lines = self.wrap_text(str(col4), font, col4_w)

        max_lines = max(len(col1_lines), len(col2_lines), len(col3_lines), len(col4_lines))

        # Calculate line height
        bbox_a = font.getbbox("A")
        line_height = (bbox_a[3] - bbox_a[1]) + 4 if bbox_a else 19

        for i in range(max_lines):
            cur_y = self.y + (i * line_height)

            # Column 1 (Left aligned)
            if i < len(col1_lines):
                self.draw.text((self.PADDING, cur_y), col1_lines[i], font=font, fill=0)

            # Column 2 (Center aligned)
            if i < len(col2_lines):
                c2_text = col2_lines[i]
                c2_bbox = font.getbbox(c2_text)
                c2_text_w = c2_bbox[2] - c2_bbox[0]
                c2_x = self.PADDING + col1_w + (col2_w - c2_text_w) // 2
                self.draw.text((c2_x, cur_y), c2_text, font=font, fill=0)

            # Column 3 (Center aligned)
            if i < len(col3_lines):
                c3_text = col3_lines[i]
                c3_bbox = font.getbbox(c3_text)
                c3_text_w = c3_bbox[2] - c3_bbox[0]
                c3_x = self.PADDING + col1_w + col2_w + (col3_w - c3_text_w) // 2
                self.draw.text((c3_x, cur_y), c3_text, font=font, fill=0)

            # Column 4 (Right aligned)
            if i < len(col4_lines):
                c4_text = col4_lines[i]
                c4_bbox = font.getbbox(c4_text)
                c4_text_w = c4_bbox[2] - c4_bbox[0]
                c4_x = self.target_width - self.PADDING - c4_text_w
                self.draw.text((c4_x, cur_y), c4_text, font=font, fill=0)

        self.y += max_lines * line_height

    def draw_dashed_line(self) -> None:
        self.draw.dashed_line([(self.PADDING, self.y), (self.target_width - self.PADDING, self.y)], fill=0, width=2)

    def draw_image(self, img_path: Optional[str], scale: int) -> None:
        if not img_path:
            return

        try:
            with Image.open(get_real_path(img_path)) as h_img:
                h_img = h_img.convert("LA")
                base_w = self.target_width - (2 * self.PADDING)
                if base_w <= 0:
                    return

                ratio = base_w / h_img.width
                h_h = int(h_img.height * ratio)
                h_img = h_img.resize((base_w, h_h), Image.Resampling.LANCZOS)

                if scale != 100:
                    target_w = int(base_w * (scale / 100.0))
                    target_h = int(h_h * (scale / 100.0))
                    h_img = h_img.resize((max(1, target_w), max(1, target_h)), Image.Resampling.LANCZOS)

                x = (self.target_width - h_img.width) // 2
                self.im.paste(h_img, (x, self.y), h_img)
                self.y += h_img.height + 10
        except Exception as e:
            LOGGER.warning(f"Failed to load image {img_path}: {e}")

    def render(
        self, 
        info: PayloadInfo, 
        locale: Optional[Locale] = None
    ) -> Image.Image:
        """Render the receipt image based on items and configuration."""

        if locale is None:
            locale = LocaleEN()  # Default to English if no locale provided

        # Calculate total
        total = sum(float(item.line_total) for item in info.items)

        # Header Image
        self.draw_image(self.config.get("header_image"), int(self.config.get("header_image_scale", 100)))

        # Header Text
        self.draw_centered_text(self.config.get("header_title", ""), self.title_font)
        self.y += 10 + self.line_spacing

        # Description
        self.draw_centered_text(self.config.get("header_description", ""), self.body_font)
        self.y += 16 + self.line_spacing

        # Pre-translate
        known_keys = {
            "no.": locale.r_number,
            "number": locale.r_number,
            "customer": locale.r_customer,
            "customer name": locale.r_customer_name,
            "customer code": locale.r_customer_code,
            "transaction": locale.r_transaction,
            "promotion": locale.r_promotion,
            "date": locale.r_date,
            "time": locale.r_time,
            "cashier": locale.r_cashier,
            "address": locale.r_address,
            "tax id": locale.r_tax_id,
            "tax id customer": locale.r_tax_id_customer,
            "branch": locale.r_branch,
            "car plate": locale.r_car_plate,
            "points": locale.r_points,
            "received": locale.r_received,
            "change": locale.r_change,
            "discount": locale.r_discount
        }

        # Header Info
        if info.header_info:
            self.y += 5
            for k, v in info.header_info.items():
                k = known_keys.get(k.lower(), k)
                self.draw_keyvalue_text(k, str(v))
            self.y += 25

        # Receipt Title
        self.draw_centered_text(self.config.get("receipt_title", ""), self.title_font)
        self.y += 5 + self.line_spacing

        # Body - Items
        self.draw_dashed_line()
        self.y += self.line_spacing + 4

        self.draw_4_columns(
            locale.r_item,
            locale.r_amount,
            locale.r_quantity,
            locale.r_total
        )
        self.y += self.line_spacing

        # Items
        for item in info.items:
            # Format numbers with commas and 2 decimal places
            price_str = f"{item.amount:,.2f}"
            qty_str = f"{item.quantity:,.2f}"
            total_str = f"{item.line_total:,.2f}"
            self.draw_4_columns(item.name, price_str, qty_str, total_str)
            self.y += 4

        self.y += 10 + self.line_spacing
        self.draw_dashed_line()
        self.y += 4 + self.line_spacing

        # Summary
        if info.pre_vat > 0 or info.vat > 0:
            self.draw_keyvalue_text(locale.r_value, f"{info.pre_vat:,.2f}")
            self.draw_keyvalue_text(locale.r_vat, f"{info.vat:,.2f}")

        # Total
        self.draw_keyvalue_text(locale.r_total_label, f"{total:,.2f}")

        # Footer Info
        if info.footer_info:
            self.y += self.line_spacing
            self.draw_dashed_line()
            self.y += self.line_spacing
            for k, v in info.footer_info.items():
                k = known_keys.get(k.lower(), k)
                self.draw_keyvalue_text(k, str(v))
            self.y += 6

        # Footer Label
        self.y += 10 + self.line_spacing
        self.draw_centered_text(self.config.get("footer_label", ""), self.title_font)
        self.y += 6 + self.line_spacing

        # Footer Image
        self.draw_image(self.config.get("footer_image"), int(self.config.get("footer_image_scale", 100)))

        self.y += self.BOTTOM_PADDING
        
        final_h = max(40, self.y)
        return self.im.crop((0, 0, self.target_width, final_h))

def generate_receipt_image(
    config: dict[str, Any],
    info: PayloadInfo,
    width: int = 384,
    locale: Optional[Locale] = None
) -> Image.Image:
    """Generate a receipt image based on configuration and transaction data.
    
    Wrapper for ReceiptRenderer to maintain backward compatibility.
    """
    
    renderer = ReceiptRenderer(config, width)
    return renderer.render(info, locale=locale)

def render_text_block(text: str, width: int = 384, font_path: str = "", font_size: int = 24) -> Image.Image:
    """Render a simple block of text as an image (replacement for legacy print_text)."""
    if not text:
        return Image.new("1", (width, 10), 255)

    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except IOError:
        font = ImageFont.load_default()

    lines = text.splitlines()
    line_h = font_size + 6
    h = len(lines) * line_h + 20

    im = Image.new("1", (width, h), 255)
    draw = ImageDraw.Draw(im)
    y = 10

    for line in lines:
        draw.text((0, y), line, font=font, fill=0)
        y += line_h

    return im.crop((0, 0, width, y + 10))
