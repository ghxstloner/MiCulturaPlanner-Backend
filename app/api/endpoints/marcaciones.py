"""
Endpoints para gestión de marcaciones
"""
import logging
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from app.schemas.responses import StandardResponse
from app.schemas.marcacion import MarcacionResponse
from app.utils.auth import get_current_active_user
from app.models.user import User
from app.db.database import get_marcaciones_recientes

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/recent", response_model=StandardResponse)
async def get_recent_marcaciones(
    limit: int = Query(10, ge=1, le=50, description="Número máximo de marcaciones a obtener"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtiene las marcaciones más recientes
    """
    try:
        marcaciones = get_marcaciones_recientes(limit)
        
        # Formatear marcaciones para respuesta
        marcaciones_formateadas = []
        for marcacion in marcaciones:
            # Determinar tipo de marcación y hora a mostrar
            if marcacion['hora_salida'] and marcacion['hora_salida'].strftime('%H:%M:%S') != '00:00:00':
                tipo_marcacion = "Salida"
                hora_marcacion = marcacion['hora_salida']
            elif marcacion['hora_entrada'] and marcacion['hora_entrada'].strftime('%H:%M:%S') != '00:00:00':
                tipo_marcacion = "Entrada"
                hora_marcacion = marcacion['hora_entrada']
            else:
                tipo_marcacion = "Pendiente"
                hora_marcacion = None
            
            marcacion_data = {
                'id_marcacion': marcacion['id_marcacion'],
                'crew_id': marcacion['crew_id'],
                'nombres': marcacion['nombres'],
                'apellidos': marcacion['apellidos'],
                'nombre_completo': f"{marcacion['nombres']} {marcacion['apellidos']}",
                'fecha_marcacion': marcacion['fecha_marcacion'].isoformat() if marcacion['fecha_marcacion'] else None,
                'hora_marcacion': hora_marcacion.strftime('%H:%M:%S') if hora_marcacion else None,
                'hora_display': hora_marcacion.strftime('%I:%M:%S %p') if hora_marcacion else 'N/A',
                'tipo_marcacion_texto': tipo_marcacion,
                'tipo_marcacion': marcacion['tipo_marcacion'],
                'descripcion_evento': marcacion['descripcion_evento'],
                'descripcion_lugar': marcacion['descripcion_lugar'],
                'mensaje': f"{tipo_marcacion} - {marcacion['nombres']} {marcacion['apellidos']}"
            }
            marcaciones_formateadas.append(marcacion_data)
        
        return StandardResponse(
            success=True,
            message=f"Se obtuvieron {len(marcaciones_formateadas)} marcaciones recientes",
            data=marcaciones_formateadas
        )
        
    except Exception as e:
        logger.error(f"Error al obtener marcaciones recientes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener marcaciones recientes"
        )

@router.get("/today", response_model=StandardResponse)
async def get_today_marcaciones(
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtiene las marcaciones del día actual
    """
    try:
        # Por ahora usar las recientes y filtrar por fecha actual
        # En producción se debería crear una función específica en database.py
        marcaciones = get_marcaciones_recientes(50)  # Obtener más para filtrar
        
        fecha_hoy = date.today()
        marcaciones_hoy = [
            m for m in marcaciones 
            if m['fecha_marcacion'] == fecha_hoy
        ]
        
        # Formatear marcaciones
        marcaciones_formateadas = []
        for marcacion in marcaciones_hoy:
            if marcacion['hora_salida'] and marcacion['hora_salida'].strftime('%H:%M:%S') != '00:00:00':
                tipo_marcacion = "Salida"
                hora_marcacion = marcacion['hora_salida']
            elif marcacion['hora_entrada'] and marcacion['hora_entrada'].strftime('%H:%M:%S') != '00:00:00':
                tipo_marcacion = "Entrada"
                hora_marcacion = marcacion['hora_entrada']
            else:
                tipo_marcacion = "Pendiente"
                hora_marcacion = None
            
            marcacion_data = {
                'id_marcacion': marcacion['id_marcacion'],
                'crew_id': marcacion['crew_id'],
                'nombres': marcacion['nombres'],
                'apellidos': marcacion['apellidos'],
                'nombre_completo': f"{marcacion['nombres']} {marcacion['apellidos']}",
                'fecha_marcacion': marcacion['fecha_marcacion'].isoformat(),
                'hora_marcacion': hora_marcacion.strftime('%H:%M:%S') if hora_marcacion else None,
                'hora_display': hora_marcacion.strftime('%I:%M:%S %p') if hora_marcacion else 'N/A',
                'tipo_marcacion_texto': tipo_marcacion,
                'descripcion_evento': marcacion['descripcion_evento'],
                'descripcion_lugar': marcacion['descripcion_lugar']
            }
            marcaciones_formateadas.append(marcacion_data)
        
        return StandardResponse(
            success=True,
            message=f"Marcaciones de hoy: {len(marcaciones_formateadas)}",
            data=marcaciones_formateadas
        )
        
    except Exception as e:
        logger.error(f"Error al obtener marcaciones de hoy: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener marcaciones de hoy"
        )