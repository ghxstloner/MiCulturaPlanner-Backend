"""
Endpoints para dashboard y estadísticas
"""
import logging
from fastapi import APIRouter, HTTPException, status, Depends
from app.schemas.responses import StandardResponse
from app.utils.auth import get_current_active_user
from app.models.user import User
from app.db.database import get_dashboard_stats

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/stats", response_model=StandardResponse)
async def get_dashboard_stats_endpoint(
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtiene estadísticas para el dashboard
    """
    try:
        stats = get_dashboard_stats()
        
        return StandardResponse(
            success=True,
            message="Estadísticas del dashboard obtenidas exitosamente",
            data=stats
        )
        
    except Exception as e:
        logger.error(f"Error al obtener stats del dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener estadísticas"
        )