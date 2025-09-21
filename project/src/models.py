from typing import Annotated, Optional
from typing_extensions import NamedTuple
from pydantic import BaseModel
from datetime import datetime


class User(NamedTuple):
    id: int
    name: str
    surname: str
    middle_name: str
    email: str
    password_hash: str
    creation_date: datetime
    avatar: str = ""
    is_admin: bool = False


class UserAuthorization(BaseModel):
    email: str
    password: str


class UserSignup(BaseModel):
    email: str
    password: str
    fio: str


class Product(BaseModel):
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    price: float = 0.0


class Profile(BaseModel):
    id: Optional[int] = None
    email: str = ""
    fio: str = ""
    avatar: str = ""
    password: Optional[str] = None


class ProfileUpdate(BaseModel):
    email: Optional[str] = None
    fio: Optional[str] = None
    password: Optional[str] = None
    avatar: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
