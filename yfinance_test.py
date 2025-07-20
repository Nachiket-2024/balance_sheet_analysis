# yfinance_test.py

import yfinance as yf
from pprint import pprint

ticker = "AAPL"
year = 2023

# Fetch data
stock = yf.Ticker(ticker)
bs = stock.balance_sheet

# Transpose if not empty
if bs.empty:
    print("Balance sheet is empty")
else:
    bs = bs.T
    print("Available Dates:", [d for d in bs.index])

    # Try to find the matching year
    bs_year = None
    for idx in bs.index:
        if idx.year == year:
            bs_year = bs.loc[idx]
            break

    if bs_year is not None:
        print(f"\nBalance Sheet for {ticker} in {year}:\n")
        pprint(bs_year.to_dict())
    else:
        print(f"No balance sheet found for year {year}")
