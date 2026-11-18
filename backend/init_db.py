"""
Prepara el esquema de la base de datos al arrancar el servidor.

Por qué existe: la cadena de migraciones de Alembic NO puede construir una base
vacía desde cero. Algunas tablas (categories, product_pages) y columnas de
orders se crearon a mano en la base vieja de Railway y nunca quedaron en una
migración, así que `alembic upgrade head` sobre una base nueva (Neon) falla.

- Base nueva (no existe la tabla alembic_version): crea todas las tablas desde
  los modelos con create_all() y marca la base como "al día" (alembic stamp head).
- Base que ya está bajo Alembic: corre `alembic upgrade head` normal, así las
  migraciones futuras se siguen aplicando como siempre.
"""
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from database import Base, engine
import models  # noqa: F401  registra todos los modelos en Base.metadata


def main() -> None:
    alembic_cfg = Config("alembic.ini")

    if inspect(engine).has_table("alembic_version"):
        print("[init_db] Base existente: aplicando migraciones pendientes...")
        command.upgrade(alembic_cfg, "head")
    else:
        print("[init_db] Base nueva: creando tablas desde los modelos...")
        Base.metadata.create_all(bind=engine)
        command.stamp(alembic_cfg, "head")

    print("[init_db] Esquema listo.")


if __name__ == "__main__":
    main()
