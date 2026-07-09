# Balance Sheet Analysis

## Overview

**Balance Sheet Analysis** is a full-stack web application for importing, storing, and exploring company balance sheet data.

The backend is built with **FastAPI**, **SQLAlchemy**, and **PostgreSQL**, while the frontend uses **React** and **Tailwind CSS**. Company financial data is retrieved from **Yahoo Finance**, normalized before storage, and exposed through REST APIs.

The application supports **Google OAuth2 authentication**, **JWT-based authorization**, and role-based access control for protected operations. It also includes an experimental **Groq LLM integration** for natural-language financial queries.

---

## Features

### Authentication & Authorization

- Google OAuth2 login
- JWT-based authentication
- Automatic user registration after first login
- Role-based authorization (Admin and Analyst)
- Protected API endpoints

### Financial Data Management

- Import balance sheet data from Yahoo Finance
- Store balance sheet data in PostgreSQL
- Retrieve balance sheets by company ticker and reporting year
- View companies with their associated balance sheet records
- Automatically create company records during imports
- Sanitize imported financial data before database insertion

### REST API

- Retrieve balance sheets
- Import new balance sheets
- Delete balance sheets
- Browse companies and their associated balance sheets

### Experimental LLM Integration

- Natural-language financial query endpoint
- Powered by the Groq API
- Current implementation forwards prompts to the LLM and is not yet grounded using stored database data

---

# Tech Stack

### Backend

- FastAPI
- SQLAlchemy
- PostgreSQL
- Alembic
- Pydantic

### Frontend

- React
- Tailwind CSS
- React Router
- Axios

### Authentication

- Google OAuth2
- JWT (JSON Web Tokens)

### External Services

- Yahoo Finance (`yfinance`)
- Groq API

---

# API Overview

## Authentication

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/auth/login` | Start Google OAuth login |
| GET | `/auth/callback` | Handle Google OAuth callback |
| GET | `/auth/me` | Retrieve the authenticated user |
| POST | `/auth/logout` | Logout |

---

## Balance Sheets

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/balance-sheet/{ticker}/{year}` | Retrieve a balance sheet |
| POST | `/balance-sheet/{ticker}/{year}` | Import a balance sheet from Yahoo Finance *(Admin only)* |
| DELETE | `/balance-sheet/{ticker}/{year}` | Delete a balance sheet *(Admin only)* |
| GET | `/balance-sheet/companies` | Retrieve companies with associated balance sheets |

---

## LLM

| Method | Endpoint | Description |
|---------|----------|-------------|
| POST | `/llm/chat` | Submit a natural-language financial query |

---

# Installation

## Clone the repository

```bash
git clone https://github.com/Nachiket-2024/balance_sheet_analysis.git

cd balance_sheet_analysis
```

---

## Install backend dependencies

```bash
pip install -r requirements.txt
```

---

## Install frontend dependencies

```bash
cd frontend

npm install
```

---

# Running the Application

## Start the backend

```bash
uvicorn backend.main:app --reload
```

---

## Start the frontend

```bash
cd frontend

npm run dev
```

---

# Environment Variables

Create a `.env` file in the project root.

```env
# PostgreSQL
DATABASE_URL=postgresql://username:password@localhost:5432/database_name

# JWT
JWT_SECRET=your_secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Google OAuth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback
GOOGLE_SCOPES=openid,email,profile

# Groq
GROQ_API_KEY=your_groq_api_key
GROQ_API_URL=https://api.groq.com/openai/v1/chat/completions
```

---

# Application Flow

1. Users authenticate using Google OAuth2.
2. A local user record is created if one does not already exist.
3. JWT authentication is used for protected API access.
4. Administrators import company balance sheet data from Yahoo Finance.
5. Imported financial data is sanitized and stored in PostgreSQL.
6. Users can browse stored balance sheet information through the frontend.
7. Users can submit natural-language questions through the experimental LLM endpoint.

---

# Current Status

The project currently includes:

- Google OAuth2 authentication
- JWT-based authorization
- Role-based access control
- Yahoo Finance balance sheet import
- PostgreSQL data storage
- REST API for balance sheet management
- React frontend for authentication and balance sheet browsing
- Experimental Groq LLM integration

---

# Limitations

Current limitations include:

- The LLM is not yet grounded using stored balance sheet data.
- Only balance sheet statements are currently supported.
- The frontend focuses on core application functionality and API interaction.
- Financial visualizations and analytics dashboards are not yet implemented.

---

# Future Improvements

Potential future enhancements include:

- Ground LLM responses using stored financial data
- Support income statements and cash flow statements
- Financial ratio calculations
- Interactive charts and dashboards
- Search and filtering
- Expanded user and role management
- Docker support
- Automated testing
- CI/CD pipeline

---

# About

This project demonstrates the development of a full-stack financial web application using modern Python and JavaScript technologies. It combines REST API development, authentication, database management, external financial data integration, and an experimental LLM interface into a single application.