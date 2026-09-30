import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# En Render, DATABASE_URL la provee automáticamente la base de datos Postgres
# que conectes al servicio. En local, si no la defines, se usa un archivo
# SQLite para poder probar la app sin instalar Postgres.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./flota.db")

# Render (y Heroku) a veces entregan la URL como "postgres://..." o
# "postgresql://...". Usamos el driver "pg8000" (100% Python, sin
# dependencias de compilador de C) en vez de psycopg2, así que reescribimos
# el prefijo para que SQLAlchemy lo use explícitamente.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+pg8000://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+pg8000://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
