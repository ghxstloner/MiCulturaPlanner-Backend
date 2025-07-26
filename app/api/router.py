"""
Router principal de la API
"""
from fastapi import APIRouter
from app.api.endpoints import auth, facial, eventos, marcaciones, tripulantes

api_router = APIRouter()

# Incluir routers de endpoints
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["autenticacion"]
)

api_router.include_router(
    facial.router,
    prefix="/facial",
    tags=["reconocimiento-facial"]
)

api_router.include_router(
    eventos.router,
    prefix="/eventos",
    tags=["eventos"]
)

api_router.include_router(
    marcaciones.router,
    prefix="/marcaciones",
    tags=["marcaciones"]
)

api_router.include_router(
    tripulantes.router,
    prefix="/tripulantes",
    tags=["tripulantes"]
)

# Endpoint de salud
@api_router.get("/health", tags=["sistema"])
async def health_check():
    """Endpoint para verificar el estado de la API"""
    return {
        "status": "ok",
        "message": "CulturaConnect Facial API está funcionando correctamente",
        "version": "1.0.0"
    }