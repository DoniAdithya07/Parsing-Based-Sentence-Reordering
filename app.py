from __future__ import annotations

import json
import os
import random
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from baseline import baseline_reorder
from data_loader import ensure_nltk_data, load_reuters_sentences
from parser_model import get_spacy_model, parser_reorder, spacy_engine_mode
from evaluate import evaluate_sequence
from preprocess import clean_and_split_sentences, format_output

PROJECT_ROOT = Path(__file__).resolve().parent


def _resolve_instance_dir() -> Path:
    env_dir = os.getenv("INSTANCE_DIR", "").strip()
    if env_dir:
        return Path(env_dir)

    # Vercel serverless runtime allows writable temporary storage under /tmp.
    if os.getenv("VERCEL", "").strip():
        return Path("/tmp/parsing_based_sentence")

    return PROJECT_ROOT / "instance"


INSTANCE_DIR = _resolve_instance_dir()
HISTORY_DB_PATH = INSTANCE_DIR / "history.db"
SECRET_KEY_PATH = INSTANCE_DIR / ".flask_secret_key"


def _load_app_secret_key() -> str:
    env_key = os.getenv("FLASK_SECRET_KEY", "").strip()
    if env_key:
        return env_key

    try:
        INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
        if SECRET_KEY_PATH.exists():
            saved_key = SECRET_KEY_PATH.read_text(encoding="utf-8").strip()
            if saved_key:
                return saved_key

        saved_key = secrets.token_hex(32)
        SECRET_KEY_PATH.write_text(saved_key, encoding="utf-8")
        return saved_key
    except OSError:
        # Last-resort fallback to avoid boot failure in restricted environments.
        return secrets.token_hex(32)

app = Flask(__name__)
app.secret_key = _load_app_secret_key()
_REUTERS_CACHE: List[str] = []
OPEN_DOMAIN_SAMPLE_BANK: List[List[str]] = [
    [
        "The city marathon started before sunrise to avoid the midday heat.",
        "Volunteers handed water bottles to runners at every checkpoint.",
        "A sudden drizzle cooled the streets and lifted everyone's pace.",
        "By noon, thousands of spectators were cheering near the finish line.",
    ],
    [
        "Mina backed up the project files before installing the update.",
        "The installation paused once because the network briefly dropped.",
        "After reconnecting, the setup resumed and completed without errors.",
        "She then ran a quick test to confirm all features were working.",
    ],
    [
        "The teacher divided the class into small groups for the science activity.",
        "Each group received a different material to test how heat moves.",
        "Students recorded observations and compared their results on a chart.",
        "In the final discussion, they connected the experiment to real-life examples.",
    ],
]
DEFAULT_FIREBASE_WEB_CONFIG = {
    "apiKey": "AIzaSyAm-MM0bHIpMf2cv0AlCYrRLM8CjRPYVr4",
    "authDomain": "parsing-based-sentence.firebaseapp.com",
    "projectId": "parsing-based-sentence",
    "appId": "1:1024287457881:web:6ccf038e021c7cd6bc6748",
    "storageBucket": "parsing-based-sentence.firebasestorage.app",
    "messagingSenderId": "1024287457881",
    "measurementId": "G-E73J28BK20",
}


def json_response(payload: Dict[str, Any], status_code: int = 200):
    response = jsonify(payload)
    response.status_code = status_code
    return response


def get_firebase_web_config() -> Dict[str, str]:
    return {
        "apiKey": os.getenv("FIREBASE_API_KEY", DEFAULT_FIREBASE_WEB_CONFIG["apiKey"]),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", DEFAULT_FIREBASE_WEB_CONFIG["authDomain"]),
        "projectId": os.getenv("FIREBASE_PROJECT_ID", DEFAULT_FIREBASE_WEB_CONFIG["projectId"]),
        "appId": os.getenv("FIREBASE_APP_ID", DEFAULT_FIREBASE_WEB_CONFIG["appId"]),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", DEFAULT_FIREBASE_WEB_CONFIG["storageBucket"]),
        "messagingSenderId": os.getenv(
            "FIREBASE_MESSAGING_SENDER_ID",
            DEFAULT_FIREBASE_WEB_CONFIG["messagingSenderId"],
        ),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID", DEFAULT_FIREBASE_WEB_CONFIG["measurementId"]),
    }


def firebase_web_enabled() -> bool:
    cfg = get_firebase_web_config()
    required = [cfg["apiKey"], cfg["authDomain"], cfg["projectId"], cfg["appId"]]
    return all(required)


