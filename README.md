# Parsing-Based Sentence Reordering

A mini NLP project that reorders shuffled sentences using a parsing-based approach and compares it with a baseline method through a Flask web interface.

## Project Overview
Parsing-Based Sentence Reordering is designed to improve sentence order quality by using syntactic information from dependency parsing. Instead of relying only on surface-level cues, the model analyzes grammatical structure (such as subject, verb, and object relations) to produce more coherent sentence sequences.

The project also provides a user-friendly web UI with pages for home, reorder testing, examples, about, dataset/docs/guide, and run history.

## Features
- Parsing-based sentence reordering using NLP dependency signals
- Baseline vs parsing comparison mode
- Visual order-difference view (position-wise comparison)
- Parsing logic preview cards (Subject, Verb, Object)
- REST APIs for sample generation and reordering
- Web interface with:
  - Google sign-in flow (Firebase Authentication)
  - Reorder dashboard
  - History page for saved run results (server-side persistence)
  - Example and About pages
- Reuters-based sample sentence sourcing (Reuters-21578 text corpus)

## Tech Stack
- Backend: Python, Flask
- NLP: spaCy, NLTK, dependency parsing techniques
- Frontend: HTML, CSS, JavaScript
- Authentication: Firebase Authentication (Google sign-in + token verification)

## Algorithm Explanation (Parsing-Based Approach)
The parsing-based approach follows these stages:

1. Input preprocessing
- Clean the text and split it into valid sentences.
- Validate minimum sentence count (at least 3).

2. Dependency parsing
- Parse each sentence using spaCy.
- Extract structural clues such as grammatical root and dependency roles.

3. Structure-aware scoring/reordering
- Use syntactic signals (for example, subject/verb/object cues and dependency relations) to estimate sentence continuity and logical order.
- Build a reordered sequence based on this score.

4. Comparison with baseline
- Run a baseline reordering strategy in parallel.
- Compare baseline and parsing outputs by position and show quality percentages.

This makes the model more grammar-aware and generally more coherent than simple heuristic ordering.


## Pipeline Roadmap
```text
Parsing-Based Sentence Reordering
|
|-- Step 1: Parse Sentence
|   |-- Dependency Parsing (Implemented)
|   `-- Constituency Parsing (Planned)
|
|-- Step 2: Apply Reordering
|   |-- Rule-Based (Implemented)
|   |-- Statistical (Planned)
|   `-- Neural (Planned)
|
`-- Step 3: Generate Output Sentence (Implemented)
```

## Dataset
- **Reuters-21578** is used as a raw text source for generating sample inputs.
- Sentences are cleaned and shuffled for demonstration.
- The project is not using Reuters-21578 as a labeled supervised sentence-order benchmark.

## Project Structure
```text
Parsing-Based Sentence/
|-- app.py
|-- baseline.py
|-- data_loader.py
|-- evaluate.py
|-- parser_model.py
|-- preprocess.py
|-- requirements.txt
|-- templates/
|-- static/
|-- tests/
|-- docs/
|   |-- specs/
|   |   `-- product_specification.md
|   `-- testing/
|       `-- testsprite/
`-- README.md
```

## Installation
### 1. Clone and move into project
```bash
git clone <your-repository-url>
cd "Parsing-Based Sentence"
```

### 2. Create virtual environment
```bash
python -m venv .venv
```

### 3. Activate environment
- Windows (PowerShell):
```powershell
.\.venv\Scripts\Activate.ps1
```
- Linux/macOS:
```bash
source .venv/bin/activate
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 5. Configure environment variables (for Firebase auth)
Set these variables before running:
- `FLASK_SECRET_KEY`
- `FIREBASE_API_KEY`
- `FIREBASE_AUTH_DOMAIN`
- `FIREBASE_PROJECT_ID`
- `FIREBASE_APP_ID`
- `FIREBASE_STORAGE_BUCKET` (optional)
- `FIREBASE_MESSAGING_SENDER_ID` (optional)
- `FIREBASE_MEASUREMENT_ID` (optional)
- `FIREBASE_SERVICE_ACCOUNT_PATH` **or** `FIREBASE_SERVICE_ACCOUNT_JSON`

## Usage Instructions
### Run the app
```bash
python app.py
```

