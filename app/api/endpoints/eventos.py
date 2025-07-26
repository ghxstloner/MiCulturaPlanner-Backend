"""
Endpoints para gestión de eventos
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from app.schemas.responses import StandardResponse, PaginatedResponse
from app.models.evento import Evento
from app.utils.auth import get_current_active_user
from app.models.user import User
from app.db.database import get_eventos_activos, get_planificacion_evento

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=StandardResponse)
async def get_eventos(
    activos_solo: bool = Query(True, description="Solo eventos activos"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtiene la lista de eventos
    """
    try:
        if activos_solo:
            eventos = get_eventos_activos()
        else:
            # TODO: Implementar función para obtener todos los eventos
            eventos = get_eventos_activos()
        
        # Formatear eventos para respuesta
        eventos_formateados = []
        for evento in eventos:
            evento_data = {
                'id_evento': evento['id_evento'],
                'fecha_evento': evento['fecha_evento'].isoformat() if evento['fecha_evento'] else None,
                'hora_inicio': evento['hora_inicio'].strftime('%H:%M:%S') if evento['hora_inicio'] else None,
                'hora_fin': evento['hora_fin'].strftime('%H:%M:%S') if evento['hora_fin'] else None,
                'descripcion_evento': evento['descripcion_evento'],
                'descripcion_lugar': evento['descripcion_lugar'],
                'descripcion_departamento': evento['descripcion_departamento'],
                'pais_nombre': evento['pais_nombre']
            }
            eventos_formateados.append(evento_data)
        
        return StandardResponse(
            success=True,
            message=f"Se encontraron {len(eventos_formateados)} eventos",
            data=eventos_formateados
        )
        
    except Exception as e:
        logger.error(f"Error al obtener eventos: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener eventos"
        )

@router.get("/{id_evento}", response_model=StandardResponse)
async def get_evento_detail(
    id_evento: int,
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtiene los detalles de un evento específico
    """
    try:
        eventos = get_eventos_activos()
        evento = next((e for e in eventos if e['id_evento'] == id_evento), None)
        
        if not evento:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evento con ID {id_evento} no encontrado"
            )
        
        evento_detail = {
            'id_evento': evento['id_evento'],
            'fecha_evento': evento['fecha_evento'].isoformat() if evento['fecha_evento'] else None,
            'hora_inicio': evento['hora_inicio'].strftime('%H:%M:%S') if evento['hora_inicio'] else None,
            'hora_fin': evento['hora_fin'].strftime('%H:%M:%S') if evento['hora_fin'] else None,
            'descripcion_evento': evento['descripcion_evento'],
            'descripcion_lugar': evento['descripcion_lugar'],
            'descripcion_departamento': evento['descripcion_departamento'],
            'pais_nombre': evento['pais_nombre'],
            'id_departamento': evento['id_departamento']
        }
        
        return StandardResponse(
            success=True,
            message="Detalles del evento obtenidos exitosamente",
            data=evento_detail
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener evento {id_evento}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener detalles del evento"
        )

@router.get("/{id_evento}/planificacion", response_model=StandardResponse)
async def get_evento_planificacion(
    id_evento: int,
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtiene la planificación de tripulantes para un evento
    """
    try:
        planificacion = get_planificacion_evento(id_evento)
        
        if not planificacion:
            return StandardResponse(
                success=True,
                message="No hay tripulantes planificados para este evento",
                data=[]
            )
        
        # Formatear planificación
        planificacion_formateada = []
        for plan in planificacion:
            plan_data = {
                'id_planificacion': plan['id'],
                'crew_id': plan['crew_id'],
                'nombres': plan['nombres'],
                'apellidos': plan['apellidos'],
                'nombre_completo': f"{plan['nombres']} {plan['apellidos']}",
                'identidad': plan['identidad'],
                'fecha_vuelo': plan['fecha_vuelo'].isoformat() if plan['fecha_vuelo'] else None,
                'hora_entrada': plan['hora_entrada'].strftime('%H:%M:%S') if plan['hora_entrada'] else None,
                'hora_salida': plan['hora_salida'].strftime('%H:%M:%S') if plan['hora_salida'] else None,
                'estatus': plan['estatus'],
                'descripcion_evento': plan['descripcion_evento'],
                'descripcion_lugar': plan['descripcion_lugar']
            }
            planificacion_formateada.append(plan_data)
        
        return StandardResponse(
            success=True,
            message=f"Planificación obtenida: {len(planificacion_formateada)} tripulantes",
            data=planificacion_formateada
        )
        
    except Exception as e:
        logger.error(f"Error al obtener planificación del evento {id_evento}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener planificación del evento"
        )