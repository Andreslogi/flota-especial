"""
Migración automática y liviana: agrega columnas nuevas a tablas que YA
existen en la base de datos, sin Alembic y sin borrar nada.

Por qué existe esto: `Base.metadata.create_all()` (usado en app/main.py)
solo crea tablas que no existen todavía. Si una tabla ya existe en tu
base de datos real (como pasa siempre después del primer arranque) y
luego le agregamos una columna nueva al modelo — por ejemplo
`Vehicle.owner` / `Vehicle.driver_name` o `Trip.driver_commission` —
`create_all()` NO la agrega. El resultado es que cualquier consulta a esa
tabla (por ejemplo `GET /api/vehicles`) revienta con un error de
"columna no existe", y en el frontend eso se ve como una vista que se
queda cargando para siempre y datos que "desaparecieron" (en realidad
siguen en la base, solo que la consulta nunca llega a responder).

Esta función corre en cada arranque (después de create_all) y agrega
cualquier columna que falte comparando el modelo contra la base real.
"""
from sqlalchemy import (
    Date, DateTime, Float, Integer, String, Text, inspect, text,
)
from sqlalchemy.engine import Engine


def _column_sql_type(column) -> str:
    t = column.type
    if isinstance(t, Text):
        return "TEXT"
    if isinstance(t, String):
        return "VARCHAR"
    if isinstance(t, Integer):
        return "INTEGER"
    if isinstance(t, Float):
        return "FLOAT"
    if isinstance(t, DateTime):
        return "TIMESTAMP"
    if isinstance(t, Date):
        return "DATE"
    return "TEXT"


def run_auto_migration(engine: Engine, base) -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table in base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # tabla nueva: ya la crea create_all(), nada que hacer

            existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_cols:
                    continue

                sql_type = _column_sql_type(column)
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {sql_type}"))
                print(f"[migracion] agregada columna faltante: {table.name}.{column.name} ({sql_type})")

                # Si el modelo define un valor por defecto simple (no una
                # función), rellenamos las filas existentes con ese valor
                # en vez de dejarlas en NULL (p. ej. driver_commission=0).
                default = getattr(column, "default", None)
                if default is not None and not default.is_callable and not default.is_sequence:
                    conn.execute(
                        text(f"UPDATE {table.name} SET {column.name} = :default WHERE {column.name} IS NULL"),
                        {"default": default.arg},
                    )