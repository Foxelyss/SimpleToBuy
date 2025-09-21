import re
import math
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import text
from models import *
from database import get_session, init_models, engine, SessionDep
from authorization import oauth2_scheme, get_current_user, query_user, verify_password, get_password_hash, create_access_token
from fastapi.responses import JSONResponse
app = FastAPI()


@app.on_event("startup")
async def on_startup():
    await init_models()


@app.on_event("shutdown")
async def on_shutdown():
    await engine.dispose()

forbidden = JSONResponse(status_code=403, content={"message": "Forbidden for you"})

def generate_validation_error_for_fields(*fields: str):
    details = {"message": "Validation error",}

    for field in fields:
        details[field] = "Validation error"

    return JSONResponse(status_code=422, content=details)

def validate_email(email: str | None):
    if email is None or re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email) is None:
        return False

    return True

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/login_oauth")
async def login_oauth(new_user: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep):
    user = await query_user(new_user.username, session)

    if not user or not verify_password(new_user.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Login failed")

    access_token = create_access_token(data={"sub": user.id})

    await session.execute(text("insert into sessions (user_id, token) values (:user_id, :token) returning token"), {"user_id": user.id, "token": access_token})
    await session.commit()
    return {"message": "Logged in successfully", "access_token": access_token}


# Module 1


@app.post("/login")
async def login(new_user: UserAuthorization, session: SessionDep):
    user = await query_user(new_user.email, session)

    if not user or not verify_password(new_user.password, user.password_hash):
        return JSONResponse(status_code=401, content={"password": "Login failed"})

    access_token = create_access_token(data={"sub": user.id})

    await session.execute(text("insert into sessions (user_id, token) values (:user_id, :token) returning token"), {"user_id": user.id, "token": access_token})
    await session.commit()
    return {"message": "Logged in successfully", "user_token": access_token}


@app.post("/logout")
async def logout(token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep):
    await session.execute(text("delete from sessions where token = :token"), {"token": token})
    await session.commit()
    return {"message": "Logged out successfully"}


@app.post("/signup")
async def register(new_user: UserSignup, session: SessionDep):
    try:
        if not validate_email(new_user.email):
            return generate_validation_error_for_fields("email")

        if new_user.password == "":
            return generate_validation_error_for_fields("password")

        fio = new_user.fio.split()
        if len(fio) < 2 or len(fio) > 3:
            return generate_validation_error_for_fields("fio")

        hashed_password = get_password_hash(new_user.password)

        name = fio[0]
        surname = fio[1]

        if len(fio) > 2:
            middle_name = fio[2]
        else:
            middle_name = None

        insert_user = text("insert into users (name,surname,middle_name, email, password_hash) values (:name, :surname,:middle_name, :email, :password) returning id")
        id = await session.execute(insert_user, {"name": name, "surname": surname, "middle_name": middle_name, "email": new_user.email, "password": hashed_password})
        await session.commit()

        user_id = id.scalar_one()

        access_token = create_access_token(data={"sub": user_id})

        await session.execute(text("insert into sessions (user_id, token) values (:user_id, :token) returning token"), {"user_id": user_id, "token": access_token})
        await session.commit()

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


    return {"message": "Registered successfully", "user_token": access_token}


@app.get("/profile")
def get_profile(user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    return {"user": {"id": user.id, "fio": user.name + " " + user.surname + (" " +user.middle_name if user.middle_name is not None else ""), "avatar": user.avatar, "email": user.email}}


@app.get("/products")
async def get_products(session: SessionDep):
    products = (await session.execute(text("select * from products"))).all()
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


@app.delete("/cart/{cart_id}")
async def remove_from_cart(cart_id: int, user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    try:
        rows_affected = await session.execute(text("delete from cart where user_id = :user_id and id = :id"), {"user_id": user.id, "id": cart_id})
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    if rows_affected.rowcount == 0:
        raise HTTPException(status_code=404, detail="Cart item not found")

    return {"message": "Removed from cart successfully"}


@app.get("/cart")
async def get_cart(user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    try:
        cart_items = (await session.execute(text("select cart.id, cart.product_id, products.name, products.description, products.price from cart inner join products on cart.product_id = products.id where cart.user_id = :user_id"), {"user_id": user.id})).all()
        return [item._asdict() for item in cart_items]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/order")
async def place_order(user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    try:
        cart_items_quantity = (await session.execute(text("select count(product_id) as quantity from cart where user_id = :user_id"), {"user_id": user.id})).scalar()

        if cart_items_quantity <= 0:
            return JSONResponse(status_code=400, content={"message": "Cart is empty"})

        order_id = await session.execute(text("insert into orders (user_id, order_price) values (:user_id, (select sum(price) from cart inner join products on cart.product_id = products.id where cart.user_id = :user_id)) returning id"), {"user_id": user.id})
        order_id = order_id.scalar_one()
        await session.commit()

        await session.execute(text("insert into order_items (order_id, product_id) select :order_id, product_id from cart where user_id = :user_id"),{"order_id": order_id, "user_id": user.id})
        await session.execute(text("delete from cart where user_id = :user_id"), {"user_id": user.id})

        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Order placed successfully"}


@app.patch("/profile")
async def update_profile(profile: ProfileUpdate, user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    try:
        if profile.avatar is None and profile.email is None and profile.password is None and profile.fio is None:
            return JSONResponse(status_code=400, content={"message": "No input provided"})

        if profile.email is not None and not validate_email(profile.email):
            return generate_validation_error_for_fields("email")

        if profile.password is not None and profile.password == "":
            return generate_validation_error_for_fields("password")

        if profile.email is not None:
            await session.execute(text("update users set email = :email where id = :id"), {"email": profile.email, "id": user.id})

        if profile.fio is not None:
            fio = profile.fio.split()

            if len(fio) < 2 or len(fio) > 3:
                return generate_validation_error_for_fields("fio")

            name = fio[0]
            surname = fio[1]

            if len(fio) > 2:
                middle_name = fio[2]
            else:
                middle_name = None

            await session.execute(text("update users set name = :name, surname = :surname, middle_name = :middle_name where id = :id"),
                                  {"name": name, "surname": surname, "middle_name": middle_name, "id": user.id})
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
        order_history = (await session.execute(text("select distinct id, (select array_agg(product_id) from order_items where order_id = orders.id) as products, order_price  from orders where user_id = :user_id"), {"user_id": user.id})).all()
        return  [product._asdict() for product in order_history]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Module 3

@app.post("/product")
async def create_product(product: Product, user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    if not user.is_admin:
        return forbidden

    if math.isinf(product.price) or math.isnan(product.price):
        return generate_validation_error_for_fields("price")
    if product.name == "":
        return generate_validation_error_for_fields("name")

    try:
        product_id = (await session.execute(text("insert into products (name, price, user_id) values (:name, :price, :user_id) returning id"),
                                            {"name": product.name, "price": product.price, "user_id": user.id})).scalar()
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Product created successfully", "id": product_id}


@app.delete("/product/{product_id}")
async def delete_product(product_id: int, user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    if not user.is_admin:
        return forbidden

    try:
        await session.execute(text("delete from products where id = :id"), {"id": product_id})
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Product deleted successfully"}


@app.patch("/product/{product_id}")
async def update_product(product_id: int, product: ProductUpdate, user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    if not user.is_admin:
        return forbidden

    if product.name is None and product.name is None or product.price is None:
        return JSONResponse(status_code=400, content={"message": "No input provided"})

    if product.price is not None and (math.isinf(product.price) or math.isnan(product.price)):
        return generate_validation_error_for_fields("price")

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

    if product_data is None:
        return JSONResponse(status_code=404, content={"message": "Product not found"})

    return Product(**product_data._asdict())
