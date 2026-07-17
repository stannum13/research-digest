import logging
from collections.abc import Generator

from sqlalchemy import Date, DateTime, UniqueConstraint, create_engine, inspect, literal, text
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.schema import Column

from settings import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _upgrade_sqlite_schema()


def _upgrade_sqlite_schema() -> None:
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    _add_missing_sqlite_columns(inspector, table_names)
    _create_missing_sqlite_indexes()


def _add_missing_sqlite_columns(inspector: Inspector, table_names: set[str]) -> None:
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name not in table_names:
                continue

            existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
            table_name = engine.dialect.identifier_preparer.format_table(table)
            for column in table.columns:
                if column.name in existing_columns or column.primary_key:
                    continue

                column_definition = _sqlite_add_column_definition(column)
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}"))
                _backfill_sqlite_column_default(connection, table_name, column)
                existing_columns.add(column.name)


def _sqlite_add_column_definition(column: Column) -> str:
    preparer = engine.dialect.identifier_preparer
    column_name = preparer.format_column(column)
    column_type = column.type.compile(dialect=engine.dialect)
    default_sql = _sqlite_default_sql(column)

    parts = [column_name, column_type]
    if default_sql is not None:
        parts.append(f"DEFAULT {default_sql}")
    if not column.nullable and default_sql is not None:
        parts.append("NOT NULL")
    return " ".join(parts)


def _sqlite_default_sql(column: Column) -> str | None:
    if column.server_default is not None:
        return str(column.server_default.arg.compile(dialect=engine.dialect))

    if column.default is None or not column.default.is_scalar:
        return None

    value = column.default.arg
    if value is None:
        return None
    return str(literal(value).compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True}))


def _backfill_sqlite_column_default(connection, table_name: str, column: Column) -> None:
    if column.default is None or not column.default.is_callable:
        return

    column_name = engine.dialect.identifier_preparer.format_column(column)
    if isinstance(column.type, DateTime):
        default_sql = "CURRENT_TIMESTAMP"
    elif isinstance(column.type, Date):
        default_sql = "CURRENT_DATE"
    else:
        return

    connection.execute(text(f"UPDATE {table_name} SET {column_name} = {default_sql} WHERE {column_name} IS NULL"))


def _create_missing_sqlite_indexes() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in table_names:
            continue

        for index in sorted(table.indexes, key=lambda table_index: table_index.name or ""):
            try:
                index.create(bind=engine, checkfirst=True)
            except SQLAlchemyError as exc:
                logger.warning("Could not create SQLite index %s: %s", index.name, exc)

        _create_missing_sqlite_unique_constraint_indexes(inspector, table)


def _create_missing_sqlite_unique_constraint_indexes(inspector: Inspector, table) -> None:
    existing_unique_column_sets = _sqlite_unique_column_sets(inspector, table.name)
    for constraint in table.constraints:
        if not isinstance(constraint, UniqueConstraint):
            continue

        column_names = tuple(column.name for column in constraint.columns)
        if column_names in existing_unique_column_sets:
            continue

        index_name = constraint.name or f"ux_{table.name}_{'_'.join(column_names)}"
        table_name = engine.dialect.identifier_preparer.format_table(table)
        columns_sql = ", ".join(engine.dialect.identifier_preparer.quote(column_name) for column_name in column_names)
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS "
                        f"{engine.dialect.identifier_preparer.quote(index_name)} ON {table_name} ({columns_sql})"
                    )
                )
        except SQLAlchemyError as exc:
            logger.warning("Could not create SQLite unique index %s: %s", index_name, exc)


def _sqlite_unique_column_sets(inspector: Inspector, table_name: str) -> set[tuple[str, ...]]:
    unique_column_sets: set[tuple[str, ...]] = set()
    for index in inspector.get_indexes(table_name):
        if not index.get("unique"):
            continue
        column_names = index.get("column_names")
        if column_names:
            unique_column_sets.add(tuple(column_names))

    for constraint in inspector.get_unique_constraints(table_name):
        column_names = constraint.get("column_names")
        if column_names:
            unique_column_sets.add(tuple(column_names))
    return unique_column_sets


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
