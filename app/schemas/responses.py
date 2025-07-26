"""
Esquemas para respuestas estándar de la API
"""
from typing import Any, Optional, List
from pydantic import BaseModel

class StandardResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None

class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[dict] = None

class PaginatedResponse(BaseModel):
    success: bool
    message: str
    data: List[Any]
    total: int
    page: int
    limit: int
    total_pages: int

class HealthResponse(BaseModel):
    status: str
    message: str
    version: str
    timestamp: Optional[str] = None