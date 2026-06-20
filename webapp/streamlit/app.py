# webapp/streamlit/app.py
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Watch Deals", page_icon="⌚", layout="wide")

DEALS_FILE = Path(__file__).parent.parent.parent / "data" / "deals.json"

st.markdown(
    "<h1 style='font-size:1.2rem;letter-spacing:4px;text-transform:uppercase;"
    "color:#c9a84c;font-weight:400'>Watch Deals</h1>",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300)
def load_deals():
    if not DEALS_FILE.exists():
        return []
    try:
        data = json.loads(DEALS_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


deals = load_deals()

if not deals:
    st.info("No deals yet — check back after the next monitor run.")
    st.stop()

df = pd.DataFrame(deals)

# ── Sidebar filters ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")

    hot_only = st.toggle("Hot deals only (≤ ceiling)")

    col1, col2 = st.columns(2)
    price_min = col1.number_input("Min $", min_value=0, value=0, step=100)
    price_max = col2.number_input("Max $", min_value=0, value=10000, step=100)

    brands = ["All"] + sorted(df["brand"].dropna().unique().tolist())
    brand = st.selectbox("Brand", brands)

    if brand != "All":
        model_pool = df[df["brand"] == brand]["model"].dropna().unique().tolist()
    else:
        model_pool = df["model"].dropna().unique().tolist()
    models = ["All"] + sorted(set(model_pool))
    model = st.selectbox("Model", models)

    sizes = ["All"] + [f"{int(s)}mm" for s in sorted(df["size_mm"].dropna().unique())]
    size = st.selectbox("Size", sizes)

    dials = ["All"] + sorted(df["dial"].dropna().unique().tolist())
    dial = st.selectbox("Dial color", dials)

    straps = ["All"] + sorted(df["strap"].dropna().unique().tolist())
    strap = st.selectbox("Strap", straps)

    all_sources = sorted(df["source"].dropna().unique().tolist())
    sources = st.multiselect("Source", all_sources, default=all_sources)

    date_options = {"All time": None, "Last 24h": 1, "Last 7 days": 7, "Last 30 days": 30}
    date_label = st.selectbox("Date seen", list(date_options.keys()))
    date_days = date_options[date_label]

# ── Apply filters ─────────────────────────────────────────────────────────────
filtered = df.copy()

if hot_only:
    filtered = filtered[filtered["is_hot"] == True]
if price_min > 0:
    filtered = filtered[filtered["price"].notna() & (filtered["price"] >= price_min)]
if price_max < 10000:
    filtered = filtered[filtered["price"].notna() & (filtered["price"] <= price_max)]
if brand != "All":
    filtered = filtered[filtered["brand"] == brand]
if model != "All":
    filtered = filtered[filtered["model"] == model]
if size != "All":
    size_val = float(size.replace("mm", ""))
    filtered = filtered[filtered["size_mm"] == size_val]
if dial != "All":
    filtered = filtered[filtered["dial"] == dial]
if strap != "All":
    filtered = filtered[filtered["strap"] == strap]
if sources:
    filtered = filtered[filtered["source"].isin(sources)]
if date_days:
    cutoff = datetime.now(timezone.utc) - timedelta(days=date_days)
    filtered = filtered[pd.to_datetime(filtered["date_seen"], utc=True) >= cutoff]

# ── Sort & display ────────────────────────────────────────────────────────────
if "date_seen" in filtered.columns:
    filtered = filtered.sort_values("date_seen", ascending=False)

hot_count = int(filtered["is_hot"].sum()) if "is_hot" in filtered.columns else 0
st.caption(
    f"**{len(filtered)}** listing{'s' if len(filtered) != 1 else ''}"
    + (f" · **{hot_count}** hot deal{'s' if hot_count != 1 else ''}" if hot_count else "")
)

DISPLAY_COLS = ["price", "is_hot", "title", "brand", "model", "ref_matches",
                "dial", "strap", "source", "date_seen", "url"]
show_cols = [c for c in DISPLAY_COLS if c in filtered.columns]

st.dataframe(
    filtered[show_cols],
    use_container_width=True,
    column_config={
        "price":       st.column_config.NumberColumn("Price ($)", format="$%d"),
        "is_hot":      st.column_config.CheckboxColumn("🔥"),
        "title":       st.column_config.TextColumn("Title", width="large"),
        "ref_matches": st.column_config.ListColumn("Ref(s)"),
        "dial":        st.column_config.TextColumn("Dial"),
        "strap":       st.column_config.TextColumn("Strap"),
        "date_seen":   st.column_config.DatetimeColumn("Seen", format="relative"),
        "url":         st.column_config.LinkColumn("Link"),
    },
    hide_index=True,
)
