from datetime import datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Usuario

settings = get_settings()
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
ALGO = "HS256"


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode()[:72], h.encode())
    except ValueError:
        return False


def create_token(user: Usuario) -> str:
    exp = datetime.utcnow() + timedelta(minutes=settings.TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user.id), "exp": exp}, settings.SECRET_KEY, algorithm=ALGO)


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> Usuario:
    err = HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas")
    try:
        uid = int(jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGO])["sub"])
    except (JWTError, KeyError, ValueError):
        raise err
    user = db.get(Usuario, uid)
    if not user or not user.activo:
        raise err
    return user


def require_roles(*roles: str):
    def dep(user: Usuario = Depends(current_user)) -> Usuario:
        if user.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permisos insuficientes")
        return user
    return dep
