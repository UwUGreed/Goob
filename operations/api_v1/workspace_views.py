from fastapi import Depends, Header
from operations.domain import workspace_views as views
from operations.domain.common import command


def register_workspace_views(app, session, actor):
    prefix = '/api/v1/workspace-views'

    def mutate(db, user, key, operation, body, run):
        result = command(db, user, key, operation, body.model_dump(), run)
        db.commit()
        return result

    @app.get(prefix)
    def listing(page: views.Page, db=Depends(session), user=Depends(actor)):
        return views.list_views(db, user, page)

    @app.post(prefix, status_code=201)
    def create(body: views.Create, idempotency_key: str = Header(default=''), db=Depends(session), user=Depends(actor)):
        return mutate(db, user, idempotency_key, 'workspace:create', body, lambda: views.create(db, user, body))

    @app.post(prefix + '/selection')
    def select(body: views.SelectView, idempotency_key: str = Header(default=''), db=Depends(session), user=Depends(actor)):
        return mutate(db, user, idempotency_key, 'workspace:select', body, lambda: views.select_view(db, user, body))

    @app.post(prefix + '/team-default')
    def publish(body: views.Publish, idempotency_key: str = Header(default=''), db=Depends(session), user=Depends(actor)):
        return mutate(db, user, idempotency_key, 'workspace:publish', body, lambda: views.publish(db, user, body))

    @app.patch(prefix + '/{identifier}')
    def update(identifier: str, body: views.Update, idempotency_key: str = Header(default=''), db=Depends(session), user=Depends(actor)):
        return mutate(db, user, idempotency_key, 'workspace:update:' + identifier, body, lambda: views.update(db, user, identifier, body))

    @app.delete(prefix + '/{identifier}')
    def delete(identifier: str, body: views.Delete, idempotency_key: str = Header(default=''), db=Depends(session), user=Depends(actor)):
        return mutate(db, user, idempotency_key, 'workspace:delete:' + identifier, body, lambda: views.delete(db, user, identifier, body))
