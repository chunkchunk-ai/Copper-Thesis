from __future__ import annotations
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "history.db"

# ── Factor weights — horizon-specific (each horizon must sum to 1.0) ──────────
FACTOR_WEIGHTS: dict[str, dict[str, float]] = {
    "1m": {
        "supply_deficit":  0.20,
        "electrification": 0.10,
        "ai_datacenter":   0.15,
        "global_demand":   0.20,
        "inventories":     0.12,
        "macro":           0.10,
        "copper_price":    0.13,
    },
    "6m": {
        "supply_deficit":  0.26,
        "electrification": 0.16,
        "ai_datacenter":   0.13,
        "global_demand":   0.15,
        "inventories":     0.10,
        "macro":           0.05,
        "copper_price":    0.15,
    },
    "1y": {
        "supply_deficit":  0.36,
        "electrification": 0.20,
        "ai_datacenter":   0.11,
        "global_demand":   0.12,
        "inventories":     0.05,
        "macro":           0.04,
        "copper_price":    0.12,
    },
}

FACTOR_LABELS: dict[str, str] = {
    "supply_deficit":  "Structural Supply Deficit",
    "electrification": "Global Electrification",
    "ai_datacenter":   "AI & Data Center Buildout",
    "global_demand":   "Global Industrial Demand",
    "inventories":     "Inventory Levels",
    "macro":           "Macro: Rates, Inflation & Cycle",
    "copper_price":    "Copper Price Dynamics",
}

# ── Composite signal thresholds ───────────────────────────────────────────────
SIGNAL_THRESHOLDS: dict[str, float] = {
    "increase": 62.0,
    "reduce":   42.0,
}

# ── Minimum valid sub-signals required to score a factor ─────────────────────
MIN_VALID_SIGNALS: int = 1

# ── Scoring horizons: label → rolling window in trading days ─────────────────
HORIZONS: dict[str, int] = {
    "1m":  21,   # ~1 trading month
    "6m":  126,  # ~6 trading months
    "1y":  252,  # ~1 trading year
}

# ── yfinance tickers ──────────────────────────────────────────────────────────
YFINANCE_TICKERS: dict[str, str] = {
    "copper":    "HG=F",      # Copper front-month futures (USD/lb)
    "gold":      "GC=F",      # Gold futures (Cu/Au ratio proxy)
    "copx":      "COPX",      # Global copper miners ETF
    "cper":      "CPER",      # US Copper Index Fund (physical proxy)
    "fxi":       "FXI",       # iShares China Large-Cap ETF
    "dxy":       "DX-Y.NYB",  # US Dollar Index (ICE)
    "tip":       "TIP",       # iShares TIPS Bond ETF
    "tlt":       "TLT",       # iShares 20+ Year Treasury
    "xlu":       "XLU",       # Utilities Select Sector SPDR
    "vst":       "VST",       # Vistra Corp (power demand proxy)
    "ceg":       "CEG",       # Constellation Energy (nuclear/power)
    "xlk":       "XLK",       # Technology Select Sector SPDR
    "silver":    "SI=F",      # Silver futures (Cu/Ag ratio denominator)
    "fcx":       "FCX",       # Freeport-McMoRan (copper options IV proxy)
    "oil":       "CL=F",      # WTI crude oil (mining energy cost / AISC proxy)
}

# ── FRED series IDs ───────────────────────────────────────────────────────────
FRED_SERIES: dict[str, str] = {
    "real_yield_10y":      "DFII10",    # 10Y TIPS real yield (daily)
    "usd_cny":             "DEXCHUS",   # USD per Chinese Yuan (daily)
    "inflation_breakeven": "T10YIE",    # 10Y breakeven inflation rate (daily)
    "us_cpi":              "CPIAUCSL",  # CPI all urban consumers (monthly)
    "us_pce":              "PCEPI",     # PCE price index — Fed's preferred gauge (monthly)
    "us_indpro":           "INDPRO",    # Industrial production index (monthly)
    "us_manuf_emp":        "MANEMP",    # All employees in manufacturing (monthly)
    "consumer_sentiment":  "UMCSENT",   # U of Michigan consumer sentiment (monthly)
}

# ── RSS feed sources ──────────────────────────────────────────────────────────
RSS_FEEDS: list[str] = [
    "https://www.mining.com/feed/",
    "https://www.kitco.com/rss/",
    "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
]

# ── News keyword dictionaries (all lowercase) ─────────────────────────────────

SUPPLY_DEFICIT_KEYWORDS: dict[str, list[str]] = {
    "bullish": [
        "copper deficit", "mine disruption", "strike", "force majeure",
        "flooding", "mine closure", "grade decline", "tc cut", "smelter loss",
        "mine halt", "production cut", "supply tightness", "ore grades",
        "underinvestment", "permitting delay", "copper shortage",
        # Geographic / geopolitical supply concentration
        "chile strike", "peru protest", "drc mining halt", "congo strike",
        "dominican republic mine", "geopolitical supply risk", "chile election",
        "sanctions copper", "export ban", "mine nationalization",
        # Inventory draws
        "lme inventory draw", "comex inventory draw", "shfe inventory low",
        "global copper deficit", "refined copper deficit",
    ],
    "bearish": [
        "copper surplus", "mine expansion", "new copper project", "record production",
        "supply increase", "copper glut", "excess supply", "new mine",
        "chile production increase", "peru mine expansion",
        "lme inventory build", "comex inventory build",
        "global copper surplus", "refined copper surplus",
    ],
}

