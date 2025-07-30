"""
Endpoints de autenticación - OPTIMIZADO
"""
import logging
import time
from datetime import timedelta
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.responses import StandardResponse
from app.utils.auth import authenticate_user, create_access_token, get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/login", response_model=LoginResponse)
async def login(login_data: LoginRequest):
    """
    Autentica un usuario y devuelve un token de acceso - OPTIMIZADO
    """
    start_time = time.time()
    
    try:
        logger.info(f"🔐 [LOGIN] Iniciando autenticación para: {login_data.login}")
        
        # ✅ AUTENTICACIÓN SÍNCRONA (ya no async)
        auth_start = time.time()
        user = authenticate_user(login_data.login, login_data.password)
        auth_elapsed = (time.time() - auth_start) * 1000
        
        logger.info(f"🔐 [LOGIN] Autenticación completada en {auth_elapsed:.2f}ms")

        if not user:
            logger.warning(f"🔐 [LOGIN] Credenciales inválidas para: {login_data.login}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario o contraseña incorrectos",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # ✅ CREAR TOKEN (operación rápida)
        token_start = time.time()
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.login}, 
            expires_delta=access_token_expires
        )
        token_elapsed = (time.time() - token_start) * 1000
        
        logger.info(f"🔐 [LOGIN] Token generado en {token_elapsed:.2f}ms")
        
        # ✅ PREPARAR RESPUESTA (operación rápida)
        user_info = {
            "login": user.login,
            "name": user.name,
            "email": user.email,
            "is_admin": user.priv_admin == 'Y',
            "active": user.active,
            "id_aerolinea": user.id_aerolinea,
            "picture": user.picture
        }
        
        total_elapsed = (time.time() - start_time) * 1000
        logger.info(f"🔐 [LOGIN] ✅ Login exitoso para {user.login} en {total_elapsed:.2f}ms TOTAL")
        
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user_info=user_info,
            message=f"Bienvenido, {user.name}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        total_elapsed = (time.time() - start_time) * 1000
        logger.error(f"🔐 [LOGIN] ❌ Error después de {total_elapsed:.2f}ms: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get("/me", response_model=StandardResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    Obtiene la información del usuario actual
    """
    try:
        user_info = {
            "login": current_user.login,
            "name": current_user.name,
            "email": current_user.email,
            "is_admin": current_user.priv_admin == 'Y',
            "id_aerolinea": current_user.id_aerolinea,
            "active": current_user.active,
            "picture": current_user.picture
        }
        
        return StandardResponse(
            success=True,
            message="Información del usuario obtenida exitosamente",
            data=user_info
        )
        
    except Exception as e:
        logger.error(f"Error al obtener información del usuario: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener información del usuario"
        )

@router.post("/verify-token", response_model=StandardResponse)
async def verify_token(current_user: User = Depends(get_current_active_user)):
    """
    Verifica si un token es válido
    """
    return StandardResponse(
        success=True,
        message="Token válido",
        data={"valid": True, "user": current_user.login}
    )