def verify_firebase_id_token(id_token: str):
    try:
        import firebase_admin
        from firebase_admin import auth, credentials
    except Exception as exc:
        return None, f"firebase-admin is not installed: {exc}"

    if not firebase_admin._apps:
        cert_payload = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        cert_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
        try:
            if cert_payload:
                cred_dict = json.loads(cert_payload)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
            elif cert_path:
                cred = credentials.Certificate(cert_path)
                firebase_admin.initialize_app(cred)
            else:
                return None, "Firebase admin is not configured on the server."
        except Exception as exc:
            return None, f"Failed to initialize Firebase admin: {exc}"

    try:
        decoded = auth.verify_id_token(id_token)
        return decoded, None
    except Exception as exc:
        return None, f"Token verification failed: {exc}"




# Backward compatibility alias
def verify_google_id_token(id_token: str):
    return verify_firebase_id_token(id_token)

def validate_reorder_input(raw_input: str, min_sentences: int = 3, max_sentences: int = 80):
    if not raw_input or not raw_input.strip():
        return [], "Input is empty"

    sentences = clean_and_split_sentences(raw_input)
    if len(sentences) < min_sentences:
        return [], f"Too few sentences. Please enter at least {min_sentences} sentences."
    if len(sentences) > max_sentences:
        return [], f"Input is too large. Please keep it within {max_sentences} sentences."
    return sentences, ""


def run_baseline_method(sentences: List[str]):
    return baseline_reorder(sentences)


def run_parsing_method(sentences: List[str]):
    nlp = get_spacy_model()
    return parser_reorder(sentences, nlp)


def detect_input_reconstruction(raw_input: str, sentences: List[str]) -> Dict[str, Any]:
    raw_text = str(raw_input or "")
    raw_lines = [line.strip() for line in raw_text.replace("\r\n", "\n").splitlines() if line.strip()]
    had_newlines = "\n" in raw_text
    had_malformed_tokens = any(token in raw_text for token in ("<", ">", "&lt", "&gt"))
    normalized_join = " ".join(sentences).lower()
    cleaned_malformed = had_malformed_tokens and ("<" not in normalized_join and ">" not in normalized_join and "&lt" not in normalized_join and "&gt" not in normalized_join)

    reconstructed_by_line_merge = had_newlines and len(raw_lines) != len(sentences)
    return {
        "raw_line_count": len(raw_lines),
        "sentence_count": len(sentences),
        "had_newlines": had_newlines,
        "had_malformed_tokens": had_malformed_tokens,
        "cleaned_malformed_tokens": cleaned_malformed,
        "reconstructed_by_line_merge": reconstructed_by_line_merge,
    }


def get_parser_diagnostics() -> Dict[str, Any]:
    nlp = get_spacy_model()
    pipes = list(getattr(nlp, "pipe_names", []) or [])
    return {
        "engine_mode": spacy_engine_mode(nlp),
        "pipe_names": pipes,
        "parse_component_available": "parser" in pipes,
    }


def to_percent(score: float | None) -> int | None:
    if score is None:
        return None
    bounded = max(0.0, min(1.0, float(score)))
    return int(round(bounded * 100))


def extract_parse_cards(sentences: List[str]):
    if not sentences:
        return []

    nlp = get_spacy_model()
    cards = []
    for sentence in sentences[:3]:
        doc = nlp(sentence)
        subject = next((t.text for t in doc if t.dep_ in {"nsubj", "nsubjpass"}), "-")
        root = next((t.text for t in doc if t.dep_ == "ROOT"), "-")
        obj = next((t.text for t in doc if t.dep_ in {"dobj", "obj", "iobj", "pobj"}), "-")
        cards.append({"sentence": sentence, "subject": subject, "verb": root, "object": obj})
    return cards


