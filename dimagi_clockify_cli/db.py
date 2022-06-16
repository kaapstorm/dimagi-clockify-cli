import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.future import Engine
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine

from dimagi_clockify_cli.config import get_config_dir


class Workspace(SQLModel, table=True):
    id: str = Field(primary_key=True)


class User(SQLModel, table=True):
    id: str = Field(primary_key=True)
    workspace_id: str = Field(foreign_key='workspace.id')
    workspace: Workspace = Relationship()


class Project(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    workspace_id: str = Field(foreign_key='workspace.id')
    workspace: Workspace = Relationship()


class Task(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    project_id: str = Field(foreign_key='project.id')
    project: Project = Relationship()


class Tag(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    workspace_id: str = Field(foreign_key='workspace.id')
    workspace: Workspace = Relationship()


def get_engine() -> Engine:
    config_dir = get_config_dir()
    filename = os.path.join(config_dir, 'cache.db')
    return create_engine(f'sqlite:///{filename}')


@contextmanager
def get_session() -> Iterator[Session]:
    engine = get_engine()
    with Session(engine) as session:
        yield session


def init_db():
    engine = get_engine()
    # `create_all()` has no effect if tables exist already
    SQLModel.metadata.create_all(engine)
