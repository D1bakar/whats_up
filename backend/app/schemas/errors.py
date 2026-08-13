from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str = Field(examples=["validation_error"])
    message: str = Field(examples=["Request validation failed"])
    request_id: str | None = Field(default=None, examples=["550e8400-e29b-41d4-a716-446655440000"])
