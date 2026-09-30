from datetime import date
from typing import List, Optional

from pydantic import BaseModel, EmailStr


class VehicleIn(BaseModel):
    plate: str
    model: Optional[str] = None
    capacity: Optional[int] = None
    year: Optional[int] = None
    status: Optional[str] = "Activo"
    owner: Optional[str] = None
    driverName: Optional[str] = None
    notes: Optional[str] = None


class ContractIn(BaseModel):
    client: str
    route: Optional[str] = None
    vehicleId: Optional[str] = None
    monthlyAmount: float = 0
    billingDay: Optional[int] = None
    startDate: Optional[date] = None
    endDate: Optional[date] = None
    status: Optional[str] = "Activo"
    notes: Optional[str] = None


class TripIn(BaseModel):
    title: str
    destination: Optional[str] = None
    date: date
    vehicleId: Optional[str] = None
    amountCharged: float = 0
    client: Optional[str] = None
    notes: Optional[str] = None


class IncomeIn(BaseModel):
    date: date
    source: Optional[str] = "Otro"
    description: str
    amount: float = 0
    method: Optional[str] = None
    notes: Optional[str] = None


class ExpenseIn(BaseModel):
    date: date
    category: str
    vehicleId: Optional[str] = None
    description: str
    provider: Optional[str] = None
    amount: float = 0
    notes: Optional[str] = None


class MaintenanceIn(BaseModel):
    date: date
    vehicleId: str
    type: str
    odometer: Optional[int] = None
    cost: float = 0
    provider: Optional[str] = None
    notes: Optional[str] = None


class PaymentIn(BaseModel):
    date: date
    amount: float
    method: Optional[str] = None


class TripPaymentIn(BaseModel):
    date: date
    amount: float
    method: Optional[str] = None
    notes: Optional[str] = None


class CategoryIn(BaseModel):
    kind: str  # "expense" | "maintenance"
    name: str


class UserIn(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str = "staff"
    vehicleIds: Optional[List[str]] = None  # solo se usa si role == "limited"


class UserRoleIn(BaseModel):
    """Para cambiar el rol (y el alcance de vehículos) de un usuario ya
    existente, sin tocar su contraseña."""
    role: str
    vehicleIds: Optional[List[str]] = None