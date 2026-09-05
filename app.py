import streamlit as st
import ccxt
import pandas as pd
import asyncio

# --- Page Setup ---
st.set_page_config(page_title="Multi-CEX Arbitrage Scanner", layout="wide")
st.title("🔥 Real-Time CEX / DEX Arbitrage Radar")

# Configure exchanges and fees
EXCHANGES_FEE_MAP = {
    'binance': 0.001,
    'kucoin': 0.001,
    'mexc': 0.0005,
    'gateio': 0.002,
    'bybit': 0.001
}
exchanges = list(EXCHANGES_FEE_MAP.keys())

symbol = st.text_input("Enter Asset Pair to Scan", "ETH/USDT").upper()

# --- Async Function to Fetch Prices ---
async def fetch_ticker(exchange_id, symbol, results):
    try:
        # Connect to exchange
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({'enableRateLimit': True})
        
        # Fetch ticker
        ticker = await exchange.fetch_ticker(symbol)
        
        # Account for taker fees
        taker_fee = EXCHANGES_FEE_MAP.get(exchange_id, 0.001)
        effective_buy = ticker['ask'] * (1 + taker_fee)
        effective_sell = ticker['bid'] * (1 - taker_fee)
        
        results.append({
            "Exchange": exchange_id.upper(),
            "Ask (Buy)": ticker['ask'],
            "Effective Buy Cost (w/ Fees)": effective_buy,
            "Bid (Sell)": ticker['bid'],
            "Effective Sell Revenue (w/ Fees)": effective_sell,
        })
        await exchange.close()
    except Exception as e:
        # Exchange doesn't support the pair or error occurred
        pass

# --- Scan Market Button Logic ---
if st.button("Run Arbitrage Scan"):
    with st.spinner(f"Scanning {len(exchanges)} exchanges for {symbol}..."):
        results_data = []
        
        # Run asynchronous fetches
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tasks = [fetch_ticker(ex_id, symbol, results_data) for ex_id in exchanges]
        loop.run_until_complete(asyncio.gather(*tasks))
        loop.close()

    if results_data:
        df = pd.DataFrame(results_data)
        
        # Sort and Find Best Pairs
        df_buy = df.sort_values(by="Effective Buy Cost (w/ Fees)")
        df_sell = df.sort_values(by="Effective Sell Revenue (w/ Fees)", ascending=False)
        
        best_buy = df_buy.iloc[0]
        best_sell = df_sell.iloc[0]
        
        # Calculate Spread
        gross_spread = best_sell['Bid (Sell)'] - best_buy['Ask (Buy)']
        net_profit = best_sell['Effective Sell Revenue (w/ Fees)'] - best_buy['Effective Buy Cost (w/ Fees)']
        net_profit_pct = (net_profit / best_buy['Effective Buy Cost (w/ Fees)']) * 100

        # Display Metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Lowest Buy Venue", f"{best_buy['Exchange']}", f"${best_buy['Ask (Buy)']}")
        col2.metric("Highest Sell Venue", f"{best_sell['Exchange']}", f"${best_sell['Bid (Sell)']}")
        col3.metric("Gross Spread", f"${gross_spread:.2f}")
        
        # Conditional formatting for profit
        if net_profit > 0:
            col4.metric("📈 Net Profit (w/ Fees)", f"${net_profit:.2f}", f"{net_profit_pct:.2f}%")
            st.success(f"⚡ OPPORTUNITY FOUND: Buy on {best_buy['Exchange']} and Sell on {best_sell['Exchange']}")
        else:
            col4.metric("📉 Net Loss (w/ Fees)", f"${net_profit:.2f}", f"{net_profit_pct:.2f}%")
            st.warning("No net profit opportunity found on this scan (fees eat the margin).")

        st.subheader("Raw Market Data (Sorted by Buy Price)")
        st.dataframe(df_buy.style.format({
            "Ask (Buy)": "${:.2f}",
            "Effective Buy Cost (w/ Fees)": "${:.2f}",
            "Bid (Sell)": "${:.2f}",
            "Effective Sell Revenue (w/ Fees)": "${:.2f}",
        }), use_container_width=True)

    else:
        st.error(f"Could not find trading data for symbol: {symbol} on the connected exchanges.")
