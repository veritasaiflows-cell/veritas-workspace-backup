import json
from pathlib import Path

import requests
import yfinance as yf
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

WORKSPACE = Path(r"C:\Users\Veritas2.0\.openclaw\workspace")
TMP = WORKSPACE / "tmp"
OUT_DIR = WORKSPACE / "06. Playbooks"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TMP.mkdir(parents=True, exist_ok=True)

TICKER = "RTX"
REPORT_PATH = OUT_DIR / "RTX Analysis - 2026-04-24.docx"
DATA_PATH = TMP / "rtx-analysis-data.json"
YAHOO_SHOT = TMP / "rtx-yahoo-screenshot.png"
IR_SHOT = TMP / "rtx-ir-q1-2026.png"


def money(v):
    if v is None:
        return "N/A"
    a = abs(v)
    if a >= 1_000_000_000:
        return f"${v/1_000_000_000:.1f}B"
    if a >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    return f"${v:,.0f}"


def pct_ratio(v):
    if v is None:
        return "N/A"
    return f"{v*100:.1f}%"


def fetch_data():
    t = yf.Ticker(TICKER)
    hist = t.history(period="1y", interval="1d", auto_adjust=False).dropna()
    info = t.info
    close = hist["Close"]
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    year_start = close[close.index.year == close.index[-1].year].iloc[0]

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
        "one_year_return_pct": float((close.iloc[-1] / close.iloc[0] - 1) * 100),
        "ytd_return_pct": float((close.iloc[-1] / year_start - 1) * 100),
    }

    fundamentals = {
        "company": info.get("longName"),
        "exchange": info.get("fullExchangeName") or info.get("exchange"),
        "sector": info.get("sectorDisp") or info.get("sector"),
        "industry": info.get("industryDisp") or info.get("industry"),
        "employees": info.get("fullTimeEmployees"),
        "summary": info.get("longBusinessSummary"),
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
        "beta": info.get("beta"),
    }

    earnings = {
        "q1_call_date": "April 21, 2026 at 8:30 AM EDT",
        "next_estimated_earnings_date": "July 21, 2026 (yfinance estimate)",
    }

    payload = {"latest": latest, "fundamentals": fundamentals, "earnings": earnings}
    DATA_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


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
    e = data["earnings"]

    doc = Document()
    set_normal_font(doc)
    add_title(
        doc,
        "RTX Corporation (NYSE: RTX) Full Analysis",
        "Prepared from workspace context, live market data, and RTX investor-relations materials. Date anchored to 2026-04-24 close.",
    )

    doc.add_heading("1. Executive Summary", level=1)
    add_bullets(doc, [
        f"RTX closed at ${latest['close']:.2f} on {latest['date']}, well below its 52-week high of ${latest['high_52w']:.2f} and currently below the 20-day, 50-day, and 200-day moving averages.",
        "Fundamentally, RTX remains a serious aerospace and defense franchise with scale, diversified end markets, and meaningful defense plus commercial aerospace relevance.",
        "Technically, the setup is weak. The stock is not in a clean long-entry posture today, and the current chart does not justify forcing a position.",
        "Q1 2026 earnings are no longer an anticipation event. They were formally presented on April 21, 2026. The real issue now is post-earnings price behavior and whether the stock can repair structure.",
        "Bottom line: credible business, weak setup, bench candidate rather than active deployment candidate right now."
    ])

    doc.add_heading("2. Price Snapshot", level=1)
    add_metric_table(doc, [
        ("Close", f"${latest['close']:.2f}"),
        ("Open", f"${latest['open']:.2f}"),
        ("Day high", f"${latest['high']:.2f}"),
        ("Day low", f"${latest['low']:.2f}"),
        ("Volume", f"{latest['volume']:,}"),
        ("20-day MA", f"${latest['ma20']:.2f}"),
        ("50-day MA", f"${latest['ma50']:.2f}"),
        ("200-day MA", f"${latest['ma200']:.2f}"),
        ("52-week high", f"${latest['high_52w']:.2f}"),
        ("52-week low", f"${latest['low_52w']:.2f}"),
        ("Recent support", f"${latest['recent_support']:.2f}"),
        ("Recent resistance", f"${latest['recent_resistance']:.2f}"),
        ("YTD return", f"{latest['ytd_return_pct']:.1f}%"),
        ("1-year return", f"{latest['one_year_return_pct']:.1f}%"),
    ])
    if YAHOO_SHOT.exists():
        doc.add_paragraph("Visual: live market snapshot")
        doc.add_picture(str(YAHOO_SHOT), width=Inches(5.9))

    doc.add_heading("3. Business Overview", level=1)
    add_bullets(doc, [
        f"Company: {f['company'] or 'RTX Corporation'}",
        f"Exchange: {f['exchange'] or 'NYSE'}",
        f"Sector / Industry: {f['sector'] or 'Industrials'} / {f['industry'] or 'Aerospace & Defense'}",
        f"Employees: {f['employees']:,}" if f['employees'] else "Employees: N/A",
        "RTX operates through Collins Aerospace, Pratt & Whitney, and Raytheon, which gives it diversified exposure to commercial aerospace systems, propulsion, and defense systems.",
        "That diversification is a real strength. It lowers single-program dependence, but it does not eliminate execution risk."
    ])

    doc.add_heading("4. Q1 2026 Earnings Context", level=1)
    add_bullets(doc, [
        f"RTX investor relations lists the Q1 2026 earnings conference call on {e['q1_call_date']}.",
        "The investor-relations event page also provides supporting materials including a presentation and press release, confirming that the quarter is fully in the market rather than still pending.",
        f"The next estimated earnings date in the market data layer is {e['next_estimated_earnings_date']}.",
        "For portfolio timing, this means RTX is no longer blocked by an imminent Q1 report. The more important question is whether the post-earnings tape confirms or rejects the bullish case.",
        "Right now, the stock's weak moving-average posture suggests the market is still unconvinced or at least not willing to reward the quarter with a clean trend reset."
    ])
    if IR_SHOT.exists():
        doc.add_paragraph("Visual: RTX investor-relations Q1 2026 earnings event page")
        doc.add_picture(str(IR_SHOT), width=Inches(6.0))

    doc.add_heading("5. Financial Quality and Valuation", level=1)
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
    add_bullets(doc, [
        "RTX has real scale and real cash generation. This is not a speculative defense concept stock.",
        "The balance sheet is workable, not pristine. Debt is meaningful, but manageable given scale and cash flow.",
        "The forward earnings multiple is materially lower than the trailing multiple, which tells you the market still expects improved execution or earnings power ahead.",
        "That matters because valuation is not cheap enough to excuse a broken chart by itself."
    ])

    doc.add_heading("6. Technical Analysis", level=1)
    add_bullets(doc, [
        f"RTX is below the 20-day (${latest['ma20']:.2f}), 50-day (${latest['ma50']:.2f}), and 200-day (${latest['ma200']:.2f}) moving averages.",
        "That is the opposite of what you want in a clean new deployment candidate.",
        f"Recent support sits near ${latest['recent_support']:.2f}. Recent resistance sits near ${latest['recent_resistance']:.2f}. A reclaim of the recent resistance zone would improve the tape, but the stock is not there now.",
        "Price sitting at the low end of the recent range is a warning sign unless there is clear reversal evidence. Right now this looks more like weakness than controlled pullback quality.",
        "In the Veritas framework, RTX is underdefined and weak enough to stay on the bench until a better base forms."
    ])

    doc.add_heading("7. Portfolio Fit", level=1)
    add_bullets(doc, [
        "Role: Tactical aerospace / defense watch",
        "Fundamental fit: Acceptable to strong",
        "Technical state: Weak / underdefined",
        "Current action: Bench / no action",
        "Upgrade trigger: reclaim the 20-day and 50-day, stabilize above fresh support, and define a real entry band plus invalidation",
        "Downgrade trigger: continued weakness below recent lows, bad post-earnings read-through, or worsening execution narrative"
    ])

    doc.add_heading("8. Key Risks", level=1)
    add_bullets(doc, [
        "Aerospace and defense execution risk can offset the benefit of thematic appeal.",
        "Supply-chain or engine-program issues can drag sentiment and margins even when long-cycle demand is healthy.",
        "A weak chart can trap capital in a mediocre holding period while better opportunities exist elsewhere.",
        "The market may require more proof of execution before rewarding RTX with a durable rerating."
    ])

    doc.add_heading("9. Bottom Line", level=1)
    doc.add_paragraph(
        "RTX is a serious company with a credible long-term business mix, but the stock is not in a serious entry posture today. The chart is weak, the setup is underdefined, and the post-earnings tape has not yet earned the benefit of the doubt. That does not make RTX a bad business. It makes it a bad force-buy. The right stance today is patience. Keep it on the tactical aerospace and defense board, but do not treat it as deployable until price repairs and the risk envelope becomes cleaner."
    )

    doc.save(REPORT_PATH)


def main():
    data = fetch_data()
    build_doc(data)
    print(json.dumps({"report_path": str(REPORT_PATH), "data_path": str(DATA_PATH)}, indent=2))


if __name__ == "__main__":
    main()
