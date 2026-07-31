from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from database import Base


class ProductPage(Base):
    __tablename__ = "product_pages"

    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), primary_key=True)
    use_custom_layout = Column(Boolean, default=False, nullable=False)
    custom_blocks = Column(Text, nullable=True)  # JSON con bloques personalizados
    description = Column(Text, nullable=True)    # Descripción larga
    specs = Column(Text, nullable=True)          # Especificaciones en JSON
    features = Column(Text, nullable=True)       # Características en JSON
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    