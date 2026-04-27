from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.db import Base


class Grievance(Base):
    __tablename__ = "grievance"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    city_bucket: Mapped[str | None] = mapped_column(Text)
    platform: Mapped[str | None] = mapped_column(Text)
    audio_path: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    transcript_raw: Mapped[str | None] = mapped_column(Text)
    worker_hash: Mapped[str] = mapped_column(Text, nullable=False)


class FilingChunk(Base):
    __tablename__ = "filing_chunk"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    doc_type: Mapped[str] = mapped_column(Text, nullable=False)
    doc_date: Mapped[str | None] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class Synthesis(Base):
    __tablename__ = "synthesis"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    scope_filter: Mapped[str | None] = mapped_column(Text)
    output_json: Mapped[str] = mapped_column(Text, nullable=False)
    grievance_ids: Mapped[str] = mapped_column(Text, nullable=False)


class Export(Base):
    __tablename__ = "export"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    synthesis_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
