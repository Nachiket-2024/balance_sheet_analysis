# --- Environment setup ---
from dotenv import load_dotenv                      # Load environment variables from .env
from pathlib import Path                            # Work with paths in an OS-agnostic way

# Calculate base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent
_ = load_dotenv(dotenv_path=BASE_DIR / ".env")     # Load .env variables

# --- FastAPI setup ---
from fastapi import FastAPI

from .auth import auth_routes
from .api import balance_sheet_routes

app = FastAPI()

# Include the authentication routes in your FastAPI app
app.include_router(auth_routes.router)

# Include the balance sheet routes in your FastAPI app
app.include_router(balance_sheet_routes.router)

@app.get("/")
async def root():
    return {"message": "Welcome to the Balance Sheet Analysis API!"}
