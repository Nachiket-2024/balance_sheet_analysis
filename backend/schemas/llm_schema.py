from pydantic import BaseModel

class ChatRequest(BaseModel):
    ticker: str | None = None  # Stock ticker symbol, e.g. "AAPL", None by default
    years: list[int] | None = None  # List of years for the balance sheet, e.g. [2023, 2024], None by default
    question: str  # User's question about the balance sheet, required

class ChatResponse(BaseModel):
    answer: str  # Generated answer from the LLM
