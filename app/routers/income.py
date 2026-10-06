from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_current_user, get_db
from ..perms import check_vehicle_in_scope, require_write, scoped_vehicle_ids

router = APIRouter()


def ser(i: models.Income) -> dict:
    return {
        "id": i.id, "date": i.date.isoformat() if i.date else None, "source": i.source,
        "description": i.description, "amount": i.amount, "method": i.method,
        "contractId": i.contract_id, "tripId": i.trip_id, "vehicleId": i.vehicle_id,
        "notes": i.notes,
    }


def kwargs(payload: schemas.IncomeIn) -> dict:
    """Mapea los campos camelCase del esquema a las columnas snake_case del
    modelo. Un ingreso registrado a mano desde este endpoint no se vincula a
    ningún viaje/contrato (eso solo lo hacen pay_trip/pay_contract), así que
    aquí solo se traduce lo que IncomeIn sí trae."""
    return dict(
        date=payload.date, source=payload.source, description=payload.description,
        amount=payload.amount, method=payload.method, notes=payload.notes,
        vehicle_id=payload.vehicleId,
    )


def _scope_filter(scope, db: Session):
    """Un ingreso cae dentro del alcance de un usuario 'limited' si su
    vehicle_id está entre los suyos, o si viene de un viaje/contrato de uno
    de esos vehículos (para ingresos antiguos, creados antes de que
    existiera la columna vehicle_id en Ingresos)."""
    trip_ids = [t.id for t in db.query(models.Trip.id).filter(models.Trip.vehicle_id.in_(scope)).all()]
    contract_ids = [c.id for c in db.query(models.Contract.id).filter(models.Contract.vehicle_id.in_(scope)).all()]
    return or_(
        models.Income.vehicle_id.in_(scope),
        models.Income.trip_id.in_(trip_ids),
        models.Income.contract_id.in_(contract_ids),
    )


def _income_in_scope(income: models.Income, user: models.User, db: Session) -> bool:
    scope = scoped_vehicle_ids(user, db)
    if scope is None:
        return True
    if income.vehicle_id and income.vehicle_id in scope:
        return True
    if income.trip_id:
        trip = db.query(models.Trip).filter(models.Trip.id == income.trip_id).first()
        if trip and trip.vehicle_id in scope:
            return True
    if income.contract_id:
        contract = db.query(models.Contract).filter(models.Contract.id == income.contract_id).first()
        if contract and contract.vehicle_id in scope:
            return True
    return False


@router.get("")
def list_income(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    q = db.query(models.Income)
    scope = scoped_vehicle_ids(user, db)
    if scope is not None:
        q = q.filter(_scope_filter(scope, db))
    return [ser(i) for i in q.order_by(models.Income.date.desc()).all()]


@router.post("")
def create_income(payload: schemas.IncomeIn, db: Session = Depends(get_db), user: models.User = Depends(require_write)):
    check_vehicle_in_scope(payload.vehicleId, user, db)
    i = models.Income(**kwargs(payload))
    db.add(i)
    db.commit()
    db.refresh(i)
    return ser(i)


@router.put("/{income_id}")
def update_income(income_id: str, payload: schemas.IncomeIn, db: Session = Depends(get_db), user: models.User = Depends(require_write)):
    i = db.query(models.Income).filter(models.Income.id == income_id).first()
    if not i:
        raise HTTPException(status_code=404, detail="Ingreso no encontrado")
    if not _income_in_scope(i, user, db):
        raise HTTPException(status_code=403, detail="Ese ingreso no está dentro de tu alcance")
    check_vehicle_in_scope(payload.vehicleId, user, db)
    for k, val in kwargs(payload).items():
        setattr(i, k, val)
    db.commit()
    db.refresh(i)
    return ser(i)


@router.delete("/{income_id}")
def delete_income(income_id: str, db: Session = Depends(get_db), user: models.User = Depends(require_write)):
    i = db.query(models.Income).filter(models.Income.id == income_id).first()
    if not i:
        raise HTTPException(status_code=404, detail="Ingreso no encontrado")
    if not _income_in_scope(i, user, db):
        raise HTTPException(status_code=403, detail="Ese ingreso no está dentro de tu alcance")
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