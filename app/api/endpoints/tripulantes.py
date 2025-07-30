"""
Endpoints para gestión de tripulantes
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from app.schemas.responses import StandardResponse
from app.utils.auth import get_current_active_user
from app.models.user import User
from app.db.database import get_tripulante_by_field, get_todos_tripulantes, get_total_tripulantes

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=StandardResponse)
async def get_all_tripulantes(
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    limit: int = Query(50, ge=1, le=100, description="Límite de tripulantes por página"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtiene todos los tripulantes activos con paginación
    """
    try:
        # Obtener el total de tripulantes
        total_tripulantes = get_total_tripulantes()
        logger.info(f"🔢 Total tripulantes obtenido: {total_tripulantes}")
        
        # Obtener tripulantes paginados
        tripulantes = get_todos_tripulantes(offset=offset, limit=limit)
        logger.info(f"📝 Tripulantes obtenidos: {len(tripulantes)}")
        
        if not tripulantes:
            metadata_empty = {
                "total": total_tripulantes,
                "offset": offset,
                "limit": limit,
                "has_more": False
            }
            logger.info(f"📊 Metadata (vacío): {metadata_empty}")
            return StandardResponse(
                success=True,
                message="No se encontraron tripulantes",
                data=[],
                metadata=metadata_empty
            )
        
        tripulantes_formateados = []
        for tripulante in tripulantes:
            tripulante_data = {
                'id_tripulante': tripulante['id_tripulante'],
                'crew_id': tripulante['crew_id'],
                'nombres': tripulante['nombres'],
                'apellidos': tripulante['apellidos'],
                'identidad': tripulante['identidad'],
                'email': tripulante['email'],
                'celular': tripulante['celular'],
                'imagen': tripulante['imagen'],
                'departamento': tripulante.get('descripcion_departamento'),
                'cargo': tripulante.get('descripcion_cargo'),
                'estatus': tripulante['estatus']
            }
            tripulantes_formateados.append(tripulante_data)
        
        # Calcular si hay más páginas
        has_more = (offset + limit) < total_tripulantes
        
        metadata_final = {
            "total": total_tripulantes,
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "current_page_count": len(tripulantes_formateados)
        }
        
        logger.info(f"📊 Metadata final: {metadata_final}")
        
        response = StandardResponse(
            success=True,
            message=f"Se encontraron {len(tripulantes_formateados)} tripulantes",
            data=tripulantes_formateados,
            metadata=metadata_final
        )
        
        metadata_log = getattr(response, 'metadata', 'No metadata field')
        logger.info(f"📤 Response.metadata enviado: {metadata_log}")
        return response
        
    except Exception as e:
        logger.error(f"❌ Error al obtener tripulantes: {str(e)}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al obtener tripulantes"
        )

@router.get("/search", response_model=StandardResponse)
async def search_tripulantes(
    q: str = Query(..., min_length=2, description="Término de búsqueda"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Busca tripulantes por crew_id, nombre o cédula
    """
    try:
        # Intentar buscar por crew_id primero
        tripulante = None
        
        # Si parece ser un crew_id (números/alfanumérico)
        if q.replace('-', '').replace('.', '').isalnum():
            tripulante = get_tripulante_by_field('crew_id', q)
            
            # Si no encontró por crew_id, intentar por cédula
            if not tripulante:
                tripulante = get_tripulante_by_field('identidad', q)
        
        if tripulante:
            tripulante_data = {
                'id_tripulante': tripulante['id_tripulante'],
                'crew_id': tripulante['crew_id'],
                'nombres': tripulante['nombres'],
                'apellidos': tripulante['apellidos'],
                'nombre_completo': f"{tripulante['nombres']} {tripulante['apellidos']}",
                'identidad': tripulante['identidad'],
                'email': tripulante['email'],
                'celular': tripulante['celular'],
                'departamento': tripulante['descripcion_departamento'],
                'cargo': tripulante['descripcion_cargo'],
                'estatus': tripulante['estatus']
            }
            
            return StandardResponse(
                success=True,
                message="Tripulante encontrado",
                data=[tripulante_data]
            )
        else:
            return StandardResponse(
                success=True,
                message="No se encontraron tripulantes con ese criterio",
                data=[]
            )
            
    except Exception as e:
        logger.error(f"Error al buscar tripulantes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al buscar tripulantes"
        )

@router.get("/{crew_id}", response_model=StandardResponse)
async def get_tripulante(
    crew_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtiene un tripulante por su crew_id
    """
    try:
        tripulante = get_tripulante_by_field('crew_id', crew_id)
        
        if not tripulante:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tripulante con crew_id {crew_id} no encontrado"
            )
        
        tripulante_data = {
            'id_tripulante': tripulante['id_tripulante'],
            'crew_id': tripulante['crew_id'],
            'nombres': tripulante['nombres'],
            'apellidos': tripulante['apellidos'],
            'nombre_completo': f"{tripulante['nombres']} {tripulante['apellidos']}",
            'identidad': tripulante['identidad'],
            'email': tripulante['email'],
            'celular': tripulante['celular'],
            'imagen': tripulante['imagen'],
            'departamento': tripulante['descripcion_departamento'],
            'cargo': tripulante['descripcion_cargo'],
            'estatus': tripulante['estatus'],
            'id_departamento': tripulante['id_departamento'],
            'id_cargo': tripulante['id_cargo']
        }
        
        return StandardResponse(
            success=True,
            message="Tripulante encontrado exitosamente",
            data=tripulante_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener tripulante {crew_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener información del tripulante"
        )