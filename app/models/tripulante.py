from typing import Optional
from pydantic import BaseModel
from datetime import date

class Tripulante(BaseModel):
    id_tripulante: int
    crew_id: str
    nombres: str
    apellidos: str
    identidad: Optional[str] = None
    email: Optional[str] = None
    celular: Optional[str] = None
    imagen: Optional[str] = None
    estatus: int = 1
    id_departamento: Optional[int] = None
    id_cargo: Optional[int] = None
    descripcion_departamento: Optional[str] = None
    descripcion_cargo: Optional[str] = None
    
    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}"
    
    class Config:
        from_attributes = True

class TripulanteCreate(BaseModel):
    crew_id: str
    nombres: str
    apellidos: str
    identidad: Optional[str] = None
    email: Optional[str] = None
    celular: Optional[str] = None
    id_departamento: Optional[int] = None
    id_cargo: Optional[int] = None