from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..deps import get_current_user, get_db
from ..perms import scoped_vehicle_ids

router = APIRouter()


def _in_month(d, month: str) -> bool:
    return bool(d) and d.isoformat()[:7] == month


@router.get("/summary")
def finance_summary(month: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Indicadores básicos de rentabilidad por vehículo para el mes dado:
    ingresos (viajes + pagos de contrato), gastos, mantenimiento y utilidad
    neta. Respeta el alcance de vehículos del usuario (un 'limited' solo ve
    sus propios carros)."""
    scope = scoped_vehicle_ids(user, db)

    vehicles_q = db.query(models.Vehicle)
    if scope is not None:
        vehicles_q = vehicles_q.filter(models.Vehicle.id.in_(scope))
    vehicles = vehicles_q.order_by(models.Vehicle.plate).all()

    if not vehicles:
        return {"month": month, "vehicles": [], "totals": _empty_totals()}

    vehicle_ids = [v.id for v in vehicles]

    trips = db.query(models.Trip).filter(models.Trip.vehicle_id.in_(vehicle_ids)).all()
    expenses = db.query(models.Expense).filter(models.Expense.vehicle_id.in_(vehicle_ids)).all()
    maintenance = db.query(models.Maintenance).filter(models.Maintenance.vehicle_id.in_(vehicle_ids)).all()
    contracts = db.query(models.Contract).filter(models.Contract.vehicle_id.in_(vehicle_ids)).all()
    contract_ids_by_vehicle = {}
    for c in contracts:
        contract_ids_by_vehicle.setdefault(c.vehicle_id, []).append(c.id)
    all_contract_ids = [c.id for c in contracts]
    payments = []
    if all_contract_ids:
        payments = (
            db.query(models.ContractPayment)
            .filter(models.ContractPayment.contract_id.in_(all_contract_ids), models.ContractPayment.month == month)
            .all()
        )
    payments_by_contract = {}
    for p in payments:
        payments_by_contract.setdefault(p.contract_id, []).append(p)

    rows = []
    totals = _empty_totals()

    for v in vehicles:
        v_trips = [t for t in trips if t.vehicle_id == v.id and _in_month(t.date, month)]
        v_expenses = [e for e in expenses if e.vehicle_id == v.id and _in_month(e.date, month)]
        v_maint = [m for m in maintenance if m.vehicle_id == v.id and _in_month(m.date, month)]
        v_contract_ids = contract_ids_by_vehicle.get(v.id, [])

        trip_income = sum(t.amount_charged or 0 for t in v_trips)
        driver_commission = sum(t.driver_commission or 0 for t in v_trips)
        contract_income = sum(
            p.amount or 0 for cid in v_contract_ids for p in payments_by_contract.get(cid, [])
        )
        expense_total = sum(e.amount or 0 for e in v_expenses)
        maint_total = sum(m.cost or 0 for m in v_maint)

        income = trip_income + contract_income
        costs = expense_total + maint_total
        net = income - costs
        margin = round((net / income) * 100, 1) if income > 0 else None

        row = {
            "vehicleId": v.id, "plate": v.plate, "model": v.model,
            "tripIncome": round(trip_income, 2), "contractIncome": round(contract_income, 2),
            "income": round(income, 2), "expenses": round(expense_total, 2),
            "maintenance": round(maint_total, 2), "driverCommission": round(driver_commission, 2),
            "net": round(net, 2), "margin": margin,
            "tripCount": len(v_trips),
        }
        rows.append(row)

        totals["income"] += row["income"]
        totals["expenses"] += row["expenses"]
        totals["maintenance"] += row["maintenance"]
        totals["driverCommission"] += row["driverCommission"]
        totals["net"] += row["net"]

    totals["margin"] = round((totals["net"] / totals["income"]) * 100, 1) if totals["income"] > 0 else None
    for k in ("income", "expenses", "maintenance", "driverCommission", "net"):
        totals[k] = round(totals[k], 2)

    return {"month": month, "vehicles": rows, "totals": totals}


def _empty_totals() -> dict:
    return {"income": 0, "expenses": 0, "maintenance": 0, "driverCommission": 0, "net": 0, "margin": None}