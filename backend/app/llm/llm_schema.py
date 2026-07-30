from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    company_id: int
    years: list[int] | None = None  # None = use every fiscal year on file for this company
    # Bounded so one request can't build an unbounded-cost prompt against the
    # Groq API, generous enough for any realistic analyst question.
    question: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    answer: str
