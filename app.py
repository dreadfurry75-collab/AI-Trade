import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(page_title="BTC Live Chart", page_icon="₿", layout="wide")

# Kraken public API: free, no key needed, works from Streamlit Cloud.
BASE_URL = "https://api.kraken.com/0/public"
PAIR = "XBTUSD"  # Kraken calls Bitcoin "XBT"

# label shown on the buttons -> Kraken interval in minutes
TIMEFRAMES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}

UP_COLOR = "#2ebd85"
DOWN_COLOR = "#f6465d"


def kraken_get(endpoint: str, params: dict) -> dict:
    """Call Kraken and return the 'result' part, or raise a readable error."""
    response = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(", ".join(data["error"]))
    return data["result"]


@st.cache_data(ttl=5)
def get_candles(interval: int) -> pd.DataFrame:
    """Download the latest candles (Kraken returns up to 720)."""
    result = kraken_get("OHLC", {"pair": PAIR, "interval": interval})
    key = [k for k in result if k != "last"][0]
    df = pd.DataFrame(
        result[key],
        columns=["time", "open", "high", "low", "close", "vwap", "volume", "count"],
    )
    df["time"] = pd.to_datetime(df["time"], unit="s")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df


@st.cache_data(ttl=5)
def get_ticker() -> dict:
    """Current price plus today's open, high and low."""
    result = kraken_get("Ticker", {"pair": PAIR})
    t = result[list(result.keys())[0]]
    return {
        "price": float(t["c"][0]),
        "open": float(t["o"]),
        "high": float(t["h"][1]),  # last 24 hours
        "low": float(t["l"][1]),   # last 24 hours
    }


def build_chart(df: pd.DataFrame, show_ma: bool) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=df["time"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            increasing_line_color=UP_COLOR,
            decreasing_line_color=DOWN_COLOR,
            name="BTC/USD",
        )
    )
    if show_ma:
        fig.add_trace(
            go.Scatter(
                x=df["time"],
                y=df["close"].rolling(20).mean(),
                mode="lines",
                line=dict(color="#4c9aff", width=1.5),
                name="20-candle average",
            )
        )
    fig.update_layout(
        template="plotly_dark",
        height=620,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False,
        xaxis_title="Time (UTC)",
        yaxis_title="Price (USD)",
        legend=dict(orientation="h", y=1.02, x=0),
    )
    return fig


# The part inside this function re-runs by itself every 5 seconds.
@st.fragment(run_every=5)
def live_chart(timeframe: str, show_ma: bool):
    try:
        candles = get_candles(TIMEFRAMES[timeframe])
        ticker = get_ticker()
    except Exception as e:
        st.error(f"Could not load prices from Kraken: {e}")
        return

    change = ticker["price"] - ticker["open"]
    change_pct = change / ticker["open"] * 100

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BTC / USD", f"${ticker['price']:,.2f}")
    c2.metric("Since today's open", f"{change_pct:+.2f}%", f"{change:+,.2f}")
    c3.metric("24h high", f"${ticker['high']:,.2f}")
    c4.metric("24h low", f"${ticker['low']:,.2f}")

    st.plotly_chart(build_chart(candles, show_ma), use_container_width=True)
    st.caption("Prices from Kraken. Refreshes every 5 seconds.")


st.title("₿ Bitcoin live chart")

col_a, col_b = st.columns([3, 1])
with col_a:
    timeframe = st.radio(
        "Timeframe", list(TIMEFRAMES.keys()), index=1, horizontal=True
    )
with col_b:
    show_ma = st.checkbox("Show 20-candle average", value=True)

live_chart(timeframe, show_ma)
