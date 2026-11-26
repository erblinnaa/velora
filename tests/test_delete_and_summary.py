from datetime import timedelta

import pytest
from sqlalchemy import inspect, text

from app import create_app
from app.ai.service import AIService
from app.extensions import db
from app.models import Material, Quiz, QuizAttempt, Subject, User, utc_now
from app.soft_delete import ensure_schema, including_deleted
from app.summary_format import parse_summary

CONFIG = {"TESTING": True, "WTF_CSRF_ENABLED": False, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "SECRET_KEY": "test-secret"}
JAVA = "public class A {\n    private int x;\n}"


@pytest.fixture()
def app(tmp_path):
    # Pa kontekst të hapur gjatë testit: çdo kërkesë ka sesionin e vet, si në server.
    application = create_app({**CONFIG, "UPLOAD_FOLDER": str(tmp_path)})
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def data(app, client):
    """Një student me një lëndë, një material, një test dhe një rezultat."""
    client.post("/register", data={"full_name": "Student Test", "email": "s@example.com", "password": "strong-pass-123"})
    with app.app_context():
        student = User.query.one()
        subject = Subject(owner=student, name="Algoritme")
        material = Material(subject=subject, title="Ligjërata e parë", content="Tekst")
        quiz = Quiz(subject=subject, title="Test: Ligjërata e parë", questions_json=[])
        attempt = QuizAttempt(quiz=quiz, student=student, score=1, total_questions=2, answers_json={})
        db.session.add_all([subject, material, quiz, attempt])
        db.session.commit()
        return {"subject": subject.id, "material": material.id, "quiz": quiz.id, "attempt": attempt.id}


def page(client, url):
    response = client.get(url)
    assert response.status_code == 200
    return response.get_data(as_text=True)


def delete(client, kind, ids):
    response = client.post(f"/{kind}s/{ids[kind]}/delete", follow_redirects=True)
    assert response.status_code == 200
    return response.get_data(as_text=True)


def restore(client, kind, ids):
    return client.post(f"/{kind}s/{ids[kind]}/restore", follow_redirects=True).get_data(as_text=True)


def stored(app, model, row_id):
    """Rreshti siç është në databazë, edhe kur është shënuar si i fshirë."""
    with app.app_context(), including_deleted():
        return db.session.get(model, row_id)


def age(app, model, row_id, seconds):
    with app.app_context(), including_deleted():
        db.session.get(model, row_id).deleted_at = utc_now() - timedelta(seconds=seconds)
        db.session.commit()


def test_deleted_material_is_hidden_but_can_be_restored(app, client, data):
    html = delete(client, "material", data)
    assert "Materiali u fshi." in html and ">Anulo</button>" in html
    assert f'action="/materials/{data["material"]}/restore"' in html
    assert 'data-expires="10"' in html
    assert "Asnjë material ende." in html
    assert '<dd class="stat-value">0</dd>' in page(client, "/dashboard")
    assert client.post(f"/materials/{data['material']}/summarize").status_code == 404
    assert stored(app, Material, data["material"]).deleted_at is not None

    assert "Materiali u kthye." in restore(client, "material", data)
    assert "Ligjërata e parë" in page(client, f"/subjects/{data['subject']}")


def test_deleted_subject_hides_its_tests_and_results_until_restored(client, data):
    html = delete(client, "subject", data)
    assert "Lënda u fshi." in html and ">Anulo</button>" in html
    for url in (f"/subjects/{data['subject']}", f"/quizzes/{data['quiz']}", f"/attempts/{data['attempt']}"):
        assert client.get(url).status_code == 404
    assert "Algoritme" not in page(client, "/dashboard")
    assert "Ende nuk ke përfunduar asnjë test" in page(client, "/history")

    assert "Lënda u kthye." in restore(client, "subject", data)
    assert "Test: Ligjërata e parë" in page(client, "/history")


@pytest.mark.parametrize("kind, model", [("material", Material), ("subject", Subject)])
def test_undo_expires_and_the_next_request_removes_the_row(app, client, data, kind, model):
    delete(client, kind, data)
    age(app, model, data[kind], 8)
    page(client, "/dashboard")
    assert stored(app, model, data[kind]) is not None

    age(app, model, data[kind], 60)
    assert "Koha për anulim ka kaluar." in restore(client, kind, data)
    assert stored(app, model, data[kind]) is None


def test_purging_a_subject_removes_everything_in_it(app, client, data):
    delete(client, "material", data)
    delete(client, "subject", data)
    age(app, Subject, data["subject"], 60)
    page(client, "/dashboard")
    for model, key in ((Subject, "subject"), (Material, "material"), (Quiz, "quiz"), (QuizAttempt, "attempt")):
        assert stored(app, model, data[key]) is None


def test_another_student_cannot_restore_or_purge(app, client, data):
    delete(client, "material", data)
    client.post("/logout")
    client.post("/register", data={"full_name": "Tjetri", "email": "t@example.com", "password": "strong-pass-123"})
    assert "Koha për anulim ka kaluar." in restore(client, "material", data)
    assert stored(app, Material, data["material"]).deleted_at is not None


def test_restore_needs_the_csrf_token(app, client, data):
    delete(client, "material", data)
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post(f"/materials/{data['material']}/restore").status_code == 400
    assert stored(app, Material, data["material"]).deleted_at is not None


def test_old_database_gets_the_new_column_without_losing_rows(app, client, data):
    with app.app_context():
        for table in ("subjects", "materials"):
            db.session.execute(text(f"ALTER TABLE {table} DROP COLUMN deleted_at"))
        db.session.commit()
        assert ensure_schema() and ensure_schema()
        for table in ("subjects", "materials"):
            assert "deleted_at" in {column["name"] for column in inspect(db.engine).get_columns(table)}
    assert "Ligjërata e parë" in page(client, f"/subjects/{data['subject']}")


def summary_with(examples):
    return AIService._format_summary({
        "title": "Titulli", "introduction": "Hyrja.", "key_points": ["Pika\ndy rreshta", "b", "c"],
        "concepts": ["x", "y", "z"], "examples": examples, "source_excerpts": ["Prova"],
    })


@pytest.mark.parametrize("example", [JAVA, f"```java\n{JAVA}\n```"])
def test_code_example_keeps_its_lines(example):
    blocks = parse_summary(summary_with([example, "Shembull me fjalë."]))
    assert ("code", JAVA) in blocks
    assert ("list", ["Shembull me fjalë."]) in blocks
    assert ("list", ["Pika dy rreshta", "b", "c"]) in blocks
    assert blocks[0] == ("title", "Titulli") and ("heading", "Shembuj praktikë") in blocks


def test_code_with_blank_lines_stays_in_one_block():
    code = "def f():\n    x = 1\n\n    return x"
    assert ("code", code) in parse_summary(summary_with([f"```python\n{code}\n```"]))


def test_old_summary_with_code_on_one_line_is_shown_as_code():
    old = 'Titulli\n\nShembuj praktikë:\n- public class A { int x; }\n- Një shembull; me fjalë.\n\nPërfundim:\nFund.'
    blocks = parse_summary(old)
    assert ("code", "public class A { int x; }") in blocks
    assert ("list", ["Një shembull; me fjalë."]) in blocks


def test_summary_page_shows_code_block_and_escapes_it(app, client, data):
    with app.app_context():
        db.session.get(Material, data["material"]).summary = summary_with(["```\nif (a < b) {\n    run();\n}\n```"])
        db.session.commit()
    html = page(client, f"/materials/{data['material']}/summary")
    assert "<pre tabindex=\"0\"><code>if (a &lt; b) {\n    run();\n}</code></pre>" in html