Open in browser:
- [http://127.0.0.1:5000](http://127.0.0.1:5000)

### Basic workflow
1. Open the **Reorder** page.
2. Paste at least 3 sentences (or load a sample).
3. Run **Baseline**, **Parsing**, or **Compare Both**.
4. Check:
- Reordered outputs
- Percentage scores
- Order Difference View
- Parsing Logic Preview

## API Endpoints (Optional for Demo)
- `GET /api/sample` - returns random Reuters dataset sample sentences only
- `POST /api/reorder` - returns reordered output using `baseline`, `parser`, or `compare`
- `POST /api/auth/google` - verifies Firebase Google ID token
- `GET /api/auth/status` - returns current authentication state
- `POST /api/auth/logout` - clears backend session
- `GET /api/history` - list run history for current account/session
- `POST /api/history` - save a run result
- `DELETE /api/history/<id>` - delete one history item
- `DELETE /api/history` - clear all history for current account/session

## Testing
Run tests locally:
```bash
pytest -q
```

CI runs automatically on push and pull requests via GitHub Actions (`.github/workflows/ci.yml`).

## Deployment (Render)
This repo includes:
- `render.yaml` (Blueprint config)
- `Procfile` (web process)
- `gunicorn` in `requirements.txt`

### Deploy steps
1. Push latest code to GitHub.
2. In Render, choose **New +** -> **Blueprint**.
3. Select this repository and deploy.
4. Set Firebase environment variables in Render (if auth is required):
   - `FIREBASE_API_KEY`
   - `FIREBASE_AUTH_DOMAIN`
   - `FIREBASE_PROJECT_ID`
   - `FIREBASE_APP_ID`
   - `FIREBASE_STORAGE_BUCKET` (optional)
   - `FIREBASE_MESSAGING_SENDER_ID` (optional)
   - `FIREBASE_MEASUREMENT_ID` (optional)
   - `FIREBASE_SERVICE_ACCOUNT_PATH` or `FIREBASE_SERVICE_ACCOUNT_JSON`

Render build installs dependencies and downloads:
- spaCy model: `en_core_web_sm`
- NLTK resources: `punkt`, `reuters`

## Deployment (Vercel)
This repo also supports Vercel deployment for the current Flask app using:
- `vercel.json`
- `app.py` as the Python serverless entry

### Deploy steps
1. Push latest code to GitHub.
2. In Vercel, click **Add New** -> **Project**.
3. Import this repository.
4. Keep default build settings and deploy.
5. Add environment variables in Vercel (if auth is needed):
   - `FLASK_SECRET_KEY`
   - `FIREBASE_API_KEY`
   - `FIREBASE_AUTH_DOMAIN`
   - `FIREBASE_PROJECT_ID`
   - `FIREBASE_APP_ID`
   - `FIREBASE_STORAGE_BUCKET` (optional)
   - `FIREBASE_MESSAGING_SENDER_ID` (optional)
   - `FIREBASE_MEASUREMENT_ID` (optional)
   - `FIREBASE_SERVICE_ACCOUNT_PATH` or `FIREBASE_SERVICE_ACCOUNT_JSON`

Note:
- Vercel uses serverless runtime. History storage is temporary unless you connect a persistent DB.
- Streamlit deployment would require rewriting the Flask UI into a Streamlit app.

## Screenshots
Add screenshots in a `docs/screenshots/` folder and update paths below.

- Home Page
  - `docs/screenshots/home.png`
- Reorder Dashboard
  - `docs/screenshots/reorder.png`
- Order Difference View
  - `docs/screenshots/order-difference.png`
- Parsing Logic Preview
  - `docs/screenshots/parsing-preview.png`
- Login/Register/Auth View
  - `docs/screenshots/auth.png`
- History Page
  - `docs/screenshots/history.png`

## Future Improvements
- Train/evaluate on a dedicated sentence ordering benchmark dataset
- Improve ranking with transformer-based coherence scoring
- Add detailed evaluation metrics (Kendall Tau, PMR, sentence-level accuracy)
- Support multilingual parsing models
- Export run history to CSV/PDF
- Add unit tests and CI pipeline for reliability

## Author
- Your Name
- College / Department
- Course / Mini Project Submission

## License
This project is for academic and educational use. You may add a formal open-source license (for example, MIT) if required.
