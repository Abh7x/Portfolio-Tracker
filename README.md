# Portfolio-Tracker

This repository demonstrates a comprehensive portfolio tracking application using:

SQLAlchemy for database storage (SQLite example)
Advanced Forex Comparison via multiple providers (weighted averages, fallback)
Transaction-Level Tracking (buy/sell) for more accurate cost basis
Streamlit for an interactive dashboard to visualize holdings, cost basis, and historical charts
Table of Contents
Features
Requirements & Installation
Usage
1. Initialize & Populate the Database
2. Run the Dashboard
Files & Structure
Configuration & API Keys
Next Steps & Improvements
Features
Database / Storage

SQLAlchemy models (User, Symbol, Transaction, Alert, HistoricalRate).
Each user can have multiple transactions (buy/sell) and alerts (upper/lower thresholds).
Transaction-Level Cost Basis

Basic average cost basis formula for buys.
Net quantity for each symbol is derived by summing buys & sells.
Advanced Forex Comparison

Integrates multiple providers (ExchangeRate.host, ExchangeRate-API, Open Exchange Rates).
Weighted averaging with fallback if a provider fails or returns invalid data.
Alerts

Users can set upper_threshold and lower_threshold for each symbol.
When the price crosses these thresholds, an email is sent automatically.
Streamlit Dashboard

View current holdings, cost basis, and live quotes.
Plot historical charts for stocks, crypto, and forex pairs over the last 30 days.
Requirements & Installation
Python 3.8+ (recommended)

Install required packages:
pip install sqlalchemy streamlit yfinance requests matplotlib plotly
(Optional) If you want to receive email alerts, set up environment variables:

EMAIL_ADDRESS: Your SMTP email address (e.g., Gmail)
EMAIL_PASSWORD: The App Password for Gmail (or equivalent for other providers)

Usage
1. Initialize & Populate the Database
Run the main Python script to create portfolio.db (SQLite) and insert demo data:
python portfolio_tracker.py

What this does:

Creates tables for users, symbols, transactions, alerts, and historical_rates.
Adds a demo user (username=demo, email=demo@example.com).
Inserts some symbols (like AAPL, bitcoin, USD_EUR) if they don’t exist.
Adds transactions and alerts for the demo user.
Fetches current prices & checks alerts once.
2. Run the Dashboard
Then launch the Streamlit dashboard:
streamlit run dashboard.py
Open the provided URL (typically http://localhost:8501/) in your web browser. In the dashboard, you can:

Select the user (e.g., demo).
View holdings (net quantities) and cost basis.
See current prices fetched live from yfinance, CoinGecko, or advanced forex rate logic.
Plot historical charts for stocks, crypto, and forex pairs over the last 30 days.

Files & Structure
.
├── portfolio_tracker.py   # Main application logic (DB models, advanced forex, alerts, etc.)
├── dashboard.py           # Streamlit dashboard
├── README.md              # Project overview & usage instructions
└── portfolio.db           # Created after running portfolio_tracker.py (SQLite file)

portfolio_tracker.py
SQLAlchemy Models: Defines User, Symbol, Transaction, Alert, HistoricalRate.
Initialization: Creates the SQLite database tables if they don’t exist.
Transaction Logic: Handles buy/sell transactions, cost basis, net holdings.
Price Fetch:
Stocks via yfinance
Crypto via CoinGecko
Forex via a weighted average from multiple providers
Alerts: Checks if the latest prices cross thresholds, then sends an email.
dashboard.py
A Streamlit web interface for exploring user holdings, cost basis, and retrieving historical charts from external APIs.
Allows you to select a user, see holdings, cost basis, and plot the last 30 days of price/rate data.

Configuration & API Keys
Email Alerts:

Configure EMAIL_ADDRESS and EMAIL_PASSWORD environment variables for your SMTP account.
Forex Providers:

In portfolio_tracker.py, the PROVIDER_CONFIG dictionary has placeholders:
python
Copy
Edit

"EXCHANGERATE_API": {
  "url": "https://v6.exchangerate-api.com/v6/YOUR_API_KEY/latest/",
  "weight": 0.8,
},
"OPEN_EXCHANGE_RATES": {
  "url": "https://openexchangerates.org/api/latest.json?app_id=YOUR_APP_ID",
  "weight": 0.9,
},
Replace YOUR_API_KEY and YOUR_APP_ID with your real keys (or store them in environment variables).

Next Steps & Improvements
User Authentication:

Add login and password hashing (e.g., use bcrypt), session management, etc.
Enhanced Cost Basis:

Implement FIFO or LIFO for partial sells, track lots, etc.
Historical Data Storage:

Automate periodic fetches and store daily close or intraday data in HistoricalRate.
The dashboard can then read from your own DB instead of making external API calls.
Expanded Alerts:

Integrate SMS (e.g., Twilio) or push notifications.
Robust Error Handling:

Add retries for network calls, handle API failures, and log errors for debugging.
UI Enhancements:

Additional Streamlit pages (e.g., for editing transactions, managing alerts) or a full web framework (Flask/Django + React/Vue).
