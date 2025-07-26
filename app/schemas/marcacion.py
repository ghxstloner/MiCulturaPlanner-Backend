"""
Esquemas para marcaciones
"""
from typing import Optional
from pydantic import BaseModel
from datetime import date, time
from decimal import Decimal

class MarcacionCreateRequest(BaseModel):
    crew_id: str
    id_evento: int
    tipo_marcacion: int = 1  # 1=entrada, 2=salida
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    transporte: Optional[Decimal] = Decimal('0.00')
    alimentacion: Optional[Decimal] = Decimal('0.00')

class MarcacionResponse(BaseModel):
    id_marcacion: int
    crew_id: str
    nombres: str
    apellidos: str
    nombre_completo: str
    fecha_marcacion: str
    hora_marcacion: Optional[str] = None
    hora_display: str
    tipo_marcacion_texto: str
    tipo_marcacion: int
    descripcion_evento: str
    descripcion_lugar: Optional[str] = None
    mensaje: str
    
    class Config:
        from_attributes = True

class MarcacionDetailResponse(BaseModel):
    id_marcacion: int
    id_planificacion: int
    id_evento: int
    id_tripulante: int
    crew_id: str
    fecha_marcacion: str
    hora_entrada: Optional[str] = None
    hora_salida: Optional[str] = None
    hora_marcacion: Optional[str] = None
    lugar_marcacion: Optional[int] = None
    punto_control: Optional[int] = None
    procesado: str
    tipo_marcacion: int
    usuario: Optional[str] = None
    transporte: Optional[Decimal] = None
    alimentacion: Optional[Decimal] = None
    
    # Información relacionada
    tripulante_nombres: Optional[str] = None
    tripulante_apellidos: Optional[str] = None
    descripcion_evento: Optional[str] = None
    descripcion_lugar: Optional[str] = None