import re
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app import create_app
from app.extensions import db
from app.models import Material, Quiz, QuizAttempt, Subject, User
from app.overview import activity_grid, local_time, local_today, subject_rows, todo_items

EMPTY_TODO = "Je në rregull. Asgjë për sot."


@pytest.fixture()
def app(tmp_path):
    application = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "UPLOAD_FOLDER": str(tmp_path), "SECRET_KEY": "test-secret"})
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def sign_up(client, email="student@example.com"):
    client.post("/register", data={"full_name": "Student Test", "email": email, "password": "strong-pass-123"})
    return User.query.filter_by(email=email).one()


def days_ago(days):
    return datetime.now(timezone.utc) - timedelta(days=days)


def add_subject(user, name, materials=0):
    subject = Subject(owner=user, name=name)
    for number in range(materials):
        subject.materials.append(Material(title=f"Ligjërata {number + 1}", content="Tekst"))
    db.session.add(subject)
    db.session.commit()
    return subject


def add_quiz(subject, title="Test: Ligjërata 1", attempts=()):
    """`attempts` është listë me çifte (pikët nga 10, para sa ditësh)."""
    student = subject.owner
    quiz = Quiz(subject=subject, title=title, questions_json=[])
    for score, age in attempts:
        quiz.attempts.append(QuizAttempt(student=student, score=score, total_questions=10, answers_json={}, created_at=days_ago(age)))
    db.session.add(quiz)
    db.session.commit()
    return quiz


def page(client, url="/dashboard"):
    response = client.get(url)
    assert response.status_code == 200
    return response.get_data(as_text=True)


def todo_box(html):
    return html.split('id="todo-title"')[1].split("</section>")[0]


def test_dashboard_without_subjects(client):
    sign_up(client)
    html = page(client)
    assert "Ende nuk ke asnjë lëndë." in html
    assert "Ende nuk ke zgjidhur asnjë test." in html
    assert EMPTY_TODO in todo_box(html)
    assert "ende pa teste" in html
    assert "lëndë pa test" not in html
    assert 'class="grid-table' not in html


def test_dashboard_with_subjects_and_attempts(client):
    user = sign_up(client)
    tested = add_subject(user, "Algoritme", materials=2)
    quiz = add_quiz(tested, attempts=[(4, 3), (10, 0)])
    add_subject(user, "Biologji", materials=1)
    html = page(client)

    assert "ke 1 lëndë pa test" in html
    assert "1 nga 2" in html and "0 nga 1" in html
    assert "2 materiale · 1 test" in html
    # Etiketa e lëndës tregon përpjekjen e fundit, mesatarja i merr të dyja.
    assert '<span class="tag tag-ok">100%</span>' in html
    assert '<span class="tag tag-warn">Pa test</span>' in html
    assert '<dd class="stat-value">70%</dd>' in html
    for attempt in quiz.attempts:
        assert f'href="/attempts/{attempt.id}"' in html
    # Sot: tri materiale dhe një test.
    assert f"{local_today():%d.%m}: 4 veprime" in html


@pytest.mark.parametrize("score, note, good", [(9, "shkëlqyeshëm", True), (8, "mirë", False)])
def test_average_note(client, score, note, good):
    subject = add_subject(sign_up(client), "Algoritme", materials=1)
    add_quiz(subject, attempts=[(score, 0)])
    html = page(client)
    assert note in html
    assert ('class="stat-note good"' in html) is good


def test_todo_lists_untested_and_stale_subjects(client):
    user = sign_up(client)
    untested = add_subject(user, "Pa asnjë test", materials=2)
    add_subject(user, "Bosh")
    old_quiz = add_quiz(add_subject(user, "E vjetër", materials=1), attempts=[(5, 20)])
    add_quiz(add_subject(user, "E freskët", materials=1), attempts=[(5, 30), (5, 2)])
    box = todo_box(page(client))

    assert "Krijo test për Pa asnjë test" in box
    assert "2 materiale pa test" in box
    assert f'href="/subjects/{untested.id}#krijo-test"' in box
    assert "Përsërit E vjetër" in box
    assert "Testi i fundit para 20 ditësh" in box
    assert f'href="/quizzes/{old_quiz.id}"' in box
    assert "Bosh" not in box
    assert "E freskët" not in box
    assert EMPTY_TODO not in box


def test_todo_shows_at_most_five_items(client):
    user = sign_up(client)
    for number in range(7):
        add_subject(user, f"Lënda {number}", materials=1)
    assert todo_box(page(client)).count("Krijo testin →") == 5


def test_todo_ignores_other_students(client):
    add_subject(sign_up(client), "E huaj", materials=1)
    client.post("/logout")
    sign_up(client, "tjeter@example.com")
    html = page(client)
    assert "E huaj" not in html
    assert EMPTY_TODO in todo_box(html)


