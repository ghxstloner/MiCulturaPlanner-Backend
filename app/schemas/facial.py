"""
Esquemas para reconocimiento facial
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class FacialRecognitionRequest(BaseModel):
    id_evento: int
    latitud: Optional[float] = 0.0
    longitud: Optional[float] = 0.0
    usar_geolocalizacion: bool = True
    tipo_geolocalizacion: str = "verificar"  # "verificar" o "reasignar"

class FacialMatch(BaseModel):
    crew_id: str
    nombres: str
    apellidos: str
    confidence: float
    distance: float
    id_tripulante: int

class FacialRecognitionResponse(BaseModel):
    success: bool
    message: str
    tripulante_info: Optional[Dict[str, Any]] = None
    marcacion_info: Optional[Dict[str, Any]] = None
    matches_found: Optional[List[FacialMatch]] = None
    processing_time: Optional[float] = None
    requires_reassignment: bool = False

class EmbeddingCreateRequest(BaseModel):
    crew_id: str
    modelo: str = "Facenet512"

class EmbeddingCreateResponse(BaseModel):
    success: bool
    message: str
    embedding_id: Optional[int] = None
    tripulante_info: Optional[Dict[str, Any]] = None

class EmbeddingInfoResponse(BaseModel):
    embedding_id: int
    crew_id: str
    modelo: str
    confidence: float
    active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    tripulante: Optional[Dict[str, Any]] = None