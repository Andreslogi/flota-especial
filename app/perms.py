"""
Reglas de permisos en un solo lugar, para que cada router las use igual.

Roles (ver también app/models.py):
  owner   -> control total + único que administra usuarios.
  manager -> control total sobre todos los vehículos, salvo editar/eliminar
             viajes ya ingresados.
  limited -> solo los vehículos que tenga asignados en user_vehicle_access;
             no ve Contratos, Ingresos ni Usuarios.
  staff   -> heredado: solo lectura, sin restricción de vehículo.
"""
from typing import Optional, Set

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import models
from .deps import get_current_user, get_db


def require_owner(user: models.User = Depends(get_current_user)) -> models.User:
    """Solo el propietario (Andrés) puede crear/editar/eliminar usuarios."""
    if user.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el propietario puede administrar usuarios")
    return user


def require_write(user: models.User = Depends(get_current_user)) -> models.User:
    """Cualquier rol que no sea de solo lectura (staff)."""
    if user.role == "staff":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tu cuenta es de solo lectura")
    return user


def require_no_limited(user: models.User = Depends(get_current_user)) -> models.User:
    """Para módulos que un usuario 'limited' no debe ver en absoluto
    (Contratos, Ingresos)."""
    if user.role == "limited":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a este módulo")
    if user.role == "staff":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tu cuenta es de solo lectura")
    return user


def require_write_no_limited(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role in ("limited", "staff"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a este módulo")
    return user


def scoped_vehicle_ids(user: models.User, db: Session) -> Optional[Set[str]]:
    """None = sin restricción (ve todos los vehículos). Un set = solo esos ids."""
    if user.role != "limited":
        return None
    rows = db.query(models.UserVehicleAccess).filter(models.UserVehicleAccess.user_id == user.id).all()
    return {r.vehicle_id for r in rows}


def check_vehicle_in_scope(vehicle_id: Optional[str], user: models.User, db: Session) -> None:
    """Lanza 403 si el usuario 'limited' intenta crear/editar un registro
    apuntando a un vehículo fuera de lo que tiene asignado. vehicle_id=None
    (registro sin vehículo asignado) también se rechaza para un 'limited',
    porque no tendría forma de verlo después."""
    scope = scoped_vehicle_ids(user, db)
    if scope is None:
        return
    if not vehicle_id or vehicle_id not in scope:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ese vehículo no está asignado a tu usuario")


def get_scope(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> Optional[Set[str]]:
    """Dependencia lista para inyectar directo en un endpoint GET."""
    return scoped_vehicle_ids(user, db)