def build_reorder_result(sentences: List[str], selected_method: str):
    baseline_output: List[str] = []
    parsing_output: List[str] = []
    baseline_score: float | None = None
    parsing_score: float | None = None
    parser_error = ""
    parser_fallback = False
    parser_engine_mode = ""
    parser_parse_component_available = False

    method = selected_method.lower().strip()
    if method == "baseline":
        baseline_output, baseline_score = run_baseline_method(sentences)
    elif method == "parser":
        parser_diag = get_parser_diagnostics()
        parser_engine_mode = str(parser_diag["engine_mode"])
        parser_parse_component_available = bool(parser_diag["parse_component_available"])
        try:
            parsing_output, parsing_score = run_parsing_method(sentences)
        except Exception as exc:
            parser_error = str(exc)
            parsing_output, parsing_score = run_baseline_method(sentences)
            parser_fallback = True
    else:
        baseline_output, baseline_score = run_baseline_method(sentences)
        parser_diag = get_parser_diagnostics()
        parser_engine_mode = str(parser_diag["engine_mode"])
        parser_parse_component_available = bool(parser_diag["parse_component_available"])
        try:
            parsing_output, parsing_score = run_parsing_method(sentences)
        except Exception as exc:
            parser_error = str(exc)
            parsing_output = baseline_output.copy()
            parsing_score = baseline_score
            parser_fallback = True
        method = "compare"

    return {
        "selected_method": method,
        "baseline_output": baseline_output,
        "parsing_output": parsing_output,
        "baseline_score": baseline_score,
        "parsing_score": parsing_score,
        "baseline_percent": to_percent(baseline_score),
        "parsing_percent": to_percent(parsing_score),
        "parser_error": parser_error,
        "parser_fallback": parser_fallback,
        "parsing_applied": method in {"parser", "compare"} and bool(parsing_output) and not parser_fallback,
        "parsing_engine_mode": parser_engine_mode,
        "parser_parse_component_available": parser_parse_component_available,
        "baseline_reordered": bool(baseline_output) and baseline_output != sentences,
        "parsing_reordered": bool(parsing_output) and parsing_output != sentences,
    }


def _open_history_db() -> sqlite3.Connection:
    conn = sqlite3.connect(HISTORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_history_db() -> None:
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    with _open_history_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_key TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                method TEXT NOT NULL,
                input_text TEXT NOT NULL,
                baseline_text TEXT NOT NULL,
                parsing_text TEXT NOT NULL,
                baseline_score REAL,
                parsing_score REAL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_run_history_actor_ts ON run_history(actor_key, created_at DESC)")
        conn.commit()


def get_history_actor_key() -> str:
    user_email = str(session.get("user_email", "")).strip().lower()
    if user_email:
        return f"user:{user_email}"

    guest_id = str(session.get("guest_id", "")).strip()
    if not guest_id:
        guest_id = secrets.token_urlsafe(18)
        session["guest_id"] = guest_id
    return f"guest:{guest_id}"


def serialize_history_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": int(row["id"]),
        "ts": int(row["created_at"]),
        "method": str(row["method"]),
        "method_label": {
            "baseline": "Run Baseline",
            "parser": "Run Parsing",
            "compare": "Compare Both",
        }.get(str(row["method"]), "Run"),
        "input_text": str(row["input_text"]),
        "baseline_text": str(row["baseline_text"]),
        "parsing_text": str(row["parsing_text"]),
        "baseline_score": row["baseline_score"],
        "parsing_score": row["parsing_score"],
    }


def initialize_runtime() -> None:
    ensure_nltk_data(allow_punkt_download=False)
    init_history_db()


def pick_open_domain_sample() -> List[str]:
    """Return a built-in sample when Reuters data is unavailable."""
    chosen = random.choice(OPEN_DOMAIN_SAMPLE_BANK)
    # Keep API shape consistent with Reuters mode (3-5 lines).
    if len(chosen) <= 5:
        return chosen.copy()

    k = random.randint(3, 5)
    return random.sample(chosen, k=k)


@app.context_processor
def inject_globals():
    return {
        "firebase_web_config": get_firebase_web_config(),
        "firebase_enabled": firebase_web_enabled(),
    }


@app.errorhandler(404)
def handle_not_found(_error):
    if request.path.startswith("/api/"):
        return json_response({"error": "Not found"}, 404)
    return "Not Found", 404


@app.errorhandler(405)
def handle_method_not_allowed(_error):
    if request.path.startswith("/api/"):
        return json_response({"error": "Method not allowed"}, 405)
    return "Method Not Allowed", 405


@app.errorhandler(500)
def handle_internal_error(_error):
    if request.path.startswith("/api/"):
        return json_response({"error": "Internal server error"}, 500)
    return "Internal Server Error", 500


@app.route("/")
def home() -> str:
    return render_template("index.html")


@app.route("/login", methods=["GET"])
def login() -> Any:
    # Legacy route kept for compatibility.
    return redirect(url_for("home"))


@app.route("/register", methods=["GET"])
def register() -> Any:
    # Legacy route kept for compatibility.
    return redirect(url_for("home"))


@app.route("/logout")
def logout() -> Any:
    # Keep backend logout for compatibility if backend session exists.
    session.clear()
    return redirect(url_for("home"))


