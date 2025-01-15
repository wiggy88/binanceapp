import streamlit as st
from binance.client import Client
import pandas as pd
import time

# Binance API Configuration
st.sidebar.header("Binance API Configuration")
api_key = st.sidebar.text_input("API Key", type="password")
api_secret = st.sidebar.text_input("API Secret", type="password")

# Initialize Binance Client
if api_key and api_secret:
    client = Client(api_key, api_secret)

# Page Configuration
st.set_page_config(page_title="Binance Trading Bot with Profit Take and Stop Loss", page_icon=":robot:", layout="wide")

# Title
st.title("Binance Trading Bot with Profit Take and Stop Loss")
st.write("Live data from Binance and automated trades based on moving averages.")

# Sidebar Configuration
st.sidebar.header("Trading Configuration")
trading_pair = st.sidebar.text_input("Trading Pair (e.g., BTCUSDT)", "BTCUSDT")
trade_amount = st.sidebar.number_input("Trade Amount (USDT)", min_value=10.0, value=50.0, step=10.0)
profit_target = st.sidebar.slider("Profit Target (%)", min_value=0.5, max_value=10.0, value=2.0)
stop_loss = st.sidebar.slider("Stop Loss (%)", min_value=0.5, max_value=10.0, value=2.0)

# Helper Functions
def get_live_data(symbol):
    """Fetch live data for the specified trading pair."""
    klines = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1MINUTE, limit=50)
    df = pd.DataFrame(klines, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    df["close"] = df["close"].astype(float)
    return df

def calculate_averages(df):
    """Calculate short, medium, and long averages."""
    short_avg = df["close"].rolling(window=5).mean().iloc[-1]  # Last 5 minutes
    medium_avg = df["close"].rolling(window=20).mean().iloc[-1]  # Last 20 minutes
    long_avg = df["close"].rolling(window=50).mean().iloc[-1]  # Last 50 minutes
    return short_avg, medium_avg, long_avg

def determine_trade_action(short_avg, medium_avg, long_avg, current_price):
    """Determine whether to buy, sell, or hold."""
    if medium_avg > long_avg and short_avg > medium_avg and current_price > short_avg:
        return "Sell"
    elif medium_avg < long_avg and short_avg < medium_avg and current_price < short_avg:
        return "Buy"
    else:
        return "Hold"

def place_order(side, quantity, symbol):
    """Place a market order."""
    try:
        order = client.order_market(
            symbol=symbol,
            side=side,
            quantity=quantity
        )
        return order
    except Exception as e:
        st.error(f"Error placing order: {e}")
        return None

# Fetch and Display Data
if st.sidebar.button("Run Bot"):
    try:
        # Check if there is an active trade
        if "active_trade" in st.session_state and st.session_state["active_trade"] is not None:
            st.warning("An active trade is already in progress.")
        else:
            while True:
                # Fetch live data
                df = get_live_data(trading_pair)
                current_price = df["close"].iloc[-1]

                # Calculate averages
                short_avg, medium_avg, long_avg = calculate_averages(df)

                # Determine trade action
                action = determine_trade_action(short_avg, medium_avg, long_avg, current_price)

                if action == "Buy":
                    # Calculate quantity to buy
                    quantity = round(trade_amount / current_price, 6)
                    order = place_order("BUY", quantity, trading_pair)
                    if order:
                        # Store the active trade details
                        st.session_state["active_trade"] = {
                            "side": "BUY",
                            "entry_price": current_price,
                            "quantity": quantity,
                            "target_price": current_price * (1 + profit_target / 100),
                            "stop_price": current_price * (1 - stop_loss / 100),
                        }
                        st.success(f"Buy order placed! Entry Price: ${current_price:.2f}")
                        break  # Exit loop after placing a buy order

                elif action == "Sell" and "active_trade" in st.session_state and st.session_state["active_trade"] is not None:
                    # Calculate quantity to sell
                    balance = client.get_asset_balance(asset=trading_pair.replace("USDT", ""))
                    quantity = float(balance["free"])
                    order = place_order("SELL", quantity, trading_pair)
                    if order:
                        # Store the active trade details
                        st.session_state["active_trade"] = {
                            "side": "SELL",
                            "entry_price": current_price,
                            "quantity": quantity,
                            "target_price": current_price * (1 - profit_target / 100),
                            "stop_price": current_price * (1 + stop_loss / 100),
                        }
                        st.success(f"Sell order placed! Entry Price: ${current_price:.2f}")
                        break  # Exit loop after placing a sell order

                # Display live data and results
                st.subheader(f"Live Data for {trading_pair}")
                st.metric("Current Price (USDT)", f"${current_price:.2f}")
                st.metric("Short Average (5-min)", f"${short_avg:.2f}")
                st.metric("Medium Average (20-min)", f"${medium_avg:.2f}")
                st.metric("Long Average (50-min)", f"${long_avg:.2f}")

                # Monitor profit and stop-loss for the active trade
                if "active_trade" in st.session_state and st.session_state["active_trade"] is not None:
                    active_trade = st.session_state["active_trade"]
                    if active_trade["side"] == "BUY":
                        if current_price >= active_trade["target_price"]:
                            st.success(f"Profit target reached! ({current_price:.2f})")
                            place_order("SELL", active_trade["quantity"], trading_pair)
                            st.session_state["active_trade"] = None  # Clear active trade after closing
                        elif current_price <= active_trade["stop_price"]:
                            st.warning(f"Stop loss triggered! ({current_price:.2f})")
                            place_order("SELL", active_trade["quantity"], trading_pair)
                            st.session_state["active_trade"] = None  # Clear active trade after closing
                    elif active_trade["side"] == "SELL":
                        if current_price <= active_trade["target_price"]:
                            st.success(f"Profit target reached! ({current_price:.2f})")
                            place_order("BUY", active_trade["quantity"], trading_pair)
                            st.session_state["active_trade"] = None  # Clear active trade after closing
                        elif current_price >= active_trade["stop_price"]:
                            st.warning(f"Stop loss triggered! ({current_price:.2f})")
                            place_order("BUY", active_trade["quantity"], trading_pair)
                            st.session_state["active_trade"] = None  # Clear active trade after closing

                # Display recent prices
                st.write(f"Active Trade: {st.session_state.get('active_trade', None)}")
                st.write("Recent Prices (Last 5):")
                st.dataframe(df.tail(5)[["close_time", "close"]])

                # Wait before next refresh
                time.sleep(300)  # 5 minutes

    except Exception as e:
        st.error(f"Error: {e}")
