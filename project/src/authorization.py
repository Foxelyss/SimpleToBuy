import datetime
from typing import Annotated, Optional
from secrets import token_hex

from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from datetime import datetime, timezone
from database import SessionDep
from models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login_oauth")


async def query_user(username, session: SessionDep):
    return User(*(await session.execute(text("select * from users where email = :email"), {"email": username})).first())


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc)

    to_encode.update({"exp": expire})
    to_encode.update({"jti": token_hex(16)})

    return get_password_hash(str(to_encode))


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user = await session.execute(text(
        "select users.* from users right join sessions on users.id = sessions.user_id where sessions.token = :token"),
                                 {"token": token})

    user = user.first()
    if user is None:
        raise credentials_exception

    user = User(*user)

    return user
