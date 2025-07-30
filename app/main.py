"""
Aplicación principal de CulturaConnect Facial Recognition API
"""
import os
import sys
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Configurar paths
current_script_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_script_path)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Imports de la aplicación
from app.core.config import settings
from app.api.router import api_router
from app.db.database import test_connection
from app.utils.face_embeddings import create_face_embeddings_table

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestión del ciclo de vida de la aplicación
    """
    # Startup
    logger.info("🚀 Iniciando CulturaConnect Facial Recognition API...")
    
    # Crear directorios necesarios
    os.makedirs(settings.TEMP_UPLOAD_PATH, exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # Verificar conexión a base de datos
    if not test_connection():
        logger.error("❌ No se pudo conectar a la base de datos")
        raise Exception("Error de conexión a base de datos")
    else:
        logger.info("✅ Conexión a base de datos verificada")
    
    logger.info("🎉 Aplicación iniciada exitosamente")
    
    yield
    
    # Shutdown
    logger.info("🛑 Cerrando CulturaConnect Facial Recognition API...")
    
    # Limpiar archivos temporales
    try:
        import shutil
        if os.path.exists(settings.TEMP_UPLOAD_PATH):
            shutil.rmtree(settings.TEMP_UPLOAD_PATH)
            logger.info("🧹 Archivos temporales limpiados")
    except Exception as e:
        logger.warning(f"⚠️ Error al limpiar archivos temporales: {e}")
    
    logger.info("👋 Aplicación cerrada correctamente")

# Crear instancia de FastAPI
app = FastAPI(
    title="CulturaConnect Facial Recognition API",
    description="""
    API de reconocimiento facial para el sistema de control de asistencia de eventos culturales.
    
    ## Características
    
    * **Reconocimiento facial** - Identificación automática de tripulantes
    * **Control de asistencia** - Registro de entradas y salidas
    * **Gestión de eventos** - Administración de eventos culturales
    * **Autenticación segura** - Sistema de login con JWT
    * **Embeddings faciales** - Creación y gestión de perfiles biométricos
    
    ## Autenticación
    
    La API utiliza autenticación JWT. Use el endpoint `/auth/login` para obtener un token
    y inclúyalo en el header `Authorization: Bearer <token>` para las demás peticiones.
    """,
    version="1.0.0",
    contact={
        "name": "Soporte Técnico",
        "email": "soporte@culturaconnect.com",
    },
    license_info={
        "name": "Propietario",
    },
    lifespan=lifespan,
    debug=settings.DEBUG
)

# ✅ MIDDLEWARE DE DEBUG PARA RASTREAR TIMING
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log del inicio de la petición
    logger.info(f"🌐 [{request.method}] {request.url.path} - INICIANDO")
    
    # Ejecutar la petición
    response = await call_next(request)
    
    # Calcular tiempo de procesamiento
    process_time = (time.time() - start_time) * 1000
    
    # Log del final de la petición con tiempo
    logger.info(f"🌐 [{request.method}] {request.url.path} - COMPLETADO en {process_time:.2f}ms (Status: {response.status_code})")
    
    # Agregar header con tiempo de procesamiento
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
    
    return response

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS if isinstance(settings.CORS_ALLOWED_ORIGINS, list) else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Middleware de hosts confiables (en producción)
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "*.culturaconnect.com"]
    )

# Manejador global de excepciones
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Manejador personalizado para excepciones HTTP"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "error_code": f"HTTP_{exc.status_code}",
            "path": str(request.url)
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Manejador para excepciones generales"""
    logger.error(f"Error no manejado en {request.url}: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Error interno del servidor",
            "error_code": "INTERNAL_SERVER_ERROR",
            "path": str(request.url)
        }
    )

# Incluir router principal
app.include_router(api_router, prefix=settings.API_V1_STR)

# Endpoint raíz
@app.get("/")
async def root():
    """Endpoint de bienvenida"""
    return {
        "message": "Bienvenido a CulturaConnect Facial Recognition API",
        "version": "1.0.0",
        "documentation": "/docs",
        "health": "/api/v1/health"
    }

# Endpoint de información de la API
@app.get("/info")
async def api_info():
    """Información detallada de la API"""
    return {
        "name": "CulturaConnect Facial Recognition API",
        "version": "1.0.0",
        "description": "Sistema de reconocimiento facial para control de asistencia en eventos culturales",
        "features": [
            "Reconocimiento facial con DeepFace",
            "Control de asistencia automatizado",
            "Gestión de eventos culturales",
            "Autenticación JWT",
            "Embeddings faciales con Facenet512"
        ],
        "endpoints": {
            "auth": f"{settings.API_V1_STR}/auth",
            "facial": f"{settings.API_V1_STR}/facial",
            "eventos": f"{settings.API_V1_STR}/eventos",
            "marcaciones": f"{settings.API_V1_STR}/marcaciones",
            "tripulantes": f"{settings.API_V1_STR}/tripulantes"
        },
        "settings": {
            "debug": settings.DEBUG,
            "face_confidence_threshold": settings.FACE_CONFIDENCE_THRESHOLD,
            "face_distance_threshold": settings.FACE_DISTANCE_THRESHOLD
        }
    }

# Servir archivos estáticos si es necesario (en desarrollo)
if settings.DEBUG:
    try:
        static_path = os.path.join(project_root, "static")
        if os.path.exists(static_path):
            app.mount("/static", StaticFiles(directory=static_path), name="static")
    except Exception as e:
        logger.warning(f"No se pudo montar directorio estático: {e}")

# Función principal para ejecutar la aplicación
def main():
    """Función principal para ejecutar la aplicación"""
    
    # Configurar logging
    settings.setup_logging()
    
    logger.info("🚀 Iniciando servidor CulturaConnect Facial Recognition API...")
    
    # Configuración del servidor
    config = {
        "app": "app.main:app",
        "host": "0.0.0.0",
        "port": settings.PORT,
        "reload": settings.DEBUG,
        "log_level": settings.LOG_LEVEL.lower(),
        "access_log": True,
        "use_colors": True,
    }
    
    # En desarrollo, habilitar reload
    if settings.DEBUG:
        config.update({
            "reload_dirs": [project_root],
            "reload_includes": ["*.py"],
        })
    
    # Ejecutar servidor
    uvicorn.run(**config)

if __name__ == "__main__":
    main()