create table if not exists users (
    id serial primary key,
    email varchar(255) not null unique,
    password_hash varchar(255) not null,
    created_at timestamp default current_timestamp,
    profile_picture varchar(255),
    admin boolean not null default false
);

create table if not exists sessions (
    id serial primary key,
    user_id integer not null references users(id),
    token varchar(255) not null unique,
    created_at timestamp default current_timestamp
);

create table if not exists products (
    id serial primary key,
    name varchar(255) not null,
    description text not null,
    price decimal(10, 2) not null,
    created_at timestamp default current_timestamp
);

create table if not exists cart (
    id serial primary key,
    user_id integer not null references users(id),
    product_id integer not null references products(id),
    quantity integer not null,
    created_at timestamp default current_timestamp
);

create table if not exists orders (
    id serial primary key,
    user_id integer not null references users(id),
    status varchar(255) not null,
    created_at timestamp default current_timestamp
);

create table if not exists order_items (
    id serial primary key,
    order_id integer not null references orders(id),
    product_id integer not null references products(id),
    quantity integer not null,
    created_at timestamp default current_timestamp
);
