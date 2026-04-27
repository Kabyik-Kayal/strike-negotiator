from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Source = Literal["voice", "synthetic"]
ExportKind = Literal["press_release", "demand_list", "brief"]


class TextIngestRequest(BaseModel):
    worker_secret: str = Field(min_length=3, description="Phone number or demo-only stable secret. Never stored.")
    language: str = Field(min_length=2, max_length=12)
    transcript: str = Field(min_length=1)
    transcript_raw: str | None = None
    city_bucket: str | None = None
    platform: str | None = None
    source: Source = "synthetic"


class GrievanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: int
    source: Source
    language: str
    city_bucket: str | None
    platform: str | None
    transcript: str
    transcript_raw: str | None


class IngestResponse(BaseModel):
    id: str
    status: Literal["stored"]


class FilingChunkCreate(BaseModel):
    id: str
    platform: str
    doc_type: str
    doc_date: str | None = None
    page: int | None = None
    text: str = Field(min_length=1)


class FilingChunkRead(FilingChunkCreate):
    model_config = ConfigDict(from_attributes=True)


class SynthesisRequest(BaseModel):
    city: str | None = None
    platform: str | None = None
    since: int | None = Field(default=None, description="Unix seconds")


class SynthesisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: int
    scope_filter: str | None
    output_json: str
    grievance_ids: str


class ExportCreate(BaseModel):
    synthesis_id: str
    kind: ExportKind


class ExportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    synthesis_id: str
    kind: ExportKind
    body_md: str
    created_at: int
