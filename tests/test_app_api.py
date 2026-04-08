import shutil
from pathlib import Path
from uuid import uuid4

import pytest

import app as app_module


@pytest.fixture
def client(monkeypatch):
    workspace_tmp = Path(__file__).resolve().parents[1] / "instance" / "test-tmp"
    workspace_tmp.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp / f"tests-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    test_db = temp_dir / "history.db"
    monkeypatch.setattr(app_module, "INSTANCE_DIR", temp_dir)
    monkeypatch.setattr(app_module, "HISTORY_DB_PATH", test_db)
    app_module.init_history_db()

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_main_routes_return_ok(client):
    for path in ["/", "/reorder", "/about", "/examples", "/history", "/dataset", "/documentation", "/guide"]:
        resp = client.get(path)
        assert resp.status_code == 200


def test_reorder_api_baseline(client):
    payload = {
        "text": "Sentence one.\nSentence two.\nSentence three.",
        "method": "baseline",
    }
    resp = client.post("/api/reorder", json=payload)
    data = resp.get_json()

    assert resp.status_code == 200
    assert data["selected_method"] == "baseline"
    assert len(data["input_sentences"]) == 3
    assert len(data["baseline_output"]) == 3


def test_reorder_api_parser_fallback_if_model_missing(client, monkeypatch):
    def _raise_model_error(_sentences):
        raise RuntimeError("spaCy model missing")

    monkeypatch.setattr(app_module, "run_parsing_method", _raise_model_error)

    payload = {
        "text": "Sentence one.\nSentence two.\nSentence three.",
        "method": "parser",
    }
    resp = client.post("/api/reorder", json=payload)
    data = resp.get_json()

    assert resp.status_code == 200
    assert data["selected_method"] == "parser"
    assert data["parser_fallback"] is True
    assert data["parser_error"] == "spaCy model missing"
    assert len(data["parsing_output"]) == 3


def test_history_crud_api(client):
    create_payload = {
        "method": "baseline",
        "input_text": "A\nB\nC",
        "baseline_text": "FORGED",
        "parsing_text": "FORGED",
        "baseline_score": 999,
        "parsing_score": 999,
    }

    create_resp = client.post("/api/history", json=create_payload)
    assert create_resp.status_code == 201
    item = create_resp.get_json()["item"]
    assert item["method"] == "baseline"
    assert item["baseline_text"] != "FORGED"
    assert item["parsing_text"] != "FORGED"
    assert item["baseline_score"] != 999
    assert item["parsing_score"] != 999

    list_resp = client.get("/api/history")
    assert list_resp.status_code == 200
    items = list_resp.get_json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == item["id"]

    delete_resp = client.delete(f"/api/history/{item['id']}")
    assert delete_resp.status_code == 200

    list_after_delete = client.get("/api/history").get_json()["items"]
    assert list_after_delete == []


def test_api_auth_status_guest(client):
    resp = client.get("/api/auth/status")
    data = resp.get_json()

    assert resp.status_code == 200
    assert data["authenticated"] is False
    assert data["guest"] is True
