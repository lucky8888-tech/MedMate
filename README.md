# SafeDose (MedMate) - Medicine Alternative Suggester with Allergy Check & Scanner

SafeDose is a rule-based Python/Flask web app that identifies safe medicine alternatives, checks a 3-tier allergy engine, and scans medicine labels from a photo using OCR. It is an installable PWA (mobile-friendly) with a text search and a camera scanner.

> **Disclaimer:** SafeDose uses fictional/educational data and is not medical advice. Always consult a licensed doctor or pharmacist.

---

## Features

- **Text search** of medicines by brand, ID, or generic name with live autocomplete.
- **3-tier allergy check** (Direct active ingredient, Drug-class, and Inactive excipient).
- **5 enforced safety rules** (strict matching, missing-data exclusion, do-not-substitute, prescribed-product warning, cautious language).
- **openFDA live API fallback** for medicines not in the local CSV dataset.
- **Camera/Scan** (OCR): capture or upload a photo of a tablet strip or syrup bottle label; SafeDose reads the printed text to identify the medicine.
  - Identification is based on **printed label text only** - never by colour or appearance.
  - SafeDose **does not recommend dosage from a photo**.
  - When text is unclear or the match is ambiguous, an **uncertainty warning** recommends pharmacist verification.
- **Feedback form** stored securely on the server (no public read endpoint; name/email optional).
- Responsive UI for phones, tablets, and laptops; installable as a PWA.

---

## Completed Levels
- [x] **Level 1:** Search and details lookup from CSV datasets
- [x] **Level 2:** Strict alternative matching and side-by-side difference breakdown
- [x] **Level 3:** 3-tier allergy check engine (Direct, Drug-Class, Inactive)
- [x] **Level 4:** Enforced 5 Safety Rules & unit testing
- [x] **Level 5:** Camera/Scan Medicine - OCR identification from a label photo

---

## Implemented Safety Rules
1. **Strict Matching:** Only suggests products matching exact active ingredient(s), strength (unit-normalized), and form.
2. **Missing Data Handling:** Excludes products with missing inactive ingredient data when an allergy list is present.
3. **Do Not Substitute Flag:** Rejects substitution requests when explicitly flagged.
4. **Prescribed Product Warning:** Alerts the user if the prescribed medicine itself matches their allergy list.
5. **Clear Language:** Avoids absolute terms like "safe", declaring only: *"No listed trigger found in the data provided."*

---

## Project Structure
```
.
├── app.py                # Flask app: API routes + production config
├── medmate.py            # Core engine: matching, allergy checks, text-from-OCR matching, CLI
├── scan.py               # OCR text extraction (pytesseract + Pillow) with graceful fallback
├── medicines.csv         # Medicine dataset
├── allergy_classes.csv   # Ingredient -> drug-class mappings
├── tests_custom.py       # Tests for the 5 safety rules
├── tests_scan.py         # Tests for scan/feedback/matching features
├── requirements.txt      # Python dependencies
├── Dockerfile            # Production image (installs Tesseract via apt)
├── render.yaml          # Render deployment blueprint
├── Procfile              # Alternative deploy (Heroku/Railway)
├── .env.example          # Documented environment variables
├── templates/index.html  # Single-page UI
└── static/               # CSS, JS (app/scan/feedback), PWA manifest + service worker + icons
```

---

## Environment Variables
Copy `.env.example` to `.env` for local use. Hosting platforms set these for you.

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key-change-in-production` | Flask secret key (set a random value in production) |
| `FLASK_DEBUG` | `1` | `1` = dev (debug on), `0` = production |
| `PORT` | `5000` | Server port (hosting platforms set this) |
| `HOST` | `127.0.0.1` | Bind address (`0.0.0.0` in production) |
| `FEEDBACK_FILE` | `feedback.json` | Local file for feedback storage (do not commit) |

---

## How to Run (Local)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the web app
```bash
python app.py
```
Then open <http://localhost:5000>

### 3. Run the core logic (command line)
```bash
python medmate.py
```

### 4. Run the tests
```bash
python -m unittest tests_custom tests_scan -v
```

---

## Enabling the Camera / Scan (OCR) Feature

Scanning needs the **Tesseract OCR engine** binary on the system (pip cannot install it):

- **Windows:** install via `winget` (run in an **elevated** PowerShell):
  ```powershell
  winget install --id tesseract-ocr.tesseract --source winget --accept-package-agreements --accept-source-agreements
  ```
  Then reopen your terminal so `tesseract` is on your PATH.
- **macOS:** `brew install tesseract`
- **Linux:** `sudo apt-get install tesseract-ocr`

If Tesseract is not installed, the rest of the app still works; only scanning is unavailable, and `/api/scan` returns a clear "OCR not available" message.

> SafeDose processes the uploaded photo in memory on your own server and never sends images to any third-party service.

---

## Deployment (Public HTTPS Site)

The project is configured for **Render** (free tier, Docker-based, automatic HTTPS). Other Docker or Procfile-based platforms (Fly.io, Railway, Heroku) work too.

### Option A - Render (recommended)

1. Push this project to a GitHub repository (the repo already has remote `github.com/lucky8888-tech/MedMate.git`).
2. Sign up at <https://render.com> (free).
3. **New + > Web Service** > connect your GitHub repo.
4. Render auto-detects `render.yaml` (Docker runtime, free plan, health check on `/api/scan/status`). Confirm and click **Create Web Service**.
5. Render builds the image (installs Tesseract via apt automatically) and gives you a public URL:
   `https://safedose.onrender.com` (HTTPS, accessible from any phone/laptop).
6. Test the link: open it, run a search, and try the scanner.

### Option B - Any Docker platform

Build and run the included `Dockerfile`:
```bash
docker build -t safedose .
docker run -p 10000:10000 -e SECRET_KEY=$(openssl rand -hex 32) -e FLASK_DEBUG=0 safedose
```

### Option C - Procfile platforms (Heroku/Railway)

Uses `Procfile` + `gunicorn`. On these platforms, ensure the Tesseract binary is available (Heroku needs the `tesseract` buildpack; Railway/Fly can use the Dockerfile instead).

---

## Security & Privacy
- No API keys or passwords are committed. `.env` and `feedback.json` are git-ignored.
- Feedback is stored in a local file on the server and is **never exposed** via a public read endpoint.
- Uploaded scan images are processed in memory only; they are not saved to disk or transmitted elsewhere.
- Set a strong `SECRET_KEY` in production (Render generates one automatically via `render.yaml`).

---

## Tech Stack
Python 3, Flask, Pillow + Tesseract (OCR), openFDA API, vanilla JS PWA, gunicorn (production server).
