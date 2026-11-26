import re
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)
from pypdf import PdfReader
from werkzeug.utils import secure_filename

from .ai_service import AIServiceError, generate_quiz, summarize_material
from .extensions import db
from .models import Material, Quiz, QuizAttempt, Subject, User


main_bp = Blueprint("main", __name__)

EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
# I njëjti kufi që kontrollon shërbimi AI para përpunimit.
MIN_AI_CHARS = 80


def safe_next_url(target):
    """Lejon vetëm adresa brenda aplikacionit pas hyrjes."""
    if not target or not target.startswith("/") or "\\" in target:
        return None
    if any(ord(char) < 32 for char in target):
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return None
    return target


def too_short_for_ai(content):
    return len(" ".join(content.split())) < MIN_AI_CHARS


def subject_form_errors(name):
    if not name:
        return {"name": "Emri i lëndës është i detyrueshëm."}
    if len(name) > 120:
        return {"name": "Emri mund të ketë më së shumti 120 karaktere."}
    return {}


def safe_color(value, default="#1f4d3a"):
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value or ""):
        return value
    return default


def owned_subject(subject_id):
    return Subject.query.filter_by(
        id=subject_id,
        user_id=current_user.id,
    ).first_or_404()


def owned_material(material_id):
    return (
        Material.query.join(Subject)
        .filter(
            Material.id == material_id,
            Subject.user_id == current_user.id,
        )
        .first_or_404()
    )