@app.route("/reorder", methods=["GET", "POST"])
def reorder() -> str:
    error = ""
    input_text = ""
    graph_input_text = ""
    input_diag: Dict[str, Any] = {}
    result = {
        "selected_method": "baseline",
        "baseline_output": [],
        "parsing_output": [],
        "baseline_score": None,
        "parsing_score": None,
        "baseline_percent": None,
        "parsing_percent": None,
        "parser_error": "",
        "parser_fallback": False,
        "parsing_applied": False,
        "parsing_engine_mode": "",
        "parser_parse_component_available": None,
        "baseline_reordered": False,
        "parsing_reordered": False,
    }
    parse_cards = []
    evaluation_rows = []

    capability_rows = [
        {
            "name": "Input reconstruction and cleaning reliability",
            "status": "Enabled",
            "details": "Fragment merge, malformed token cleanup, and input-level diagnostics are active.",
        },
        {
            "name": "Topic-aware + pronoun-aware ordering",
            "status": "Enabled",
            "details": "Parser ranking uses topic continuity, entity flow, and pronoun-aware transition scoring.",
        },
        {
            "name": "Explainable and fast pipeline",
            "status": "Enabled",
            "details": "SVO preview cards, sentence flow graph, and lightweight heuristic scoring are available in UI.",
        },
        {
            "name": "Safe fallback on high-risk mixed-topic inputs",
            "status": "Enabled",
            "details": "High-diversity reorder gating and parser fallback protect against unstable output.",
        },
        {
            "name": "Debug diagnostics in API",
            "status": "Enabled",
            "details": "/api/reorder returns input diagnostics, parser mode, fallback flags, and reorder activity flags.",
        },
    ]

    if request.method == "POST":
        raw_input = request.form.get("input_text", "")
        selected_method = request.form.get("method", "baseline")
        input_text = raw_input
        graph_input_text = raw_input
        sentences, validation_error = validate_reorder_input(raw_input)

        if validation_error:
            error = "Please paste text with at least 3 sentences." if validation_error == "Input is empty" else validation_error
            result["selected_method"] = selected_method
        else:
            # Keep flow-graph input aligned with model inputs.
            graph_input_text = format_output(sentences)
            try:
                result = build_reorder_result(sentences, selected_method)
                input_diag = detect_input_reconstruction(raw_input, sentences)
                if result["parser_error"]:
                    error = f"{result['parser_error']} Using fallback output for parsing view."

                baseline_eval = evaluate_sequence(result["baseline_output"], sentences) if result["baseline_output"] else {}
                parsing_eval = evaluate_sequence(result["parsing_output"], sentences) if result["parsing_output"] else {}

                evaluation_rows = [
                    {
                        "metric": "Exact Match",
                        "baseline": f"{baseline_eval.get('exact_match', 0.0) * 100:.1f}%" if baseline_eval else "-",
                        "parsing": f"{parsing_eval.get('exact_match', 0.0) * 100:.1f}%" if parsing_eval else "-",
                    },
                    {
                        "metric": "PMR (Perfect Match Ratio)",
                        "baseline": f"{baseline_eval.get('pmr', 0.0) * 100:.1f}%" if baseline_eval else "-",
                        "parsing": f"{parsing_eval.get('pmr', 0.0) * 100:.1f}%" if parsing_eval else "-",
                    },
                    {
                        "metric": "Pairwise Accuracy",
                        "baseline": f"{baseline_eval.get('pairwise_accuracy', 0.0) * 100:.1f}%" if baseline_eval else "-",
                        "parsing": f"{parsing_eval.get('pairwise_accuracy', 0.0) * 100:.1f}%" if parsing_eval else "-",
                    },
                    {
                        "metric": "Kendall Tau",
                        "baseline": f"{baseline_eval.get('kendall_tau', 0.0):.3f}" if baseline_eval else "-",
                        "parsing": f"{parsing_eval.get('kendall_tau', 0.0):.3f}" if parsing_eval else "-",
                    },
                ]

                reference_for_cards = result["parsing_output"] or result["baseline_output"]
                parse_cards = extract_parse_cards(reference_for_cards)
            except Exception as exc:
                error = str(exc)
                result["selected_method"] = selected_method

    diagnostics_has_run = bool(result["baseline_output"] or result["parsing_output"])
    diagnostics = {
        "has_run": diagnostics_has_run,
        "raw_line_count": input_diag.get("raw_line_count"),
        "sentence_count": input_diag.get("sentence_count"),
        "had_newlines": input_diag.get("had_newlines"),
        "reconstructed_by_line_merge": input_diag.get("reconstructed_by_line_merge"),
        "had_malformed_tokens": input_diag.get("had_malformed_tokens"),
        "cleaned_malformed_tokens": input_diag.get("cleaned_malformed_tokens"),
        "parsing_applied": result.get("parsing_applied"),
        "parsing_engine_mode": result.get("parsing_engine_mode"),
        "parser_parse_component_available": result.get("parser_parse_component_available"),
        "parser_fallback": result.get("parser_fallback"),
        "baseline_reordered": result.get("baseline_reordered"),
        "parsing_reordered": result.get("parsing_reordered"),
    }

    return render_template(
        "reorder.html",
        input_text=input_text,
        graph_input_text=graph_input_text,
        baseline_text=format_output(result["baseline_output"]),
        parsing_text=format_output(result["parsing_output"]),
        baseline_score=result["baseline_score"],
        parsing_score=result["parsing_score"],
        baseline_percent=result["baseline_percent"],
        parsing_percent=result["parsing_percent"],
        selected_method=result["selected_method"],
        parse_cards=parse_cards,
        evaluation_rows=evaluation_rows,
        capability_rows=capability_rows,
        diagnostics=diagnostics,
        error=error,
    )

