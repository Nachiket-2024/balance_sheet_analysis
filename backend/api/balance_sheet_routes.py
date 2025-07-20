# ---------------------- Imports ----------------------

# FastAPI imports for route handling, dependency injection, and HTTP errors
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

# External library used to fetch stock data, including balance sheets
import yfinance as yf

# SQLAlchemy models
from ..models.balance_sheet_model import BalanceSheet  # DB model for balance sheet data
from ..models.company_model import Company  # DB model for company data
from ..models.admin_model import Admin  # DB model for admin (used in role-checking)

# Pydantic response schemas
from ..schemas.balance_sheet_schema import CompanyWithBalanceSheets, BalanceSheetOut, CompanyOut

# Dependency for getting the database session
from ..db.session import get_db

# Role-based access control dependency
from ..auth.auth_user_check import admin_only

# External mapping from yfinance keys → DB fields
from ..utils.yfinance_field_map import YFINANCE_TO_DB_FIELDS

# Utility to sanitize input dictionaries (removes NaNs, None, infs, etc.)
from ..utils.sanitize_fields import sanitize_dict

# ---------------------- Create Router ----------------------

# Initialize API router with a URL prefix and tag for grouping in docs
router = APIRouter(
    prefix="/balance-sheet",
    tags=["Balance Sheet"]
)

# ---------------------- GET: Fetch Specific Balance Sheet ----------------------

@router.get("/{ticker}/{year}", response_model=BalanceSheetOut)
async def get_balance_sheet(ticker: str, year: int, db: Session = Depends(get_db)):
    # Query DB for balance sheet matching ticker and year
    balance_sheet = db.query(BalanceSheet).filter(
        BalanceSheet.ticker == ticker,
        BalanceSheet.year == year
    ).first()

    if not balance_sheet:
        raise HTTPException(status_code=404, detail="Balance sheet not found for the given ticker and year.")

    # Return Pydantic schema, ORM mode converts SQLAlchemy model to JSON
    return balance_sheet

# ---------------------- POST: Create Balance Sheet Entry ----------------------

@router.post("/{ticker}/{year}")
async def create_balance_sheet(
    ticker: str,
    year: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(admin_only)  # Requires admin access
):
    """
    Create a new balance sheet using data fetched from yfinance.
    If the company doesn't exist, it is created.
    """
    try:
        # Prevent duplicate creation
        existing = db.query(BalanceSheet).filter(
            BalanceSheet.ticker == ticker,
            BalanceSheet.year == year
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Balance sheet for the given year already exists.")

        # Fetch and transpose balance sheet from yfinance
        stock = yf.Ticker(ticker)
        bs = stock.balance_sheet
        bs = bs.T if not bs.empty else None

        # If data is missing or does not contain the target year
        if bs is None or year not in [d.year for d in bs.index]:
            raise HTTPException(status_code=404, detail="No balance sheet data found for the given year from yfinance.")

        # Extract year-specific row
        bs_year = None
        for idx in bs.index:
            if idx.year == year:
                bs_year = bs.loc[idx]
                break

        # Final check if year's data was found
        if bs_year is None:
            raise HTTPException(status_code=404, detail="Year not available in balance sheet data.")

        # Create a dictionary to hold DB-ready fields using mapped keys
        raw_field_mapping = {}
        for yahoo_field, db_field in YFINANCE_TO_DB_FIELDS.items():
            value = bs_year.get(yahoo_field)
            if value is not None and hasattr(BalanceSheet, db_field):
                raw_field_mapping[db_field] = value

        # Add required fields
        raw_field_mapping["ticker"] = ticker
        raw_field_mapping["year"] = year

        # Sanitize the field mapping using utility
        clean_fields = sanitize_dict(raw_field_mapping)

        # Ensure company exists in DB
        company = db.query(Company).filter(Company.name == ticker).first()
        if not company:
            company = Company(name=ticker)
            db.add(company)
            db.commit()
            db.refresh(company)

        # Create balance sheet DB row
        new_balance = BalanceSheet(**clean_fields)
        db.add(new_balance)
        db.commit()
        db.refresh(new_balance)

        return {
            "message": "Balance sheet created successfully from yfinance.",
            "balance_sheet": new_balance
        }

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Constraint error while creating balance sheet.")
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# ---------------------- DELETE: Delete a Balance Sheet ----------------------

@router.delete("/{ticker}/{year}")
async def delete_balance_sheet(
    ticker: str,
    year: int,
    db: Session = Depends(get_db),
    admin: Admin = Depends(admin_only)
):
    """
    Delete a balance sheet entry by ticker and year.
    Only accessible to admins.
    """
    try:
        # Locate the balance sheet
        balance_sheet = db.query(BalanceSheet).filter(
            BalanceSheet.ticker == ticker,
            BalanceSheet.year == year
        ).first()

        if not balance_sheet:
            raise HTTPException(status_code=404, detail="Balance sheet not found for the given ticker and year.")

        db.delete(balance_sheet)
        db.commit()

        return {"message": "Balance sheet deleted successfully."}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# ---------------------- GET: All Companies with Their Balance Sheets ----------------------

@router.get("/companies", response_model=list[CompanyWithBalanceSheets])
async def get_all_companies(db: Session = Depends(get_db)):
    """
    Get all companies along with their balance sheet records.
    """
    try:
        companies = db.query(Company).all()

        if not companies:
            raise HTTPException(status_code=404, detail="No companies found.")

        companies_with_balance_sheets: list[CompanyWithBalanceSheets] = []

        # Loop through companies and fetch associated balance sheets
        for company in companies:
            if not company.name:
                continue

            balance_sheets = db.query(BalanceSheet).filter(
                BalanceSheet.ticker == company.name
            ).all()

            companies_with_balance_sheets.append(
                CompanyWithBalanceSheets(
                    company=CompanyOut(
                        name=company.name,
                        industry=company.industry if hasattr(company, "industry") else None
                    ),
                    balance_sheets=[
                        BalanceSheetOut(
                            ticker=bs.ticker,
                            year=bs.year,
                            **{
                                k: getattr(bs, k)
                                for k in BalanceSheetOut.model_fields.keys()
                                if k not in {"ticker", "year"} and hasattr(bs, k)
                            }
                        )
                        for bs in balance_sheets
                    ]
                )
            )

        return companies_with_balance_sheets

    except HTTPException as e:
        raise e
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
