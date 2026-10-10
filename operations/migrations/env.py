from alembic import context
from operations.persistence.database import engine_for
from operations.persistence.models import Base

with engine_for().connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
