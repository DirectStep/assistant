from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.enums import TA_CENTER  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    CondPageBreak,
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from app.pdf.service import PdfArticle, PdfSection


def write_digest_pdf(
    output_path: Path,
    *,
    digest_date: str,
    intro: str,
    sections: list[PdfSection],
    sources: list[PdfArticle],
) -> None:
    regular_font, bold_font = _register_fonts()
    styles = _build_styles(regular_font, bold_font)
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=18 * mm,
        title=f"Ежедневная сводка - {digest_date}",
        author="Personal Assistant",
    )
    story: list[Any] = [
        Paragraph("ПЕРСОНАЛЬНЫЙ АССИСТЕНТ", styles["eyebrow"]),
        Spacer(1, 3 * mm),
        Paragraph("ЕЖЕДНЕВНАЯ СВОДКА", styles["cover_title"]),
        Spacer(1, 3 * mm),
        Paragraph(escape(digest_date), styles["cover_date"]),
        Spacer(1, 7 * mm),
        HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CBD2D0")),
        Spacer(1, 7 * mm),
        Paragraph("1. Главное за день", styles["section_title"]),
        Paragraph(_with_line_breaks(intro), styles["body"]),
    ]

    for section_number, section in enumerate(sections, 2):
        story.extend(
            [
                Spacer(1, 8 * mm),
                CondPageBreak(34 * mm),
                Paragraph(f"{section_number}. {escape(section.title)}", styles["section_title"]),
            ]
        )
        if not section.articles:
            story.append(Spacer(1, 3 * mm))
            story.append(
                Paragraph(
                    "За последние 24 часа важных новостей не найдено.",
                    styles["empty"],
                )
            )
            continue
        for article in section.articles:
            article_parts = [
                CondPageBreak(52 * mm),
                Paragraph(f"{article.position:02d}", styles["number"]),
                Paragraph(_link(article.url, article.title), styles["article_title"]),
                Paragraph("ЧТО ПРОИЗОШЛО", styles["label"]),
                Paragraph(escape(article.summary), styles["body"]),
                Spacer(1, 2 * mm),
                Paragraph("ПОЧЕМУ ВАЖНО", styles["label"]),
                Paragraph(escape(article.why_it_matters), styles["body"]),
                Spacer(1, 1 * mm),
                Paragraph(
                    f"Источник: {_link(article.url, article.source)}",
                    styles["source"],
                ),
                Spacer(1, 5 * mm),
            ]
            story.extend(article_parts)

    story.extend(
        [
            Spacer(1, 8 * mm),
            CondPageBreak(42 * mm),
            Paragraph("Источники", styles["section_title"]),
        ]
    )
    if sources:
        for position, article in enumerate(sources, 1):
            story.append(
                Paragraph(
                    f"{position}. {_link(article.url, f'{article.source} - {article.title}')}",
                    styles["source_item"],
                )
            )
    else:
        story.append(Paragraph("Ссылок на материалы нет.", styles["empty"]))

    def draw_page(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#697270"))
        canvas.setFont(regular_font, 8)
        if doc.page > 1:
            canvas.drawRightString(A4[0] - 16 * mm, A4[1] - 9 * mm, digest_date)
        canvas.drawCentredString(A4[0] / 2, 10 * mm, str(doc.page))
        canvas.restoreState()

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)


def _register_fonts() -> tuple[str, str]:
    candidates = [
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
    ]
    for regular_path, bold_path in candidates:
        if regular_path.is_file() and bold_path.is_file():
            pdfmetrics.registerFont(TTFont("Assistant", str(regular_path)))
            pdfmetrics.registerFont(TTFont("Assistant-Bold", str(bold_path)))
            return "Assistant", "Assistant-Bold"
    return "Helvetica", "Helvetica-Bold"


def _build_styles(regular_font: str, bold_font: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    petrol = colors.HexColor("#126D68")
    return {
        "eyebrow": ParagraphStyle(
            "Eyebrow",
            parent=base["Normal"],
            fontName=bold_font,
            fontSize=9,
            leading=11,
            textColor=petrol,
            spaceAfter=0,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName=bold_font,
            fontSize=25,
            leading=28,
            alignment=0,
            textColor=colors.HexColor("#171B1A"),
        ),
        "cover_date": ParagraphStyle(
            "CoverDate",
            parent=base["Normal"],
            fontName=regular_font,
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#596260"),
        ),
        "section_title": ParagraphStyle(
            "SectionTitle",
            parent=base["Heading1"],
            fontName=bold_font,
            fontSize=17,
            leading=21,
            textColor=colors.HexColor("#171B1A"),
            spaceAfter=10,
            borderColor=colors.HexColor("#CBD2D0"),
            borderWidth=0,
            borderPadding=(0, 0, 7, 0),
        ),
        "number": ParagraphStyle(
            "Number",
            parent=base["Normal"],
            fontName=bold_font,
            fontSize=8.5,
            leading=10,
            textColor=petrol,
        ),
        "article_title": ParagraphStyle(
            "ArticleTitle",
            parent=base["Heading2"],
            fontName=bold_font,
            fontSize=13.5,
            leading=17,
            textColor=colors.HexColor("#171B1A"),
            spaceAfter=7,
        ),
        "label": ParagraphStyle(
            "Label",
            parent=base["Normal"],
            fontName=bold_font,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#171B1A"),
            spaceBefore=7,
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=regular_font,
            fontSize=10,
            leading=14.2,
            textColor=colors.HexColor("#171B1A"),
        ),
        "source": ParagraphStyle(
            "Source",
            parent=base["Normal"],
            fontName=regular_font,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#596260"),
            spaceBefore=7,
        ),
        "source_item": ParagraphStyle(
            "SourceItem",
            parent=base["Normal"],
            fontName=regular_font,
            fontSize=8.2,
            leading=11,
            leftIndent=4 * mm,
            firstLineIndent=-4 * mm,
            spaceAfter=4,
        ),
        "empty": ParagraphStyle(
            "Empty",
            parent=base["Normal"],
            fontName=regular_font,
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#697270"),
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base["Normal"],
            alignment=TA_CENTER,
        ),
    }


def _link(url: str, label: str) -> str:
    return f"<a href={quoteattr(url)} color='#126D68'>{escape(label)}</a>"


def _with_line_breaks(text: str) -> str:
    return "<br/>".join(escape(line) for line in text.splitlines())
