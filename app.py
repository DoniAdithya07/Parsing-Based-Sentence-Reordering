from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from baseline import baseline_reorder
from data_loader import ensure_nltk_data, load_reuters_sentences
from parser_model import get_spacy_model, parser_reorder
from preprocess import clean_and_split_sentences, format_output

PROJECT_ROOT = Path(__file__).resolve().parent

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "replace-this-with-a-random-secret-key")
_REUTERS_CACHE: List[str] = []


def json_response(payload: Dict[str, Any], status_code: int = 200):
    response = jsonify(payload)
    response.status_code = status_code
    return response


def get_firebase_web_config() -> Dict[str, str]:
    return {
        "apiKey": os.getenv("FIREBASE_API_KEY", ""),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", ""),
        "projectId": os.getenv("FIREBASE_PROJECT_ID", ""),
        "appId": os.getenv("FIREBASE_APP_ID", ""),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", ""),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", ""),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID", ""),
    }


def firebase_web_enabled() -> bool:
    cfg = get_firebase_web_config()
    required = [cfg["apiKey"], cfg["authDomain"], cfg["projectId"], cfg["appId"]]
    return all(required)


def verify_google_id_token(id_token: str):
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


def validate_reorder_input(raw_input: str, min_sentences: int = 3, max_sentences: int = 30):
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


def to_percent(score: float | None) -> int | None:
    if score is None:
        return None
    bounded = max(0.0, min(1.0, float(score)))
    return int(round(bounded * 100))


def build_comparison_rows(baseline_output: List[str], parsing_output: List[str]):
    rows = []
    max_len = max(len(baseline_output), len(parsing_output)) if (baseline_output or parsing_output) else 0
    for idx in range(max_len):
        base_sentence = baseline_output[idx] if idx < len(baseline_output) else ""
        parse_sentence = parsing_output[idx] if idx < len(parsing_output) else ""
        same_position = base_sentence == parse_sentence and bool(base_sentence)

        rows.append(
            {
                "position": idx + 1,
                "baseline": base_sentence,
                "parsing": parse_sentence,
                "baseline_correct": same_position,
                "parsing_correct": bool(parse_sentence),
            }
        )
    return rows


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

    method = selected_method.lower().strip()
    if method == "baseline":
        baseline_output, baseline_score = run_baseline_method(sentences)
    elif method == "parser":
        parsing_output, parsing_score = run_parsing_method(sentences)
    else:
        baseline_output, baseline_score = run_baseline_method(sentences)
        parsing_output, parsing_score = run_parsing_method(sentences)
        method = "compare"

    return {
        "selected_method": method,
        "baseline_output": baseline_output,
        "parsing_output": parsing_output,
        "baseline_score": baseline_score,
        "parsing_score": parsing_score,
        "baseline_percent": to_percent(baseline_score),
        "parsing_percent": to_percent(parsing_score),
    }


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


@app.route("/login", methods=["GET", "POST"])
def login() -> Any:
    # Local username/password auth is disabled.
    return redirect(url_for("home"))


@app.route("/register", methods=["GET", "POST"])
def register() -> Any:
    # Local username/password auth is disabled.
    return redirect(url_for("home"))


@app.route("/logout")
def logout() -> Any:
    # Keep backend logout for compatibility if backend session exists.
    session.clear()
    return redirect(url_for("home"))


