import logging
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.digest import DailyDigest, DigestArticle

logger = logging.getLogger(__name__)

RUSSIAN_MONTHS = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)

SECTION_TITLES = (
    ("ai", "Искусственный интеллект"),
    ("russian_market", "Российский рынок"),
    ("geopolitics", "Геополитика"),
    ("russia_ukraine", "Россия - Украина"),
    ("startups", "Стартапы и венчурный рынок"),
)


@dataclass(frozen=True, slots=True)
class PdfArticle:
    position: int
    title: str
    url: str
    source: str
    summary: str
    why_it_matters: str


@dataclass(frozen=True, slots=True)
class PdfSection:
    title: str
    articles: list[PdfArticle]


class DigestPdfService:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        template_dir = Path(__file__).parent / "templates"
        self.environment = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(("html", "xml")),
        )

    def generate(self, digest: DailyDigest) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / f"daily_digest_{digest.date.isoformat()}.pdf"
        temporary_path = output_path.with_suffix(".tmp.pdf")
        sections, sources = _build_sections(digest.articles)
        template = self.environment.get_template("daily_digest.html")
        html = template.render(
            digest_date=_format_date(digest.date.day, digest.date.month, digest.date.year),
            intro=digest.intro or "Значимых событий по выбранным темам не найдено.",
            sections=sections,
            sources=sources,
        )
        if not _write_with_weasyprint(html, temporary_path):
            from app.pdf.reportlab_fallback import write_digest_pdf

            write_digest_pdf(
                temporary_path,
                digest_date=_format_date(digest.date.day, digest.date.month, digest.date.year),
                intro=digest.intro or "Значимых событий по выбранным темам не найдено.",
                sections=sections,
                sources=sources,
            )
        temporary_path.replace(output_path)
        logger.info("PDF generated: %s", output_path.name)
        return output_path.resolve()


def _build_sections(
    digest_articles: list[DigestArticle],
) -> tuple[list[PdfSection], list[PdfArticle]]:
    by_section: dict[str, list[PdfArticle]] = {key: [] for key, _ in SECTION_TITLES}
    sources: list[PdfArticle] = []
    seen_urls: set[str] = set()
    for link in digest_articles:
        article = PdfArticle(
            position=link.position,
            title=link.article.title,
            url=link.article.url,
            source=link.article.source,
            summary=link.summary,
            why_it_matters=link.why_it_matters,
        )
        by_section.setdefault(link.section, []).append(article)
        if article.url not in seen_urls:
            sources.append(article)
            seen_urls.add(article.url)
    sections = [PdfSection(title, by_section[key]) for key, title in SECTION_TITLES]
    return sections, sources


def _format_date(day: int, month: int, year: int) -> str:
    return f"{day} {RUSSIAN_MONTHS[month]} {year}"


def _write_with_weasyprint(html: str, output_path: Path) -> bool:
    try:
        from weasyprint import HTML  # type: ignore[import-untyped]
    except (ImportError, OSError):
        logger.warning("WeasyPrint system libraries unavailable; using ReportLab fallback")
        return False
    HTML(string=html, base_url=str(Path(__file__).parent)).write_pdf(output_path)
    return True
