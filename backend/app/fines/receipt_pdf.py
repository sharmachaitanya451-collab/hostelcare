"""ReportLab PDF receipt generator for HostelCare fine payments."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)
IST_TZ = ZoneInfo("Asia/Kolkata")

# Brand palette matching HostelCare UI
COLOR_WARM_IVORY = colors.HexColor("#FFFCF7")
COLOR_SAND = colors.HexColor("#F7EFE6")
COLOR_BORDER = colors.HexColor("#E8DCCF")
COLOR_DEEP_PLUM = colors.HexColor("#292039")
COLOR_MUTED_PLUM = colors.HexColor("#5C536B")
COLOR_ROSE = colors.HexColor("#D94378")
COLOR_TERRACOTTA = colors.HexColor("#C95337")
COLOR_SAFFRON = colors.HexColor("#F4AA35")
COLOR_TEAL = colors.HexColor("#368F83")
COLOR_EMERALD_BG = colors.HexColor("#D1FAE5")
COLOR_EMERALD_TEXT = colors.HexColor("#065F46")

_FONT_CANDIDATES: list[tuple[str, str]] = [
    (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ),
]

_REGISTERED_FONTS: tuple[str, str, bool] | None = None


def _resolve_fonts() -> tuple[str, str, bool]:
    """Register a Unicode TTF font with rupee glyph support when available."""
    global _REGISTERED_FONTS
    if _REGISTERED_FONTS is not None:
        return _REGISTERED_FONTS

    for regular_path, bold_path in _FONT_CANDIDATES:
        if Path(regular_path).is_file() and Path(bold_path).is_file():
            try:
                if "HostelCareSans" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("HostelCareSans", regular_path))
                if "HostelCareSansBold" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("HostelCareSansBold", bold_path))
                _REGISTERED_FONTS = ("HostelCareSans", "HostelCareSansBold", True)
                return _REGISTERED_FONTS
            except (OSError, ValueError) as exc:
                logger.debug("Skipping unusable font %s: %s", regular_path, exc)
                continue

    _REGISTERED_FONTS = ("Helvetica", "Helvetica-Bold", False)
    return _REGISTERED_FONTS


def sanitize_receipt_filename(receipt_number: str) -> str:
    """Build a safe deterministic PDF filename from the authoritative receipt number."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", str(receipt_number or "").strip()).strip("-")
    if not cleaned:
        cleaned = "receipt"
    return f"HostelCare-{cleaned}.pdf"


def _format_ist_timestamp(raw_iso: str | None) -> str:
    if not raw_iso:
        return "—"
    try:
        dt = datetime.fromisoformat(str(raw_iso))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        local_dt = dt.astimezone(IST_TZ)
        return local_dt.strftime("%d %b %Y, %I:%M %p IST")
    except ValueError:
        return str(raw_iso)


def _draw_hostelcare_logo(pdf: canvas.Canvas, x: float, y: float, size: float = 34.0) -> None:
    """Draw the HostelCare rounded badge with arch and courtyard lamp vector motif."""
    pdf.saveState()
    # Rounded square badge in Indian Rose with subtle Terracotta accent
    pdf.setFillColor(COLOR_ROSE)
    pdf.setStrokeColor(COLOR_TERRACOTTA)
    pdf.setLineWidth(0.8)
    pdf.roundRect(x, y, size, size, radius=size * 0.28, stroke=1, fill=1)

    # Map 24x24 icon coordinates into the centered inner 20x20 box
    scale = (size * 0.62) / 24.0
    ox = x + (size - 24.0 * scale) / 2.0
    oy = y + (size - 24.0 * scale) / 2.0

    def px(vx: float) -> float:
        return ox + vx * scale

    def py(vy: float) -> float:
        # SVG y goes down; PDF y goes up
        return oy + (24.0 - vy) * scale

    pdf.setStrokeColor(COLOR_WARM_IVORY)
    pdf.setLineWidth(2.0 * scale)
    pdf.setLineCap(1)
    pdf.setLineJoin(1)

    # Outer architectural arch: M4 21 V11 C4 7 8 4 12 4 C16 4 20 7 20 11 V21
    outer = pdf.beginPath()
    outer.moveTo(px(4), py(21))
    outer.lineTo(px(4), py(11))
    outer.curveTo(px(4), py(7), px(8), py(4), px(12), py(4))
    outer.curveTo(px(16), py(4), px(20), py(7), px(20), py(11))
    outer.lineTo(px(20), py(21))
    pdf.drawPath(outer, stroke=1, fill=0)

    # Inner courtyard doorway: M9 21 V13 C9 11.5 10.3 10.5 12 10.5 C13.7 10.5 15 11.5 15 13 V21
    inner = pdf.beginPath()
    inner.moveTo(px(9), py(21))
    inner.lineTo(px(9), py(13))
    inner.curveTo(px(9), py(11.5), px(10.3), py(10.5), px(12), py(10.5))
    inner.curveTo(px(13.7), py(10.5), px(15), py(11.5), px(15), py(13))
    inner.lineTo(px(15), py(21))
    pdf.drawPath(inner, stroke=1, fill=0)

    # Saffron courtyard lamp flame dot at (12, 7.5)
    pdf.setFillColor(COLOR_SAFFRON)
    pdf.setStrokeColor(COLOR_SAFFRON)
    pdf.circle(px(12), py(7.5), 1.3 * scale, stroke=1, fill=1)
    pdf.restoreState()


