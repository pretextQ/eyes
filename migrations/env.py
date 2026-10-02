from logging.config import fileConfig

from alembic import context

from eyes.server.config import Settings
from eyes.server.storage.database import database
from eyes.server.storage.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
settings = Settings()

if context.is_offline_mode():
    context.configure(
        url=settings.database_url.get_secret_value(),
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine, _ = database(settings)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            compare_type=True,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
