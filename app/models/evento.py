"""
Modelo para eventos
"""
from typing import Optional
from pydantic import BaseModel
from datetime import date, time

class Evento(BaseModel):
    id_evento: int
    fecha_evento: Optional[date] = None
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    id_pais: Optional[int] = None
    id_provincia: Optional[int] = None
    id_lugar: Optional[int] = None
    descripcion_evento: Optional[str] = None
    id_departamento: Optional[int] = None
    estatus: int = 1
    descripcion_lugar: Optional[str] = None
    descripcion_departamento: Optional[str] = None
    pais_nombre: Optional[str] = None
    
    class Config:
        from_attributes = True

class EventoCreate(BaseModel):
    fecha_evento: date
    hora_inicio: time
    hora_fin: time
    id_pais: int
    id_provincia: Optional[int] = None
    id_lugar: int
    descripcion_evento: str
    id_departamento: int

class EventoUpdate(BaseModel):
    fecha_evento: Optional[date] = None
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    id_pais: Optional[int] = None
    id_provincia: Optional[int] = None
    id_lugar: Optional[int] = None
    descripcion_evento: Optional[str] = None
    id_departamento: Optional[int] = None
    estatus: Optional[int] = None