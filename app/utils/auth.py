"""
Utilidades de autenticación y autorización
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
from app.db.database import get_user_by_login
from app.models.user import User

logger = logging.getLogger(__name__)

# Configuración de seguridad
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Configuración JWT
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña contra su hash"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Error al verificar contraseña: {str(e)}")
        return False

def get_password_hash(password: str) -> str:
    """Genera el hash de una contraseña"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea un token JWT"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    try:
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error al crear token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al generar token de acceso"
        )

def verify_token(token: str) -> Optional[dict]:
    """Verifica y decodifica un token JWT"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"Token inválido: {str(e)}")
        return None

def authenticate_user(login: str, password: str) -> Optional[User]:
    """Autentica un usuario con login y contraseña"""
    try:
        user_data = get_user_by_login(login)
        if not user_data:
            logger.warning(f"Usuario no encontrado: {login}")
            return None
        
        # En el sistema original, las contraseñas están hasheadas con SHA256
        # Verificamos primero si es SHA256, sino usamos bcrypt
        stored_password = user_data['pswd']
        
        if len(stored_password) == 64:  # SHA256 hex string
            import hashlib
            password_sha256 = hashlib.sha256(password.encode()).hexdigest()
            password_valid = password_sha256 == stored_password
        else:
            # Asumir que es bcrypt
            password_valid = verify_password(password, stored_password)
        
        if not password_valid:
            logger.warning(f"Contraseña incorrecta para usuario: {login}")
            return None
        
        return User(**user_data)
        
    except Exception as e:
        logger.error(f"Error al autenticar usuario {login}: {str(e)}")
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Obtiene el usuario actual desde el token JWT"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = verify_token(token)
        
        if payload is None:
            raise credentials_exception
        
        login: str = payload.get("sub")
        if login is None:
            raise credentials_exception
        
        user_data = get_user_by_login(login)
        if user_data is None:
            raise credentials_exception
        
        return User(**user_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener usuario actual: {str(e)}")
        raise credentials_exception

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Verifica que el usuario esté activo"""
    if current_user.active != 'Y':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Usuario inactivo"
        )
    return current_user

def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Requiere que el usuario sea administrador"""
    if current_user.priv_admin != 'Y':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos de administrador"
        )
    return current_user