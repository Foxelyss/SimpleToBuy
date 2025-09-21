"""empty message

Revision ID: 7eda90400a02
Revises:
Create Date: 2025-09-16 21:28:22.483416

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7eda90400a02'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.execute("""create table if not exists users (
        id serial primary key,
        name varchar(255) not null,
        surname varchar(255) not null,
        middle_name varchar(255),
        email varchar(255) not null unique,
        password_hash varchar(255) not null,
        created_at timestamp default current_timestamp,
        profile_picture varchar(255) default '/avatars/default.jpg',
        admin boolean not null default false
    );""")

    op.execute("""create table if not exists sessions (
        id serial primary key,
        user_id integer not null references users(id),
        token varchar(255) not null unique,
        created_at timestamp default current_timestamp
        );""")

    op.execute("""create table if not exists products (
        id serial primary key,
        name varchar(255) not null,
        description text not null,
        price decimal(10, 2) not null
    );""")

    op.execute("""create table if not exists cart (
        id serial primary key,
        user_id integer not null references users(id),
        product_id integer not null references products(id)
        );""")

    op.execute("""create table if not exists orders (
        id serial primary key,
        user_id integer not null references users(id),
        order_price decimal(10, 2) not null
    );""")

    op.execute("""create table if not exists order_items (
        id serial primary key,
        order_id integer not null references orders(id),
        product_id integer not null references products(id)
        );""")

    # Insert initial data
    op.execute("""
        INSERT INTO users (name,surname,email,password_hash,admin)
        VALUES ('Иван','Иванов','admin@shop.ru','$2b$12$cu3d0kFKys1MV05bjTlf2.9Xkr9J1Jw.1BJzbX5EOT9VBgK1gQ4QK',true),
        ('Пётр','Васильев','user@shop.ru','$2b$12$0RKgMj9g0Lb2N.5vu8B0.ORF93awJOC/MnxkP0nT2NlF8VmYy5rSq',false)
    """)

    op.execute("""
        INSERT INTO products (name, description, price)
        VALUES ('Квас благодей', 'Для здоровья людей', 100),
               ('Хлеб', 'Обычный серый хлеб', 200)
    """)



def downgrade():
    op.execute("DROP TABLE users")
    op.execute("DROP TABLE orders")
    op.execute("DROP TABLE order_items")
    op.execute("DROP TABLE cart")
    op.execute("DROP TABLE products")