@app.route("/history")
def history() -> str:
    return render_template("history.html")


@app.route("/about")
def about() -> str:
    return render_template("about.html")


@app.route("/dataset")
def dataset() -> str:
    return render_template("dataset.html")


@app.route("/presentation")
def presentation() -> str:
    return render_template("presentation.html")


@app.route("/api/auth/firebase", methods=["POST"])
@app.route("/api/auth/google", methods=["POST"])
def auth_firebase():
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("idToken", "")).strip()
    if not token:
        return json_response({"error": "Missing Firebase ID token"}, 400)

    decoded, err = verify_firebase_id_token(token)
    if err:
        return json_response({"error": err}, 401)

    email = str(decoded.get("email", ""))
    name = str(decoded.get("name", "")) or email or str(decoded.get("uid", "user"))

    session["user"] = name
    session["user_email"] = email
    provider = str((decoded.get("firebase") or {}).get("sign_in_provider", "firebase"))
    session["auth_provider"] = provider

    return json_response(
        {
            "message": "Firebase login successful",
            "user": {
                "name": name,
                "email": email,
                "provider": provider,
            },
        }
    )


@app.route("/api/auth/status", methods=["GET"])
def auth_status():
    if not session.get("user"):
        return json_response({"authenticated": False, "guest": True})
    return json_response(
        {
            "authenticated": True,
            "user": {
                "name": session.get("user", ""),
                "email": session.get("user_email", ""),
                "provider": session.get("auth_provider", "firebase"),
            },
        }
    )


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return json_response({"message": "Logged out"})


@app.route("/api/sample", methods=["GET"])
def random_sample():
    global _REUTERS_CACHE
    source_mode = str(request.args.get("source", "auto")).strip().lower()
    if source_mode not in {"auto", "dataset", "open"}:
        return json_response({"error": "Invalid source. Use auto, dataset, or open."}, 400)

    if source_mode != "open":
        try:
            if len(_REUTERS_CACHE) < 80:
                _REUTERS_CACHE = load_reuters_sentences(limit=400)
        except Exception:
            _REUTERS_CACHE = []

    if source_mode in {"auto", "dataset"} and len(_REUTERS_CACHE) >= 3:
        k = random.randint(3, 5)
        picked = random.sample(_REUTERS_CACHE, k=k)
        return json_response(
            {
                "source": "dataset",
                "sentences": picked,
                "text": "\n".join(picked),
                "count": len(picked),
            }
        )

    if source_mode == "dataset":
        return json_response({"error": "Reuters dataset sample is unavailable right now."}, 503)

    picked = pick_open_domain_sample()
    return json_response(
        {
            "source": "open",
            "sentences": picked,
            "text": "\n".join(picked),
            "count": len(picked),
        }
    )


