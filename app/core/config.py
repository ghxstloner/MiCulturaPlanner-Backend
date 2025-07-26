import os
import secrets
from typing import List, Optional
from pydantic_settings import BaseSettings
import logging

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    DEBUG: bool = True
    PORT: int = 8000
    # Database Settings
    DB_HOST: str
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    DB_PORT: int = 3306
    
    # CORS Settings
    CORS_ALLOWED_ORIGINS: List[str] = ["*"]
    
    # Face Recognition Settings
    FACE_CONFIDENCE_THRESHOLD: float = 0.70
    FACE_DISTANCE_THRESHOLD: float = 0.4
    MAX_FACE_MATCHES: int = 5
    
    # File Upload Settings
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB
    TEMP_UPLOAD_PATH: str = "./temp_uploads"
    ALLOWED_IMAGE_EXTENSIONS: List[str] = ["jpg", "jpeg", "png"]
    
    # Geolocation Settings
    GEOLOCATION_ENABLED: bool = True
    GEOLOCATION_MAX_DISTANCE_METERS: int = 100
    
    # Logging Settings
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

    def setup_logging(self):
        """Configurar logging para la aplicación"""
        # Crear directorio de logs si no existe
        os.makedirs(os.path.dirname(self.LOG_FILE), exist_ok=True)
        
        # Configurar nivel de logging
        log_level = getattr(logging, self.LOG_LEVEL.upper(), logging.INFO)
        
        # Configurar formato
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # Configurar logging
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=[
                logging.FileHandler(self.LOG_FILE, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )

# Instancia global de configuración
settings = Settings()

# Configurar logging al importar
settings.setup_logging()