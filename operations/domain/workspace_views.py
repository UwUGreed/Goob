"""Tenant-scoped presentation settings, independent of operational permissions."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select
from operations.domain.common import Problem, dump
from operations.persistence.models import WorkspaceView, WorkspaceSelection, Branch, now

Page = Literal['overview', 'dispatch']
WIDGETS = {
    'overview': {'metrics', 'urgent', 'maintenance', 'renewals', 'reviews', 'schedule', 'availability', 'stock'},
    'dispatch': {'queue', 'schedule', 'map'},
}
COLUMNS = {'customer', 'trade', 'status', 'technician', 'time'}


class Shape(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Tile(Shape):
    i: str = Field(max_length=32)
    x: int = Field(ge=0, le=12, strict=True)
    y: int = Field(ge=0, le=256, strict=True)
    w: int = Field(ge=1, le=12, strict=True)
    h: int = Field(ge=2, le=24, strict=True)


class Layouts(Shape):
    lg: list[Tile] = Field(max_length=8)
    md: list[Tile] = Field(max_length=8)
    sm: list[Tile] = Field(max_length=8)


class Preferences(Shape):
    trade: Literal['All', 'Plumbing', 'HVAC', 'Electrical'] = 'All'
    jobStatus: Literal['All', 'Unassigned', 'Assigned', 'En route', 'Arrived', 'Working', 'Completed'] = 'All'
    available: StrictBool = False
    names: StrictBool = True
    routes: StrictBool = True
    density: Literal['comfortable', 'compact'] = 'comfortable'


class Configuration(Shape):
    version: int = Field(default=1, ge=1, le=1, strict=True)
    layouts: Layouts
    hidden: list[str] = Field(default_factory=list, max_length=8)
    columns: list[str] = Field(default_factory=lambda: ['customer', 'trade', 'status', 'technician', 'time'], max_length=5)
    preferences: Preferences = Field(default_factory=Preferences)
    mode: Literal['2D', '3D'] = '2D'

    def for_page(self, page):
        allowed = WIDGETS[page]
        if len(set(self.hidden)) != len(self.hidden) or set(self.hidden) - allowed or set(self.hidden) == allowed:
            raise Problem('Choose valid widgets and keep at least one visible.', 422)
        if len(set(self.columns)) != len(self.columns) or set(self.columns) - COLUMNS:
            raise Problem('Invalid job-list columns.', 422)
        for breakpoint, cols in [('lg', 12), ('md', 6), ('sm', 1)]:
            tiles = getattr(self.layouts, breakpoint)
            if len(tiles) != len(allowed) or {t.i for t in tiles} != allowed:
                raise Problem('Layout must contain each supported widget exactly once.', 422)
            for t in tiles:
                minimum = 1 if breakpoint == 'sm' else (6 if page == 'dispatch' and t.i == 'schedule' else 3)
                if t.x + t.w > cols or t.w < minimum:
                    raise Problem('Widget exceeds grid bounds or is too narrow.', 422)
        return self.model_dump()


class Create(Shape):
    page: Page
    name: str = Field(min_length=1, max_length=80)
    configuration: Configuration


class Update(Shape):
    revision: int = Field(ge=1, strict=True)
    name: str = Field(min_length=1, max_length=80)
    configuration: Configuration


class SelectView(Shape):
    page: Page
    view_id: str | None = Field(default=None, max_length=80)


class Publish(Create):
    revision: int = Field(ge=0, strict=True)


class Delete(Shape):
    revision: int = Field(ge=1, strict=True)


def list_views(db, actor, page):
    personal = list(db.scalars(select(WorkspaceView).where(
        WorkspaceView.tenant_id == actor.tenant, WorkspaceView.page == page,
        WorkspaceView.scope == 'personal', WorkspaceView.subject == actor.subject).order_by(WorkspaceView.updated_at)))
    team = db.get(WorkspaceView, (actor.tenant, 'team-' + page))
    selection = db.get(WorkspaceSelection, (actor.tenant, actor.subject, page))
    active = selection.view_id if selection and any(v.id == selection.view_id for v in personal) else None
    return {'views': [dump(v) for v in personal], 'teamDefault': dump(team) if team else None, 'activeViewId': active}


def owned(db, actor, identifier):
    row = db.get(WorkspaceView, (actor.tenant, identifier))
    if not row or row.scope != 'personal' or row.subject != actor.subject:
        raise Problem('Workspace view not found.', 404)
    return row


def name(value):
    value = value.strip()
    if not value:
        raise Problem('Give this view a name.', 422)
    return value


def revision(row, expected):
    if row.revision != expected:
        raise Problem('This view changed in another session. Reload saved views before retrying.', 409)


def select_view(db, actor, body):
    if body.view_id:
        row = owned(db, actor, body.view_id)
        if row.page != body.page:
            raise Problem('View belongs to another page.', 422)
    selection = db.get(WorkspaceSelection, (actor.tenant, actor.subject, body.page))
    if selection is None:
        selection = WorkspaceSelection(tenant_id=actor.tenant, subject=actor.subject, page=body.page)
        db.add(selection)
    selection.view_id = body.view_id
    return {'activeViewId': body.view_id}


def create(db, actor, body):
    if len(list_views(db, actor, body.page)['views']) >= 32:
        raise Problem('Keep up to 32 personal views per page.', 422)
    row = WorkspaceView(tenant_id=actor.tenant, subject=actor.subject, page=body.page,
                        scope='personal', name=name(body.name), configuration=body.configuration.for_page(body.page))
    db.add(row)
    db.flush()
    select_view(db, actor, SelectView(page=body.page, view_id=row.id))
    return dump(row)


def update(db, actor, identifier, body):
    row = owned(db, actor, identifier)
    revision(row, body.revision)
    row.name, row.configuration = name(body.name), body.configuration.for_page(row.page)
    row.revision += 1
    row.updated_at = now()
    return dump(row)


def delete(db, actor, identifier, body):
    row = owned(db, actor, identifier)
    revision(row, body.revision)
    for selection in db.scalars(select(WorkspaceSelection).where(
            WorkspaceSelection.tenant_id == actor.tenant, WorkspaceSelection.view_id == identifier)):
        selection.view_id = None
    db.flush()
    db.delete(row)
    return {'deleted': True}


def publish(db, actor, body):
    branches = set(db.scalars(select(Branch.id).where(Branch.tenant_id == actor.tenant)))
    if actor.role != 'owner' or set(actor.branches) != branches:
        raise Problem('An owner with access to all branches must publish the team default.', 403)
    row = db.get(WorkspaceView, (actor.tenant, 'team-' + body.page))
    if row:
        revision(row, body.revision)
        row.name, row.configuration = name(body.name), body.configuration.for_page(body.page)
        row.revision += 1
        row.updated_at = now()
    else:
        if body.revision != 0:
            raise Problem('Team default changed; reload before publishing.', 409)
        row = WorkspaceView(tenant_id=actor.tenant, id='team-' + body.page, subject='',
                            scope='team', page=body.page, name=name(body.name),
                            configuration=body.configuration.for_page(body.page))
        db.add(row)
    db.flush()
    return dump(row)
