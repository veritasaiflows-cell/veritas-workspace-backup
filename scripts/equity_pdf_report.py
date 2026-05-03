import argparse
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
PLAYBOOKS = WORKSPACE / "06. Playbooks"
TMP.mkdir(parents=True, exist_ok=True)
PLAYBOOKS.mkdir(parents=True, exist_ok=True)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_pdf(data, out_path):
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="VeritasTitle", parent=styles["Title"], fontSize=20, leading=24, textColor=colors.HexColor("#111111")))
    styles.add(ParagraphStyle(name="VeritasSub", parent=styles["Normal"], fontSize=10, leading=12, textColor=colors.HexColor("#3f3f3f")))
    styles.add(ParagraphStyle(name="VeritasHead", parent=styles["Heading2"], fontSize=14, leading=18, textColor=colors.HexColor("#111111")))
    styles.add(ParagraphStyle(name="VeritasBody", parent=styles["BodyText"], fontSize=10.5, leading=14, textColor=colors.HexColor("#111111")))
    styles.add(ParagraphStyle(name="VeritasAlert", parent=styles["BodyText"], fontSize=10.5, leading=14, textColor=colors.HexColor("#8b1e00")))

    latest = data["latest"]
    f = data["fundamentals"]
    verdict = data.get("verdict", "WATCH / BENCH")
    verdict_reason = data.get("verdict_reason", "Technical structure still needs work.")

    safe = data["ticker"].lower().replace(".", "-")
    price_panel = TMP / f"{safe}-price-panel.png"
    history_panel = TMP / f"{safe}-history-panel.png"

    doc = SimpleDocTemplate(str(out_path), pagesize=letter, rightMargin=0.6 * inch, leftMargin=0.6 * inch, topMargin=0.55 * inch, bottomMargin=0.55 * inch)
    story = []

    story.append(Paragraph(f"{f['company']} ({data['ticker']}) PDF Brief", styles["VeritasTitle"]))
    story.append(Paragraph("Veritas finance-first fixed-layout brief", styles["VeritasSub"]))
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph(
        f"<b>VERITAS ALERT:</b> {data['ticker']} closed at ${latest['close']:.2f} on {latest['date']}. "
        f"Current status: <b>{verdict}</b>. {verdict_reason}", styles["VeritasAlert"]))
    story.append(Spacer(1, 0.16 * inch))

    story.append(Paragraph("1. Executive Summary", styles["VeritasHead"]))
    story.append(Paragraph(
        f"{f['company']} remains a serious large-cap company with real scale, institutional support, and durable relevance in {f['sector']} / {f['industry']}. "
        f"Analyst context remains constructive, with a mean target of ${f['target_mean_price']:.2f}, {f['analyst_count']} analysts, and a rating of {f['analyst_rating']}.", styles["VeritasBody"]))
    story.append(Paragraph(
        f"At the market level, the stock closed at ${latest['close']:.2f}, with recent support near ${latest['recent_support']:.2f}, resistance near ${latest['recent_resistance']:.2f}, and 20-day / 50-day / 200-day levels at ${latest['ma20']:.2f} / ${latest['ma50']:.2f} / ${latest['ma200']:.2f}. "
        f"That means the timing call is driven by setup quality, not admiration for the business.", styles["VeritasBody"]))
    story.append(Paragraph(
        f"Bottom line: the company remains worth covering, but the current verdict is {verdict}. Any upgrade needs better technical repair and a cleaner risk-defined setup.", styles["VeritasBody"]))
    story.append(Spacer(1, 0.14 * inch))

    story.append(Paragraph("2. Company Snapshot", styles["VeritasHead"]))
    rows = [
        ["Ticker", f"{data['ticker']} ({f['exchange']})"],
        ["Full name", f['company']],
        ["Sector / industry", f"{f['sector']} / {f['industry']}"],
        ["Market cap", data['snapshot']['market_cap']],
        ["Consensus target", data['snapshot']['consensus_target']],
        ["Dividend yield", data['snapshot']['dividend_yield']],
        ["Current status", verdict],
    ]
    table = Table(rows, colWidths=[1.9 * inch, 4.7 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#eef2f7"), colors.white]),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111111")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.16 * inch))

    if price_panel.exists():
        story.append(Paragraph("3. Visual Snapshot", styles["VeritasHead"]))
        story.append(Image(str(price_panel), width=6.7 * inch, height=3.4 * inch))
        story.append(Spacer(1, 0.12 * inch))

    if history_panel.exists():
        story.append(Paragraph("4. Historical Trend", styles["VeritasHead"]))
        story.append(Image(str(history_panel), width=6.7 * inch, height=3.0 * inch))
        story.append(Spacer(1, 0.12 * inch))

    story.append(Paragraph("5. Action View", styles["VeritasHead"]))
    story.append(Paragraph(
        f"Verdict: <b>{verdict}</b>. {verdict_reason} Analyst support and business quality may remain constructive, but the current market posture still argues for patience over deployment.", styles["VeritasBody"]))

    doc.build(story)


def main():
    parser = argparse.ArgumentParser(description="Generate a PDF brief from visual equity report assets.")
    parser.add_argument("ticker", help="Ticker symbol, e.g. RTX")
    parser.add_argument("--data-json", default=None, help="Optional JSON data path")
    parser.add_argument("--out", default=None, help="Optional PDF output path")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    safe = ticker.lower().replace(".", "-")
    default_paths = [
        TMP / f"{safe}-visual-report-data.json",
        TMP / f"{safe}-analysis-data-v2.json",
        TMP / "rtx-analysis-data-v2.json",
    ]
    data_path = Path(args.data_json) if args.data_json else next((p for p in default_paths if p.exists()), None)
    if not data_path or not data_path.exists():
        raise SystemExit(f"No data JSON found for {ticker}. Expected one of: {default_paths}")

    data = load_json(data_path)
    out_path = Path(args.out) if args.out else PLAYBOOKS / f"{ticker} PDF Brief - {data['latest']['date']}.pdf"
    build_pdf(data, out_path)
    print(json.dumps({"ticker": ticker, "data_path": str(data_path), "pdf_path": str(out_path)}, indent=2))


if __name__ == "__main__":
    main()
