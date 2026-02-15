<p align="center">
  <h1 align="center">📊 Financial Analysis Agent</h1>
  <p align="center">
    <strong>AI-Powered Financial Document Analysis with Human-in-the-Loop Approval</strong>
  </p>
  <p align="center">
    <em>A multi-agent system built on LangGraph that extracts, analyzes, and generates comprehensive financial reports from PDF documents — with real-time progress tracking and human oversight at critical checkpoints.</em>
  </p>
</p>

---

## 🎯 Overview

Financial Analysis Agent is a full-stack application that leverages a **Supervisor Agent Architecture** powered by [LangGraph](https://github.com/langchain-ai/langgraph) to orchestrate multiple specialized AI agents. Users upload financial PDF documents, and the system autonomously performs document extraction, financial analysis, compliance checking, risk assessment, and report generation — pausing at key checkpoints for human review and approval.

---

## ✨ Features

### 🤖 Multi-Agent Orchestration

- **Supervisor Agent Pattern** — A LangGraph-based supervisor coordinates the entire workflow
- **5 Specialized Agents** — Document Extraction, Finance Analysis, Compliance, Risk Assessment, and Report Generation
- **Parallel Execution** — Finance Analysis and Compliance agents run concurrently for faster processing

### 👤 Human-in-the-Loop

- **Two Approval Checkpoints** — Extraction Review & Final Report Approval
- **Editable Draft Reports** — Modify analysis, compliance, and risk sections before final approval
- **Feedback Integration** — Provide notes and feedback at each checkpoint

### 📄 Document Processing

- **PDF Upload & Extraction** — Supports structured and unstructured PDF documents via PyMuPDF and pdfplumber
- **RAG (Retrieval-Augmented Generation)** — Ask specific questions about uploaded documents
- **Vector Store Integration** — Qdrant-powered vector search for accurate document retrieval

### 📊 Report Generation

- **Automated PDF Reports** — Professional financial reports generated with ReportLab
- **Downloadable Output** — One-click PDF report download after approval
- **Comprehensive Analysis** — Includes financial metrics, compliance status, and risk assessment

### 🔄 Real-Time Communication

- **WebSocket Progress Tracking** — Live updates via Django Channels & Daphne
- **Session Management** — Track multiple analysis sessions with status monitoring
- **Retry Mechanisms** — Automatic and manual retry from the last checkpoint on failure

### 🐳 Containerized Deployment

- **Docker Compose** — One-command deployment with multi-service orchestration
- **Nginx Reverse Proxy** — Production-grade frontend serving
- **Health Checks** — Automated backend health monitoring

---

## 🛠️ Tech Stack

### Backend

| Technology                            | Purpose                                |
| ------------------------------------- | -------------------------------------- |
| **Python 3.12**                       | Core language                          |
| **Django + DRF**                      | REST API framework                     |
| **Django Channels + Daphne**          | WebSocket support (ASGI)               |
| **LangGraph**                         | Multi-agent workflow orchestration     |
| **LangChain**                         | LLM integrations & document processing |
| **Google Gemini**                     | Primary LLM for analysis               |
| **Groq**                              | Fast LLM inference                     |
| **Qdrant**                            | Vector database for RAG                |
| **FastEmbed / Sentence Transformers** | Document embeddings                    |
| **PyMuPDF + pdfplumber**              | PDF parsing & extraction               |
| **ReportLab**                         | PDF report generation                  |
| **SQLite**                            | Session & metadata storage             |

### Frontend

| Technology        | Purpose                    |
| ----------------- | -------------------------- |
| **React 18**      | UI framework               |
| **TypeScript**    | Type-safe development      |
| **WebSocket API** | Real-time progress updates |

### DevOps

| Technology                  | Purpose                             |
| --------------------------- | ----------------------------------- |
| **Docker & Docker Compose** | Containerization & orchestration    |
| **Nginx**                   | Reverse proxy & static file serving |
| **Daphne**                  | ASGI production server              |

---

## 📐 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                     │
│              Upload PDF → Track Progress → Download Report  │
│                    WebSocket    REST API                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Backend (Django + Daphne)                  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              LangGraph Supervisor Workflow             │  │
│  │                                                       │  │
│  │  📄 Document Extraction                               │  │
│  │        ↓                                              │  │
│  │  🔔 Human Review Checkpoint                           │  │
│  │        ↓                                              │  │
│  │  ┌──────────────────┬──────────────────┐              │  │
│  │  │ 💰 Finance       │ ⚖️ Compliance    │ (parallel)   │  │
│  │  │   Analysis       │    Check         │              │  │
│  │  └──────────────────┴──────────────────┘              │  │
│  │        ↓                                              │  │
│  │  📊 Risk Assessment                                   │  │
│  │        ↓                                              │  │
│  │  📝 Report Generation                                 │  │
│  │        ↓                                              │  │
│  │  🔔 Final Approval Checkpoint                         │  │
│  │        ↓                                              │  │
│  │  ✅ Complete → Download PDF                            │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  Vector Store (Qdrant) ←→ LLMs (Gemini / Groq)             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**
- **Node.js 18+** and **npm**
- **Docker** and **Docker Compose** (for containerized deployment)
- **Git**

### API Keys Required

You will need API keys for the following services. Create a `.env` file in the project root (or in `backend/`) with:

```env
GOOGLE_API_KEY=your_google_gemini_api_key
GROQ_API_KEY=your_groq_api_key
QDRANT_URL=your_qdrant_cloud_url        # or use localhost for local Qdrant
QDRANT_API_KEY=your_qdrant_api_key      # if using Qdrant Cloud
```

---

## ⚡ Quick Start (Docker — Recommended)

The easiest way to run the entire application:

```bash
# 1. Clone the repository
git clone https://github.com/your-username/FinancialAnalysisAgent.git
cd FinancialAnalysisAgent

# 2. Create your .env file with API keys (see above)

# 3. Build and start all services
docker compose -p finapp up -d --build

# 4. Check that containers are running
docker compose -p finapp ps

# 5. View logs (optional, useful for debugging)
docker compose -p finapp logs -f
```

🌐 **Access the app at** → [http://localhost](http://localhost)

#### Docker Management Commands

```bash
# Stop containers (keeps them for restart later)
docker compose -p finapp stop

# Restart stopped containers
docker compose -p finapp start

# Stop AND remove containers + networks (full cleanup)
docker compose -p finapp down

# Rebuild after code changes
docker compose -p finapp up -d --build
```

---

## 🔧 Manual Setup (Development)

If you prefer to run the backend and frontend separately for development:

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/your-username/FinancialAnalysisAgent.git
cd FinancialAnalysisAgent
```

### 2️⃣ Backend Setup

```bash
# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Navigate to the backend directory
cd backend

# Create the media directory for file uploads
mkdir media

# Apply database migrations
python manage.py makemigrations
python manage.py migrate

# Start the development server (choose one):

# Option A: Django dev server
python manage.py runserver

# Option B: Daphne ASGI server (recommended — supports WebSockets)
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

✅ **Backend is now running at** → [http://127.0.0.1:8000](http://127.0.0.1:8000)

#### Verify the Backend

```bash
# Check the root endpoint
curl http://127.0.0.1:8000/

# Test file upload
curl -X POST -F "file=@/path/to/your/document.pdf" http://127.0.0.1:8000/api/upload/
```

### 3️⃣ Frontend Setup

Open a **new terminal** and navigate to the frontend directory:

```bash
cd frontend

# Install Node.js dependencies
npm install

# Start the React development server
npm start
```

✅ **Frontend is now running at** → [http://localhost:3000](http://localhost:3000)

> **Note:** The frontend proxies API requests to `http://localhost:8000` automatically during development (configured in `package.json`).

---

## 📡 API Endpoints

| Method | Endpoint                      | Description                       |
| ------ | ----------------------------- | --------------------------------- |
| `GET`  | `/`                           | API info & available endpoints    |
| `POST` | `/api/upload/`                | Upload a PDF file                 |
| `GET`  | `/api/sessions/`              | List all analysis sessions        |
| `POST` | `/api/sessions/<id>/start/`   | Start analysis pipeline           |
| `GET`  | `/api/sessions/<id>/status/`  | Get session status & preview      |
| `POST` | `/api/sessions/<id>/approve/` | Approve a checkpoint              |
| `GET`  | `/api/sessions/<id>/report/`  | Download the generated PDF report |
| `POST` | `/api/sessions/<id>/retry/`   | Retry a failed analysis           |

### WebSocket

```
ws://127.0.0.1:8000/ws/progress/<session_id>/
```

Provides real-time progress messages during analysis.

---

## 📋 Workflow

The analysis pipeline follows this sequence:

1. **📤 Upload** — User uploads a PDF financial document
2. **📄 Document Extraction** — Agent parses and extracts text, tables, and structure
3. **🔔 Extraction Review** — _Human checkpoint_ — Review extracted content before analysis
4. **💰 Finance Analysis + ⚖️ Compliance Check** — Two agents run _in parallel_
5. **📊 Risk Assessment** — Evaluates financial risks based on analysis results
6. **📝 Report Generation** — Compiles all findings into a structured report
7. **🔔 Final Report Approval** — _Human checkpoint_ — Review, edit, and approve the draft
8. **✅ Complete** — Final PDF report is generated and available for download

---

## 📁 Project Structure

```
FinancialAnalysisAgent/
├── backend/
│   ├── agents/                     # AI Agent modules
│   │   ├── document_extraction.py  # PDF parsing & text extraction
│   │   ├── finance_analysis.py     # Financial metrics analysis
│   │   ├── compliance.py           # Regulatory compliance checking
│   │   ├── risk_assessment.py      # Risk evaluation
│   │   └── report_generation.py    # PDF report creation
│   ├── workflows/
│   │   ├── financial_analysis_workflow.py  # LangGraph supervisor workflow
│   │   ├── supervisor.py           # Supervisor agent logic
│   │   ├── state.py                # Workflow state definitions
│   │   ├── checkpointer.py         # State persistence
│   │   └── retry.py                # Retry mechanisms
│   ├── api/
│   │   ├── views.py                # REST API endpoints
│   │   ├── consumers.py            # WebSocket consumers
│   │   ├── models.py               # Database models
│   │   └── serializers.py          # DRF serializers
│   ├── config/                     # Django project settings
│   ├── Dockerfile                  # Backend container definition
│   └── entrypoint.sh               # Container startup script
├── frontend/
│   ├── src/
│   │   ├── App.tsx                 # Main React application
│   │   ├── App.css                 # Application styles
│   │   └── components/             # React components
│   ├── Dockerfile                  # Multi-stage build (Node → Nginx)
│   ├── nginx.conf                  # Nginx configuration
│   └── package.json                # Node.js dependencies
├── docker-compose.yml              # Multi-service orchestration
├── requirements.txt                # Python dependencies
└── README.md
```

---

## 🛡️ Troubleshooting

### Frontend dependency issues

If you encounter broken dependencies or red underlines in your IDE:

```bash
cd frontend

# Remove existing installation
rmdir /s /q node_modules     # Windows
# rm -rf node_modules         # macOS / Linux

del package-lock.json         # Windows
# rm package-lock.json        # macOS / Linux

# Reinstall everything
npm install
```

### Backend not connecting

- Ensure the backend is running on port `8000`
- For WebSocket support, use **Daphne** instead of `runserver`:
  ```bash
  daphne -b 0.0.0.0 -p 8000 config.asgi:application
  ```

### Docker issues

```bash
# View container logs for debugging
docker compose -p finapp logs -f

# Rebuild from scratch
docker compose -p finapp down
docker compose -p finapp up -d --build
```

---

## 📄 License

This project is for educational and research purposes.

---
