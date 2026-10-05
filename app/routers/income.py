from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_current_user, get_db
from ..perms import require_no_limited, require_write_no_limited

router = APIRouter()


def ser(i: models.Income) -> dict:
    return {
        "id": i.id, "date": i.date.isoformat() if i.date else None, "source": i.source,
        "description": i.description, "amount": i.amount, "method": i.method,
        "contractId": i.contract_id, "tripId": i.trip_id, "notes": i.notes,
    }


@router.get("")
def list_income(db: Session = Depends(get_db), _=Depends(require_no_limited)):
    return [ser(i) for i in db.query(models.Income).order_by(models.Income.date.desc()).all()]


@router.post("")
def create_income(payload: schemas.IncomeIn, db: Session = Depends(get_db), _=Depends(require_write_no_limited)):
    i = models.Income(**payload.dict())
    db.add(i)
    db.commit()
    db.refresh(i)
    return ser(i)


@router.put("/{income_id}")
def update_income(income_id: str, payload: schemas.IncomeIn, db: Session = Depends(get_db), _=Depends(require_write_no_limited)):
    i = db.query(models.Income).filter(models.Income.id == income_id).first()
    if not i:
        raise HTTPException(status_code=404, detail="Ingreso no encontrado")
    for k, val in payload.dict().items():
        setattr(i, k, val)
    db.commit()
    db.refresh(i)
    return ser(i)


@router.delete("/{income_id}")
def delete_income(income_id: str, db: Session = Depends(get_db), _=Depends(require_write_no_limited)):
    i = db.query(models.Income).filter(models.Income.id == income_id).first()
    if not i:
        raise HTTPException(status_code=404, detail="Ingreso no encontrado")
    # Si este ingreso vino de un pago de viaje o de contrato (en vez de
    # haberse creado manualmente), hay que borrar primero ese pago — si no,
    # Postgres rechaza el borrado del ingreso porque el pago todavía lo
    # referencia (igual que al "deshacer pago" desde Viajes/Contratos).
    db.query(models.TripPayment).filter(models.TripPayment.income_id == income_id).delete()
    db.query(models.ContractPayment).filter(models.ContractPayment.income_id == income_id).delete()
    db.flush()
    db.delete(i)
    db.commit()
    return {"ok": True}