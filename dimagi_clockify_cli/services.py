from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlmodel import Session

from dimagi_clockify_cli.config import Config
from dimagi_clockify_cli.db import Project, Tag, Task, User, Workspace


class Client:
    """
    A thin wrapper around requests.Session.
    """

    def __init__(
            self,
            requests_session: requests.Session,
            config: Config,
    ) -> None:
        self.session = requests_session
        self.config = config

    def request(
            self,
            method: str,
            endpoint: str,
            **kwargs
    ) -> requests.Response:
        url = slash_join(self.config.base_url, endpoint)
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Api-Key': self.config.api_key,
        }
        headers.update(kwargs.pop('headers', {}))
        response = self.session.request(
            method,
            url,
            headers=headers,
            **kwargs,
        )
        return response


@contextmanager
def get_client(config):
    with requests.Session() as requests_session:
        client = Client(requests_session, config)
        yield client


def get_workspace(
        session: Session,
        client: Client,
) -> Workspace:
    stmt = select(Workspace)
    result = session.execute(stmt)
    workspace = result.scalars().one_or_none()
    if workspace is None:
        user = fetch_user(session, client)
        workspace = user.workspace
    return workspace


def get_user(
        session: Session,
        client: Client,
) -> User:
    stmt = select(User).options(selectinload(User.workspace))
    result = session.execute(stmt)
    user = result.scalars().one_or_none()
    if user is None:
        user = fetch_user(session, client)
    return user


def fetch_user(
        session: Session,
        client: Client,
) -> User:
    response = client.request('GET', '/user')
    response.raise_for_status()
    data = response.json()
    workspace = Workspace(id=data['defaultWorkspace'])
    user = User(id=data['id'], workspace=workspace)
    session.add(user)
    session.commit()
    return user


def get_project(
        session: Session,
        client: Client,
        workspace: Workspace,
        project_name: str,
) -> Project:
    stmt = (
        select(Project)
        .options(selectinload(Project.workspace))
        .where(Project.name == project_name)
    )
    result = session.execute(stmt)
    project = result.scalars().one_or_none()
    if project is None:
        project = fetch_project(session, client, workspace, project_name)
    return project


def fetch_project(
        session: Session,
        client: Client,
        workspace: Workspace,
        project_name: str,
) -> Project:
    endpoint = f'/workspaces/{workspace.id}/projects'
    params = {'name': project_name}
    response = client.request('GET', endpoint, params=params)
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError(f'Project "{project_name}" not found')
    if len(data) > 1:
        raise ValueError(f'Multiple projects "{project_name}" found')
    project = Project(
        id=data[0]['id'],
        # Use `project_name` instead of `data[0]['name']`, because if
        # they are not exactly the same, we will keep fetching.
        name=project_name,
        workspace=workspace,
    )
    session.add(project)
    session.commit()
    return project


def get_tags(
        session: Session,
        client: Client,
        workspace: Workspace,
        tag_names: List[str],
) -> List[Tag]:
    tags = []
    for tag_name in tag_names:
        stmt = (
            select(Tag)
            .options(selectinload(Tag.workspace))
            .where(Tag.name == tag_name)
        )
        result = session.execute(stmt)
        tag = result.scalars().one_or_none()
        if tag is None:
            tag = fetch_tag(session, client, workspace, tag_name)
        tags.append(tag)
    return tags


def fetch_tag(
        session: Session,
        client: Client,
        workspace: Workspace,
        tag_name: str,
) -> Tag:
    endpoint = f'/workspaces/{workspace.id}/tags'
    params = {
        'name': tag_name,
        'archived': False,
    }
    response = client.request('GET', endpoint, params=params)
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError(f'Tag "{tag_name}" not found')
    if len(data) > 1:
        raise ValueError(f'Multiple tags "{tag_name}" found')
    tag = Tag(
        id=data[0]['id'],
        name=tag_name,
        workspace=workspace,
    )
    session.add(tag)
    session.commit()
    return tag


def get_task(
        session: Session,
        client: Client,
        project: Project,
        task_name: str,
) -> Task:
    stmt = (
        select(Task)
        .options(selectinload(Task.project).selectinload(Project.workspace))
        .where(Task.project == project)
        .where(Task.name == task_name)
    )
    result = session.execute(stmt)
    task = result.scalars().one_or_none()
    if task is None:
        task = fetch_task(session, client, project, task_name)
    return task


def fetch_task(
        session: Session,
        client: Client,
        project: Project,
        task_name: str,
) -> Task:
    endpoint = (
        f'/workspaces/{project.workspace.id}'
        f'/projects/{project.id}/tasks'
    )
    params = {'name': task_name}
    response = client.request('GET', endpoint, params=params)
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError(f'Task "{task_name}" not found')
    if len(data) > 1:
        raise ValueError(f'Multiple tasks "{task_name}" found')
    task = Task(
        id=data[0]['id'],
        name=task_name,
        project=project,
    )
    session.add(task)
    session.commit()
    return task


def stop_timer(
        client: Client,
        workspace: Workspace,
        user: User,
        since_dt: Optional[datetime] = None,
) -> None:
    if since_dt is None:
        since_dt = datetime.now()
    endpoint = f'/workspaces/{workspace.id}/user/{user.id}/time-entries'
    # End a minute earlier to prevent overlapping time entries
    body = {'end': zulu(since_dt - timedelta(minutes=1))}
    # Returns a 404 if timer is not running
    client.request('PATCH', endpoint, json=body)


def add_time_entry(
        client: Client,
        description: str,
        workspace: Workspace,
        project: Project,
        task: Task,
        tags: List[Tag],
        since_dt: Optional[datetime] = None,
) -> None:
    if since_dt is None:
        since_dt = datetime.utcnow()
    endpoint = f'/workspaces/{workspace.id}/time-entries'
    body = {
        'start': zulu(since_dt),
        'billable': is_billable(tags),
        'description': description,
        'projectId': project.id,
        'taskId': task.id,
        'tagIds': [t.id for t in tags]
    }
    response = client.request('POST', endpoint, json=body)
    response.raise_for_status()


def slash_join(*strings) -> str:
    """
    Joins strings with a single ``/``.

    >>> slash_join('http://example.com', 'foo')
    'http://example.com/foo'
    >>> slash_join('http://example.com/', '/foo/')
    'http://example.com/foo/'

    """
    if len(strings) == 0:
        return ''
    if len(strings) == 1:
        return strings[0]
    left = [strings[0].rstrip('/')]
    right = [strings[-1].lstrip('/')]
    middle = [s.strip('/') for s in strings[1:-1]]
    return '/'.join(left + middle + right)


def zulu(local_dt: datetime) -> str:
    """
    Returns a UTC datetime as ISO-formatted in Zulu time.

    >>> dt = datetime.utcfromtimestamp(1640995200)
    >>> zulu(dt)
    '2022-01-01T00:00:00Z'

    """
    utc_dt = local_dt.astimezone(timezone.utc)
    return utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def is_billable(tags: List[Tag]) -> bool:
    """
    Returns ``True`` if any tag in ``tags`` is "Overhead"

    >>> overhead = Tag(name='Overhead')
    >>> not_overhead = Tag(name='Foo:Bar')
    >>> is_billable([not_overhead])
    True
    >>> is_billable([not_overhead, overhead])
    False

    """
    return not any(t.name == 'Overhead' for t in tags)
