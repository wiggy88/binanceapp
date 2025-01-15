import streamlit as st
from binance.client import Client
import pandas as pd
import time
import plotly.graph_objects as go

# Page Configuration
st.set_page_config(page_title="Binance Trading Bot", page_icon=":robot:", layout="wide")

# Sidebar Configuration
st.sidebar.header("Binance API Configuration")
api_key = st.sidebar.text_input("API Key", type="password")
api_secret = st.sidebar.text_input("API Secret", type="password")

st.sidebar.header("Trading Configuration")
trading_pair = st.sidebar.text_input("Trading Pair (e.g., SHIBUSDT)", "SHIBUSDT")
trade_amount = st.sidebar.number_input("Trade Amount (USDT)", min_value=2.0, value=2.0, step=1.0)
profit_target = st.sidebar.slider("Profit Target (%)", min_value=0.5, max_value=10.0, value=2.0)
stop_loss = st.sidebar.slider("Stop Loss (%)", min_value=0.5, max_value=10.0, value=2.0)

# Initialize State
if "bot_running" not in st.session_state:
    st.session_state["bot_running"] = False
if "active_trade" not in st.session_state:
    st.session_state["active_trade"] = None

# Dynamic Display Placeholders
price_display = st.empty()
signal_display = st.empty()
log_display = st.empty()
chart_display = st.empty()

# Initialize Binance Client
client = Client(api_key, api_secret) if api_key and api_secret else None

# Helper Functions
def get_live_data(symbol):
    """Fetch live data for the specified trading pair."""
    try:
        klines = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1MINUTE, limit=50)
        df = pd.DataFrame(klines, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "num_trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df.set_index("open_time", inplace=True)
        df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].astype(float)
        return df
    except Exception as e:
        return None

def calculate_averages(df):
    """Add short, medium, and long moving averages to the DataFrame."""
    df["short_avg"] = df["close"].rolling(window=5).mean()
    df["medium_avg"] = df["close"].rolling(window=20).mean()
    df["long_avg"] = df["close"].rolling(window=50).mean()
    return df

def determine_trade_action(df):
    """Determine trade action based on moving averages."""
    if len(df) < 50:  # Ensure enough data for long average
        return "Hold", None, None, None

    short_avg = df["short_avg"].iloc[-1]
    medium_avg = df["medium_avg"].iloc[-1]
    long_avg = df["long_avg"].iloc[-1]
    current_price = df["close"].iloc[-1]

    if medium_avg < long_avg and short_avg < medium_avg and current_price < short_avg:
        return "Buy", short_avg, medium_avg, long_avg
    return "Hold", short_avg, medium_avg, long_avg

# Main Bot Logic (Simplified Without `st.experimental_rerun`)
def run_bot():
    """Run the trading bot."""
    if not client:
        st.warning("Please configure your Binance API keys.")
        return

    logs = []
    while st.session_state["bot_running"]:
        # Fetch live data
        df = get_live_data(trading_pair)
        if df is None:
            logs.append("Error fetching live data.")
            st.warning("Error fetching live data.")
            break

        df = calculate_averages(df)
        current_price = df["close"].iloc[-1]

        # Determine trade action
        action, short_avg, medium_avg, long_avg = determine_trade_action(df)

        # Update UI elements
        price_display.markdown(f"""
        ### Live Metrics
        - **Current Price:** ${current_price:.8f}
        - **Short EMA (5):** {f"${short_avg:.8f}" if short_avg else "N/A"}
        - **Medium EMA (20):** {f"${medium_avg:.8f}" if medium_avg else "N/A"}
        - **Long EMA (50):** {f"${long_avg:.8f}" if long_avg else "N/A"}
        """)
        signal_display.markdown(f"### Current Signal: **{action}**")

        # Trade Logic
        if action == "Buy" and not st.session_state["active_trade"]:
            st.session_state["active_trade"] = {
                "entry_price": current_price,
                "target_price": current_price * (1 + profit_target / 100),
                "stop_price": current_price * (1 - stop_loss / 100),
            }
            logs.append(f"Buy order placed at ${current_price:.8f}")

        # Check Active Trade
        if st.session_state["active_trade"]:
            trade = st.session_state["active_trade"]
            if current_price >= trade["target_price"]:
                logs.append(f"Profit target hit! Sold at ${current_price:.8f}")
                st.session_state["active_trade"] = None
            elif current_price <= trade["stop_price"]:
                logs.append(f"Stop loss triggered! Sold at ${current_price:.8f}")
                st.session_state["active_trade"] = None

        # Initialize the iteration count in session state
        if "iteration" not in st.session_state:
            st.session_state["iteration"] = 0

        # Update Chart Logic
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price"
        ))
        fig.add_trace(go.Scatter(x=df.index, y=df["short_avg"], mode="lines", name="Short EMA (5)"))
        fig.add_trace(go.Scatter(x=df.index, y=df["medium_avg"], mode="lines", name="Medium EMA (20)"))
        fig.add_trace(go.Scatter(x=df.index, y=df["long_avg"], mode="lines", name="Long EMA (50)"))

        # Increment the persistent iteration count
        st.session_state["iteration"] += 1

        # Use the updated iteration count as a unique key
        chart_display.plotly_chart(fig, key=f"chart_update_{st.session_state['iteration']}")

        # Log Display
        log_display.text("\n".join(logs[-10:]))

        # Sleep to avoid excessive updates
        time.sleep(5)

# Start/Stop Bot Buttons
if st.sidebar.button("Start Bot"):
    if not st.session_state["bot_running"]:
        st.session_state["bot_running"] = True
        run_bot()

if st.sidebar.button("Stop Bot"):
    st.session_state["bot_running"] = False
    st.warning("Bot stopped!")