def render_receipt_pdf(receipt: dict[str, Any]) -> bytes:
    """Render an official single-page A4 portrait PDF receipt from trusted receipt data."""
    font_regular, font_bold, supports_rupee = _resolve_fonts()
    currency_prefix = "₹" if supports_rupee else "INR "

    buf = BytesIO()
    page_w, page_h = A4
    pdf = canvas.Canvas(buf, pagesize=A4)
    pdf.setTitle(f"HostelCare Receipt {receipt.get('receiptNumber', '')}")
    pdf.setAuthor("HostelCare")

    margin_x = 46.0
    card_w = page_w - 2 * margin_x
    card_top = page_h - 46.0
    inner_x = margin_x + 28.0
    inner_w = card_w - 56.0

    # Calculate wrapped description lines first so card height fits content cleanly
    description_text = str(receipt.get("fineDescription") or "—").strip()
    desc_lines = simpleSplit(description_text, font_regular, 10, inner_w - 24.0)
    if not desc_lines:
        desc_lines = ["—"]
    desc_box_h = 34.0 + len(desc_lines) * 14.0

    # Fixed section heights + dynamic description height -> single A4 page without blank space
    card_h = 388.0 + desc_box_h
    card_bottom = card_top - card_h

    # Outer receipt card
    pdf.setFillColor(COLOR_WARM_IVORY)
    pdf.setStrokeColor(COLOR_BORDER)
    pdf.setLineWidth(1.2)
    pdf.roundRect(margin_x, card_bottom, card_w, card_h, radius=14, stroke=1, fill=1)

    # 1. Centered Branding Header
    cursor_y = card_top - 48.0
    logo_size = 32.0
    wordmark_w = pdfmetrics.stringWidth("HostelCare", font_bold, 20)
    header_group_w = logo_size + 10.0 + wordmark_w
    group_x = (page_w - header_group_w) / 2.0

    _draw_hostelcare_logo(pdf, group_x, cursor_y - 4.0, size=logo_size)

    text_x = group_x + logo_size + 10.0
    hostel_w = pdfmetrics.stringWidth("Hostel", font_bold, 20)
    pdf.setFont(font_bold, 20)
    pdf.setFillColor(COLOR_DEEP_PLUM)
    pdf.drawString(text_x, cursor_y + 5.0, "Hostel")
    pdf.setFillColor(COLOR_ROSE)
    pdf.drawString(text_x + hostel_w, cursor_y + 5.0, "Care")

    cursor_y -= 22.0
    pdf.setFont(font_bold, 9.5)
    pdf.setFillColor(COLOR_TEAL)
    pdf.drawCentredString(page_w / 2.0, cursor_y, "HOSTELCARE — OFFICIAL PAYMENT RECEIPT")

    cursor_y -= 14.0
    pdf.setStrokeColor(COLOR_BORDER)
    pdf.setLineWidth(1.0)
    pdf.line(inner_x, cursor_y, inner_x + inner_w, cursor_y)

    # 2. Receipt Number & Status Banner
    cursor_y -= 56.0
    banner_h = 44.0
    pdf.setFillColor(COLOR_SAND)
    pdf.setStrokeColor(COLOR_BORDER)
    pdf.roundRect(inner_x, cursor_y, inner_w, banner_h, radius=10, stroke=1, fill=1)

    pdf.setFont(font_bold, 7.5)
    pdf.setFillColor(COLOR_MUTED_PLUM)
    pdf.drawString(inner_x + 14.0, cursor_y + 27.0, "RECEIPT NUMBER")

    pdf.setFont(font_bold, 12.5)
    pdf.setFillColor(COLOR_DEEP_PLUM)
    pdf.drawString(inner_x + 14.0, cursor_y + 11.0, str(receipt.get("receiptNumber") or "—"))

    status_label = str(receipt.get("paymentStatus") or "paid").upper()
    badge_w = max(56.0, pdfmetrics.stringWidth(status_label, font_bold, 8.5) + 22.0)
    badge_h = 20.0
    badge_x = inner_x + inner_w - 14.0 - badge_w
    badge_y = cursor_y + (banner_h - badge_h) / 2.0
    pdf.setFillColor(COLOR_EMERALD_BG)
    pdf.roundRect(badge_x, badge_y, badge_w, badge_h, radius=10, stroke=0, fill=1)
    pdf.setFont(font_bold, 8.5)
    pdf.setFillColor(COLOR_EMERALD_TEXT)
    pdf.drawCentredString(badge_x + badge_w / 2.0, badge_y + 6.5, status_label)

    # 3. 2-Column Structured Fields Grid
    col_gap = 20.0
    col_w = (inner_w - col_gap) / 2.0
    col1_x = inner_x
    col2_x = inner_x + col_w + col_gap

    rows = [
        (
            ("FINE REFERENCE", str(receipt.get("fineReference") or "—")),
            ("PAYMENT DATE & TIME", _format_ist_timestamp(receipt.get("paidAt"))),
        ),
        (
            ("STUDENT NAME", str(receipt.get("studentName") or "—")),
            ("ROLL NUMBER", str(receipt.get("studentRoll") or "—")),
        ),
        (
            ("PAYMENT METHOD", str(receipt.get("paymentMethod") or "—").upper()),
            ("TRANSACTION REFERENCE", str(receipt.get("transactionReference") or "—")),
        ),
    ]

    cursor_y -= 24.0
    for (left_label, left_val), (right_label, right_val) in rows:
        pdf.setFont(font_bold, 7.5)
        pdf.setFillColor(COLOR_MUTED_PLUM)
        pdf.drawString(col1_x, cursor_y, left_label)
        pdf.drawString(col2_x, cursor_y, right_label)

        cursor_y -= 14.0
        pdf.setFont(font_bold, 10)
        pdf.setFillColor(COLOR_DEEP_PLUM)
        left_clipped = simpleSplit(left_val, font_bold, 10, col_w)[0] if left_val else "—"
        right_clipped = simpleSplit(right_val, font_bold, 10, col_w)[0] if right_val else "—"
        pdf.drawString(col1_x, cursor_y, left_clipped)
        pdf.drawString(col2_x, cursor_y, right_clipped)

        cursor_y -= 24.0

    # 4. Fine Category & Description Box
    desc_top = cursor_y + 6.0
    desc_bottom = desc_top - desc_box_h
    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(COLOR_BORDER)
    pdf.roundRect(inner_x, desc_bottom, inner_w, desc_box_h, radius=10, stroke=1, fill=1)

    pdf.setFont(font_bold, 7.5)
    pdf.setFillColor(COLOR_MUTED_PLUM)
    category_label = str(receipt.get("fineCategory") or "Disciplinary Fine").upper()
    pdf.drawString(inner_x + 12.0, desc_top - 14.0, category_label)

    pdf.setFont(font_regular, 10)
    pdf.setFillColor(COLOR_DEEP_PLUM)
    line_y = desc_top - 30.0
    for line in desc_lines:
        pdf.drawString(inner_x + 12.0, line_y, line)
        line_y -= 14.0

    # 5. Prominent Total Amount Paid Row
    amount_y = desc_bottom - 26.0
    pdf.setStrokeColor(COLOR_BORDER)
    pdf.line(inner_x, amount_y + 16.0, inner_x + inner_w, amount_y + 16.0)

    pdf.setFont(font_bold, 11)
    pdf.setFillColor(COLOR_MUTED_PLUM)
    pdf.drawString(inner_x, amount_y - 2.0, "Total Amount Paid")

    amount_str = f"{currency_prefix}{receipt.get('amountInr', '0.00')}"
    pdf.setFont(font_bold, 18)
    pdf.setFillColor(COLOR_TEAL)
    pdf.drawRightString(inner_x + inner_w, amount_y - 4.0, amount_str)

    # 6. Footer Note inside Receipt Card
    footer_y = card_bottom + 20.0
    pdf.setFont(font_regular, 8.5)
    pdf.setFillColor(COLOR_MUTED_PLUM)
    pdf.drawCentredString(
        page_w / 2.0,
        footer_y,
        "Official HostelCare payment receipt generated from verified hostel dues records.",
    )

    pdf.showPage()
    pdf.save()
    return buf.getvalue()
