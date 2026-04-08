import pytest

import app as app_module


@pytest.fixture(scope="module")
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/reorder",
        "/about",
        "/examples",
        "/history",
        "/dataset",
        "/documentation",
        "/guide",
    ],
)
def test_page_layout_contains_shared_shell(client, path):
    resp = client.get(path)
    assert resp.status_code == 200

    html = resp.get_data(as_text=True)
    assert '<nav class="tube-nav">' in html
    assert 'id="login-btn"' in html
    assert 'id="logout-btn"' in html
    assert '<footer class="site-footer">' in html
    assert "static/main.js" in html
    assert "static/firebase-auth.js" in html


def test_home_has_hero_and_typing_title(client):
    html = client.get("/").get_data(as_text=True)
    assert 'class="hero-wrap"' in html
    assert 'id="typing-title"' in html
    assert "static/hero.css" in html
    assert "static/hero.js" in html


def test_reorder_has_primary_controls(client):
    html = client.get("/reorder").get_data(as_text=True)
    assert 'id="reorder-form"' in html
    assert 'name="method" value="baseline"' in html
    assert 'name="method" value="parser"' in html
    assert 'name="method" value="compare"' in html
    assert 'id="load-sample"' in html
    assert 'id="history-list"' not in html


def test_history_has_history_mount_points(client):
    html = client.get("/history").get_data(as_text=True)
    assert 'id="history-list"' in html
    assert 'id="clear-history"' in html
