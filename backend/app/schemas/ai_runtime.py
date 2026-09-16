from typing import Any
from pydantic import BaseModel, Field

class AIRuntimeRequest(BaseModel):
    guild_id: int
    module_key: str = Field(min_length=1, max_length=80)
    capability: str = Field(min_length=1, max_length=80)
    input_text: str = Field(min_length=1, max_length=200000)
    system_prompt: str | None = Field(default=None, max_length=50000)
    source_language: str | None = Field(default=None, max_length=32)
    target_language: str | None = Field(default=None, max_length=32)
    model: str | None = Field(default=None, max_length=255)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, ge=1, le=32768)
    metadata: dict[str, Any] = Field(default_factory=dict)
    image_data_urls: list[str] = Field(default_factory=list, max_length=4)

class AIRuntimeResponse(BaseModel):
    text: str
    provider_id: str
    provider_name: str
    provider_type: str
    model: str | None
    input_units: int = 0
    output_units: int = 0
    latency_ms: int
