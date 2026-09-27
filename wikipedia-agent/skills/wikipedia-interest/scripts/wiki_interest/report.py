"""One-page A4 PDF: Summary -> Key details -> Next steps, with method and limitations."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepInFrame, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .charts import FONTS

pdfmetrics.registerFont(TTFont("DejaVu", str(FONTS / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(FONTS / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold")

H1 = ParagraphStyle("h1", fontName="DejaVu-Bold", fontSize=15, leading=18, spaceAfter=1)
H2 = ParagraphStyle("h2", fontName="DejaVu-Bold", fontSize=9.5, leading=12, spaceBefore=4, spaceAfter=1)
BODY = ParagraphStyle("body", fontName="DejaVu", fontSize=8.3, leading=10.8)
SMALL = ParagraphStyle("small", fontName="DejaVu", fontSize=6.8, leading=8.4, textColor=colors.HexColor("#52514e"))
CELL = ParagraphStyle("cell", fontName="DejaVu", fontSize=7, leading=8.4)

LIMITATIONS = [
    "Pageviews measure reading on Wikipedia, not purchase intent or willingness to pay.",
    "Raw totals are not comparable across editions (different audience sizes); compare trends and edition-adjusted share instead.",
    "Only the exact article titles listed are counted; views arriving via redirects or related articles are excluded.",
    "Readers of a language edition are not a country: e.g. English or Russian editions serve many countries.",
    "Agent filter 'user' excludes self-identified bots and 'automated' traffic, but some undetected automation may remain.",
]


def _fmt(v, suffix="%"):
    return "–" if v is None else f"{v:+.1f}{suffix}"


def _p(text: str, style=BODY) -> Paragraph:
    return Paragraph(escape(text), style)


def build(analysis: dict, chart: str, path: str, summary: str | None = None,
          findings: list[str] | None = None, next_steps: list[str] | None = None) -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=10 * mm, bottomMargin=8 * mm, title=f"Wikipedia interest: {analysis['topic']}")
    p = analysis["params"]
    story = [_p(f"Wikipedia interest: {analysis['topic']}", H1),
             _p(f"{', '.join(p['languages'])} Wikipedia · {p['start'][:7]} to {p['end'][:7]} · monthly, human readers", SMALL)]

    story += [_p("Summary", H2), _p(summary or analysis["auto_summary"])]
    story += [Spacer(1, 2 * mm), Image(chart, width=186 * mm, height=76 * mm)]

    header = ["Edition", "Article(s)", "Median / month", "Growth", "Edition-adj.", "Trend p", "Confidence"]
    rows = [header]
    for lang, m in analysis["series"].items():
        arts = "; ".join(a["title"] for a in analysis["resolution"]["languages"][lang]["articles"])
        rows.append([lang, Paragraph(escape(arts), CELL), f"{m.get('median_monthly_views', 0):,}",
                     _fmt(m.get("growth_pct")), _fmt(m.get("share_growth_pct")),
                     "–" if "trend_test" not in m else f"{m['trend_test']['p_value']:.3f}", m.get("confidence", "–")])
    table = Table(rows, colWidths=[15 * mm, 58 * mm, 24 * mm, 20 * mm, 22 * mm, 17 * mm, 22 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "DejaVu"), ("FONTNAME", (0, 0), (-1, 0), "DejaVu-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7), ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#52514e")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#e4e3df")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT")]))
    story += [_p("Key details", H2), table,
              _p(f"Growth basis: {next(iter(analysis['series'].values()), {}).get('growth_basis', '–')}. "
                 "Edition-adj. = change in the article's share of all views in that edition. "
                 "Trend p = seasonal Mann-Kendall test (lower = more consistent trend).", SMALL)]

    for f in findings or analysis["auto_findings"]:
        story.append(_p("• " + f))

    steps = next_steps or analysis.get("auto_next_steps") or []
    if steps:
        story += [_p("Recommended next steps", H2)] + [_p("• " + s) for s in steps]

    notes = list(LIMITATIONS) + analysis.get("warnings", [])
    story += [_p("Method & limitations", H2)] + [_p("• " + n, SMALL) for n in notes]
    story.append(_p(
        f"Source: Wikimedia Analytics API (pageviews per-article and aggregate, {p['access']}, agent={p['agent']}). "
        f"Articles matched via Wikidata interlanguage links from {analysis['resolution']['source_lang']} Wikipedia. "
        f"Run {analysis['run_id']}, generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.", SMALL))

    doc.build([KeepInFrame(doc.width, doc.height, story, mode="shrink")])  # guarantees a single page
    return path
