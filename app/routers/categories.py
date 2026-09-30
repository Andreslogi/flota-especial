from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_current_user, get_db
from ..perms import require_write_no_limited

router = APIRouter()

VALID_KINDS = {"general"}


def ser(c: models.Category) -> dict:
    return {"id": c.id, "kind": c.kind, "name": c.name}


@router.get("")
def list_categories(kind: str | None = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Cualquier usuario autenticado puede LEER la lista (la necesita para
    llenar los desplegables de Gastos/Mantenimiento); solo un admin puede
    modificarla (ver abajo)."""
    q = db.query(models.Category)
    if kind:
        q = q.filter(models.Category.kind == kind)
    return [ser(c) for c in q.order_by(models.Category.name).all()]


@router.post("")
def create_category(payload: schemas.CategoryIn, db: Session = Depends(get_db), _=Depends(require_write_no_limited)):
    if payload.kind not in VALID_KINDS:
        raise HTTPException(status_code=400, detail="kind debe ser 'general'")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")
    c = models.Category(kind=payload.kind, name=name)
    db.add(c)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Esa categoría ya existe")
    db.refresh(c)
    return ser(c)


@router.delete("/{category_id}")
def delete_category(category_id: str, db: Session = Depends(get_db), _=Depends(require_write_no_limited)):
    c = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    db.delete(c)
    db.commit()
    return {"ok": True}