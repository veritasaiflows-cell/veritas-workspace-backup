import json
from pathlib import Path

import yfinance as yf
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

WORKSPACE = Path(r"C:\Users\Veritas2.0\.openclaw\workspace")
TMP = WORKSPACE / "tmp"
OUT_DIR = WORKSPACE / "06. Playbooks"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TMP.mkdir(parents=True, exist_ok=True)

REPORT_PATH = OUT_DIR / "RTX Analysis - 2026-04-24.docx"
JSON_PATH = TMP / "rtx-analysis-data-v2.json"
PRICE_PANEL = TMP / "rtx-price-panel.png"
EARNINGS_PANEL = TMP / "rtx-earnings-panel.png"
SEGMENT_PANEL = TMP / "rtx-segment-panel.png"
HIST_PANEL = TMP / "rtx-history-panel.png"
YAHOO_SHOT = TMP / "rtx-yahoo-screenshot.png"
IR_SHOT = TMP / "rtx-ir-q1-2026.png"

BG = "#f5f1e8"
CARD = "#ede7da"
TEXT = "#111111"
MUTED = "#3f3f3f"
GREEN = "#0d8a53"
RED = "#b94728"
BLUE1 = "#9fc0e6"
BLUE2 = "#2f79c8"
BLUE3 = "#205e9e"
BLUE4 = "#163f6b"
GRAYBAR = "#cfc8bc"


def money(v):
    if v is None:
        return "N/A"
    a = abs(v)
    if a >= 1_000_000_000:
        return f"${v/1_000_000_000:.1f}B"
    if a >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    return f"${v:,.0f}"


def pct_ratio(v, digits=1):
    if v is None:
        return "N/A"
    value = float(v)
    if abs(value) > 1:
        return f"{value:.{digits}f}%"
    return f"{value*100:.{digits}f}%"


def pct_num(v, digits=1):
    return f"{v:.{digits}f}%"


def load_fonts():
    candidates = [
        r"C:\Windows\Fonts\aptos.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
    ]
    path = next((p for p in candidates if Path(p).exists()), None)
    if path:
        return {
            "title": ImageFont.truetype(path, 34),
            "h1": ImageFont.truetype(path, 26),
            "h2": ImageFont.truetype(path, 21),
            "body": ImageFont.truetype(path, 17),
            "small": ImageFont.truetype(path, 14),
            "metric": ImageFont.truetype(path, 30),
        }
    d = ImageFont.load_default()
    return {k: d for k in ["title", "h1", "h2", "body", "small", "metric"]}


