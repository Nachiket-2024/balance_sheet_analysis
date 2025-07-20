# Balance Sheet Analysis

---

## Overview

The Balance Sheet Analysis application is designed to help analysts and top-management users analyze and visualize financial data. The backend is built with FastAPI, SQLAlchemy, and PostgreSQL, while the frontend is developed using React and TailwindCSS. It allows users to retrieve balance sheet data for specific companies, authenticate via Google OAuth2, and perform various data analyses based on role-based access. The app integrates with external APIs like Groq for advanced AI-driven insights.

---

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, PostgreSQL 
- **Frontend**: React, TailwindCSS
- **Other**: Pydantic, Requests

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Nachiket-2024/balance_sheet_analysis.git
cd balance_sheet_analysis
```

### 2. Set up the environment

Install Backend dependencies with pip:

```bash
pip install -r requirements.txt
```

Install Frontend dependencies:

```bash
cd frontend
npm install
```

---

## Run the App

### 1. Start the FastAPI backend

```bash
uvicorn backend.main:app --reload
```

### 2. Run the React frontend

```bash
cd frontend
npm run dev
```

---

## .env Setup

Make a `.env` file at the root of the project (balance_sheet_analysis) with the following content:

```ini
# Postgresql Database URL
DATABASE_URL=postgresql://username:password@localhost:5432/db_name

# JWT Secret Key used for signing tokens
JWT_SECRET=jwt_secret_key_here
JWT_ALGORITHM=jwt_algorithm_here

# JWT Token Expiry
ACCESS_TOKEN_EXPIRE_MINUTES=minutes_in_numbers_here
REFRESH_TOKEN_EXPIRE_DAYS=time_in_days_here

# Google OAuth2 Credentials
GOOGLE_CLIENT_ID=google_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback
GOOGLE_SCOPES=openid,email,profile
GOOGLE_TOKEN_FILE=token.json

# Groq Credentials
GROQ_API_URL=https://api.groq.com/openai/v1/chat/completions
GROQ_API_KEY=groq_key_here
```

---
