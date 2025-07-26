"""
Esquemas Pydantic para la API
"""
from .auth import LoginRequest, LoginResponse, TokenData, UserResponse
from .facial import (
    FacialRecognitionRequest, FacialRecognitionResponse, FacialMatch,
    EmbeddingCreateRequest, EmbeddingCreateResponse, EmbeddingInfoResponse
)
from .responses import StandardResponse, ErrorResponse, PaginatedResponse, HealthResponse
from .marcacion import (
    MarcacionResponse, MarcacionCreateRequest, MarcacionDetailResponse
)

__all__ = [
    # Auth schemas
    "LoginRequest", "LoginResponse", "TokenData", "UserResponse",
    
    # Facial recognition schemas
    "FacialRecognitionRequest", "FacialRecognitionResponse", "FacialMatch",
    "EmbeddingCreateRequest", "EmbeddingCreateResponse", "EmbeddingInfoResponse",
    
    # Response schemas
    "StandardResponse", "ErrorResponse", "PaginatedResponse", "HealthResponse",
    
    # Marcacion schemas
    "MarcacionResponse", "MarcacionCreateRequest", "MarcacionDetailResponse"
]