from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.repositories import ReviewEvalRepository
from app.db.store import InMemoryStore
from app.models.schemas import ProviderConfig


def hydrate_provider_configs(store: InMemoryStore, session: Session) -> list[ProviderConfig]:
    try:
        configs = ReviewEvalRepository(session).list_provider_configs()
    except SQLAlchemyError:
        session.rollback()
        return []
    store.provider_configs = {config.id: config for config in configs}
    return configs