def owned_quiz(quiz_id):
    return (
        Quiz.query.join(Subject)
        .filter(
            Quiz.id == quiz_id,
            Subject.user_id == current_user.id,
        )
        .first_or_404()
    )


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("landing.html")


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    errors = {}

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        theme = request.form.get("theme", "light")

        if not 2 <= len(full_name) <= 120:
            errors["full_name"] = "Shkruaj emrin e plotë (2 deri në 120 karaktere)."
        if len(email) > 255 or not EMAIL_PATTERN.fullmatch(email):
            errors["email"] = "Shkruaj një adresë email-i të vlefshme."
        elif User.query.filter_by(email=email).first():
            errors["email"] = "Ky email është i regjistruar tashmë."
        if len(password) < 8:
            errors["password"] = "Fjalëkalimi duhet të ketë të paktën 8 karaktere."

        if not errors:
            user = User(
                full_name=full_name,
                email=email,
                theme=theme if theme in {"light", "dark"} else "light",
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            login_user(user)
            flash("Llogaria u krijua me sukses. Mirë se erdhe!", "success")
            return redirect(url_for("main.dashboard"))

    return render_template("auth/register.html", errors=errors)


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    errors = {}

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            errors["form"] = "Email ose fjalëkalim i pasaktë."
        else:
            login_user(user)
            return redirect(
                safe_next_url(request.args.get("next"))
                or url_for("main.dashboard")
            )

    return render_template("auth/login.html", errors=errors)


@main_bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Dole nga llogaria.", "success")
    return redirect(url_for("main.index"))


@main_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        selected_theme = request.form.get("theme", "").strip().lower()

        # Ndërruesi i temës në shirit e ruan zgjedhjen në sfond.
        in_background = request.headers.get("X-Requested-With") == "fetch"

        if selected_theme not in {"light", "dark"}:
            if in_background:
                return ("", 400)
            flash("Zgjidh një temë të vlefshme.", "danger")
            return redirect(url_for("main.settings"))

        current_user.theme = selected_theme
        db.session.commit()

        if in_background:
            return ("", 204)

        flash("Preferenca e pamjes u ruajt.", "success")
        return redirect(url_for("main.settings"))

    return render_template("settings.html")


@main_bp.get("/dashboard")
@login_required
def dashboard():
    subjects = (
        Subject.query.filter_by(user_id=current_user.id)
        .order_by(Subject.created_at.desc())
        .all()
    )

    all_attempts = (
        QuizAttempt.query.filter_by(user_id=current_user.id)
        .order_by(QuizAttempt.created_at.desc())
        .all()
    )
    ratios = [
        attempt.score / attempt.total_questions
        for attempt in all_attempts
        if attempt.total_questions
    ]

    total_materials = sum(len(subject.materials) for subject in subjects)
    total_quizzes = sum(len(subject.quizzes) for subject in subjects)

    return render_template(
        "dashboard.html",
        subjects=subjects,
        attempts=all_attempts[:5],
        attempt_count=len(all_attempts),
        average_score=round(sum(ratios) / len(ratios) * 100) if ratios else None,
        total_materials=total_materials,
        total_quizzes=total_quizzes,
    )


@main_bp.route("/subjects/new", methods=["GET", "POST"])
@login_required
def create_subject():
    errors = {}

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        color = safe_color(request.form.get("color"))
        errors = subject_form_errors(name)

        if not errors:
            subject = Subject(
                name=name,
                description=description,
                color=color,
                owner=current_user,
            )

            db.session.add(subject)
            db.session.commit()

            flash("Lënda u krijua. Tani shto materialin e parë.", "success")
            return redirect(
                url_for("main.subject_detail", subject_id=subject.id)
            )

    return render_template("subjects/form.html", subject=None, errors=errors)


@main_bp.route("/subjects/<int:subject_id>/edit", methods=["GET", "POST"])
@login_required
def edit_subject(subject_id):
    subject = owned_subject(subject_id)
    errors = {}

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        errors = subject_form_errors(name)

        if not errors:
            subject.name = name
            subject.description = request.form.get("description", "").strip()
            subject.color = safe_color(
                request.form.get("color"),
                subject.color,
            )
            db.session.commit()
            flash("Lënda u përditësua.", "success")
            return redirect(
                url_for("main.subject_detail", subject_id=subject.id)
            )

    return render_template("subjects/form.html", subject=subject, errors=errors)


@main_bp.post("/subjects/<int:subject_id>/delete")
@login_required
def delete_subject(subject_id):
    subject = owned_subject(subject_id)

    db.session.delete(subject)
    db.session.commit()

    flash("Lënda dhe të dhënat e saj u fshinë.", "success")
    return redirect(url_for("main.dashboard"))


def render_subject(subject, errors=None):
    return render_template(
        "subjects/detail.html",
        subject=subject,
        errors=errors or {},
        min_ai_chars=MIN_AI_CHARS,
    )


@main_bp.get("/subjects/<int:subject_id>")
@login_required
def subject_detail(subject_id):
    return render_subject(owned_subject(subject_id))


@main_bp.post("/subjects/<int:subject_id>/materials")
@login_required
def add_material(subject_id):
    subject = owned_subject(subject_id)
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    uploaded = request.files.get("pdf_file")
    original_filename = None
    mime_type = "text/plain"
    errors = {}

    if not title:
        errors["title"] = "Titulli i materialit është i detyrueshëm."
    elif len(title) > 180:
        errors["title"] = "Titulli mund të ketë më së shumti 180 karaktere."

    if uploaded and uploaded.filename:
        if not uploaded.filename.lower().endswith(".pdf"):
            errors["pdf_file"] = "Lejohen vetëm dokumentet PDF."
        else:
            try:
                reader = PdfReader(uploaded.stream)
                content = "\n\n".join(
                    page.extract_text() or "" for page in reader.pages
                ).strip()
            except Exception:
                errors["pdf_file"] = (
                    "PDF-ja nuk mund të lexohej. Kontrollo që dokumenti të jetë i vlefshëm."
                )
            else:
                original_filename = (
                    secure_filename(uploaded.filename) or "dokument.pdf"
                )[-255:]
                mime_type = "application/pdf"
                if not content:
                    errors["pdf_file"] = (
                        "Në këtë PDF nuk u gjet tekst. Dokumentet e skanuara nuk "
                        "mbështeten, prandaj ngjite tekstin te fusha “Teksti”."
                    )

    # PostgreSQL nuk pranon karakterin NUL, që disa PDF e përmbajnë.
    content = content.replace("\x00", "")

    if not content and "pdf_file" not in errors:
        errors["content"] = "Shto tekst ose zgjidh një PDF me përmbajtje."

    if errors:
        return render_subject(subject, errors)

    material = Material(
        subject=subject,
        title=title,
        content=content,
        original_filename=original_filename,
        mime_type=mime_type,
    )

    db.session.add(material)
    db.session.commit()

    flash("Materiali u ruajt dhe është gati për përpunim.", "success")
    return redirect(url_for("main.subject_detail", subject_id=subject.id))


@main_bp.post("/materials/<int:material_id>/delete")
@login_required
def delete_material(material_id):
    material = owned_material(material_id)
    subject_id = material.subject_id

    db.session.delete(material)
    db.session.commit()

    flash("Materiali u fshi.", "success")
    return redirect(url_for("main.subject_detail", subject_id=subject_id))


@main_bp.post("/materials/<int:material_id>/summarize")
@login_required
def summarize(material_id):
    material = owned_material(material_id)

    if too_short_for_ai(material.content):
        flash(
            f"Materiali është shumë i shkurtër. Duhen të paktën {MIN_AI_CHARS} karaktere.",
            "warning",
        )
    else:
        try:
            material.summary = summarize_material(material.content)
            db.session.commit()
            flash("Përmbledhja u krijua.", "success")
        except AIServiceError as exc:
            flash(str(exc), "danger")

    return redirect(
        url_for("main.subject_detail", subject_id=material.subject_id)
    )


@main_bp.get("/materials/<int:material_id>/summary")
@login_required
def material_summary(material_id):
    material = owned_material(material_id)

    if not material.summary:
        flash("Ky material ende nuk ka përmbledhje.", "warning")
        return redirect(
            url_for("main.subject_detail", subject_id=material.subject_id)
        )

    return render_template("subjects/summary.html", material=material)


@main_bp.post("/materials/<int:material_id>/summary/delete")
@login_required
def delete_summary(material_id):
    material = owned_material(material_id)
    subject_id = material.subject_id

    material.summary = None
    db.session.commit()

    flash(
        "Përmbledhja u fshi. Materiali origjinal u ruajt.",
        "success",
    )

    return redirect(
        url_for("main.subject_detail", subject_id=subject_id)
    )


@main_bp.post("/subjects/<int:subject_id>/quizzes")
@login_required
def create_quiz(subject_id):
    subject = owned_subject(subject_id)
    material_id = request.form.get("material_id", type=int)
    question_count = request.form.get("question_count", 5, type=int)

    material = (
        next(
            (item for item in subject.materials if item.id == material_id),
            None,
        )
        if material_id
        else None
    )

    if not material:
        flash("Zgjidh një material për krijimin e testit.", "danger")
        return redirect(
            url_for("main.subject_detail", subject_id=subject.id)
        )

    if too_short_for_ai(material.content):
        flash(
            f"Materiali është shumë i shkurtër. Duhen të paktën {MIN_AI_CHARS} karaktere.",
            "warning",
        )
        return redirect(
            url_for("main.subject_detail", subject_id=subject.id)
        )

    try:
        questions = generate_quiz(material.content, question_count)

        quiz = Quiz(
            subject=subject,
            title=f"Test: {material.title}"[:180],
            questions_json=questions,
        )

        db.session.add(quiz)
        db.session.commit()

        flash("Testi u krijua me sukses.", "success")
        return redirect(url_for("main.quiz_detail", quiz_id=quiz.id))

    except AIServiceError as exc:
        flash(str(exc), "danger")
        return redirect(
            url_for("main.subject_detail", subject_id=subject.id)
        )


@main_bp.get("/quizzes/<int:quiz_id>")
@login_required
def quiz_detail(quiz_id):
    quiz = owned_quiz(quiz_id)
    return render_template("quiz.html", quiz=quiz)


@main_bp.post("/quizzes/<int:quiz_id>/submit")
@login_required
def submit_quiz(quiz_id):
    quiz = owned_quiz(quiz_id)
    answers = {}
    score = 0

    for index, question in enumerate(quiz.questions_json):
        answer = request.form.get(f"answer_{index}", "")
        answers[str(index)] = answer

        if answer.isdecimal() and int(answer) == question.get("correct_index"):
            score += 1

    attempt = QuizAttempt(
        quiz=quiz,
        student=current_user,
        score=score,
        total_questions=len(quiz.questions_json),
        answers_json=answers,
    )

    db.session.add(attempt)
    db.session.commit()

    # Post/Redirect/Get: rifreskimi i rezultatit nuk e dërgon testin sërish.
    return redirect(
        url_for("main.attempt_detail", attempt_id=attempt.id),
        code=303,
    )


def review_answers(attempt):
    """Lidh çdo pyetje me përgjigjen e studentit dhe atë të saktë."""
    answers = attempt.answers_json or {}
    review = []

    for index, question in enumerate(attempt.quiz.questions_json):
        options = question.get("options") or []
        correct_index = question.get("correct_index")
        answer = str(answers.get(str(index), ""))
        # E njëjta rregull si te vlerësimi në submit_quiz.
        chosen_index = int(answer) if answer.isdecimal() else None

        def option_text(position):
            if isinstance(position, int) and 0 <= position < len(options):
                return options[position]
            return None

        review.append(
            {
                "question": question.get("question", ""),
                "chosen": option_text(chosen_index),
                "correct": option_text(correct_index),
                "is_correct": chosen_index is not None
                and chosen_index == correct_index,
                "explanation": question.get("explanation"),
                "source_excerpt": question.get("source_excerpt"),
            }
        )

    return review


@main_bp.get("/attempts/<int:attempt_id>")
@login_required
def attempt_detail(attempt_id):
    attempt = QuizAttempt.query.filter_by(
        id=attempt_id,
        user_id=current_user.id,
    ).first_or_404()

    return render_template(
        "result.html",
        attempt=attempt,
        review=review_answers(attempt),
    )


@main_bp.get("/history")
@login_required
def history():
    attempts = (
        QuizAttempt.query.filter_by(user_id=current_user.id)
        .order_by(QuizAttempt.created_at.desc())
        .all()
    )

    return render_template("history.html", attempts=attempts)
