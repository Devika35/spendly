import pytest

import database.db as db
from app import app as flask_app


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    """Point every get_db() call at a fresh, seeded temp database."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()


@pytest.fixture
def app():
    """Used by pytest-flask to provide the `client` fixture."""
    # CSRF is off so tests can post forms directly; CSRF tests switch it back on
    flask_app.config.update(TESTING=True, CSRF_ENABLED=False)
    return flask_app


@pytest.fixture
def demo_user_id():
    return db.get_user_by_email("demo@spendly.com")["id"]


@pytest.fixture
def empty_user_id():
    """A registered user with no expenses."""
    return db.create_user("Asha Verma", "asha@example.com", "password123")


@pytest.fixture
def login(client):
    """Call login(user_id) to put that user in the test client's session."""
    def _login(user_id):
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
    return _login
