# portfolio_tracker.py

import os
import requests
import yfinance as yf
from datetime import datetime
from typing import Dict, List, Optional

# ----------------------
# SQLAlchemy imports
# ----------------------
from sqlalchemy import (
    create_engine, Column, Integer, Float, String,
    DateTime, Boolean, ForeignKey, func
)
from sqlalchemy.orm import sessionmaker, relationship, declarative_base

# ----------------------
# For email alerts (optional)
# ----------------------
import smtplib
from email.mime.text import MIMEText

# ----------------------
# 1. DATABASE SETUP
# ----------------------
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)

    # Relationship example: user.transactions, user.alerts
    transactions = relationship("Transaction", back_populates="user")
    alerts = relationship("Alert", back_populates="user")

class Symbol(Base):
    """
    Could represent a stock, crypto, or forex pair.
    symbol_type might be 'stock', 'crypto', or 'forex'.
    For forex, we could store 'USD_EUR' as name.
    """
    __tablename__ = "symbols"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)   # e.g. 'AAPL', 'bitcoin', 'USD_EUR'
    symbol_type = Column(String, nullable=False)         # 'stock', 'crypto', 'forex'

    transactions = relationship("Transaction", back_populates="symbol")
    alerts = relationship("Alert", back_populates="symbol")
    historical_rates = relationship("HistoricalRate", back_populates="symbol")

class Transaction(Base):
    """
    A record of a buy or sell.
    quantity > 0 => buy, quantity < 0 => sell.
    price => price per share/coin/unit in USD
    """
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)  # price per unit in USD
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")
    symbol = relationship("Symbol", back_populates="transactions")

class Alert(Base):
    """
    Upper/lower threshold alerts for a given user and symbol.
    If current_price crosses above or below these thresholds, trigger an email.
    """
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False)
    upper_threshold = Column(Float, nullable=True)
    lower_threshold = Column(Float, nullable=True)
    active = Column(Boolean, default=True)

    user = relationship("User", back_populates="alerts")
    symbol = relationship("Symbol", back_populates="alerts")

class HistoricalRate(Base):
    """
    Stores historical data for each symbol.
    For forex, `close` = the exchange rate.
    For stocks/crypto, `close` = closing price.
    """
    __tablename__ = "historical_rates"
    id = Column(Integer, primary_key=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    close = Column(Float, nullable=False)

    symbol = relationship("Symbol", back_populates="historical_rates")

DB_FILE = "portfolio.db"
engine = create_engine(f"sqlite:///{DB_FILE}", echo=False)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)

# ------------------------
# 2. EMAIL ALERT FUNCTION
# ------------------------
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "YOUR_EMAIL@gmail.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "YOUR_APP_PASSWORD")

def send_email_alert(to_email: str, subject: str, body: str):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())

# --------------------------------------------------------
# 3. TRANSACTION-LEVEL COST BASIS (simple average example)
# --------------------------------------------------------
def calculate_average_cost_basis(session, user_id: int, symbol_id: int) -> float:
    """
    Simple average cost basis:
     total_cost = sum(quantity * price) for all buy transactions
     total_shares = sum(quantity) for all buy transactions
    average = total_cost / total_shares

    This ignores partial sells. 
    More advanced logic would handle FIFO, LIFO, or reduce total_shares for sells.
    """
    txs = (
        session.query(Transaction)
        .filter(Transaction.user_id == user_id,
                Transaction.symbol_id == symbol_id)
        .all()
    )
    total_cost = 0.0
    total_quantity = 0.0
    for t in txs:
        if t.quantity > 0:  # buy
            total_cost += t.quantity * t.price
            total_quantity += t.quantity
        else:
            # For sells, you might reduce total_quantity or do advanced logic
            pass

    if total_quantity > 0:
        return total_cost / total_quantity
    return 0.0

def get_current_holdings(session, user_id: int) -> Dict[str, float]:
    """
    Return {symbol_name: net_quantity} for the user, summing buys and sells.
    """
    results = (
        session.query(Symbol.name, func.sum(Transaction.quantity))
        .join(Transaction, Symbol.id == Transaction.symbol_id)
        .filter(Transaction.user_id == user_id)
        .group_by(Symbol.name)
        .all()
    )
    return {r[0]: r[1] for r in results}

