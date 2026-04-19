from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    odoo_connections: Mapped[list["OdooConnection"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class OdooConnection(Base):
    __tablename__ = "odoo_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(500))
    db_name: Mapped[str] = mapped_column(String(120))
    username: Mapped[str] = mapped_column(String(255))
    api_key_ct: Mapped[str] = mapped_column(Text)  # Fernet-encrypted
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="odoo_connections")


class Insight(Base):
    """Local-only AI-generated notes attached to an Odoo project.

    We store them here (instead of Odoo chatter) so the Pi doesn't hammer
    Odoo with mail.messages, and so we can dedup via content_hash.
    """

    __tablename__ = "insights"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", "content_hash", name="uq_insight_dedup"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("odoo_connections.id", ondelete="CASCADE"))
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(40))  # "risk" | "digest" | "plan" | "breakdown"
    severity: Mapped[str] = mapped_column(String(10), default="info")  # info | warn | high
    title: Mapped[str] = mapped_column(String(255))
    body_md: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AppSetting(Base):
    """Singleton (id=1) — global app-level settings overridable from the UI.

    We store the Anthropic API key here (encrypted) so users can rotate it
    without touching .env on the Pi.
    """

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    anthropic_api_key_ct: Mapped[str | None] = mapped_column(Text, nullable=True)
    anthropic_model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class CostLog(Base):
    """One row per Claude API call — enough to audit spend and cache effectiveness."""

    __tablename__ = "cost_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    feature: Mapped[str] = mapped_column(String(60))  # "plan" | "breakdown" | "chat" | "digest" | "risk" | "stakeholder"
    model: Mapped[str] = mapped_column(String(60))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
