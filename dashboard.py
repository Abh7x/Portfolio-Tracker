# dashboard.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests

from sqlalchemy.orm import sessionmaker
from portfolio_tracker import (
    engine, init_db, User, Symbol, Transaction, Alert, HistoricalRate,
    fetch_stock_price, fetch_crypto_price, get_advanced_forex_rate,
    calculate_average_cost_basis, get_current_holdings
)

# Initialize the database and session
init_db()
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

st.title("Portfolio Dashboard")

# 1) Let user pick from existing users
user_names = [u.username for u in session.query(User).all()]
selected_user = st.selectbox("Select User", user_names)

if selected_user:
    user_obj = session.query(User).filter_by(username=selected_user).first()
    st.subheader(f"Hello, {user_obj.username}!")

    # 2) Display current holdings
    holdings = get_current_holdings(session, user_obj.id)
    holdings_df = pd.DataFrame(
        [(k, v) for k,v in holdings.items()],
        columns=["Symbol", "Net Quantity"]
    )
    st.write("**Current Holdings**")
    st.dataframe(holdings_df)

    # 3) Cost Basis & Current Price
    st.write("**Cost Basis & Current Price**")
    rows = []
    for sym_name, quantity in holdings.items():
        if quantity == 0:
            continue
        symbol_obj = session.query(Symbol).filter_by(name=sym_name).first()
        if not symbol_obj:
            continue

        avg_cost = calculate_average_cost_basis(session, user_obj.id, symbol_obj.id)
        current_price = None

        if symbol_obj.symbol_type == "stock":
            current_price = fetch_stock_price(sym_name)
        elif symbol_obj.symbol_type == "crypto":
            current_price = fetch_crypto_price(sym_name)
        elif symbol_obj.symbol_type == "forex":
            base, target = sym_name.split("_")
            current_price = get_advanced_forex_rate(base, target)

        if current_price:
            rows.append({
                "Symbol": sym_name,
                "Quantity": quantity,
                "Avg Cost": round(avg_cost, 2),
                "Current Price": round(current_price, 4),
                "Market Value": round(quantity * current_price, 2),
            })

    if rows:
        cost_df = pd.DataFrame(rows)
        st.dataframe(cost_df)

    # 4) Historical Charts
    st.write("**Historical Chart**")
    if rows:
        chart_symbol = st.selectbox("Symbol to chart", [r["Symbol"] for r in rows])
        if chart_symbol:
            symbol_obj = session.query(Symbol).filter_by(name=chart_symbol).first()
            if symbol_obj:
                if symbol_obj.symbol_type == "stock":
                    # Fetch last 1 month from yfinance
                    import yfinance as yf
                    data = yf.download(tickers=chart_symbol, period="1mo", interval="1d", progress=False)
                    if not data.empty:
                        fig = px.line(
                            data_frame=data.reset_index(),
                            x="Date",
                            y="Close",
                            title=f"{chart_symbol} - 1 Month"
                        )
                        st.plotly_chart(fig)
                    else:
                        st.warning("No stock data found.")

                elif symbol_obj.symbol_type == "forex":
                    # e.g. "USD_EUR"
                    base, target = chart_symbol.split("_")
                    ts_url = "https://api.exchangerate.host/timeseries"
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=30)
                    params = {
                        "base": base,
                        "start_date": start_date.strftime("%Y-%m-%d"),
                        "end_date": end_date.strftime("%Y-%m-%d"),
                        "symbols": target
                    }
                    resp = requests.get(ts_url, params=params).json()
                    rates = resp.get("rates", {})
                    dates = []
                    values = []
                    for d_str, dd in rates.items():
                        if dd and target in dd:
                            dates.append(d_str)
                            values.append(dd[target])

                    if dates:
                        df_fx = pd.DataFrame({"date": dates, "rate": values})
                        df_fx["date"] = pd.to_datetime(df_fx["date"])
                        fig = px.line(df_fx, x="date", y="rate", title=f"{chart_symbol} - 1 Month")
                        st.plotly_chart(fig)
                    else:
                        st.warning("No forex data found.")

                elif symbol_obj.symbol_type == "crypto":
                    # e.g. "bitcoin"
                    coingecko_url = f"https://api.coingecko.com/api/v3/coins/{chart_symbol}/market_chart"
                    params = {"vs_currency": "usd", "days": "30"}
                    r = requests.get(coingecko_url, params=params).json()
                    if "prices" in r:
                        times = [datetime.fromtimestamp(p[0]/1000) for p in r["prices"]]
                        values = [p[1] for p in r["prices"]]
                        df_crypto = pd.DataFrame({"date": times, "price": values})
                        fig = px.line(df_crypto, x="date", y="price", title=f"{chart_symbol} - 30 Days")
                        st.plotly_chart(fig)
                    else:
                        st.warning("No crypto chart data found.")
