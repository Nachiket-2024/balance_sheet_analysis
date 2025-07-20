import os
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from ..schemas.llm_schema import ChatRequest, ChatResponse
import traceback
import requests  # For making HTTP requests to Groq AI
from ..db.session import get_db  # Assuming this function provides a session to the DB
from ..models.balance_sheet_model import BalanceSheet

# Load environment variables from .env file
load_dotenv()

# Fetch Groq API URL and Key from .env file
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = os.getenv("GROQ_API_URL")

# Ensure both environment variables are present
if not GROQ_API_KEY or not GROQ_API_URL:
    raise ValueError("GROQ_API_KEY and GROQ_API_URL must be set in the .env file")

# Create a FastAPI router with a common prefix and tag
router = APIRouter(
    prefix="/llm",
    tags=["LLM Integration"]
)

# ---------------------- POST: Chat with LLM ----------------------

@router.post("/chat", response_model=ChatResponse)
async def chat_with_llm(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Handle chat queries using Groq AI.

    Steps:
    1. Get the query from the user.
    2. Let Groq AI figure out the relevant ticker and year information (if any).
    3. If ticker and year are detected, fetch the balance sheet data from the database.
    4. Pass the query and extracted data to Groq AI to generate the answer.
    5. Return the Groq AI-generated answer.
    """
    try:
        # Step 1: Send the query to Groq AI without pre-processing (no manual extraction of ticker/year)
        user_query = request.question

        # Step 2: Send the query to Groq AI, where Groq AI handles the logic of extracting ticker and year
        prompt = f"Given the following query, extract the relevant stock ticker (e.g., 'AAPL' for Apple) and year(s) if mentioned, and generate a response: '{user_query}'"

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        # Step 3: Make the request to Groq API
        response = requests.post(GROQ_API_URL, json={"query": prompt}, headers=headers)

        # Ensure we got a valid response from Groq
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Groq API error: {response.text}")

        # Parse the Groq response to extract the answer
        result = response.json()
        answer = result.get("response", "").strip()

        if not answer:
            raise HTTPException(status_code=404, detail="Groq AI couldn't process the query.")

        # Step 4: Return the Groq-generated answer
        return ChatResponse(answer=answer)

    except HTTPException as e:
        raise e
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
