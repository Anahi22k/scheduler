# Scheduler (Capstone)

A web app that helps students draft semester schedules by combining **degree & AU Core requirement tracking**, **career/interest-aware course ranking**, and **constraint-based schedule generation** (time conflicts, unavailable days, credit limits, prerequisites).

---

## Repository layout

| Path | Purpose |
|------|---------|
| `backend/app.py` | Flask API: `/generate`, `/majors`, `/careers`. Loads JSON data and wires the engines together. |
| `backend/requirement_engine.py` | Computes remaining major + AU Core requirements from completed courses. |
| `backend/recommendation_engine.py` | Ranks courses (required-first / RapidFuzz career/interest similarity / seats). |
| `backend/schedule_generator.py` | Parses meeting times, filters sections, backtracking schedule search, ranks schedules. |
| `backend/scheduler.py` | Earlier scheduler experiment (legacy); the live app uses `schedule_generator.py`. |
| `backend/convert_onet.py` | Optional utility for ONET career data (uses pandas). |
| `backend/data/` | Runtime datasets: course offerings, programs, AU Core, careers. |
| `frontend/` | React (Vite) UI — collects student input and displays ranked schedules + warnings. |
| `scraper/` | Eagle Service scraping (`eagle_service_scraper.py`, program scrapers); has its own `requirements.txt`. |

---

## Prerequisites

- **Python 3.11** 
- **Node.js 18**  frontend

---

## Running locally

The frontend calls **`http://127.0.0.1:5000`** (`frontend/src/App.jsx`). Run backend and frontend in **two terminals**.

### 1. Backend

Paths like `data/courses_clean.json` are **relative to the `backend` folder**, so run Flask from **`backend`**:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Server: **http://127.0.0.1:5000**

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually **http://127.0.0.1:5173**).

### 3. Course data (`courses_clean.json`)

The API loads **`backend/data/courses_clean.json`**. If this file is missing, the server will error on startup.

The scraper writes **`scraper/courses_clean.json`**. Copy it into place:

```bash
cp scraper/courses_clean.json backend/data/courses_clean.json
```

Regenerate when you change terms (see `TERM_CODE` in `scraper/eagle_service_scraper.py`, e.g. `2026S`).

---

## API overview

| Endpoint | Method | Description |
|---------|--------|-------------|
| `/majors` | GET | Majors from `data/programs/programs_all.json` |
| `/careers` | GET | Career titles from `data/onet_careers.json` (autocomplete) |
| `/generate` | POST | JSON body: major, completed courses, credits completed, unavailable days, interests, career, `max_courses`, etc. Returns schedules, requirement summary, warnings, and edge-case diagnostics. |

---

## Scraper data (optional)

```bash
cd scraper
python -m venv .venv
source .venv/bin/activate          
pip install -r requirements.txt
python eagle_service_scraper.py
```

Program/major data: see `scrape_programs.py` and related scripts in `scraper/`.

---

## Production frontend build

```bash
cd frontend
npm run build
```

Output is **`frontend/dist/`**. You still need the Flask API reachable from the browser, or configure a proxy and change hardcoded API URLs in `frontend/src/App.jsx`.

---

## Other

- **Prerequisites** are inferred from catalog-style description text; incomplete data affects eligibility and warnings.

