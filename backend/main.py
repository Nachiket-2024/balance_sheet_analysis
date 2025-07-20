# ---------------------- Environment Setup ----------------------

from dotenv import load_dotenv                      # Load environment variables from .env
from pathlib import Path                            # For working with file paths in an OS-independent way

# Calculate the base directory (root of the project)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env file located at project root
_ = load_dotenv(dotenv_path=BASE_DIR / ".env")

# ---------------------- FastAPI Setup ----------------------

from fastapi import FastAPI  # Import FastAPI app constructor

# ---------------------- CORS Setup ----------------------

from fastapi.middleware.cors import CORSMiddleware  # CORS middleware to allow frontend/backend interaction

# ---------------------- Route Imports ----------------------

# Import your custom route files
from .auth import auth_routes                      # Authentication routes (OAuth, login)
from .api import balance_sheet_routes, llm_routes  # Routes for balance sheet and LLM chat

# ---------------------- FastAPI App Initialization ----------------------

# Create a FastAPI app instance
app = FastAPI()

# Add CORS middleware — allows React frontend to access this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Allow requests from your frontend dev server
    allow_credentials=True,
    allow_methods=["*"],                      # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],                      # Allow all headers (Authorization, Content-Type, etc.)
)

# ---------------------- Route Registration ----------------------

# Include authentication routes under /auth/*
app.include_router(auth_routes.router)

# Include balance sheet routes under /balance-sheet/*
app.include_router(balance_sheet_routes.router)

# Include LLM routes under /llm/*
app.include_router(llm_routes.router)

# ---------------------- Root Endpoint ----------------------

@app.get("/")
async def root():
    """
    Basic root endpoint to confirm the API is running.
    """
    return {"message": "Welcome to the Balance Sheet Analysis API!"}
