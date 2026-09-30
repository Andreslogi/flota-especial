#!/usr/bin/env python3
"""
Migra los datos de tu base local (SQLite, flota.db) a la base de datos de
producción en Render (PostgreSQL), para no perder nada de lo que ya
registraste en pruebas (usuarios, vehículos, contratos, viajes, etc.).

USO (desde tu computador, parado en la carpeta flota-app, con el entorno
virtual activado -- el mismo donde corre tu app en local):

    python scripts/migrate_sqlite_to_render.py "postgresql://usuario:clave@host/basedatos"

El argumento es la "External Database URL" que te da Render en el panel de
tu base de datos (dashboard de la base -> pestaña "Connect" -> "External
Database URL"). Tiene que ser la EXTERNA, no la "Internal" (esa solo
funciona desde dentro de la red de Render).

Corre ESTE script después de que el servicio web ya haya arrancado al
menos una vez en Render (así ya existe el usuario administrador que
creaste con ADMIN_EMAIL/ADMIN_PASSWORD). Es seguro: a ese usuario le
actualiza la clave para que quede la que usas en local (así no tienes que
memorizar dos claves distintas), y no duplica nada si lo vuelves a correr.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import models

SQLITE_PATH = Path(__file__).resolve().parent.parent / "flota.db"


def make_engine(url: str):
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+pg8000://", 1)
    elif url.startswith("postgresql://") and "+pg8000" not in url:
        url = url.replace("postgresql://", "postgresql+pg8000://", 1)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


def copy_users(src, dst):
    """Los usuarios se emparejan por correo (no por id): un despliegue nuevo
    en Render ya trae creado el usuario de ADMIN_EMAIL con otra contraseña,
    así que a ese lo actualizamos en vez de duplicarlo, y devolvemos el mapa
    de "id local -> id real en producción" para que las demás tablas que
    apunten a un usuario (como el acceso por vehículo) usen el id correcto."""
    id_remap = {}
    copied, updated = 0, 0
    for row in src.query(models.User).all():
        existing = dst.query(models.User).filter(models.User.email == row.email).first()
        if existing:
            existing.name = row.name
            existing.password_hash = row.password_hash
            existing.role = row.role
            id_remap[row.id] = existing.id
            updated += 1
        else:
            new_user = models.User(
                id=row.id, email=row.email, name=row.name,
                password_hash=row.password_hash, role=row.role,
            )
            dst.add(new_user)
            id_remap[row.id] = row.id
            copied += 1
    dst.commit()
    print(f"  users: {copied} nuevo(s), {updated} actualizado(s) (contraseña/rol igualados a tu base local).")
    return id_remap


def copy_categories(src, dst):
    existing_keys = {(c.kind, c.name) for c in dst.query(models.Category).all()}
    copied = 0
    for row in src.query(models.Category).all():
        if (row.kind, row.name) in existing_keys:
            continue
        dst.add(models.Category(id=row.id, kind=row.kind, name=row.name))
        existing_keys.add((row.kind, row.name))
        copied += 1
    dst.commit()
    print(f"  categories: {copied} nueva(s) (las que ya coincidían en nombre se omitieron).")


def copy_by_id(src, dst, Model, extra_field_map=None):
    """Copia genérica para tablas que nunca se auto-siembran: si el id ya
    existe en destino (por ejemplo por una corrida anterior de este mismo
    script), se omite esa fila."""
    name = Model.__tablename__
    existing_ids = {r.id for r in dst.query(Model.id).all()}
    rows = src.query(Model).all()
    copied = 0
    for row in rows:
        if row.id in existing_ids:
            continue
        data = {c.name: getattr(row, c.name) for c in Model.__table__.columns}
        if extra_field_map:
            for field, remap in extra_field_map.items():
                if data.get(field) is not None:
                    data[field] = remap.get(data[field], data[field])
        dst.add(Model(**data))
        copied += 1
    if copied:
        dst.commit()
    print(f"  {name}: {copied} registro(s) copiados." if rows else f"  {name}: sin datos en origen.")


def copy_user_vehicle_access(src, dst, user_id_remap):
    existing_pairs = {(r.user_id, r.vehicle_id) for r in dst.query(models.UserVehicleAccess).all()}
    copied = 0
    for row in src.query(models.UserVehicleAccess).all():
        target_user_id = user_id_remap.get(row.user_id, row.user_id)
        pair = (target_user_id, row.vehicle_id)
        if pair in existing_pairs:
            continue
        dst.add(models.UserVehicleAccess(user_id=target_user_id, vehicle_id=row.vehicle_id))
        existing_pairs.add(pair)
        copied += 1
    if copied:
        dst.commit()
    print(f"  user_vehicle_access: {copied} registro(s) copiados.")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    target_url = sys.argv[1]

    if not SQLITE_PATH.exists():
        print(f"No encuentro {SQLITE_PATH}.")
        print("Corre este script desde la carpeta flota-app, en el mismo computador")
        print("donde has estado probando la app (ahí es donde vive tu flota.db real).")
        sys.exit(1)

    print(f"Origen (local):   {SQLITE_PATH}")
    print(f"Destino (Render): {target_url.split('@')[-1] if '@' in target_url else target_url}")
    print()

    source_engine = make_engine(f"sqlite:///{SQLITE_PATH}")
    target_engine = make_engine(target_url)

    try:
        target_engine.connect().close()
    except Exception as e:
        print(f"No pude conectarme a la base de destino: {e}")
        print("Revisa que copiaste la 'External Database URL' completa desde Render.")
        sys.exit(1)

    # Por si acaso este script corre antes de que la app haya creado las
    # tablas en Render (normalmente ya existen; esto no hace daño si ya están).
    Base.metadata.create_all(bind=target_engine)

    SourceSession = sessionmaker(bind=source_engine)
    TargetSession = sessionmaker(bind=target_engine)
    src = SourceSession()
    dst = TargetSession()

    try:
        user_id_remap = copy_users(src, dst)
        copy_by_id(src, dst, models.Vehicle)
        copy_user_vehicle_access(src, dst, user_id_remap)
        copy_categories(src, dst)
        copy_by_id(src, dst, models.Contract)
        copy_by_id(src, dst, models.Trip)
        copy_by_id(src, dst, models.Income)
        copy_by_id(src, dst, models.ContractPayment)
        copy_by_id(src, dst, models.TripPayment)
        copy_by_id(src, dst, models.Expense)
        copy_by_id(src, dst, models.Maintenance)
    finally:
        src.close()
        dst.close()

    print("\nListo. Ya puedes entrar a tu app en Render con las mismas cuentas y")
    print("contraseñas que usabas en local.")


if __name__ == "__main__":
    main()