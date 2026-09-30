from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import seed
from .database import Base, SessionLocal, engine
from .migrate import run_auto_migration
from .routers import auth, categories, contracts, expenses, finance, income, maintenance, trips, users, vehicles

# Crea las tablas si no existen. Para un proyecto en crecimiento, lo ideal a
# futuro es migrar a Alembic para versionar cambios de esquema; para arrancar
# y desplegar rápido en Render, esto es suficiente.
Base.metadata.create_all(bind=engine)

# create_all() de arriba NO modifica tablas que ya existían (solo crea las
# que faltan), así que cualquier columna nueva que le agreguemos a un modelo
# existente (p. ej. Vehicle.owner) necesita esto para llegar a producción
# sin perder los datos que ya había. Ver app/migrate.py para el detalle.
run_auto_migration(engine, Base)

with SessionLocal() as _db:
    seed.seed_admin(_db)
    seed.seed_categories(_db)
    seed.migrate_user_roles(_db)

app = FastAPI(title="Control de Flota API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(vehicles.router, prefix="/api/vehicles", tags=["vehicles"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
app.include_router(contracts.router, prefix="/api/contracts", tags=["contracts"])
app.include_router(trips.router, prefix="/api/trips", tags=["trips"])
app.include_router(income.router, prefix="/api/income", tags=["income"])
app.include_router(expenses.router, prefix="/api/expenses", tags=["expenses"])
app.include_router(maintenance.router, prefix="/api/maintenance", tags=["maintenance"])
app.include_router(finance.router, prefix="/api/finance", tags=["finance"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


# El frontend (HTML/CSS/JS) se sirve como archivos estáticos. Este mount va
# de último a propósito: así las rutas /api/* de arriba se resuelven primero.
app.mount("/", StaticFiles(directory="static", html=True), name="static")