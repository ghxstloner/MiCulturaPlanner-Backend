"""
Endpoints de autenticación
"""
import logging
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
    Autentica un usuario y devuelve un token de acceso
    """
    try:
        # Autenticar usuario
        user = await authenticate_user(login_data.login, login_data.password)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario o contraseña incorrectos",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Crear token de acceso
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.login}, 
            expires_delta=access_token_expires
        )
        
        # Información del usuario para la respuesta
        user_info = {
            "login": user.login,
            "name": user.name,
            "email": user.email,
            "is_admin": user.priv_admin == 'Y',
            "active": user.active,
            "id_aerolinea": user.id_aerolinea,
            "picture": user.picture
        }
        
        logger.info(f"Usuario autenticado exitosamente: {user.login}")
        
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user_info=user_info,
            message=f"Bienvenido, {user.name}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en login: {str(e)}")
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