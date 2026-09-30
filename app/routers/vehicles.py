from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_current_user, get_db
from ..perms import require_write_no_limited, scoped_vehicle_ids

router = APIRouter()


def ser(v: models.Vehicle) -> dict:
    return {
        "id": v.id, "plate": v.plate, "model": v.model, "capacity": v.capacity,
        "year": v.year, "status": v.status, "owner": v.owner, "driverName": v.driver_name,
        "notes": v.notes,
    }


def kwargs(payload: schemas.VehicleIn) -> dict:
    return dict(
        plate=payload.plate, model=payload.model, capacity=payload.capacity, year=payload.year,
        status=payload.status, owner=payload.owner, driver_name=payload.driverName, notes=payload.notes,
    )


@router.get("")
def list_vehicles(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    q = db.query(models.Vehicle)
    scope = scoped_vehicle_ids(user, db)
    if scope is not None:
        q = q.filter(models.Vehicle.id.in_(scope))
    return [ser(v) for v in q.order_by(models.Vehicle.plate).all()]


# Crear/editar/eliminar vehículos es un dato "maestro" de la flota: solo
# propietario y gerente lo administran (un usuario con vehículos asignados
# no puede dar de alta ni modificar vehículos, solo trabajarlos).
@router.post("")
def create_vehicle(payload: schemas.VehicleIn, db: Session = Depends(get_db), _=Depends(require_write_no_limited)):
    v = models.Vehicle(**kwargs(payload))
    db.add(v)
    db.commit()
    db.refresh(v)
    return ser(v)


@router.put("/{vehicle_id}")
def update_vehicle(vehicle_id: str, payload: schemas.VehicleIn, db: Session = Depends(get_db), _=Depends(require_write_no_limited)):
    v = db.query(models.Vehicle).filter(models.Vehicle.id == vehicle_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    for k, val in kwargs(payload).items():
        setattr(v, k, val)
    db.commit()
    db.refresh(v)
    return ser(v)


@router.delete("/{vehicle_id}")
def delete_vehicle(vehicle_id: str, db: Session = Depends(get_db), _=Depends(require_write_no_limited)):
    v = db.query(models.Vehicle).filter(models.Vehicle.id == vehicle_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    db.delete(v)
    db.commit()
    return {"ok": True}