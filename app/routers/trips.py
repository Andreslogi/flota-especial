from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_current_user, get_db
from ..perms import check_vehicle_in_scope, require_write, scoped_vehicle_ids

router = APIRouter()

# Porcentaje del valor del viaje que corresponde al conductor. Se calcula y
# se guarda en el momento de crear/editar el viaje, para que quede fijo en
# el histórico aunque el porcentaje cambie más adelante.
DRIVER_COMMISSION_RATE = 0.07


def ser(t: models.Trip) -> dict:
    return {
        "id": t.id, "title": t.title, "destination": t.destination,
        "date": t.date.isoformat() if t.date else None,
        "vehicleId": t.vehicle_id,
        "amountCharged": t.amount_charged, "driverCommission": t.driver_commission,
        "client": t.client, "notes": t.notes,
    }


def kwargs(payload: schemas.TripIn) -> dict:
    return dict(
        title=payload.title, destination=payload.destination, date=payload.date,
        vehicle_id=payload.vehicleId,
        amount_charged=payload.amountCharged,
        driver_commission=round((payload.amountCharged or 0) * DRIVER_COMMISSION_RATE, 2),
        client=payload.client, notes=payload.notes,
    )


def ser_payment(p: models.TripPayment) -> dict:
    return {
        "id": p.id, "tripId": p.trip_id, "date": p.date.isoformat() if p.date else None,
        "amount": p.amount, "method": p.method, "notes": p.notes, "incomeId": p.income_id,
    }


def require_trip_edit(user: models.User = Depends(get_current_user)) -> models.User:
    """Solo el propietario (y un 'limited' dentro de su alcance) puede editar
    o eliminar un viaje ya ingresado. 'manager' puede crear viajes nuevos,
    pero no tocar los que ya existen."""
    if user.role == "manager":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes editar ni eliminar viajes ya ingresados")
    if user.role == "staff":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tu cuenta es de solo lectura")
    return user


# IMPORTANTE: esta ruta literal debe declararse ANTES de "/{trip_id}"
# para que FastAPI no la interprete como un trip_id llamado "payments".
@router.get("/payments")
def list_trip_payments(tripId: str | None = None, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    q = db.query(models.TripPayment)
    if tripId:
        q = q.filter(models.TripPayment.trip_id == tripId)
    scope = scoped_vehicle_ids(user, db)
    if scope is not None:
        q = q.join(models.Trip, models.Trip.id == models.TripPayment.trip_id).filter(models.Trip.vehicle_id.in_(scope))
    return [ser_payment(p) for p in q.order_by(models.TripPayment.date).all()]


@router.get("")
def list_trips(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    q = db.query(models.Trip)
    scope = scoped_vehicle_ids(user, db)
    if scope is not None:
        q = q.filter(models.Trip.vehicle_id.in_(scope))
    return [ser(t) for t in q.order_by(models.Trip.date.desc()).all()]


@router.post("")
def create_trip(payload: schemas.TripIn, db: Session = Depends(get_db), user: models.User = Depends(require_write)):
    check_vehicle_in_scope(payload.vehicleId, user, db)
    t = models.Trip(**kwargs(payload))
    db.add(t)
    db.commit()
    db.refresh(t)
    return ser(t)


@router.put("/{trip_id}")
def update_trip(trip_id: str, payload: schemas.TripIn, db: Session = Depends(get_db), user: models.User = Depends(require_trip_edit)):
    t = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    check_vehicle_in_scope(t.vehicle_id, user, db)
    check_vehicle_in_scope(payload.vehicleId, user, db)
    for k, val in kwargs(payload).items():
        setattr(t, k, val)
    db.commit()
    db.refresh(t)
    return ser(t)


@router.delete("/{trip_id}")
def delete_trip(trip_id: str, db: Session = Depends(get_db), user: models.User = Depends(require_trip_edit)):
    t = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    check_vehicle_in_scope(t.vehicle_id, user, db)
    # Se eliminan los abonos/pagos asociados (pero se conservan los ingresos
    # ya generados, como respaldo histórico de la plata que sí entró).
    db.query(models.TripPayment).filter(models.TripPayment.trip_id == trip_id).delete()
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.post("/{trip_id}/pay")
def pay_trip(trip_id: str, payload: schemas.TripPaymentIn, db: Session = Depends(get_db), user: models.User = Depends(require_write)):
    """Registra un pago total o un abono para un viaje: crea el ingreso
    vinculado y el registro del pago/abono con su fecha."""
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Viaje no encontrado")
    check_vehicle_in_scope(trip.vehicle_id, user, db)
    if payload.amount is None or payload.amount <= 0:
        raise HTTPException(status_code=400, detail="El monto del pago debe ser mayor a cero")

    description = f"Viaje — {trip.title}"
    if trip.client:
        description += f" · {trip.client}"

    income = models.Income(
        date=payload.date, source="Viaje de turismo", description=description,
        amount=payload.amount, method=payload.method, trip_id=trip.id,
        notes=payload.notes or "Generado automáticamente desde el módulo de Viajes.",
    )
    db.add(income)
    db.flush()  # asigna income.id sin cerrar la transacción

    payment = models.TripPayment(
        trip_id=trip_id, date=payload.date, amount=payload.amount,
        method=payload.method, notes=payload.notes, income_id=income.id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return ser_payment(payment)


@router.delete("/payments/{payment_id}")
def undo_trip_payment(payment_id: str, db: Session = Depends(get_db), user: models.User = Depends(require_write)):
    """Revierte un pago/abono de un viaje: borra el registro del pago y el
    ingreso que había generado."""
    payment = db.query(models.TripPayment).filter(models.TripPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    trip = db.query(models.Trip).filter(models.Trip.id == payment.trip_id).first()
    if trip:
        check_vehicle_in_scope(trip.vehicle_id, user, db)
    # Primero el pago (que es quien referencia al ingreso) y luego el
    # ingreso: al revés, Postgres rechaza el borrado del ingreso porque el
    # pago todavía le apunta (violación de llave foránea) — SQLite no es
    # tan estricto con esto, por eso el error solo aparecía en producción.
    income_id = payment.income_id
    db.delete(payment)
    db.flush()
    if income_id:
        income = db.query(models.Income).filter(models.Income.id == income_id).first()
        if income:
            db.delete(income)
    db.commit()
    return {"ok": True}