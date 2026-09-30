import uuid

from sqlalchemy import (
    Column, String, Integer, Float, Date, DateTime, ForeignKey, Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from .database import Base


def gen_id() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_id)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    # Roles:
    #  owner    -> control total; el único que puede crear/eliminar/editar usuarios.
    #  manager  -> control total sobre todos los vehículos, EXCEPTO editar/eliminar
    #              viajes ya ingresados (sí puede crear viajes nuevos).
    #  limited  -> solo puede ver y trabajar los vehículos que se le asignen en
    #              user_vehicle_access (Vehículos, Viajes, Programación, Gastos,
    #              Mantenimiento y Finanzas); no ve Contratos, Ingresos ni Usuarios.
    #  staff    -> heredado de la versión anterior: solo lectura, sin restricción
    #              de vehículo (para cuentas simples de "ver todo, no tocar nada").
    role = Column(String, nullable=False, default="owner")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserVehicleAccess(Base):
    """Para usuarios con role='limited': qué vehículos puede ver y en cuáles
    puede registrar información (viajes, gastos, mantenimiento)."""
    __tablename__ = "user_vehicle_access"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    vehicle_id = Column(String, ForeignKey("vehicles.id"), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "vehicle_id", name="uq_user_vehicle"),)


class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(String, primary_key=True, default=gen_id)
    plate = Column(String, nullable=False)
    model = Column(String)
    capacity = Column(Integer)
    year = Column(Integer)
    status = Column(String, default="Activo")
    owner = Column(String)  # propietario del vehículo (no todos son del dueño de la operación)
    driver_name = Column(String)  # conductor asignado, para liquidar su comisión
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Contract(Base):
    __tablename__ = "contracts"
    id = Column(String, primary_key=True, default=gen_id)
    client = Column(String, nullable=False)
    route = Column(String)
    vehicle_id = Column(String, ForeignKey("vehicles.id"), nullable=True)
    monthly_amount = Column(Float, nullable=False, default=0)
    billing_day = Column(Integer)
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(String, default="Activo")
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ContractPayment(Base):
    __tablename__ = "contract_payments"
    id = Column(String, primary_key=True, default=gen_id)
    contract_id = Column(String, ForeignKey("contracts.id"), nullable=False)
    month = Column(String, nullable=False)  # "YYYY-MM"
    date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)
    method = Column(String)
    income_id = Column(String, ForeignKey("income.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("contract_id", "month", name="uq_contract_month"),)


class Trip(Base):
    __tablename__ = "trips"
    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String, nullable=False)
    destination = Column(String)
    date = Column(Date, nullable=False)
    vehicle_id = Column(String, ForeignKey("vehicles.id"), nullable=True)
    passengers = Column(Integer)
    amount_charged = Column(Float, nullable=False, default=0)
    driver_commission = Column(Float, nullable=False, default=0)  # 7% de amount_charged, calculado al guardar
    client = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TripPayment(Base):
    """Pago (total o abono) recibido por un viaje de turismo. A diferencia de
    ContractPayment (uno por mes), un viaje puede tener varios abonos con
    fecha distinta hasta completar el valor cobrado."""
    __tablename__ = "trip_payments"
    id = Column(String, primary_key=True, default=gen_id)
    trip_id = Column(String, ForeignKey("trips.id"), nullable=False)
    date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)
    method = Column(String)
    notes = Column(Text)
    income_id = Column(String, ForeignKey("income.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Income(Base):
    __tablename__ = "income"
    id = Column(String, primary_key=True, default=gen_id)
    date = Column(Date, nullable=False)
    source = Column(String, default="Otro")
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False, default=0)
    method = Column(String)
    contract_id = Column(String, ForeignKey("contracts.id"), nullable=True)
    trip_id = Column(String, ForeignKey("trips.id"), nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Expense(Base):
    __tablename__ = "expenses"
    id = Column(String, primary_key=True, default=gen_id)
    date = Column(Date, nullable=False)
    category = Column(String, nullable=False)
    vehicle_id = Column(String, ForeignKey("vehicles.id"), nullable=True)
    description = Column(String, nullable=False)
    provider = Column(String)
    amount = Column(Float, nullable=False, default=0)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Category(Base):
    """Categorías de Gastos y tipos de Mantenimiento, administrables desde
    la app (en vez de quedar fijas en el código) para que un administrador
    pueda completar la lista sin necesitar un cambio de código."""
    __tablename__ = "categories"
    id = Column(String, primary_key=True, default=gen_id)
    kind = Column(String, nullable=False)  # "expense" | "maintenance"
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("kind", "name", name="uq_category_kind_name"),)


class Maintenance(Base):
    __tablename__ = "maintenance"
    id = Column(String, primary_key=True, default=gen_id)
    date = Column(Date, nullable=False)
    vehicle_id = Column(String, ForeignKey("vehicles.id"), nullable=False)
    type = Column(String, nullable=False)
    odometer = Column(Integer)
    cost = Column(Float, nullable=False, default=0)
    provider = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())