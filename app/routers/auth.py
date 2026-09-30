from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import models
from ..deps import get_current_user, get_db
from ..security import create_access_token, verify_password

router = APIRouter()


def ser_user(u: models.User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role}


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Correo o contraseña incorrectos")
    token = create_access_token({"sub": user.id})
    return {"access_token": token, "token_type": "bearer", "user": ser_user(user)}


@router.get("/me")
def me(user: models.User = Depends(get_current_user)):
    return ser_user(user)