ELECTRIFICATION_KEYWORDS: dict[str, list[str]] = {
    "bullish": [
        "grid upgrade", "transmission line", "substation", "ev sales",
        "electric vehicle", "charging infrastructure", "grid investment",
        "renewable energy", "energy transition", "copper demand",
        "power infrastructure", "utilities capex", "grid expansion",
        "electrification", "grid modernization",
    ],
    "bearish": [
        "ev slowdown", "ev cancellation", "grid delay", "copper demand falls",
        "ev adoption stalls",
        # Aluminum substitution risk
        "aluminum substitution", "aluminium replaces copper", "aluminum wiring",
        "copper substitution", "aluminum conductor", "lighter aluminum cable",
        "efficiency reduces copper", "less copper per ev",
    ],
}

AI_DATACENTER_KEYWORDS: dict[str, list[str]] = {
    "bullish": [
        "data center", "ai power", "hyperscaler", "compute buildout",
        "power demand", "grid capacity", "infrastructure spending",
        "microsoft campus", "amazon aws expansion", "meta ai", "google data center",
        "ai infrastructure", "gigawatt", "nuclear power ai",
    ],
    "bearish": [
        "ai winter", "capex cut", "data center delay", "compute slowdown",
        "cloud spending falls",
    ],
}

CHINA_PMI_KEYWORDS: dict[str, list[str]] = {
    "bullish": [
        "china pmi expansion", "caixin pmi above 50", "nbs pmi beat",
        "china manufacturing growth", "chinese factory output rises",
        "china industrial output", "pmi above 50",
        "china property recovery", "chinese construction growth",
        "china infrastructure push", "china copper imports surge",
        "china copper stockpile release",
    ],
    "bearish": [
        "china pmi contraction", "caixin pmi below 50", "nbs pmi miss",
        "china manufacturing contracts", "chinese factory output falls",
        "china industrial slowdown", "pmi below 50",
        # China property and hoarding risk
        "china property slump", "chinese real estate crisis", "evergrande",
        "china construction falls", "china property pmi",
        "china hoarding copper", "china strategic copper reserve",
    ],
}

ORE_GRADE_KEYWORDS: dict[str, list[str]] = {
    "bullish": [
        "ore grade decline", "aisc rising", "all-in sustaining cost",
        "mining cost inflation", "cost per pound", "grade decline",
        "lower ore grades", "processing costs rise", "mine cost",
        "capex without production", "stranded capital", "mining capex surge",
        "cost basis miners", "higher mining costs",
    ],
    "bearish": [
        "ore grade improvement", "aisc falling", "cost reduction",
        "mining efficiency", "lower aisc", "cost per pound falls",
        "technology reduces mining cost",
    ],
}

TARIFF_KEYWORDS: dict[str, list[str]] = {
    "bullish": [
        "copper tariff", "us copper import duty", "tariff on copper",
        "copper trade restriction", "copper import tax",
    ],
    "bearish": [
        "copper tariff lifted", "trade deal copper", "tariff exemption",
        "copper export restriction", "tariff retaliation",
    ],
}

INFRASTRUCTURE_KEYWORDS: dict[str, list[str]] = {
    "bullish": [
        "infrastructure spending", "grid investment", "power infrastructure",
        "middle east construction", "southeast asia electrification",
        "us infrastructure bill", "saudi neom", "india grid", "vietnam electrification",
        "defense spending copper", "military procurement",
        "us infrastructure", "global infrastructure",
    ],
    "bearish": [
        "infrastructure spending cut", "grid investment delayed",
        "construction slowdown", "capital spending freeze",
    ],
}

# ── World market indices (for World Markets tab) ─────────────────────────────
WORLD_MARKET_TICKERS: dict[str, str] = {
    "S&P 500":       "^GSPC",
    "Nasdaq":        "^IXIC",
    "FTSE 100":      "^FTSE",
    "DAX":           "^GDAXI",
    "Nikkei 225":    "^N225",
    "Hang Seng":     "^HSI",
    "Shanghai":      "000001.SS",
    "ASX 200":       "^AXJO",
    "IBOVESPA":      "^BVSP",
    "KOSPI":         "^KS11",
    "EM (EEM)":      "EEM",
    "VIX":           "^VIX",
}

# ── COT (CFTC Commitment of Traders) ─────────────────────────────────────────
COT_URL = "https://www.cftc.gov/dea/newcot/deacot.txt"
COT_COPPER_NAME = "COPPER- #1"

# ── Central bank keyword filter (for World Market AI brief) ──────────────────
CENTRAL_BANK_KEYWORDS: dict[str, list[str]] = {
    "bullish": [
        "rate cut", "dovish pivot", "easing cycle", "quantitative easing",
        "stimulus", "rate hold", "pause", "lower rates", "cut rates",
    ],
    "bearish": [
        "rate hike", "hawkish", "tightening", "quantitative tightening",
        "higher for longer", "inflation concern", "restrictive policy",
        "hike rates", "raise rates",
    ],
}

# ── Thesis break conditions (displayed in dashboard) ─────────────────────────
THESIS_BREAKS: list[str] = [
    "China PMI below 48 for 2+ consecutive months",
    "Major new greenfield copper mine approved (>500kt nameplate capacity)",
    "10Y real yield (DFII10) rises above 2.5% and holds",
    "Aluminum substitution accelerates materially in grid or EV applications",
    "Global EV monthly sales -20% YoY for 3+ consecutive months",
    "AI power demand projections revised sharply downward by major utilities",
    "Copper scrap/recycling rate increases materially above 35% of total supply",
    "Chile/Peru/DRC election or policy change restricts exports materially",
    "US copper tariff removed or China demand collapses (PMI <45 for 3M+)",
]