@app.route("/reorder", methods=["GET", "POST"])
def reorder() -> str:
    ensure_nltk_data()
    error = ""
    input_text = ""
    result = {
        "selected_method": "baseline",
        "baseline_output": [],
        "parsing_output": [],
        "baseline_score": None,
        "parsing_score": None,
        "baseline_percent": None,
        "parsing_percent": None,
    }
    comparison_rows = []
    parse_cards = []

    if request.method == "POST":
        raw_input = request.form.get("input_text", "")
        selected_method = request.form.get("method", "baseline")
        input_text = raw_input
        sentences, validation_error = validate_reorder_input(raw_input)

        if validation_error:
            error = "Please paste text with at least 3 sentences." if validation_error == "Input is empty" else validation_error
            result["selected_method"] = selected_method
        else:
            result = build_reorder_result(sentences, selected_method)
            if result["baseline_output"] and result["parsing_output"]:
                comparison_rows = build_comparison_rows(result["baseline_output"], result["parsing_output"])
            reference_for_cards = result["parsing_output"] or result["baseline_output"]
            parse_cards = extract_parse_cards(reference_for_cards)

    return render_template(
        "reorder.html",
        input_text=input_text,
        baseline_text=format_output(result["baseline_output"]),
        parsing_text=format_output(result["parsing_output"]),
        baseline_score=result["baseline_score"],
        parsing_score=result["parsing_score"],
        baseline_percent=result["baseline_percent"],
        parsing_percent=result["parsing_percent"],
        selected_method=result["selected_method"],
        comparison_rows=comparison_rows,
        parse_cards=parse_cards,
        error=error,
    )


@app.route("/history")
def history() -> str:
    return render_template("history.html")


@app.route("/about")
def about() -> str:
    return render_template("about.html")


@app.route("/examples")
def examples() -> str:
    return render_template("examples.html")


@app.route("/api/auth/google", methods=["POST"])
def auth_google():
    payload = request.get_json(silent=True) or {}
    token = str(payload.get("idToken", "")).strip()
    if not token:
        return json_response({"error": "Missing Firebase ID token"}, 400)

    decoded, err = verify_google_id_token(token)
    if err:
        return json_response({"error": err}, 401)

    email = str(decoded.get("email", ""))
    name = str(decoded.get("name", "")) or email or str(decoded.get("uid", "user"))

    session["user"] = name
    session["user_email"] = email
    session["auth_provider"] = "google"

    return json_response(
        {
            "message": "Google login successful",
            "user": {
                "name": name,
                "email": email,
                "provider": "google",
            },
        }
    )


@app.route("/api/auth/status", methods=["GET"])
def auth_status():
    if not session.get("user"):
        return json_response({"authenticated": False})
    return json_response(
        {
            "authenticated": True,
            "user": {
                "name": session.get("user", ""),
                "email": session.get("user_email", ""),
                "provider": session.get("auth_provider", "google"),
            },
        }
    )


@app.route("/api/sample", methods=["GET"])
def random_sample():
    global _REUTERS_CACHE
    try:
        if len(_REUTERS_CACHE) < 80:
            _REUTERS_CACHE = load_reuters_sentences(limit=400)
    except Exception:
        _REUTERS_CACHE = []

    if len(_REUTERS_CACHE) < 5:
        fallback = [
            "The company reported strong quarterly earnings.",
            "Investors reacted positively in the market.",
            "Shares rose by five percent after the announcement.",
            "Analysts said the guidance looked stable.",
            "Trading volume remained above the weekly average.",
        ]
        picked = random.sample(fallback, k=3)
    else:
        k = random.randint(3, 5)
        picked = random.sample(_REUTERS_CACHE, k=k)

    return json_response(
        {
            "sentences": picked,
            "text": "\n".join(picked),
            "count": len(picked),
        }
    )


@app.route("/api/reorder", methods=["POST"])
def api_reorder():
    ensure_nltk_data()

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
    return json_response(
        {
            "input_sentences": sentences,
            "selected_method": result["selected_method"],
            "baseline_output": result["baseline_output"],
            "parsing_output": result["parsing_output"],
            "baseline_text": format_output(result["baseline_output"]),
            "parsing_text": format_output(result["parsing_output"]),
            "baseline_score": result["baseline_score"],
            "parsing_score": result["parsing_score"],
            "baseline_percent": result["baseline_percent"],
            "parsing_percent": result["parsing_percent"],
            "count": len(sentences),
        }
    )


if __name__ == "__main__":
    app.run(debug=True)