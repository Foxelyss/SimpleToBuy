import asyncio
import datetime
from typing import Annotated, Optional

import jwt
from jwt import InvalidTokenError
from typing_extensions import NamedTuple

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import create_engine, select
from passlib.context import CryptContext
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import text
from hashlib import sha256
from fastapi_login import LoginManager
from fastapi_login.exceptions import InvalidCredentialsException
from datetime import datetime
from datetime import datetime, timedelta, timezone
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost/simpletobuy"

engine = create_async_engine(DATABASE_URL, echo=True)
Base = declarative_base()
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session

async def create_db_and_tables():
    await init_models()


SessionDep = Annotated[AsyncSession, Depends(get_session)]

SECRET = "super-secret-key"
manager = LoginManager(SECRET, "/login")
app = FastAPI()

@app.on_event("startup")
async def on_startup():
    await init_models()

# Status: 403
# Content-Type: application/json
# Body:
# {
# “message”: “Login failed”
# }
# При попытке доступа авторизованным пользователем к функциям
# недоступным для своей группы во всех запросах необходимо возвращать
# JSON, пример ответа:
# Status: 403
# Content-Type: application/json
# Body:
# {
# “message”: “Forbidden for you”
# }
# При попытке получить несуществующий ресурс необходимо возвращать
# JSON, пример ответа:
# Status: 404
# Content-Type: application/json
# Body:
# {
# "message": "Not found"
# }
# В случае ошибок связанных с валидацией данных во всех запросах
# необходимо возвращать JSON, пример ответа:
# Status: 422
# Content-Type: application/json Body:
# {
# “message”: “Validation error”,
# “field_1”: “Validation error”,
# ...
# }
class User(NamedTuple):
    id:int
    email:str
    name:str
    surname:str
    middle_name:str
    password_hash:str
    creation_date:datetime
    avatar:str
    is_admin:bool
class UserAuthorization(BaseModel):
    email: str
    password: str

class UserSignup(BaseModel):
    email: str
    password: str
    fio: str

class Product(BaseModel):
    id: int
    name: str
    description: str
    price: float
    category: str

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None

class Profile(BaseModel):
    id: int
    email: str
    fio: str
    avatar: str

class ProfileUpdate(BaseModel):
    email: Optional[str] = None
    fio: Optional[str] = None
    avatar: Optional[str] = None

SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 300

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def query_user(username, session: SessionDep):
    return User(*(await session.execute(text("select * from users where email = :email"), {"email": username})).first())


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user = await session.execute(text("select users.* from users right join sessions on users.id = sessions.user_id where sessions.token = :token"), {"token": token})

    user = user.first()
    if user is None:
        raise credentials_exception

    user = User(*user)

    return user


# Module 1

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

@manager.user_loader()
async def load(username):
    async with  async_session() as db:
        return await query_user(username=username,session=db)


@app.post("/login")
async def login(new_user: UserAuthorization, session: SessionDep):
    user = await query_user(new_user.email,session)

    if not user or not verify_password(new_user.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # token = session.execute(text("insert into sessions (user_id) values (:user_id) returning token"), {"user_id": user.id})

    access_token = create_access_token(data={"sub": user.id})

    await session.execute(text("insert into sessions (user_id, token) values (:user_id, :token) returning token"), {"user_id": user.id, "token": access_token})
    await session.commit()
    return {"message": "Logged in successfully","access_token": access_token}

@app.post("/logout")
async def logout(token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep):
    await session.execute(text("delete from sessions where token = :token"), {"token": token})
    await session.commit()
    return {"message": "Logged out successfully"}

@app.post("/signup")
async def register(new_user: UserSignup, session: SessionDep):
    try:
        user = text("insert into users (name,surname,middle_name, email, password_hash) values (:name, :surname,:middle_name, :email, :password)")
        hashed_password = get_password_hash(new_user.password)
        fio = new_user.fio.split()

        name = fio[0]
        surname = fio[1]

        if len(fio) > 2:
            middle_name = fio[2]
        else:
            middle_name = None

        await session.execute(user, {"name": name,"surname": surname,"middle_name": middle_name, "email": new_user.email, "password": hashed_password})
        await session.commit()

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    user = await query_user(new_user.email,session)

    access_token = create_access_token(data={"sub": user.id})

    await session.execute(text("insert into sessions (user_id, token) values (:user_id, :token) returning token"), {"user_id": user.id, "token": access_token})
    await session.commit()

    return {"message": "Registered successfully", "token": access_token}

@app.get("/profile")
def get_profile(user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    return user._asdict()

@app.get("/products")
async def get_products(session: SessionDep):
    products =(await session.execute(text("select * from products"))).all()
    return [product._asdict() for product in products]


# Module 2


@app.post("/cart/{product_id}")
async def add_to_cart(product_id: int, user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    try:
        await session.execute(text("insert into cart (user_id, product_id) values (:user_id, :product_id)"), {"user_id": user.id, "product_id": product_id})
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Added to cart successfully"}


@app.delete("/cart/{id}")
async def remove_from_cart(id: int, user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    try:
        await session.execute(text("delete from cart where user_id = :user_id and id = :id"), {"user_id": user.id, "id": id})
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Removed from cart successfully"}


@app.get("/cart")
async def get_cart(user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    try:
        cart_items = (await session.execute(text("select * from cart where user_id = :user_id"), {"user_id": user.id})).all()
        return [item._asdict() for item in cart_items]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/order")
async def place_order(user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    try:
        await session.execute(text("insert into orders (user_id) values (:user_id)"), {"user_id": user.id})
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Order placed successfully"}

@app.patch("/profile")
async def update_profile(profile: ProfileUpdate, user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    try:
        if profile.email:
            await session.execute(text("update users set email = :email where id = :id"), {"email": profile.email, "id": user.id})
        if profile.fio:
            fio = profile.fio.split()

            name = fio[0]
            surname = fio[1]

            if len(fio) > 2:
                middle_name = fio[2]
            else:
                middle_name = None


            await session.execute(text("update users set name = :name, surname = :surname, middle_name = :middle_name where id = :id"), {"name": name, "surname": surname, "middle_name": middle_name, "id": user.id})
        if profile.avatar:
            await session.execute(text("update users set avatar = :avatar where id = :id"), {"avatar": profile.avatar, "id": user.id})
        await session.commit()

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": "Profile updated successfully"}

@app.get("/order")
async def get_order_history(user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    try:
        order_history = (await session.execute(text("select * from orders where user_id = :user_id"), {"user_id": user.id})).all()
        return order_history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Module 3

@app.post("/product")
async def create_product(product: Product, user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        product_id = (await session.execute(text("insert into products (name, price, user_id) values (:name, :price, :user_id) returning id"), {"name": product.name, "price": product.price, "user_id": user.id})).scalar()
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Product created successfully","id": product_id}


@app.delete("/product/{id}")
async def delete_product(product_id: int, user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        await session.execute(text("delete from products where id = :id"), {"id": product_id})
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Product deleted successfully"}

@app.patch("/product/{id}")
async def update_product(product_id: int, product: Product, user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        if product.name is not None:
            await session.execute(text("update products set name = :name where id = :id"), {"name": product.name, "id": product_id})
        if product.description is not None:
            await session.execute(text("update products set description = :description where id = :id"), {"description": product.description, "id": product_id})
        if product.price is not None:
            await session.execute(text("update products set price = :price where id = :id"), {"price": product.price, "id": product_id})

        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    product_data = await session.execute(text("select * from products where id = :id"), {"id": product_id})
    product_data = product_data.first()
    return Product(**product_data._asdict())