# ------------------------------
# 4. FETCH STOCK & CRYPTO PRICES
# ------------------------------
def fetch_stock_price(symbol: str) -> Optional[float]:
    """
    Use yfinance for the last intraday close.
    """
    try:
        data = yf.download(tickers=symbol, period="1d", interval="1m", progress=False)
        if not data.empty:
            return data["Close"].iloc[-1]
    except Exception:
        pass
    return None

def fetch_crypto_price(coin_id: str) -> Optional[float]:
    """
    Fetch from CoinGecko. coin_id like 'bitcoin', 'ethereum'.
    """
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": coin_id, "vs_currencies": "usd"}
    try:
        r = requests.get(url, params=params)
        data = r.json()
        return data[coin_id]["usd"]
    except:
        return None

# --------------------------------------
# 5. ADVANCED FOREX COMPARISON (WEIGHTS)
# --------------------------------------
PROVIDER_CONFIG = {
    "EXCHANGERATE_HOST": {
        "url": "https://api.exchangerate.host/latest",
        "weight": 1.0,  # reliability weight
    },
    "EXCHANGERATE_API": {
        # Replace 'YOUR_API_KEY' with your own key
        "url": "https://v6.exchangerate-api.com/v6/YOUR_API_KEY/latest/",
        "weight": 0.8,
    },
    "OPEN_EXCHANGE_RATES": {
        # Replace 'YOUR_APP_ID' with your own key
        "url": "https://openexchangerates.org/api/latest.json?app_id=YOUR_APP_ID",
        "weight": 0.9,
    },
}

def fetch_forex_rate(provider_key: str, base: str, target: str) -> Optional[float]:
    """
    Fetch a single forex rate from a given provider. Return None if fails.
    """
    config = PROVIDER_CONFIG[provider_key]
    url = config["url"]
    try:
        if "EXCHANGERATE_HOST" in provider_key:
            # https://api.exchangerate.host/latest?base=USD&symbols=EUR
            params = {"base": base, "symbols": target}
            r = requests.get(url, params=params)
            data = r.json()
            return data["rates"][target]

        elif "EXCHANGERATE_API" in provider_key:
            # https://v6.exchangerate-api.com/v6/YOUR_API_KEY/latest/USD
            if not url.endswith("/"):
                url += "/"
            url += base
            r = requests.get(url)
            data = r.json()
            return data["conversion_rates"].get(target)

        elif "OPEN_EXCHANGE_RATES" in provider_key:
            r = requests.get(url)
            data = r.json()
            rates = data["rates"]
            if base == "USD":
                return rates.get(target)
            else:
                if base in rates and target in rates:
                    return rates[target] / rates[base]
    except:
        return None

    return None

def get_advanced_forex_rate(base: str, target: str) -> Optional[float]:
    """
    Gather rates from multiple providers, weigh them, compute a weighted average.
    Fallback if a provider fails or returns None.
    """
    total_weighted_rate = 0.0
    total_weight = 0.0

    for provider_key, info in PROVIDER_CONFIG.items():
        weight = info["weight"]
        rate = fetch_forex_rate(provider_key, base, target)
        if rate is not None:
            total_weighted_rate += rate * weight
            total_weight += weight

    if total_weight > 0:
        return total_weighted_rate / total_weight
    return None

# -------------------------------------------
# 6. CHECK ALERTS (STOCK, CRYPTO, OR FOREX)
# -------------------------------------------
def check_and_trigger_alerts(session, symbol_name: str, current_price: float):
    """
    Find all alerts for this symbol, check if current_price crosses thresholds,
    send email if triggered.
    """
    symbol_obj = session.query(Symbol).filter_by(name=symbol_name).first()
    if not symbol_obj:
        return

    alerts = (
        session.query(Alert)
        .filter(Alert.symbol_id == symbol_obj.id, Alert.active == True)
        .all()
    )
    for alert in alerts:
        triggered = False
        msg_lines = []
        if alert.upper_threshold and current_price >= alert.upper_threshold:
            triggered = True
            msg_lines.append(
                f"{symbol_name} above threshold {alert.upper_threshold} (current: {current_price:.4f})"
            )
        if alert.lower_threshold and current_price <= alert.lower_threshold:
            triggered = True
            msg_lines.append(
                f"{symbol_name} below threshold {alert.lower_threshold} (current: {current_price:.4f})"
            )

        if triggered:
            subject = f"Price Alert for {symbol_name}"
            body = "\n".join(msg_lines)
            # Send email to user
            send_email_alert(alert.user.email, subject, body)

