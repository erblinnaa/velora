"""Llogaritjet që shfaqin paneli dhe lista e lëndëve. Vetëm lexojnë të dhënat."""

from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Ora e Kosovës. Databaza ruan gjithçka në UTC.
TIMEZONE = ZoneInfo("Europe/Belgrade")
# Pas kaq ditësh pa test, lënda del te "Për të bërë" për përsëritje.
REVIEW_AFTER_DAYS = 14
TODO_LIMIT = 5
ACTIVITY_WEEKS = 8

WEEKDAYS = ["E hënë", "E martë", "E mërkurë", "E enjte", "E premte", "E shtunë", "E diel"]
MONTHS = [
    "janar", "shkurt", "mars", "prill", "maj", "qershor",
    "korrik", "gusht", "shtator", "tetor", "nëntor", "dhjetor",
]


def quiz_title(material_title):
    """Titulli i testit që krijohet nga një material."""
    return f"Test: {material_title}"[:180]


def local_time(value):
    """Koha në Kosovë. SQLite e kthen kohën UTC pa zonë kohore."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(TIMEZONE)


def local_date(value):
    return local_time(value).date()


def local_today():
    return datetime.now(TIMEZONE).date()


def long_date(day):
    return f"{WEEKDAYS[day.weekday()]}, {day.day} {MONTHS[day.month - 1]}"


def average_percent(attempts):
    ratios = [a.score / a.total_questions for a in attempts if a.total_questions]
    return round(sum(ratios) / len(ratios) * 100) if ratios else None


def subject_rows(subjects, attempts):
    """Një rresht për çdo lëndë. `attempts` vjen nga më e reja te më e vjetra."""
    by_subject = {}
    for attempt in attempts:
        by_subject.setdefault(attempt.quiz.subject_id, []).append(attempt)

    rows = []
    for subject in subjects:
        # Testi nuk ruan lidhje me materialin, prandaj njihet nga titulli.
        titles = {quiz.title for quiz in subject.quizzes}
        own = by_subject.get(subject.id, [])
        rows.append(
            {
                "subject": subject,
                "materials": len(subject.materials),
                "quizzes": len(subject.quizzes),
                "tested": sum(quiz_title(m.title) in titles for m in subject.materials),
                "last": own[0] if own else None,
                "average": average_percent(own),
            }
        )
    return rows


def todo_items(rows, today):
    """Së pari lëndët pa test, pastaj ato që duhen përsëritur (më e vjetra e para)."""
    untested = [
        {"kind": "create", "subject": row["subject"], "materials": row["materials"]}
        for row in rows
        if row["materials"] and not row["quizzes"]
    ]
    stale = []
    for row in rows:
        if not row["last"]:
            continue
        days = (today - local_date(row["last"].created_at)).days
        if days > REVIEW_AFTER_DAYS:
            stale.append(
                {"kind": "review", "subject": row["subject"], "days": days, "quiz_id": row["last"].quiz_id}
            )
    stale.sort(key=lambda item: item["days"], reverse=True)
    return (untested + stale)[:TODO_LIMIT]


def activity_grid(subjects, attempts, today):
    """Qelizat e 8 javëve, javë pas jave nga e hëna te e diela, javën aktuale në fund."""
    counts = Counter(local_date(m.created_at) for s in subjects for m in s.materials)
    counts.update(local_date(a.created_at) for a in attempts)

    start = today - timedelta(days=today.weekday(), weeks=ACTIVITY_WEEKS - 1)
    cells = []
    for offset in range(ACTIVITY_WEEKS * 7):
        day = start + timedelta(days=offset)
        count = counts[day] if day <= today else 0
        cells.append({"date": day, "count": count, "level": min(count, 3), "future": day > today})
    return cells