@app.route("/api/reorder", methods=["POST"])
def api_reorder():
    payload = request.get_json(silent=True)
    if payload is None or not isinstance(payload, dict):
        return json_response({"error": "Invalid JSON body"}, 400)

    raw_input = str(payload.get("text", ""))
    if not raw_input.strip():
        return json_response({"error": "Input is empty"}, 400)

    selected_method = str(payload.get("method", "compare")).lower().strip()
    if selected_method not in {"baseline", "parser", "compare"}:
        return json_response({"error": "Invalid method. Use baseline, parser, or compare."}, 400)

    sentences, validation_error = validate_reorder_input(raw_input)
    if validation_error:
        return json_response({"error": validation_error}, 400)

    result = build_reorder_result(sentences, selected_method)
    input_diag = detect_input_reconstruction(raw_input, sentences)

    return json_response(
        {
            "input_sentences": sentences,
            "input_diagnostics": input_diag,
            "selected_method": result["selected_method"],
            "baseline_output": result["baseline_output"],
            "parsing_output": result["parsing_output"],
            "baseline_text": format_output(result["baseline_output"]),
            "parsing_text": format_output(result["parsing_output"]),
            "baseline_score": result["baseline_score"],
            "parsing_score": result["parsing_score"],
            "baseline_percent": result["baseline_percent"],
            "parsing_percent": result["parsing_percent"],
            "parser_error": result["parser_error"],
            "parser_fallback": result["parser_fallback"],
            "parsing_applied": result["parsing_applied"],
            "parsing_engine_mode": result["parsing_engine_mode"],
            "parser_parse_component_available": result["parser_parse_component_available"],
            "baseline_reordered": result["baseline_reordered"],
            "parsing_reordered": result["parsing_reordered"],
            "count": len(sentences),
        }
    )


@app.route("/api/history", methods=["GET"])
def api_history_list():
    actor_key = get_history_actor_key()
    limit_raw = str(request.args.get("limit", "40")).strip()
    try:
        limit = max(1, min(100, int(limit_raw)))
    except ValueError:
        limit = 40

    with _open_history_db() as conn:
        rows = conn.execute(
            """
            SELECT id, actor_key, created_at, method, input_text, baseline_text, parsing_text, baseline_score, parsing_score
            FROM run_history
            WHERE actor_key = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (actor_key, limit),
        ).fetchall()

    return json_response({"items": [serialize_history_row(r) for r in rows]})


@app.route("/api/history", methods=["POST"])
def api_history_create():
    actor_key = get_history_actor_key()
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_response({"error": "Invalid JSON body"}, 400)

    method = str(payload.get("method", "compare")).strip().lower()
    if method not in {"baseline", "parser", "compare"}:
        return json_response({"error": "Invalid method."}, 400)

    input_text = str(payload.get("input_text", "")).strip()
    if not input_text:
        return json_response({"error": "input_text is required."}, 400)

    sentences, validation_error = validate_reorder_input(input_text)
    if validation_error:
        return json_response({"error": validation_error}, 400)

    result = build_reorder_result(sentences, method)
    baseline_text = format_output(result["baseline_output"])
    parsing_text = format_output(result["parsing_output"])
    baseline_score = result["baseline_score"]
    parsing_score = result["parsing_score"]

    now_ts = int(time.time() * 1000)
    with _open_history_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO run_history (
                actor_key, created_at, method, input_text, baseline_text, parsing_text, baseline_score, parsing_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (actor_key, now_ts, method, input_text, baseline_text, parsing_text, baseline_score, parsing_score),
        )
        conn.commit()
        item_id = int(cursor.lastrowid)

        row = conn.execute(
            """
            SELECT id, actor_key, created_at, method, input_text, baseline_text, parsing_text, baseline_score, parsing_score
            FROM run_history
            WHERE id = ? AND actor_key = ?
            """,
            (item_id, actor_key),
        ).fetchone()

    return json_response({"item": serialize_history_row(row)}, 201)


@app.route("/api/history", methods=["DELETE"])
def api_history_clear():
    actor_key = get_history_actor_key()
    with _open_history_db() as conn:
        deleted = conn.execute("DELETE FROM run_history WHERE actor_key = ?", (actor_key,)).rowcount
        conn.commit()
    return json_response({"deleted": int(deleted)})


@app.route("/api/history/<int:item_id>", methods=["DELETE"])
def api_history_delete_item(item_id: int):
    actor_key = get_history_actor_key()
    with _open_history_db() as conn:
        deleted = conn.execute("DELETE FROM run_history WHERE id = ? AND actor_key = ?", (item_id, actor_key)).rowcount
        conn.commit()

    if deleted == 0:
        return json_response({"error": "History item not found"}, 404)
    return json_response({"deleted": int(deleted)})


initialize_runtime()


if __name__ == "__main__":
    debug_enabled = os.getenv("FLASK_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}
    app.run(debug=debug_enabled)










