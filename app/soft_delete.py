"""Fshirja me mundësi anulimi.

"Fshi" vetëm shënon `deleted_at`. Rreshtat e shënuar nuk shfaqen askund, dhe
fshihen përfundimisht në kërkesën e parë të studentit pasi kalon afati.
"""

import logging
from datetime import timedelta

from sqlalchemy import event, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, with_loader_criteria

from .extensions import db
from .models import Material, Quiz, QuizAttempt, Subject, utc_now


logger = logging.getLogger(__name__)

# Sa sekonda shfaqet "Anulo".
UNDO_SECONDS = 10
# Pak kohë shtesë, që një klikim në sekondën e fundit të arrijë te serveri.
UNDO_GRACE_SECONDS = 3
INCLUDE_DELETED = "include_deleted"

_subjects = Subject.__table__
_quizzes = Quiz.__table__
# Testet e lëndëve të fshira, që edhe rezultatet e tyre të fshihen nga pamja.
_hidden_quiz_ids = (
    select(_quizzes.c.id)
    .join(_subjects, _subjects.c.id == _quizzes.c.subject_id)
    .where(_subjects.c.deleted_at.is_not(None))
)


@event.listens_for(Session, "do_orm_execute")
def hide_deleted_rows(state):
    if not state.is_select or state.is_column_load or state.session.info.get(INCLUDE_DELETED):
        return
    state.statement = state.statement.options(
        with_loader_criteria(Subject, Subject.deleted_at.is_(None), include_aliases=True),
        with_loader_criteria(Material, Material.deleted_at.is_(None), include_aliases=True),
        with_loader_criteria(
            QuizAttempt, QuizAttempt.quiz_id.not_in(_hidden_quiz_ids), include_aliases=True
        ),
    )


class including_deleted:
    """Brenda këtij blloku shihen edhe rreshtat e shënuar si të fshirë."""

    def __enter__(self):
        db.session.info[INCLUDE_DELETED] = True

    def __exit__(self, *exc_info):
        db.session.info.pop(INCLUDE_DELETED, None)


def purge_expired(user_id):
    """Fshin përfundimisht atë që studenti e ka fshirë dhe nuk e ka anuluar me kohë."""
    cutoff = utc_now() - timedelta(seconds=UNDO_SECONDS + UNDO_GRACE_SECONDS)
    with including_deleted():
        materials = (
            Material.query.join(Subject)
            .filter(Subject.user_id == user_id, Material.deleted_at < cutoff)
            .all()
        )
        subjects = Subject.query.filter(
            Subject.user_id == user_id, Subject.deleted_at < cutoff
        ).all()
        if not materials and not subjects:
            return
        for item in [*materials, *subjects]:
            db.session.delete(item)
        db.session.commit()


def deleted_subject(subject_id, user_id):
    """Lënda e fshirë që ende mund të kthehet, ose None."""
    with including_deleted():
        return Subject.query.filter(
            Subject.id == subject_id,
            Subject.user_id == user_id,
            Subject.deleted_at.is_not(None),
        ).first()


def deleted_material(material_id, user_id):
    """Materiali i fshirë që ende mund të kthehet, ose None."""
    with including_deleted():
        return (
            Material.query.join(Subject)
            .filter(
                Material.id == material_id,
                Subject.user_id == user_id,
                Subject.deleted_at.is_(None),
                Material.deleted_at.is_not(None),
            )
            .first()
        )


UPGRADE_SQL = (
    "ALTER TABLE subjects ADD COLUMN IF NOT EXISTS deleted_at timestamptz; "
    "ALTER TABLE materials ADD COLUMN IF NOT EXISTS deleted_at timestamptz;"
)


def ensure_schema() -> bool:
    """Shton kolonën `deleted_at` te databazat e krijuara para saj. Nuk ndryshon asgjë tjetër.

    Kthen False kur databaza nuk u përditësua dot.
    """
    column_type = db.DateTime(timezone=True).compile(dialect=db.engine.dialect)
    try:
        inspector = inspect(db.engine)
        for table in ("subjects", "materials"):
            if not inspector.has_table(table):
                continue
            if "deleted_at" in {column["name"] for column in inspector.get_columns(table)}:
                continue
            with db.engine.begin() as connection:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN deleted_at {column_type}"))
            logger.warning("Database updated: added column %s.deleted_at", table)
    except SQLAlchemyError as exc:
        logger.error(
            "Database could not be updated (%s). If the app's database user does not own "
            "the tables, run this once as their owner (e.g. postgres): %s",
            type(exc).__name__,
            UPGRADE_SQL,
        )
        return False
    return True
