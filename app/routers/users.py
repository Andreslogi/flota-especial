from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_db
from ..perms import require_owner
from ..security import hash_password

router = APIRouter()

VALID_ROLES = {"owner", "manager", "limited", "staff"}


def ser(u: models.User, db: Session) -> dict:
    out = {"id": u.id, "email": u.email, "name": u.name, "role": u.role}
    if u.role == "limited":
        rows = db.query(models.UserVehicleAccess).filter(models.UserVehicleAccess.user_id == u.id).all()
        out["vehicleIds"] = [r.vehicle_id for r in rows]
    else:
        out["vehicleIds"] = []
    return out


def _set_vehicle_access(user_id: str, vehicle_ids: list[str] | None, db: Session) -> None:
    db.query(models.UserVehicleAccess).filter(models.UserVehicleAccess.user_id == user_id).delete()
    for vid in (vehicle_ids or []):
        db.add(models.UserVehicleAccess(user_id=user_id, vehicle_id=vid))


@router.get("")
def list_users(db: Session = Depends(get_db), _=Depends(require_owner)):
    return [ser(u, db) for u in db.query(models.User).order_by(models.User.created_at).all()]


@router.post("")
def create_user(payload: schemas.UserIn, db: Session = Depends(get_db), _=Depends(require_owner)):
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Ese correo ya está registrado")
    role = payload.role if payload.role in VALID_ROLES else "staff"
    u = models.User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=role,
    )
    db.add(u)
    db.flush()
    if role == "limited":
        _set_vehicle_access(u.id, payload.vehicleIds, db)
    db.commit()
    db.refresh(u)
    return ser(u, db)


@router.put("/{user_id}/role")
def update_user_role(user_id: str, payload: schemas.UserRoleIn, db: Session = Depends(get_db), owner: models.User = Depends(require_owner)):
    """Cambia el rol (y, si aplica, el alcance de vehículos) de un usuario
    que ya existe. Solo el propietario puede hacerlo."""
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Rol inválido")
    if user_id == owner.id and payload.role != "owner":
        raise HTTPException(status_code=400, detail="No puedes quitarte a ti mismo el rol de propietario")
    u.role = payload.role
    _set_vehicle_access(user_id, payload.vehicleIds if payload.role == "limited" else [], db)
    db.commit()
    db.refresh(u)
    return ser(u, db)


@router.delete("/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db), owner: models.User = Depends(require_owner)):
    if user_id == owner.id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propio usuario")
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    db.query(models.UserVehicleAccess).filter(models.UserVehicleAccess.user_id == user_id).delete()
    db.delete(u)
    db.commit()
    return {"ok": True}