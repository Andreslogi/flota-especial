from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_current_user, get_db
from ..perms import check_vehicle_in_scope, require_write, scoped_vehicle_ids

router = APIRouter()


def ser(m: models.Maintenance) -> dict:
    return {
        "id": m.id, "date": m.date.isoformat() if m.date else None, "vehicleId": m.vehicle_id,
        "type": m.type, "odometer": m.odometer, "cost": m.cost, "provider": m.provider,
        "notes": m.notes,
    }


def kwargs(payload: schemas.MaintenanceIn) -> dict:
    return dict(
        date=payload.date, vehicle_id=payload.vehicleId, type=payload.type,
        odometer=payload.odometer, cost=payload.cost, provider=payload.provider,
        notes=payload.notes,
    )


@router.get("")
def list_maintenance(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    q = db.query(models.Maintenance)
    scope = scoped_vehicle_ids(user, db)
    if scope is not None:
        q = q.filter(models.Maintenance.vehicle_id.in_(scope))
    return [ser(m) for m in q.order_by(models.Maintenance.date.desc()).all()]


@router.post("")
def create_maintenance(payload: schemas.MaintenanceIn, db: Session = Depends(get_db), user: models.User = Depends(require_write)):
    check_vehicle_in_scope(payload.vehicleId, user, db)
    m = models.Maintenance(**kwargs(payload))
    db.add(m)
    db.commit()
    db.refresh(m)
    return ser(m)


@router.put("/{record_id}")
def update_maintenance(record_id: str, payload: schemas.MaintenanceIn, db: Session = Depends(get_db), user: models.User = Depends(require_write)):
    m = db.query(models.Maintenance).filter(models.Maintenance.id == record_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    check_vehicle_in_scope(m.vehicle_id, user, db)
    check_vehicle_in_scope(payload.vehicleId, user, db)
    for k, val in kwargs(payload).items():
        setattr(m, k, val)
    db.commit()
    db.refresh(m)
    return ser(m)


@router.delete("/{record_id}")
def delete_maintenance(record_id: str, db: Session = Depends(get_db), user: models.User = Depends(require_write)):
    m = db.query(models.Maintenance).filter(models.Maintenance.id == record_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    check_vehicle_in_scope(m.vehicle_id, user, db)
    db.delete(m)
    db.commit()
    return {"ok": True}