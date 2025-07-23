from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Integer, Numeric, String, Text, Date, Float,
    ForeignKey, LargeBinary, func
)
from sqlalchemy.orm import relationship
from database import Base
import uuid
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

class User(Base):
    __tablename__ = "users"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, nullable=True)
    role = Column(Enum("customer", "supplier", "admin", name="user_roles"), nullable=False)
    name = Column(String, nullable=False)
    surname = Column(String, nullable=True)
    phone_number = Column(String, index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(Enum("active", "disabled", "pending", name="user_statuses"), server_default="active", nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    business_phone_number = Column(String, index=True, nullable=True)
    business_email = Column(String, nullable=True)
    business_name = Column(String, nullable=True)
    business_category = Column(String, nullable=True)
    business_description = Column(String, nullable=True)
    business_type = Column(String, nullable=True)
    personal_image_path = Column(String, nullable=True)
    business_image_path = Column(String, nullable=True)
    business_created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    requests = relationship("RequestPost", back_populates="customer", cascade="all, delete")
    offers = relationship("Offer", back_populates="supplier", cascade="all, delete")
    products = relationship("Product", back_populates="supplier", cascade="all, delete")
    customer_orders = relationship("Order", foreign_keys="[Order.customer_id]", back_populates="customer")
    supplier_orders = relationship("Order", foreign_keys="[Order.supplier_id]", back_populates="supplier")

class RequestPost(Base):
    __tablename__ = "request_posts"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(Text)
    category = Column(Text)
    offer_price = Column(Numeric(12, 2))
    quantity = Column(Integer, default=1)
    status = Column(Enum("open", "accepted", "declined", "cancelled", name="request_statuses"), server_default="open", nullable=False)
    customer_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    image_path = Column(String, nullable=True)

    customer = relationship("User", back_populates="requests")
    offers = relationship("Offer", back_populates="request", cascade="all, delete")


class Product(Base):
    __tablename__ = "products"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String)
    description = Column(Text)
    category = Column(String, nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    supplier_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"))
    image_path = Column(String, nullable=True)

    supplier = relationship("User", back_populates="products")

class Offer(Base):
    __tablename__ = "offers"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(PG_UUID(as_uuid=True), ForeignKey("request_posts.id"), nullable=False)
    supplier_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    proposed = Column(Numeric(12, 2), nullable=False)
    status = Column(
        Enum("pending", "accepted", "rejected", name="offer_statuses"),
        server_default="pending", nullable=False
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    request = relationship("RequestPost", back_populates="offers")
    supplier = relationship("User", back_populates="offers")


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    device_id = Column(String, nullable=False)
    token = Column(String, unique=True, nullable=False)
    issued_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_used = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(PG_UUID(as_uuid=True), ForeignKey("request_posts.id"), nullable=False)
    offer_id = Column(PG_UUID(as_uuid=True), ForeignKey("offers.id"), nullable=False)
    customer_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    supplier_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    status = Column(
        Enum("placed", "delivered", "cancelled", name="order_statuses"),
        server_default="placed", nullable=False
    )

    total_price = Column(Numeric(12, 2), nullable=False)
    quantity = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    request = relationship("RequestPost")
    offer = relationship("Offer")
    customer = relationship("User", foreign_keys=[customer_id], back_populates="customer_orders")
    supplier = relationship("User", foreign_keys=[supplier_id], back_populates="supplier_orders")
