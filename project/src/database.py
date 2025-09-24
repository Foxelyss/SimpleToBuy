from typing import Annotated, TypeAlias

import os

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from fastapi import Depends

DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL is None:
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost/simpletobuy"

engine = create_async_engine(DATABASE_URL, echo=True)
Base = declarative_base()
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


SessionDep: TypeAlias = Annotated[AsyncSession, Depends(get_session)]
