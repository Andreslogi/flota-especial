"""
Herramienta de línea de comandos para arreglar accesos sin perder datos.

Se conecta a la MISMA base de datos que usa la app (lee DATABASE_URL del
.env / entorno, igual que app/database.py), así que corre esto desde la
carpeta del proyecto, con el entorno virtual activado.

Uso:
  python manage_users.py list
      Lista todos los usuarios (correo y rol), sin mostrar contraseñas.

  python manage_users.py reset-password correo@ejemplo.com "NuevaClave123"
      Cambia la contraseña de un usuario que ya existe. Todo lo demás
      (vehículos, contratos, gastos, etc.) queda intacto.

  python manage_users.py create-admin correo@ejemplo.com "Nombre Apellido" "Clave123"
      Crea un usuario administrador nuevo (por si no recuerdas NINGÚN
      usuario existente). Si el correo ya existe, se lo sube a admin y le
      cambia la contraseña en vez de duplicarlo.
"""
import sys

from app.database import SessionLocal
from app import models
from app.security import hash_password


def list_users():
    db = SessionLocal()
    try:
        users = db.query(models.User).order_by(models.User.created_at).all()
        if not users:
            print("No hay usuarios todavía.")
            return
        print(f"{'CORREO':35} {'NOMBRE':25} ROL")
        print("-" * 70)
        for u in users:
            print(f"{u.email:35} {u.name:25} {u.role}")
    finally:
        db.close()


def reset_password(email: str, new_password: str):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            print(f"No existe ningún usuario con el correo '{email}'.")
            print("Usa 'create-admin' si quieres crear uno nuevo.")
            sys.exit(1)
        user.password_hash = hash_password(new_password)
        db.commit()
        print(f"Listo. La contraseña de '{email}' (rol: {user.role}) fue actualizada.")
    finally:
        db.close()


def create_admin(email: str, name: str, password: str):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if user:
            user.role = "admin"
            user.name = name
            user.password_hash = hash_password(password)
            db.commit()
            print(f"Ya existía '{email}': lo dejé como administrador y le cambié la contraseña.")
        else:
            user = models.User(email=email, name=name, password_hash=hash_password(password), role="admin")
            db.add(user)
            db.commit()
            print(f"Usuario administrador '{email}' creado correctamente.")
    finally:
        db.close()


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd = args[0]
    if cmd == "list":
        list_users()
    elif cmd == "reset-password" and len(args) == 3:
        reset_password(args[1], args[2])
    elif cmd == "create-admin" and len(args) == 4:
        create_admin(args[1], args[2], args[3])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()