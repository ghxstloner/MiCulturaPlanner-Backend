"""
Endpoints para reportes y estadísticas
"""
import logging
from fastapi import APIRouter, HTTPException, status, Depends
from app.schemas.responses import StandardResponse
from app.utils.auth import get_current_active_user
from app.models.user import User
from app.db.database import get_reportes_stats_completos

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/stats", response_model=StandardResponse)
async def get_reportes_stats(
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtiene estadísticas completas para reportes
    """
    try:
        stats = get_reportes_stats_completos()
        
        if not stats:
            return StandardResponse(
                success=True,
                message="No hay datos suficientes para generar estadísticas",
                data={
                    'totalEventos': 0,
                    'eventosActivos': 0,
                    'eventosFinalizados': 0,
                    'promedioAsistencia': 0,
                    'eventosPorMes': {},
                    'asistenciaCompleta': 0,
                    'asistenciaParcial': 0,
                    'ausencias': 0,
                    'tendenciaEventos': 0,
                    'tendenciaMarcaciones': 0
                }
            )
        
        return StandardResponse(
            success=True,
            message="Estadísticas obtenidas exitosamente",
            data=stats
        )
        
    except Exception as e:
        logger.error(f"Error al obtener estadísticas de reportes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener estadísticas de reportes"
        )