def fake_row(name, materials=1, quizzes=1, tested_on=None):
    last = SimpleNamespace(created_at=tested_on, quiz_id=1) if tested_on else None
    return {"subject": SimpleNamespace(name=name), "materials": materials, "quizzes": quizzes, "last": last}


def test_review_starts_after_fourteen_days_and_oldest_comes_first():
    today = date(2026, 11, 26)
    noon = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)
    rows = [fake_row(f"{age} ditë", tested_on=noon - timedelta(days=age)) for age in (14, 15, 40)]
    rows.append(fake_row("e re", quizzes=0))
    items = todo_items(rows, today)
    assert [item["subject"].name for item in items] == ["e re", "40 ditë", "15 ditë"]


def test_material_counts_as_tested_by_quiz_title(app):
    user = User(full_name="Student Test", email="a@example.com", password_hash="x")
    subject = add_subject(user, "Algoritme", materials=3)
    add_quiz(subject, "Test: Ligjërata 2")
    add_quiz(subject, "Test: Ligjërata 2")
    assert subject_rows([subject], [])[0]["tested"] == 1


def test_activity_covers_eight_weeks_ending_this_week():
    today = date(2026, 11, 26)  # e enjte
    attempts = [SimpleNamespace(created_at=datetime(2026, 11, 26, 12, tzinfo=timezone.utc))] * 5
    cells = activity_grid([], attempts, today)
    assert len(cells) == 56
    assert cells[0]["date"] == date(2026, 10, 5) and cells[-1]["date"] == date(2026, 11, 29)
    current = next(cell for cell in cells if cell["date"] == today)
    assert (current["count"], current["level"]) == (5, 3)
    assert [cell["future"] for cell in cells[-4:]] == [False, True, True, True]


def test_subject_list_page(client):
    sign_up(client)
    assert "Ende nuk ke asnjë lëndë." in page(client, "/subjects")
    add_subject(User.query.one(), "Algoritme", materials=1)
    html = page(client, "/subjects")
    assert "Algoritme" in html and "0 nga 1" in html


def test_subject_list_requires_login(client):
    response = client.get("/subjects")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_phone_navigation_is_on_inner_pages(client):
    sign_up(client)
    html = page(client, "/settings")
    assert 'class="bottom-nav"' in html and 'class="topbar"' in html
    assert ">ST</a>" in html
    # Në telefon dalja nga llogaria gjendet te Cilësimet.
    assert 'class="phone-only sign-out"' in html


def stat_notes(html):
    return re.findall(r'class="stat-note[^"]*" title="([^"]*)"', html)


def test_each_stat_has_its_own_note(client):
    user = sign_up(client)
    assert stat_notes(page(client)) == ["asnjë ende", "asnjë ende", "asnjë ende", "ende pa teste"]

    big = add_subject(user, "Algoritme", materials=3)
    add_subject(user, "Biologji", materials=1)
    assert stat_notes(page(client))[:3] == ["2 pa test", "shumica te Algoritme", "asnjë ende"]

    add_quiz(big, attempts=[(10, 3)])
    day = local_today() - timedelta(days=3)
    assert stat_notes(page(client)) == ["1 pa test", "shumica te Algoritme", f"i fundit më {day:%d.%m}", "shkëlqyeshëm"]


def test_stat_note_when_every_subject_has_a_test(client):
    add_quiz(add_subject(sign_up(client), "Algoritme", materials=1))
    assert stat_notes(page(client))[0] == "të gjitha me test"


@pytest.mark.parametrize("stored, shown", [
    (datetime(2026, 1, 15, 23, 30), "16.01.2026 00:30"),  # dimër: UTC+1
    (datetime(2026, 7, 15, 22, 30, tzinfo=timezone.utc), "16.07.2026 00:30"),  # verë: UTC+2
])
def test_utc_is_shown_as_kosovo_time(stored, shown):
    assert local_time(stored).strftime("%d.%m.%Y %H:%M") == shown


def test_pages_show_kosovo_time(client):
    subject = add_subject(sign_up(client), "Algoritme", materials=1)
    moment = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)
    subject.materials[0].created_at = moment
    quiz = add_quiz(subject, attempts=[(5, 0)])
    quiz.created_at = moment
    attempt = quiz.attempts[0]
    attempt.created_at = moment
    db.session.commit()

    for url in ("/history", f"/attempts/{attempt.id}"):
        assert "16.01.2026 00:30" in page(client, url)
    assert "16.01.2026" in page(client)
    detail = page(client, f"/subjects/{subject.id}")
    assert detail.count("16.01.2026") == 3 and "15.01.2026" not in detail
