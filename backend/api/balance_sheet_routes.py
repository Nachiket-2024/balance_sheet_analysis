from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..models.balance_sheet_model import BalanceSheet
from ..schemas.balance_sheet_schema import BalanceSheetBase
from ..models.company_model import Company
from ..models.admin_model import Admin
from ..db.session import get_db
from ..auth.auth_user_check import admin_only

# Create FastAPI router for balance sheet related routes with prefix and tags
router = APIRouter(
    prefix="/balance-sheet",  # Prefix for all routes in this router
    tags=["Balance Sheet"],    # Tags to categorize the routes in the docs
)

# Route to get the balance sheet for a company by ticker and year
@router.get("/{ticker}/{year}")
async def get_balance_sheet(ticker: str, year: int, db: Session = Depends(get_db)):
    """
    Get the balance sheet of a company for a given year by its ticker.
    """
    try:
        balance_sheet = db.query(BalanceSheet).filter(BalanceSheet.ticker == ticker, BalanceSheet.year == year).first()
        
        if not balance_sheet:
            raise HTTPException(status_code=404, detail="Balance sheet not found for the given ticker and year.")
        
        return balance_sheet
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# Route to create a balance sheet entry (Admin only)
@router.post("/{ticker}/{year}")
async def create_balance_sheet(ticker: str, year: int, balance_data: BalanceSheetBase, db: Session = Depends(get_db), admin: Admin = Depends(admin_only)):
    """
    Create a new balance sheet entry for a company.
    If the company doesn't exist, it will be created.
    """
    try:
        # Check if the company exists in the company table based on the ticker
        company = db.query(Company).filter(Company.name == ticker).first()

        if not company:
            # If company doesn't exist, create a new company
            company = Company(name=ticker, industry="Unknown")  # Assuming default industry as "Unknown"
            db.add(company)
            db.commit()
            db.refresh(company)

        # Check if the balance sheet for the ticker and year already exists
        existing_balance_sheet = db.query(BalanceSheet).filter(BalanceSheet.ticker == ticker, BalanceSheet.year == year).first()
        
        if existing_balance_sheet:
            raise HTTPException(status_code=400, detail="Balance sheet for the given year already exists.")
        
        # Create a new balance sheet entry
        new_balance_sheet = BalanceSheet(
            ticker=ticker,
            year=year,
            **balance_data.dict()  # Map Pydantic fields to the SQLAlchemy model
        )

        db.add(new_balance_sheet)
        db.commit()
        db.refresh(new_balance_sheet)

        return {"message": "Balance sheet created successfully.", "balance_sheet": new_balance_sheet}
    
    except IntegrityError:
        db.rollback()  # Rollback in case of any integrity issues (like duplicate keys)
        raise HTTPException(status_code=400, detail="Error creating balance sheet entry due to database constraint.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# Route to update an existing balance sheet entry (Admin only)
@router.put("/{ticker}/{year}")
async def update_balance_sheet(ticker: str, year: int, balance_data: BalanceSheetBase, db: Session = Depends(get_db), admin: Admin = Depends(admin_only)):
    """
    Update the balance sheet entry for a company by ticker and year.
    """
    try:
        # Check if the balance sheet exists
        balance_sheet = db.query(BalanceSheet).filter(BalanceSheet.ticker == ticker, BalanceSheet.year == year).first()
        
        if not balance_sheet:
            raise HTTPException(status_code=404, detail="Balance sheet not found for the given ticker and year.")
        
        # Update fields of the existing balance sheet
        for field, value in balance_data.model_dump(exclude_unset=True).items():
            setattr(balance_sheet, field, value)
        
        db.commit()
        db.refresh(balance_sheet)
        
        return {"message": "Balance sheet updated successfully.", "balance_sheet": balance_sheet}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# Route to delete a balance sheet entry (Admin only)
@router.delete("/{ticker}/{year}")
async def delete_balance_sheet(ticker: str, year: int, db: Session = Depends(get_db), admin: Admin = Depends(admin_only)):
    """
    Delete the balance sheet entry for a company by ticker and year.
    """
    try:
        balance_sheet = db.query(BalanceSheet).filter(BalanceSheet.ticker == ticker, BalanceSheet.year == year).first()

        if not balance_sheet:
            raise HTTPException(status_code=404, detail="Balance sheet not found for the given ticker and year.")

        db.delete(balance_sheet)
        db.commit()
        
        return {"message": "Balance sheet deleted successfully."}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# Route to get all companies with balance sheets
@router.get("/companies")
async def get_all_companies(db: Session = Depends(get_db)):
    """
    Get all companies listed in the company table, along with their associated balance sheets.
    """
    try:
        companies = db.query(Company).all()
        if not companies:
            raise HTTPException(status_code=404, detail="No companies found.")

        companies_with_balance_sheets = []
        
        for company in companies:
            balance_sheets = db.query(BalanceSheet).filter(BalanceSheet.ticker == company.name).all()
            companies_with_balance_sheets.append({
                "company": company,
                "balance_sheets": balance_sheets
            })
        
        return companies_with_balance_sheets
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
