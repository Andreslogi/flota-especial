import os

from sqlalchemy.orm import Session

from . import models
from .security import hash_password


def seed_admin(db: Session) -> None:
    """Crea el primer usuario administrador si la tabla de usuarios está vacía.
    Toma las credenciales de las variables de entorno ADMIN_EMAIL / ADMIN_PASSWORD
    (ver .env.example)."""
    if db.query(models.User).count() > 0:
        return
    email = os.getenv("ADMIN_EMAIL", "admin@tuempresa.com")
    password = os.getenv("ADMIN_PASSWORD", "cambia-esta-clave")
    name = os.getenv("ADMIN_NAME", "Administrador")
    user = models.User(email=email, name=name, password_hash=hash_password(password), role="owner")
    db.add(user)
    db.commit()


# Mapeo puntual, una sola vez, de las 3 cuentas reales que ya existían con el
# esquema viejo (todas con role="admin") a los roles nuevos y más finos que
# pidió el dueño de la operación. Si alguno de estos correos no existe en tu
# base (por ejemplo en una instalación nueva), simplemente no hace nada.
NAMED_ROLE_ASSIGNMENTS = {
    "andreslopez010@hotmail.com": ("owner", None),
    "trsancristobal@outlook.com": ("manager", None),
    "pucheros614@hotmail.com": ("limited", ["SPQ063", "TRE695", "WHN199"]),
}


def migrate_user_roles(db: Session) -> None:
    """Lleva los roles de la versión anterior (solo "admin" / "staff") al
    esquema nuevo (owner / manager / limited / staff), UNA sola vez por
    usuario: solo toca cuentas que todavía tengan el rol legado "admin". Una
    vez que una cuenta ya tiene un rol nuevo (asignado aquí o cambiado a mano
    por el propietario desde Usuarios), esta función nunca la vuelve a tocar
    — así un cambio posterior desde la app no se revierte solo en el próximo
    arranque.

    1) Las 3 cuentas conocidas de este negocio (ver NAMED_ROLE_ASSIGNMENTS)
       quedan con el rol exacto que se pidió, y a la de alcance limitado se
       le asignan sus 3 vehículos por placa.
    2) Cualquier otro usuario legado con role="admin" pasa a "manager" por
       defecto (control total sobre los vehículos, pero sin poder gestionar
       usuarios ni tocar viajes ya ingresados) — un valor por defecto
       prudente hasta que el propietario ajuste el rol exacto desde la app.
    """
    changed = False

    for email, (role, plates) in NAMED_ROLE_ASSIGNMENTS.items():
        u = db.query(models.User).filter(models.User.email == email).first()
        if not u or u.role != "admin":
            continue  # no existe, o ya fue migrado/editado antes: no lo tocamos
        u.role = role
        if role == "limited" and plates:
            vehicles = db.query(models.Vehicle).filter(models.Vehicle.plate.in_(plates)).all()
            for v in vehicles:
                db.add(models.UserVehicleAccess(user_id=u.id, vehicle_id=v.id))
        changed = True

    # SessionLocal usa autoflush=False, así que sin este flush() la consulta
    # de abajo no vería los cambios de role recién asignados arriba (todavía
    # pendientes en memoria) y volvería a traer esas mismas 3 cuentas con
    # role=="admin", pisando el rol que se les acaba de asignar.
    if changed:
        db.flush()

    legacy_admins = db.query(models.User).filter(models.User.role == "admin").all()
    for u in legacy_admins:
        u.role = "manager"
        changed = True

    if changed:
        db.commit()


# Gastos y Mantenimiento comparten UNA sola lista de categorías (kind
# "general"), administrable desde la app. Antes eran dos listas separadas
# ("expense" / "maintenance"); UNIFIED_CATEGORIES junta lo que ya había en
# las dos más las categorías nuevas pedidas.
UNIFIED_CATEGORIES = [
    # Ya existían (categorías de Gastos)
    "ACPM", "Requintada de muelles", "Lavada", "Engrasada", "Peajes",
    "Administración", "Quincena conductor",
    # Ya existían (tipos de Mantenimiento)
    "Cambio de aceite", "Engrase general", "Requinte de muelles",
    "Cambio de llantas", "Frenos", "Batería", "Revisión técnico-mecánica",
    "Filtros", "Sistema eléctrico", "Latonería y pintura",
    "Alineación y balanceo", "Otro",
    # Nuevas
    "Parqueadero", "Alimentación", "Hotel", "Seguridad social conductor",
    "Tensionada frenos", "Tensionada clutch", "Soat", "Comisión aseo",
    "Alternador", "Arranque", "Camisa uniforme", "Pantalón uniforme",
    "Zapatillas", "Servicio eléctrico", "Hoja principal", "Hoja segunda",
    "Hoja tercera", "Diafragma", "Amortiguadores", "Gasolina",
    "Tumbada de rueda delantera izquierda", "Tumbada de rueda delantera derecha",
    "Tumbada de rueda trasera izquierda", "Tumbada de rueda trasera derecha",
    "Cardanes", "Cruceta", "Guaya", "Troque", "Implementos de aseo",
    "Estopa", "Vetun", "Crema pulidora", "Jabón", "Límpido", "Fabuloso",
    "Jabón rey liquido", "Químico baño",
]


def seed_categories(db: Session) -> None:
    """Prepara la lista compartida de categorías (kind='general') usada por
    Gastos y Mantenimiento.

    1) Si en tu base todavía existían las listas viejas y separadas
       ("expense" / "maintenance" — de una versión anterior), las junta en
       "general" sin perder ninguna que ya hubieras agregado a mano.
    2) Agrega cualquier categoría de UNIFIED_CATEGORIES que todavía no esté
       en la lista (así, cuando subamos categorías nuevas más adelante, se
       agregan solas sin duplicar ni borrar las que ya existen).
    """
    existing_names = {c.name for c in db.query(models.Category).filter(models.Category.kind == "general").all()}
    changed = False

    legacy = db.query(models.Category).filter(models.Category.kind.in_(["expense", "maintenance"])).all()
    for c in legacy:
        if c.name not in existing_names:
            db.add(models.Category(kind="general", name=c.name))
            existing_names.add(c.name)
        db.delete(c)
        changed = True

    for name in UNIFIED_CATEGORIES:
        if name not in existing_names:
            db.add(models.Category(kind="general", name=name))
            existing_names.add(name)
            changed = True

    if changed:
        db.commit()