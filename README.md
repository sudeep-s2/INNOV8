# Info2Impact — GenAI Platform for Automated Content Transformation

**Smart India Hackathon 2026**
- **Problem Statement ID:** SIH26154
- **Organization:** National Technical Research Organisation (NTRO)
- **Category:** Software
- **Theme:** Smart Automation
- **Team Name:** Innov8

---

## 📌 Project Overview

**Info2Impact** is an air-gapped, sovereign GenAI content transformation engine designed for high-security environments like NTRO. It ingests complex technical documents (threat intel, advisories, SCADA breach reports, policy papers) and implements a **"Understand Once, Transform Many"** paradigm:

1. **Multi-Format Ingestion & Semantic Chunking:** Ingests pasted text, TXT, and PDF files with token-aware semantic chunking and character offset tracking.
2. **Single-Pass Canonical Extraction:** Parses raw documents once using local **Qwen3 (8B)** via **Ollama**, producing a strictly validated `StructuredContentModel` (facts, entities, metrics, dates, risks, and recommendations).
3. **Deterministic Grounding Validator:** Pure Python code validation ensuring all factual claims cite valid `SourceChunk` IDs, with automated single-pass healing retry on drift.
4. **Multi-Output Orchestration:** Generates tailored communication artefacts from the *same* canonical model without re-analyzing the raw source:
   - 📊 **Executive Summary** (leadership decisions, risk posture, metric highlights)
   - 🛡️ **Advisory Brief** (technical observations, threat exposure, mandatory directives)
   - 📢 **Public Communication** (jargon-free citizen guidance, plain language messaging)
   - 📑 **Presentation Outline** (slide-by-slide briefing with data highlights and speaker notes)
5. **Interactive Dashboard:** Modern React 18 + TypeScript + Vite frontend with real-time health monitoring, configuration controls, and tabbed artefact viewers.

---

## 🛠️ Technology Stack

- **Local LLM Inference:** Ollama v0.33.2 running `qwen3:8b` (100% on-premise, zero cloud API reliance, air-gapped).
- **Backend:** Python 3.13, FastAPI (async REST API), Pydantic v2 (Rust-backed validation).
- **Document Parsing:** `pypdf`, custom UTF-8/Latin-1 sanitizer, deterministic chunker.
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS.
- **Testing:** Pytest (97 automated test cases covering models, parsers, AI service, validators, generators, and live Ollama integration).

---

## 📋 System Requirements

- **Python:** 3.10+ (Python 3.13 tested)
- **Node.js:** 18.0+ & **npm**
- **Ollama:** Installed and running locally (`http://localhost:11434`) with model `qwen3:8b`

---

## 🚀 Quick Start

### 1. Start Ollama (with Qwen3 8B)
```bash
ollama run qwen3:8b
```

### 2. Backend Setup & Run
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Docs: `http://127.0.0.1:8000/docs`
- Health Check: `http://127.0.0.1:8000/api/health`

### 3. Frontend Setup & Run
```bash
cd frontend
npm install
npm run dev
```
- Web Application: `http://localhost:5173/`

---

## 🧪 Automated Testing

Run the full backend test suite:
```bash
cd backend
python -m pytest tests -v
```
All 97 unit, mock, and integration tests pass with 100% success rate.
