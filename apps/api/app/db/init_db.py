"""Create missing tables, refusing incompatible existing schemas before startup."""
from sqlalchemy import inspect
from app.db.base import Base
from app.db.session import engine


class SchemaCompatibilityError(RuntimeError):
    pass


def validate_existing_schema(bind) -> None:
    inspector = inspect(bind)
    existing = set(inspector.get_table_names())
    problems = []
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            continue
        columns = {c["name"]: c for c in inspector.get_columns(table.name)}
        for column in table.columns:
            stored = columns.get(column.name)
            if stored is None:
                problems.append(f"{table.name}.{column.name}:missing")
            elif stored["type"]._type_affinity is not column.type._type_affinity:
                problems.append(f"{table.name}.{column.name}:type")
        expected_pk = {c.name for c in table.primary_key.columns}
        actual_pk = set(inspector.get_pk_constraint(table.name).get("constrained_columns") or [])
        if expected_pk != actual_pk:
            problems.append(f"{table.name}:primary_key")
    if problems:
        # Schema identifiers only; never print database URLs or row contents.
        raise SchemaCompatibilityError(
            "Incompatible database schema; back up and run an explicit migration before startup: "
            + ", ".join(problems[:20])
        )


def init_db() -> None:
    from app.db import models  # noqa: F401
    validate_existing_schema(engine)
    Base.metadata.create_all(bind=engine)
