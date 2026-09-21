from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "legal" / "public-offer-uk.md"
OUTPUT = ROOT / "output" / "pdf" / "guildconsole-public-offer-uk.pdf"
PUBLIC = ROOT / "admin-frontend" / "public" / "documents" / "guildconsole-public-offer-uk.pdf"

FONT_REGULAR = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")
pdfmetrics.registerFont(TTFont("GC-Regular", str(FONT_REGULAR)))
pdfmetrics.registerFont(TTFont("GC-Bold", str(FONT_BOLD)))

PAGE_W, PAGE_H = A4
TEAL = colors.HexColor("#0F766E")
INK = colors.HexColor("#12222C")
MUTED = colors.HexColor("#59717C")
LINE = colors.HexColor("#D7E4E5")


def markup(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\w)(https?://[^\s<]+)", r'<link href="\1" color="#0F766E">\1</link>', text)
    return text.replace("  ", " ")


def draw_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(TEAL)
    canvas.rect(0, PAGE_H - 10 * mm, PAGE_W, 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("GC-Bold", 7.5)
    canvas.drawString(18 * mm, PAGE_H - 6.6 * mm, "GUILDCONSOLE // ПУБЛІЧНА ОФЕРТА")
    canvas.setFont("GC-Regular", 7.5)
    canvas.drawRightString(PAGE_W - 18 * mm, PAGE_H - 6.6 * mm, "LRM-IT")
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 13 * mm, PAGE_W - 18 * mm, 13 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("GC-Regular", 7)
    canvas.drawString(18 * mm, 8.5 * mm, "Редакція від 21.09.2026 · guildconsole.lrm-it.com")
    canvas.drawRightString(PAGE_W - 18 * mm, 8.5 * mm, f"Сторінка {doc.page}")
    canvas.restoreState()


styles = getSampleStyleSheet()
title = ParagraphStyle("TitleGC", parent=styles["Title"], fontName="GC-Bold", fontSize=21, leading=25,
                       textColor=INK, alignment=TA_CENTER, spaceAfter=7 * mm)
subtitle = ParagraphStyle("SubtitleGC", parent=styles["Normal"], fontName="GC-Regular", fontSize=10.2,
                          leading=15, textColor=MUTED, alignment=TA_CENTER, spaceAfter=5 * mm)
heading = ParagraphStyle("HeadingGC", parent=styles["Heading2"], fontName="GC-Bold", fontSize=12.5,
                         leading=16, textColor=TEAL, spaceBefore=5 * mm, spaceAfter=2.5 * mm,
                         keepWithNext=True)
body = ParagraphStyle("BodyGC", parent=styles["BodyText"], fontName="GC-Regular", fontSize=9.3,
                      leading=14.2, textColor=INK, alignment=TA_LEFT, spaceAfter=2.2 * mm,
                      splitLongWords=False)


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=20 * mm, bottomMargin=18 * mm, title="Договір публічної оферти GuildConsole",
                            author="ФОП Лавріненко Катерина Георгіївна", subject="Умови надання цифрових послуг GuildConsole")

    story = []
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    first_h1 = True
    for raw in lines:
        line = raw.strip()
        if not line or line == "---":
            continue
        if line.startswith("# "):
            if first_h1:
                story.extend([Spacer(1, 13 * mm), Paragraph(markup(line[2:]), title)])
                first_h1 = False
            else:
                story.append(Paragraph(markup(line[2:]), heading))
        elif line.startswith("## "):
            value = line[3:]
            if value.startswith("про надання"):
                story.append(Paragraph(markup(value), subtitle))
            else:
                story.append(Paragraph(markup(value), heading))
        else:
            story.append(Paragraph(markup(line.rstrip("  ")), body))

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    PUBLIC.write_bytes(OUTPUT.read_bytes())
    print(OUTPUT)
    print(PUBLIC)


if __name__ == "__main__":
    build()
