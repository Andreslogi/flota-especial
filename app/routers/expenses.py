from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_current_user, get_db
from ..perms import check_vehicle_in_scope, require_write, scoped_vehicle_ids

router = APIRouter()


def ser(e: models.Expense) -> dict:
    return {
        "id": e.id, "date": e.date.isoformat() if e.date else None, "category": e.category,
        "vehicleId": e.vehicle_id, "description": e.description, "provider": e.provider,
        "amount": e.amount, "notes": e.notes,
    }


def kwargs(payload: schemas.ExpenseIn) -> dict:
    return dict(
        date=payload.date, category=payload.category, vehicle_id=payload.vehicleId,
        description=payload.description, provider=payload.provider, amount=payload.amount,
        notes=payload.notes,
    )


@router.get("")
def list_expenses(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    q = db.query(models.Expense)
    scope = scoped_vehicle_ids(user, db)
    if scope is not None:
        q = q.filter(models.Expense.vehicle_id.in_(scope))
    return [ser(e) for e in q.order_by(models.Expense.date.desc()).all()]


@router.post("")
def create_expense(payload: schemas.ExpenseIn, db: Session = Depends(get_db), user: models.User = Depends(require_write)):
    check_vehicle_in_scope(payload.vehicleId, user, db)
    e = models.Expense(**kwargs(payload))
    db.add(e)
    db.commit()
    db.refresh(e)
    return ser(e)


@router.put("/{expense_id}")
def update_expense(expense_id: str, payload: schemas.ExpenseIn, db: Session = Depends(get_db), user: models.User = Depends(require_write)):
    e = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    check_vehicle_in_scope(e.vehicle_id, user, db)
    check_vehicle_in_scope(payload.vehicleId, user, db)
    for k, val in kwargs(payload).items():
        setattr(e, k, val)
    db.commit()
    db.refresh(e)
    return ser(e)


@router.delete("/{expense_id}")
def delete_expense(expense_id: str, db: Session = Depends(get_db), user: models.User = Depends(require_write)):
    e = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    check_vehicle_in_scope(e.vehicle_id, user, db)
    db.delete(e)
    db.commit()
    return {"ok": True}