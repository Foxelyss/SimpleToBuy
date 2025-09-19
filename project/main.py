import re
import math
from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from models import *
from database import get_session, init_models, engine, SessionDep
from authorization import oauth2_scheme, get_current_user, query_user, verify_password, get_password_hash, create_access_token

app = FastAPI()


@app.on_event("startup")
async def on_startup():
    await init_models()


@app.on_event("shutdown")
async def on_shutdown():
    await engine.dispose()


# Module 1

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}


@app.post("/login")
async def login(new_user: UserAuthorization, session: SessionDep):
    user = await query_user(new_user.email, session)

    if not user or not verify_password(new_user.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(data={"sub": user.id})

    await session.execute(text("insert into sessions (user_id, token) values (:user_id, :token) returning token"), {"user_id": user.id, "token": access_token})
    await session.commit()
    return {"message": "Logged in successfully", "access_token": access_token}


@app.post("/logout")
async def logout(token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep):
    await session.execute(text("delete from sessions where token = :token"), {"token": token})
    await session.commit()
    return {"message": "Logged out successfully"}


@app.post("/signup")
async def register(new_user: UserSignup, session: SessionDep):
    try:
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', new_user.email) is None:
            raise HTTPException(status_code=422, detail={"message": "Validation error", "email": "Validation error", })

        if new_user.password is None:
            raise HTTPException(status_code=422, detail={"message": "Validation error", "password": "Validation error", })

        fio = new_user.fio.split()
        if len(fio) < 2 or len(fio) > 3:
            raise HTTPException(status_code=422, detail={"message": "Validation error", "fio": "Validation error", })

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

    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    user_id = id.scalar_one()

    access_token = create_access_token(data={"sub": user_id})

    await session.execute(text("insert into sessions (user_id, token) values (:user_id, :token) returning token"), {"user_id": user_id, "token": access_token})
    await session.commit()

    return {"message": "Registered successfully", "token": access_token}


@app.get("/profile")
def get_profile(user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    return user._asdict()


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
        cart_items = (await session.execute(text("select * from cart where user_id = :user_id"), {"user_id": user.id})).all()
        return [item._asdict() for item in cart_items]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/order")
async def place_order(user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    try:
        order_id = await session.execute(text("insert into orders (user_id) values (:user_id) returning id"), {"user_id": user.id})
        await session.commit()

        order_id = order_id.scalar_one()

        await session.execute(text("insert into order_items (order_id, product_id, quantity) select :order_id, product_id, quantity from cart where user_id = :user_id"),
                              {"order_id": order_id, "user_id": user.id})
        await session.execute(text("delete from cart where user_id = :user_id"), {"user_id": user.id})

        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Order placed successfully"}


@app.patch("/profile")
async def update_profile(profile: ProfileUpdate, user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    try:
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', profile.email) is None:
            raise HTTPException(status_code=422, detail={"message": "Validation error", "email": "Validation error", })

        if profile.password is None:
            raise HTTPException(status_code=422, detail={"message": "Validation error", "password": "Validation error", })

        if profile.email:
            await session.execute(text("update users set email = :email where id = :id"), {"email": profile.email, "id": user.id})

        if profile.fio:
            fio = profile.fio.split()

            if len(fio) < 2 or len(fio) > 3:
                raise HTTPException(status_code=422, detail={"message": "Validation error", "fio": "Validation error", })

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
        order_history = (await session.execute(text("select * from orders where user_id = :user_id"), {"user_id": user.id})).all()
        return order_history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Module 3

@app.post("/product")
async def create_product(product: Product, user: Annotated[User, Depends(get_current_user)], session: SessionDep):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    if math.isinf(product.price) or math.isnan(product.price):
        raise HTTPException(status_code=400, detail={"message": "Validation error", "price": "Validation error"})
    if product.name == "":
        raise HTTPException(status_code=422, detail={"message": "Validation error", "password": "Validation error", })


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
        raise HTTPException(status_code=403, detail="Forbidden")

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
        raise HTTPException(status_code=403, detail="Forbidden")

    if product.name is None and product.name and None or product.price and None:
        raise HTTPException(status_code=422, detail={"message": "Validation error", "name": "Validation error", })

    if product.price is not None and (math.isinf(product.price) or math.isnan(product.price)):
        raise HTTPException(status_code=422, detail={"message": "Validation error", "price": "Validation error", })

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
        raise HTTPException(status_code=404, detail="Product not found")

    return Product(**product_data._asdict())
