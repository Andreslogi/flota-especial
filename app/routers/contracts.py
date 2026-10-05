from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_current_user, get_db
from ..perms import require_no_limited, require_write_no_limited

router = APIRouter()


def ser_contract(c: models.Contract) -> dict:
    return {
        "id": c.id, "client": c.client, "route": c.route, "vehicleId": c.vehicle_id,
        "monthlyAmount": c.monthly_amount, "billingDay": c.billing_day,
        "startDate": c.start_date.isoformat() if c.start_date else None,
        "endDate": c.end_date.isoformat() if c.end_date else None,
        "status": c.status, "notes": c.notes,
    }


def ser_payment(p: models.ContractPayment) -> dict:
    return {
        "id": p.id, "contractId": p.contract_id, "month": p.month,
        "date": p.date.isoformat() if p.date else None, "amount": p.amount,
        "method": p.method, "incomeId": p.income_id,
    }


def contract_kwargs(payload: schemas.ContractIn) -> dict:
    return dict(
        client=payload.client, route=payload.route, vehicle_id=payload.vehicleId,
        monthly_amount=payload.monthlyAmount, billing_day=payload.billingDay,
        start_date=payload.startDate, end_date=payload.endDate,
        status=payload.status, notes=payload.notes,
    )


# IMPORTANTE: esta ruta literal debe declararse ANTES de "/{contract_id}"
# para que FastAPI no la interprete como un contract_id llamado "payments".
@router.get("/payments")
def list_payments(month: str | None = None, db: Session = Depends(get_db), _=Depends(require_no_limited)):
    q = db.query(models.ContractPayment)
    if month:
        q = q.filter(models.ContractPayment.month == month)
    return [ser_payment(p) for p in q.all()]


@router.get("")
def list_contracts(db: Session = Depends(get_db), _=Depends(require_no_limited)):
    return [ser_contract(c) for c in db.query(models.Contract).order_by(models.Contract.client).all()]


@router.post("")
def create_contract(payload: schemas.ContractIn, db: Session = Depends(get_db), _=Depends(require_write_no_limited)):
    c = models.Contract(**contract_kwargs(payload))
    db.add(c)
    db.commit()
    db.refresh(c)
    return ser_contract(c)


@router.put("/{contract_id}")
def update_contract(contract_id: str, payload: schemas.ContractIn, db: Session = Depends(get_db), _=Depends(require_write_no_limited)):
    c = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    for k, val in contract_kwargs(payload).items():
        setattr(c, k, val)
    db.commit()
    db.refresh(c)
    return ser_contract(c)


@router.delete("/{contract_id}")
def delete_contract(contract_id: str, db: Session = Depends(get_db), _=Depends(require_write_no_limited)):
    c = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    # Se eliminan los registros de pago asociados (pero se conservan los ingresos
    # ya generados, como respaldo histórico de la plata que sí entró).
    db.query(models.ContractPayment).filter(models.ContractPayment.contract_id == contract_id).delete()
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.post("/{contract_id}/pay")
def pay_contract(
    contract_id: str, month: str, payload: schemas.PaymentIn,
    db: Session = Depends(get_db), _=Depends(require_write_no_limited),
):
    """Registra el pago de un contrato para el mes indicado (?month=YYYY-MM):
    crea el ingreso vinculado y marca ese mes como pagado."""
    contract = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    existing = db.query(models.ContractPayment).filter(
        models.ContractPayment.contract_id == contract_id, models.ContractPayment.month == month,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ese contrato ya está marcado como pagado ese mes")

    description = f"Contrato — {contract.client}"
    if contract.route:
        description += f" · {contract.route}"
    description += f" ({month})"

    income = models.Income(
        date=payload.date, source="Contrato", description=description,
        amount=payload.amount, method=payload.method, contract_id=contract.id,
        notes="Generado automáticamente desde el módulo de Contratos.",
    )
    db.add(income)
    db.flush()  # asigna income.id sin cerrar la transacción

    payment = models.ContractPayment(
        contract_id=contract_id, month=month, date=payload.date,
        amount=payload.amount, method=payload.method, income_id=income.id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return ser_payment(payment)


@router.delete("/{contract_id}/pay")
def undo_payment(contract_id: str, month: str, db: Session = Depends(get_db), _=Depends(require_write_no_limited)):
    """Revierte el pago de un contrato en un mes: borra el registro de pago
    y el ingreso que había generado."""
    payment = db.query(models.ContractPayment).filter(
        models.ContractPayment.contract_id == contract_id, models.ContractPayment.month == month,
    ).first()
    if not payment:
        raise HTTPException(status_code=404, detail="No hay un pago registrado ese mes")
    # Primero el pago (que es quien referencia al ingreso) y luego el
    # ingreso: al revés, Postgres rechaza el borrado del ingreso porque el
    # pago todavía le apunta (violación de llave foránea).
    income_id = payment.income_id
    db.delete(payment)
    db.flush()
    if income_id:
        income = db.query(models.Income).filter(models.Income.id == income_id).first()
        if income:
            db.delete(income)
    db.commit()
    return {"ok": True}