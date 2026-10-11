from alembic import context

from operations.persistence.database import engine_for
from operations.persistence.models import Base


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    with engine_for().connect() as connection:
        run(connection)