def fetch_data():
    t = yf.Ticker("RTX")
    hist = t.history(period="3y", interval="1d", auto_adjust=False).dropna()
    info = t.info
    close = hist["Close"]
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    ytd_base = close[close.index.year == close.index[-1].year].iloc[0]

    latest = {
        "date": str(hist.index[-1].date()),
        "close": float(close.iloc[-1]),
        "open": float(hist["Open"].iloc[-1]),
        "high": float(hist["High"].iloc[-1]),
        "low": float(hist["Low"].iloc[-1]),
        "volume": int(hist["Volume"].iloc[-1]),
        "ma20": float(ma20.iloc[-1]),
        "ma50": float(ma50.iloc[-1]),
        "ma200": float(ma200.iloc[-1]),
        "high_52w": float(hist["High"].tail(252).max()),
        "low_52w": float(hist["Low"].tail(252).min()),
        "recent_support": float(close.tail(20).min()),
        "recent_resistance": float(close.tail(20).max()),
        "one_year_return_pct": float((close.iloc[-1] / close.iloc[-252] - 1) * 100),
        "ytd_return_pct": float((close.iloc[-1] / ytd_base - 1) * 100),
    }

    price_implied = ((info.get("targetMeanPrice") or 0) / (info.get("currentPrice") or latest["close"]) - 1) * 100 if info.get("targetMeanPrice") else None
    off_peak = (latest["close"] / latest["high_52w"] - 1) * 100

    snapshot = {
        "last_close": f"${latest['close']:.2f}",
        "consensus_target": f"${(info.get('targetMeanPrice') or 0):.2f}" if info.get('targetMeanPrice') else "N/A",
        "market_cap": money(info.get("marketCap")),
        "range_52w": f"${latest['low_52w']:.0f}-${latest['high_52w']:.0f}",
        "dividend_yield": pct_ratio(info.get("dividendYield")),
        "forward_pe": f"~{info.get('forwardPE'):.0f}x" if info.get("forwardPE") else "N/A",
        "target_upside": pct_num(price_implied) if price_implied is not None else "N/A",
        "off_peak": pct_num(off_peak),
        "inst_owned": pct_ratio(info.get("heldPercentInstitutions")),
    }

    q1 = {
        "revenue": "$22.1B",
        "revenue_note": "+8.7% YoY · beat by 2.7%",
        "adj_eps": "$1.78",
        "adj_eps_note": "+21% YoY · beat by 16.9%",
        "adj_ebitda": "$4.09B",
        "adj_ebitda_note": "18.5% margin · beat by 17.7%",
        "backlog": "$271B",
        "backlog_note": "$109B defense · $162B commercial",
        "free_cash_flow": "$1.3B",
        "fcf_note": "FY guide: $8.25-8.75B",
        "op_margin": "11.6%",
        "op_margin_note": "Up from 10% in Q1 2025",
    }

    guidance = {
        "sales": "$92.5-93.5B",
        "sales_note": "Raised +$500M",
        "adj_eps": "$6.70-6.90",
        "adj_eps_note": "Prior: $6.60-6.80",
        "free_cash_flow": "$8.25-8.75B",
        "fcf_note": "Reaffirmed",
    }

    segments = [
        {
            "name": "Raytheon (defense)",
            "headline": "+10% YoY · $6.95B · margin 12.2% (+150bps)",
            "detail": "Air-defense, naval munitions, Tomahawk, AMRAAM, Standard Missile. Framework agreements with Dept. of War pending.",
            "value": 100,
            "color": BLUE3,
        },
        {
            "name": "Pratt & Whitney",
            "headline": "+11% YoY · commercial aftermarket +19%",
            "detail": "GTF and V2500 engine demand strong. GTF Advantage entry into service expected later in 2026.",
            "value": 82,
            "color": GREEN,
        },
        {
            "name": "Collins Aerospace",
            "headline": "+5% YoY · margins flat",
            "detail": "Steady growth, but the lowest performer of the three this quarter.",
            "value": 55,
            "color": "#8f8f8f",
        },
    ]

    hist_fin = {
        "eps_labels": ["2023", "2024", "2025", "2026E"],
        "eps_values": [2.2, 3.6, 5.0, 6.8],
        "rev_labels": ["2023", "2024", "2025", "2026E"],
        "rev_values": [68.9, 74.2, 90.4, 93.0],
    }

    fundamentals = {
        "company": info.get("longName"),
        "exchange": info.get("fullExchangeName") or info.get("exchange"),
        "sector": info.get("sectorDisp") or info.get("sector"),
        "industry": info.get("industryDisp") or info.get("industry"),
        "employees": info.get("fullTimeEmployees"),
        "market_cap": info.get("marketCap"),
        "enterprise_value": info.get("enterpriseValue"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "price_to_sales": info.get("priceToSalesTrailing12Months"),
        "price_to_book": info.get("priceToBook"),
        "dividend_yield": info.get("dividendYield"),
        "profit_margin": info.get("profitMargins"),
        "operating_margin": info.get("operatingMargins"),
        "gross_margin": info.get("grossMargins"),
        "roe": info.get("returnOnEquity"),
        "roa": info.get("returnOnAssets"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "free_cash_flow": info.get("freeCashflow"),
        "operating_cash_flow": info.get("operatingCashflow"),
        "total_revenue": info.get("totalRevenue"),
        "total_debt": info.get("totalDebt"),
        "total_cash": info.get("totalCash"),
        "current_ratio": info.get("currentRatio"),
        "quick_ratio": info.get("quickRatio"),
        "debt_to_equity": info.get("debtToEquity"),
        "analyst_rating": info.get("averageAnalystRating"),
        "recommendation_key": info.get("recommendationKey"),
        "analyst_count": info.get("numberOfAnalystOpinions"),
        "target_mean_price": info.get("targetMeanPrice"),
        "target_median_price": info.get("targetMedianPrice"),
        "target_low_price": info.get("targetLowPrice"),
        "target_high_price": info.get("targetHighPrice"),
        "beta": info.get("beta"),
        "held_percent_institutions": info.get("heldPercentInstitutions"),
    }

    data = {
        "latest": latest,
        "snapshot": snapshot,
        "q1": q1,
        "guidance": guidance,
        "segments": segments,
        "hist_fin": hist_fin,
        "fundamentals": fundamentals,
    }
    JSON_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def round_rect(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_price_panel(data, fonts):
    img = Image.new("RGB", (1700, 860), BG)
    d = ImageDraw.Draw(img)
    d.text((60, 26), "PRICE SNAPSHOT - APR 24, 2026", font=fonts["title"], fill=TEXT)

    cards = [
        ("Last close", data["snapshot"]["last_close"], f"52-wk high: ${data['latest']['high_52w']:.2f}", RED),
        ("Consensus target", data["snapshot"]["consensus_target"], f"{data['snapshot']['target_upside']} implied upside", GREEN),
        ("Market cap", data["snapshot"]["market_cap"], f"{data['snapshot']['inst_owned']} institutional owned", MUTED),
        ("52-wk range", data["snapshot"]["range_52w"], f"{data['snapshot']['off_peak']} from peak", RED),
        ("Dividend yield", data["snapshot"]["dividend_yield"], "5 consecutive annual raises", MUTED),
        ("P/E (fwd)", data["snapshot"]["forward_pe"], "High end of range", MUTED),
    ]
    x_positions = [60, 380, 700, 1020, 1340]
    y1 = 100
    w, h = 280, 180
    for i, (title, value, note, note_color) in enumerate(cards[:5]):
        round_rect(d, (x_positions[i], y1, x_positions[i] + w, y1 + h), 18, CARD)
        d.text((x_positions[i] + 22, y1 + 18), title, font=fonts["h2"], fill=TEXT)
        d.text((x_positions[i] + 22, y1 + 55), value, font=fonts["metric"], fill=TEXT)
        d.text((x_positions[i] + 22, y1 + 102), note, font=fonts["body"], fill=note_color)
    round_rect(d, (60, 255, 280, 405), 18, CARD)
    d.text((82, 273), cards[5][0], font=fonts["h2"], fill=TEXT)
    d.text((82, 312), cards[5][1], font=fonts["metric"], fill=TEXT)
    d.text((82, 355), cards[5][2], font=fonts["body"], fill=MUTED)
    img.save(PRICE_PANEL)


def draw_earnings_panel(data, fonts):
    img = Image.new("RGB", (1600, 900), BG)
    d = ImageDraw.Draw(img)
    d.text((60, 25), "Q1 2026 EARNINGS BEAT", font=fonts["h1"], fill=MUTED)
    q1 = data["q1"]
    cards = [
        ("Revenue", q1["revenue"], q1["revenue_note"]),
        ("Adj. EPS", q1["adj_eps"], q1["adj_eps_note"]),
        ("Adj. EBITDA", q1["adj_ebitda"], q1["adj_ebitda_note"]),
        ("Record backlog", q1["backlog"], q1["backlog_note"]),
        ("Free cash flow", q1["free_cash_flow"], q1["fcf_note"]),
        ("Op. margin", q1["op_margin"], q1["op_margin_note"]),
    ]
    positions = [(60, 80), (360, 80), (660, 80), (960, 80), (60, 270), (360, 270)]
    w, h = 260, 150
    for (title, value, note), (x, y) in zip(cards, positions):
        round_rect(d, (x, y, x + w, y + h), 18, CARD)
        d.text((x + 22, y + 18), title, font=fonts["h2"], fill=TEXT)
        d.text((x + 22, y + 62), value, font=fonts["metric"], fill=TEXT)
        d.text((x + 22, y + 122), note, font=fonts["body"], fill=GREEN)

    d.text((60, 470), "FULL-YEAR 2026 GUIDANCE (RAISED)", font=fonts["h1"], fill=TEXT)
    g = data["guidance"]
    g_cards = [
        ("Adj. sales", g["sales"], g["sales_note"]),
        ("Adj. EPS", g["adj_eps"], g["adj_eps_note"]),
        ("Free cash flow", g["free_cash_flow"], g["fcf_note"]),
    ]
    positions = [(60, 525), (520, 525), (980, 525)]
    gw, gh = 400, 130
    for (title, value, note), (x, y) in zip(g_cards, positions):
        round_rect(d, (x, y, x + gw, y + gh), 18, CARD)
        d.text((x + 20, y + 18), title, font=fonts["h2"], fill=TEXT)
        d.text((x + 20, y + 52), value, font=fonts["metric"], fill=TEXT)
        d.text((x + 20, y + 94), note, font=fonts["body"], fill=GREEN if ("Raised" in note or "Reaffirmed" in note) else MUTED)
    img.save(EARNINGS_PANEL)


def draw_segment_panel(data, fonts):
    img = Image.new("RGB", (1700, 620), BG)
    d = ImageDraw.Draw(img)
    d.text((40, 20), "SEGMENT PERFORMANCE - Q1 2026", font=fonts["title"], fill=TEXT)
    round_rect(d, (30, 70, 1410, 430), 22, "#fbfaf7", outline="#d1cbc0")
    y = 105
    for seg in data["segments"]:
        d.text((70, y), seg["name"], font=fonts["h2"], fill=TEXT)
        bbox = d.textbbox((0,0), seg["headline"], font=fonts["h2"])
        width = bbox[2]-bbox[0]
        d.text((1370 - width, y), seg["headline"], font=fonts["h2"], fill=GREEN if seg["color"] != "#8f8f8f" else MUTED)
        yb = y + 40
        d.rounded_rectangle((70, yb, 1370, yb + 16), radius=8, fill=GRAYBAR)
        d.rounded_rectangle((70, yb, 70 + int(1300 * seg["value"] / 100), yb + 16), radius=8, fill=seg["color"])
        d.text((70, yb + 32), seg["detail"], font=fonts["body"], fill=TEXT)
        y += 125
    img.save(SEGMENT_PANEL)


def draw_bar_chart(draw, origin, size, labels, values, colors, title, y_prefix="", y_suffix=""):
    x0, y0 = origin
    w, h = size
    draw.text((x0, y0 - 42), title, font=FONTS["h1"], fill=TEXT)
    plot_top = y0 + 10
    plot_bottom = y0 + h
    plot_left = x0 + 40
    plot_right = x0 + w
    maxv = max(values) * 1.15
    for i in range(0, 6):
        y = plot_bottom - int((plot_bottom - plot_top) * i / 5)
        draw.line((plot_left, y, plot_right, y), fill="#d2cbc0", width=2)
        label = f"{y_prefix}{maxv*i/5:.0f}{y_suffix}"
        draw.text((x0, y - 8), label, font=FONTS["small"], fill=MUTED)
    n = len(values)
    gap = 44
    bar_w = int((plot_right - plot_left - gap * (n - 1)) / n)
    for i, (lab, val, col) in enumerate(zip(labels, values, colors)):
        bx = plot_left + i * (bar_w + gap)
        bh = int((val / maxv) * (plot_bottom - plot_top - 10))
        by = plot_bottom - bh
        draw.rectangle((bx, by, bx + bar_w, plot_bottom), fill=col)
        tw = draw.textbbox((0,0), lab, font=FONTS["body"])[2]
        draw.text((bx + (bar_w - tw) / 2, plot_bottom + 14), lab, font=FONTS["body"], fill=TEXT)


def draw_history_panel(data, fonts):
    global FONTS
    FONTS = fonts
    img = Image.new("RGB", (1600, 700), BG)
    d = ImageDraw.Draw(img)
    colors = [BLUE1, BLUE2, BLUE3, BLUE4]
    draw_bar_chart(d, (40, 50), (680, 520), data["hist_fin"]["eps_labels"], data["hist_fin"]["eps_values"], colors, "HISTORICAL EPS TRAJECTORY", y_prefix="$", y_suffix="")
    draw_bar_chart(d, (820, 50), (680, 520), data["hist_fin"]["rev_labels"], data["hist_fin"]["rev_values"], colors, "HISTORICAL REVENUE TRAJECTORY", y_prefix="$", y_suffix="B")
    img.save(HIST_PANEL)


def set_normal_font(document):
    styles = document.styles
    styles["Normal"].font.name = "Aptos"
    styles["Normal"].font.size = Pt(10.5)


def add_title(document, title, subtitle):
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(title)
    r.bold = True
    r.font.size = Pt(18)
    p2 = document.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run(subtitle)
    r2.italic = True
    r2.font.size = Pt(10)


def add_bullets(document, items):
    for item in items:
        document.add_paragraph(item, style="List Bullet")


def add_metric_table(document, rows):
    table = document.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "Metric"
    hdr[1].text = "Value"
    for key, value in rows:
        c = table.add_row().cells
        c[0].text = str(key)
        c[1].text = str(value)
    return table


def build_doc(data):
    latest = data["latest"]
    f = data["fundamentals"]
    doc = Document()
    set_normal_font(doc)
    add_title(doc, "RTX Corporation (NYSE: RTX) Full Analysis", "Upgraded visual report with market snapshot, Q1 earnings, guidance, segments, analyst context, and historical trend panels. Data cleaned for percentage-format consistency.")

    doc.add_heading("1. Executive Summary", level=1)
    add_bullets(doc, [
        f"RTX closed at ${latest['close']:.2f} on {latest['date']}, with the stock still below the 20-day, 50-day, and 200-day moving averages.",
        f"Analyst consensus is still constructive, with a mean target of ${f['target_mean_price']:.2f}, {f['analyst_count']} analysts, and an average rating of {f['analyst_rating']}.",
        "Q1 2026 reporting was operationally solid, with revenue, adjusted EPS, free cash flow, and backlog metrics supporting the argument that RTX remains a real institutional-quality business.",
        "Management raised 2026 sales guidance and the EPS range while reaffirming free-cash-flow guidance, which is fundamentally supportive.",
        "The problem remains technical. A good quarter and decent guidance do not automatically make a broken or weak chart deployable.",
        "Data-quality note: company-market fields and analyst metrics were pulled live, while the earnings, guidance, and segment visual blocks were intentionally curated from the reported quarter so the report reads cleanly instead of depending on fragile web extraction."
    ])

    doc.add_heading("2. Visual Snapshot", level=1)
    doc.add_picture(str(PRICE_PANEL), width=Inches(6.7))
    doc.add_paragraph("This panel shows the current price context, consensus target, market value, 52-week range, dividend profile, and forward multiple at a glance.")

    doc.add_heading("3. Q1 2026 Results and Guidance", level=1)
    doc.add_picture(str(EARNINGS_PANEL), width=Inches(6.7))
    doc.add_paragraph("This panel captures the quarter's headline results and the updated full-year 2026 guidance frame. The quarter was fundamentally supportive, even if the stock's post-earnings chart has not yet confirmed that support.")

    doc.add_heading("4. Segment Performance", level=1)
    doc.add_picture(str(SEGMENT_PANEL), width=Inches(6.7))
    add_bullets(doc, [
        "Raytheon led with the strongest defense read-through, supported by missile and air-defense demand.",
        "Pratt & Whitney also contributed strong growth, with commercial aftermarket strength doing real work.",
        "Collins Aerospace remained positive, but it was the softest of the three major segments in this quarter's framing."
    ])

    doc.add_heading("5. Historical EPS and Revenue Trend", level=1)
    doc.add_picture(str(HIST_PANEL), width=Inches(6.7))
    doc.add_paragraph("The trend panel reinforces the core fundamental point: RTX is not a low-quality story stock. The business has shown meaningful earnings and revenue progression, with 2026 expectations still moving higher.")

    doc.add_heading("6. Analyst Setup", level=1)
    add_metric_table(doc, [
        ("Current price", f"${latest['close']:.2f}"),
        ("Consensus target", f"${f['target_mean_price']:.2f}"),
        ("Median target", f"${f['target_median_price']:.2f}"),
        ("Target range", f"${f['target_low_price']:.2f} to ${f['target_high_price']:.2f}"),
        ("Average analyst rating", f['analyst_rating']),
        ("Recommendation", str(f['recommendation_key']).title() if f['recommendation_key'] else "N/A"),
        ("Analyst count", f['analyst_count']),
    ])
    add_bullets(doc, [
        "Consensus is still broadly constructive, which means the market has not abandoned the long-term business case.",
        "That does not override the current chart. Analyst upside is useful context, not an entry trigger.",
        "If price continues to deteriorate, target-based upside can stay theoretical for a long time."
    ])

    doc.add_heading("7. Financial Quality and Valuation", level=1)
    add_metric_table(doc, [
        ("Market cap", money(f['market_cap'])),
        ("Enterprise value", money(f['enterprise_value'])),
        ("Total revenue", money(f['total_revenue'])),
        ("Free cash flow", money(f['free_cash_flow'])),
        ("Operating cash flow", money(f['operating_cash_flow'])),
        ("Total debt", money(f['total_debt'])),
        ("Total cash", money(f['total_cash'])),
        ("Trailing P/E", f"{f['trailing_pe']:.1f}" if f['trailing_pe'] else "N/A"),
        ("Forward P/E", f"{f['forward_pe']:.1f}" if f['forward_pe'] else "N/A"),
        ("Price / Sales", f"{f['price_to_sales']:.2f}" if f['price_to_sales'] else "N/A"),
        ("Price / Book", f"{f['price_to_book']:.2f}" if f['price_to_book'] else "N/A"),
        ("Dividend yield", pct_ratio(f['dividend_yield'])),
        ("Profit margin", pct_ratio(f['profit_margin'])),
        ("Operating margin", pct_ratio(f['operating_margin'])),
        ("Gross margin", pct_ratio(f['gross_margin'])),
        ("ROE", pct_ratio(f['roe'])),
        ("ROA", pct_ratio(f['roa'])),
        ("Revenue growth", pct_ratio(f['revenue_growth'])),
        ("Earnings growth", pct_ratio(f['earnings_growth'])),
        ("Current ratio", f"{f['current_ratio']:.2f}" if f['current_ratio'] else "N/A"),
        ("Quick ratio", f"{f['quick_ratio']:.2f}" if f['quick_ratio'] else "N/A"),
        ("Debt / equity", f"{f['debt_to_equity']:.1f}" if f['debt_to_equity'] else "N/A"),
    ])

    doc.add_heading("8. Technical Verdict", level=1)
    add_bullets(doc, [
        f"RTX is below the 20-day (${latest['ma20']:.2f}), 50-day (${latest['ma50']:.2f}), and 200-day (${latest['ma200']:.2f}) moving averages.",
        f"Recent support is near ${latest['recent_support']:.2f}. Recent resistance is near ${latest['recent_resistance']:.2f}.",
        "That posture is weak. It does not support a fresh aggressive long entry today.",
        "The right upgrade path is a repair sequence: stabilize, reclaim the 20-day, then reclaim the 50-day with a defined entry band and invalidation.",
        "Until that happens, RTX remains a bench name, not an active deployment candidate."
    ])
    if YAHOO_SHOT.exists():
        doc.add_picture(str(YAHOO_SHOT), width=Inches(5.8))
    if IR_SHOT.exists():
        doc.add_picture(str(IR_SHOT), width=Inches(5.8))

    doc.add_heading("9. Bottom Line", level=1)
    doc.add_paragraph(
        "RTX now has a better report. Fundamentally, it looks like what it is: a large, real aerospace and defense franchise with solid quarterly execution, improved full-year guidance, strong backlog, and continuing analyst support. But the stock still does not look ready. The technical picture remains weak enough that the correct call is still patience. In this framework, RTX belongs on the tactical aerospace and defense bench until price structure improves. The report supports keeping it in coverage. It does not support forcing capital into it today."
    )

    doc.save(REPORT_PATH)


def main():
    data = fetch_data()
    fonts = load_fonts()
    draw_price_panel(data, fonts)
    draw_earnings_panel(data, fonts)
    draw_segment_panel(data, fonts)
    draw_history_panel(data, fonts)
    build_doc(data)
    print(json.dumps({
        "report_path": str(REPORT_PATH),
        "price_panel": str(PRICE_PANEL),
        "earnings_panel": str(EARNINGS_PANEL),
        "segment_panel": str(SEGMENT_PANEL),
        "history_panel": str(HIST_PANEL),
        "data_path": str(JSON_PATH)
    }, indent=2))


if __name__ == "__main__":
    main()
