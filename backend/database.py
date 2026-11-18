from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os

# Carga las variables del archivo .env
load_dotenv()

# Lee la URL de conexión desde .env
DATABASE_URL = os.getenv("DATABASE_URL")

# Algunos proveedores usan 'postgres://' pero SQLAlchemy necesita 'postgresql://'
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# pool_pre_ping: Neon cierra conexiones inactivas cuando la base "duerme";
# esto descarta las conexiones muertas antes de usarlas en vez de dar error.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

# Cada petición a la API tendrá su propia sesión de DB
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base de la que heredan todos los modelos
Base = declarative_base()


# Abre y cierra la sesión automáticamente en cada endpoint que use la DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
