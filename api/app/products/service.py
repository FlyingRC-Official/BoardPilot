from uuid import UUID

from app.db.store import InMemoryStore
from app.models.schemas import Product, ProductAlias, ProductAliasCreate, ProductCreate


def create_product(store: InMemoryStore, payload: ProductCreate) -> Product:
    return store.add_product(Product(**payload.model_dump()))


def list_products(store: InMemoryStore) -> list[Product]:
    return list(store.products.values())


def get_product(store: InMemoryStore, product_id: UUID) -> Product:
    return store.products[product_id]


def create_alias(store: InMemoryStore, product_id: UUID, payload: ProductAliasCreate) -> ProductAlias:
    if product_id not in store.products:
        raise KeyError("product not found")
    return store.add_alias(ProductAlias(product_id=product_id, **payload.model_dump()))

