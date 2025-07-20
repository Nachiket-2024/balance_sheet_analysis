# --- Environment setup ---
from dotenv import load_dotenv                      # Load environment variables from .env
from pathlib import Path                            # Work with paths in an OS-agnostic way

# Calculate base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent
_ = load_dotenv(dotenv_path=BASE_DIR / ".env")     # Load .env variables

# --- FastAPI setup ---
from fastapi import FastAPI

# --- CORS setup ---
from fastapi.middleware.cors import CORSMiddleware  # Import CORS middleware for cross-origin requests

# Import route modules
from .auth import auth_routes
from .api import balance_sheet_routes

# Create FastAPI instance
app = FastAPI()

# Add CORS middleware — essential for frontend-backend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL during development
    allow_credentials=True,
    allow_methods=["*"],                      # Includes GET, POST, OPTIONS, etc.
    allow_headers=["*"],                      # Includes Authorization, Content-Type, etc.
)

# Include authentication-related routes
app.include_router(auth_routes.router)

# Include balance sheet–related API routes
app.include_router(balance_sheet_routes.router)

# Basic root endpoint for health check
@app.get("/")
async def root():
    return {"message": "Welcome to the Balance Sheet Analysis API!"}
