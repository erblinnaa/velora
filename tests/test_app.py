import pytest

from app import create_app
from app.extensions import db
from app.models import Quiz


@pytest.fixture()
def app(tmp_path):
    application = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "UPLOAD_FOLDER": str(tmp_path), "SECRET_KEY": "test-secret", "AI_PROVIDER": "ollama", "AI_TIMEOUT_SECONDS": 1, "OLLAMA_TIMEOUT_SECONDS": 1})
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email="student@example.com"):
    return client.post("/register", data={"full_name": "Student Test", "email": email, "password": "strong-pass-123"}, follow_redirects=True)


def test_register_and_login(client):
    response = register(client)
    assert response.status_code == 200
    assert b"<h1>Paneli</h1>" in response.data
    client.post("/logout")
    response = client.post("/login", data={"email": "student@example.com", "password": "strong-pass-123"}, follow_redirects=True)
    assert b"<h1>Paneli</h1>" in response.data


def test_subject_and_material_flow(client):
    register(client)
    response = client.post("/subjects/new", data={"name": "Programim", "description": "Python dhe web", "color": "#6c63ff"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Programim" in response.data
    from app.models import Subject
    subject = Subject.query.first()
    response = client.post(f"/subjects/{subject.id}/materials", data={"title": "Hyrje", "content": "Flask eshte nje framework web ne Python."}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Hyrje" in response.data


def test_quiz_is_scored_and_saved(client):
    register(client)
    client.post("/subjects/new", data={"name": "Algoritme", "description": "", "color": "#6c63ff"})
    from app.models import Subject
    subject = Subject.query.first()
    quiz = Quiz(subject=subject, title="Test prove", questions_json=[{"question": "2 + 2?", "options": ["3", "4", "5", "6"], "correct_index": 1}, {"question": "Gjuha?", "options": ["Python", "HTML", "CSS", "SQL"], "correct_index": 0, "explanation": "Flask shkruhet në Python.", "source_excerpt": "Flask është framework në Python."}])
    db.session.add(quiz)
    db.session.commit()
    response = client.post(f"/quizzes/{quiz.id}/submit", data={"answer_0": "1", "answer_1": "3"})
    assert len(quiz.attempts) == 1
    attempt = quiz.attempts[0]
    assert attempt.score == 1
    assert response.status_code == 303
    assert response.headers["Location"].endswith(f"/attempts/{attempt.id}")

    # Rifreskimi i faqes së rezultatit nuk ruan përpjekje të re.
    for _ in range(2):
        result = client.get(response.headers["Location"])
        assert result.status_code == 200
    assert len(quiz.attempts) == 1

    page = result.get_data(as_text=True)
    assert "50%" in page
    assert page.count("review-item is-correct") == 1
    assert page.count("review-item is-wrong") == 1
    for text in ("SQL", "Python", "Flask shkruhet në Python.", "Flask është framework në Python."):
        assert text in page


def test_result_is_private_to_its_student(client):
    register(client)
    client.post("/subjects/new", data={"name": "Algoritme", "description": ""})
    from app.models import Subject
    quiz = Quiz(subject=Subject.query.first(), title="Test prove", questions_json=[{"question": "2 + 2?", "options": ["3", "4", "5", "6"], "correct_index": 1}])
    db.session.add(quiz)
    db.session.commit()
    # Pa përgjigje: shënohet si e tillë, jo si e saktë.
    location = client.post(f"/quizzes/{quiz.id}/submit", data={}).headers["Location"]
    assert "Pa përgjigje" in client.get(location).get_data(as_text=True)

    client.post("/logout")
    register(client, email="tjeter@example.com")
    assert client.get(location).status_code == 404


def test_local_ai_unavailable_is_reported_without_fallback(client):
    register(client)
    client.post("/subjects/new", data={"name": "AI", "description": "", "color": "#6c63ff"})
    from app.models import Subject
    subject = Subject.query.first()
    content = "Ky është një material studimi mjaftueshëm i gjatë për të testuar lidhjen me shërbimin lokal të inteligjencës artificiale në Velora."
    client.post(f"/subjects/{subject.id}/materials", data={"title": "Material", "content": content})
    material = subject.materials[0]
    response = client.post(f"/materials/{material.id}/summarize", follow_redirects=True)
    assert "Shërbimi lokal AI".encode("utf-8") in response.data
    assert material.summary is None