# ----------------------------
# 7. MAIN EXAMPLE FLOW
# ----------------------------
def main():
    # 1) Initialize DB
    init_db()
    session = SessionLocal()

    # ---------------------
    # 2) Create a demo user
    # ---------------------
    user = session.query(User).filter_by(username="demo").first()
    if not user:
        user = User(username="demo", email="demo@example.com")
        session.add(user)
        session.commit()

    # ---------------------
    # 3) Upsert some symbols
    # ---------------------
    symbols_data = [
        ("AAPL", "stock"),
        ("bitcoin", "crypto"),
        ("USD_EUR", "forex"),
    ]
    for name, s_type in symbols_data:
        existing = session.query(Symbol).filter_by(name=name).first()
        if not existing:
            s_obj = Symbol(name=name, symbol_type=s_type)
            session.add(s_obj)
    session.commit()

    # ---------------------
    # 4) Add transactions if none exist
    # ---------------------
    aapl = session.query(Symbol).filter_by(name="AAPL").first()
    btc = session.query(Symbol).filter_by(name="bitcoin").first()

    existing_tx = session.query(Transaction).filter_by(user_id=user.id).first()
    if not existing_tx:
        # Buy 10 shares of AAPL at $120
        t1 = Transaction(user_id=user.id, symbol_id=aapl.id, quantity=10, price=120.0)
        # Buy 0.02 bitcoin at $30000
        t2 = Transaction(user_id=user.id, symbol_id=btc.id, quantity=0.02, price=30000)
        session.add_all([t1, t2])
        session.commit()

    # ---------------------
    # 5) Add Alerts if none
    # ---------------------
    existing_alert_aapl = session.query(Alert).filter_by(user_id=user.id, symbol_id=aapl.id).first()
    if not existing_alert_aapl:
        aapl_alert = Alert(
            user_id=user.id, symbol_id=aapl.id,
            upper_threshold=200.0, lower_threshold=100.0, active=True
        )
        session.add(aapl_alert)

    existing_alert_btc = session.query(Alert).filter_by(user_id=user.id, symbol_id=btc.id).first()
    if not existing_alert_btc:
        btc_alert = Alert(
            user_id=user.id, symbol_id=btc.id,
            upper_threshold=40000.0, lower_threshold=20000.0, active=True
        )
        session.add(btc_alert)

    session.commit()

    # ---------------------
    # 6) Fetch current prices & check alerts
    # ---------------------
    # a) AAPL
    aapl_price = fetch_stock_price("AAPL")
    if aapl_price:
        print(f"AAPL price: {aapl_price:.2f}")
        check_and_trigger_alerts(session, "AAPL", aapl_price)

    # b) bitcoin
    btc_price = fetch_crypto_price("bitcoin")
    if btc_price:
        print(f"Bitcoin price: {btc_price:.2f}")
        check_and_trigger_alerts(session, "bitcoin", btc_price)

    # c) USD_EUR (forex)
    usd_eur_rate = get_advanced_forex_rate("USD", "EUR")
    if usd_eur_rate:
        print(f"USD_EUR average rate: {usd_eur_rate:.4f}")
        check_and_trigger_alerts(session, "USD_EUR", usd_eur_rate)

    # ---------------------
    # 7) Calculate cost basis
    # ---------------------
    aapl_avg_cost = calculate_average_cost_basis(session, user.id, aapl.id)
    print(f"AAPL average cost basis: ${aapl_avg_cost:.2f}")

    # ---------------------
    # 8) Current holdings
    # ---------------------
    holdings = get_current_holdings(session, user.id)
    print("Current holdings (net quantity):", holdings)

    session.close()
    print("Done.")

if __name__ == "__main__":
    main()
