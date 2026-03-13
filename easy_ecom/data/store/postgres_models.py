from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from easy_ecom.data.store.postgres_db import Base


class ClientModel(Base):
    __tablename__ = "clients"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    business_name: Mapped[str] = mapped_column(String(255), default="")
    owner_name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    currency_code: Mapped[str] = mapped_column(String(16), default="")
    currency_symbol: Mapped[str] = mapped_column(String(8), default="")
    website_url: Mapped[str] = mapped_column(String(255), default="")
    facebook_url: Mapped[str] = mapped_column(String(255), default="")
    instagram_url: Mapped[str] = mapped_column(String(255), default="")
    whatsapp_number: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class RoleModel(Base):
    __tablename__ = "roles"

    role_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    role_name: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")


class UserModel(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(255), index=True, default="")
    password: Mapped[str] = mapped_column(Text, default="")
    password_hash: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[str] = mapped_column(String(8), default="true")
    created_at: Mapped[str] = mapped_column(String(64), default="")


class UserRoleModel(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role_code: Mapped[str] = mapped_column(String(64), primary_key=True)
