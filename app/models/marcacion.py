"""
Modelo para marcaciones
"""
from typing import Optional
from pydantic import BaseModel
from datetime import date, time
from decimal import Decimal

class Marcacion(BaseModel):
    id_marcacion: int
    id_planificacion: int
    id_evento: Optional[int] = None
    id_tripulante: Optional[int] = None
    crew_id: Optional[str] = None
    fecha_marcacion: Optional[date] = None
    hora_entrada: Optional[time] = None
    hora_salida: Optional[time] = None
    hora_marcacion: Optional[time] = None
    lugar_marcacion: Optional[int] = None
    punto_control: Optional[int] = None
    procesado: str = '0'
    tipo_marcacion: int = 1
    usuario: Optional[str] = None
    transporte: Optional[Decimal] = Decimal('0.00')
    alimentacion: Optional[Decimal] = Decimal('0.00')
    
    # Campos calculados de las joins
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    descripcion_evento: Optional[str] = None
    descripcion_lugar: Optional[str] = None
    
    class Config:
        from_attributes = True

class MarcacionCreate(BaseModel):
    id_planificacion: int
    id_evento: int
    id_tripulante: int
    crew_id: str
    fecha_marcacion: date
    hora_entrada: Optional[time] = None
    hora_salida: Optional[time] = None
    lugar_marcacion: Optional[int] = None
    punto_control: Optional[int] = 1
    tipo_marcacion: int = 1
    usuario: Optional[str] = "facial_ai"
    transporte: Optional[Decimal] = Decimal('0.00')
    alimentacion: Optional[Decimal] = Decimal('0.00')

class MarcacionUpdate(BaseModel):
    hora_entrada: Optional[time] = None
    hora_salida: Optional[time] = None
    hora_marcacion: Optional[time] = None
    lugar_marcacion: Optional[int] = None
    punto_control: Optional[int] = None
    procesado: Optional[str] = None
    tipo_marcacion: Optional[int] = None
    usuario: Optional[str] = None
    transporte: Optional[Decimal] = None
    alimentacion: Optional[Decimal] = None