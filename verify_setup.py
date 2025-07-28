#!/usr/bin/env python3
"""
Script de verificación del sistema CulturaConnect.

Este script verifica que todo el sistema esté configurado correctamente
para la generación de embeddings y reconocimiento facial.
"""

import os
import sys
import logging
from typing import Dict, Any, List
import requests
from urllib.parse import urljoin

# Agregar el directorio del proyecto al path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app.core.config import settings
from app.db.database import get_db_connection, close_connection, test_connection
from app.utils.face_embeddings import create_face_embeddings_table

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SystemVerifier:
    def __init__(self):
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = 0
        
    def log_success(self, message: str):
        """Log mensaje de éxito"""
        logger.info(f"✅ {message}")
        self.checks_passed += 1
        
    def log_error(self, message: str):
        """Log mensaje de error"""
        logger.error(f"❌ {message}")
        self.checks_failed += 1
        
    def log_warning(self, message: str):
        """Log mensaje de advertencia"""
        logger.warning(f"⚠️  {message}")
        self.warnings += 1
        
    def verify_environment(self) -> bool:
        """Verifica las variables de entorno"""
        logger.info("🔍 Verificando variables de entorno...")
        
        required_vars = [
            'DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME',
            'IMAGE_BASE_URL'
        ]
        
        missing_vars = []
        for var in required_vars:
            value = getattr(settings, var, None)
            if not value:
                missing_vars.append(var)
        
        if missing_vars:
            self.log_error(f"Variables de entorno faltantes: {', '.join(missing_vars)}")
            return False
        else:
            self.log_success("Todas las variables de entorno están configuradas")
            return True
    
    def verify_database_connection(self) -> bool:
        """Verifica la conexión a la base de datos"""
        logger.info("🔍 Verificando conexión a la base de datos...")
        
        try:
            if test_connection():
                self.log_success("Conexión a la base de datos exitosa")
                return True
            else:
                self.log_error("No se pudo conectar a la base de datos")
                return False
        except Exception as e:
            self.log_error(f"Error al conectar a la base de datos: {str(e)}")
            return False
    
    def verify_tripulantes_data(self) -> bool:
        """Verifica que existan tripulantes con imágenes"""
        logger.info("🔍 Verificando datos de tripulantes...")
        
        connection = None
        try:
            connection = get_db_connection()
            if not connection:
                self.log_error("No se pudo conectar para verificar tripulantes")
                return False
            
            cursor = connection.cursor()
            
            # Contar tripulantes activos
            cursor.execute("SELECT COUNT(*) as total FROM tripulantes WHERE estatus = 1")
            total_active = cursor.fetchone()['total']
            
            # Contar tripulantes con imagen
            cursor.execute("""
                SELECT COUNT(*) as total 
                FROM tripulantes 
                WHERE estatus = 1 AND imagen IS NOT NULL AND imagen != ''
            """)
            with_images = cursor.fetchone()['total']
            
            cursor.close()
            
            if total_active == 0:
                self.log_error("No hay tripulantes activos en la base de datos")
                return False
            
            if with_images == 0:
                self.log_error("No hay tripulantes activos con imágenes")
                return False
            
            self.log_success(f"Tripulantes activos: {total_active}, con imágenes: {with_images}")
            
            if with_images < total_active:
                self.log_warning(f"{total_active - with_images} tripulantes sin imagen")
            
            return True
            
        except Exception as e:
            self.log_error(f"Error al verificar tripulantes: {str(e)}")
            return False
        finally:
            close_connection(connection)
    
    def verify_image_url_access(self) -> bool:
        """Verifica el acceso a las URLs de imágenes"""
        logger.info("🔍 Verificando acceso a URLs de imágenes...")
        
        # Obtener un tripulante de ejemplo
        connection = None
        try:
            connection = get_db_connection()
            if not connection:
                self.log_error("No se pudo conectar para verificar URLs")
                return False
            
            cursor = connection.cursor()
            cursor.execute("""
                SELECT crew_id, imagen 
                FROM tripulantes 
                WHERE estatus = 1 AND imagen IS NOT NULL AND imagen != ''
                LIMIT 1
            """)
            sample = cursor.fetchone()
            cursor.close()
            
            if not sample:
                self.log_warning("No hay tripulantes con imagen para probar URLs")
                return True
            
            # Construir URL de prueba
            test_url = f"{settings.IMAGE_BASE_URL}/{sample['crew_id']}/{sample['imagen']}"
            
            try:
                response = requests.head(test_url, timeout=10)
                if response.status_code == 200:
                    self.log_success(f"URL de imagen accesible: {test_url}")
                    return True
                else:
                    self.log_error(f"URL no accesible (HTTP {response.status_code}): {test_url}")
                    return False
                    
            except requests.exceptions.RequestException as e:
                self.log_error(f"Error al acceder URL: {str(e)}")
                return False
            
        except Exception as e:
            self.log_error(f"Error al verificar URLs: {str(e)}")
            return False
        finally:
            close_connection(connection)
    
    def verify_dependencies(self) -> bool:
        """Verifica que las dependencias estén instaladas"""
        logger.info("🔍 Verificando dependencias...")
        
        required_modules = [
            'deepface', 'numpy', 'opencv-python', 'requests',
            'pymysql', 'scipy', 'tensorflow'
        ]
        
        missing_modules = []
        for module in required_modules:
            try:
                if module == 'opencv-python':
                    __import__('cv2')
                else:
                    __import__(module.replace('-', '_'))
            except ImportError:
                missing_modules.append(module)
        
        if missing_modules:
            self.log_error(f"Módulos faltantes: {', '.join(missing_modules)}")
            self.log_error("Ejecute: pip install -r requirements.txt")
            return False
        else:
            self.log_success("Todas las dependencias están instaladas")
            return True
    
    def verify_directories(self) -> bool:
        """Verifica que existan los directorios necesarios"""
        logger.info("🔍 Verificando directorios...")
        
        required_dirs = [
            settings.TEMP_UPLOAD_PATH,
            'logs'
        ]
        
        for dir_path in required_dirs:
            try:
                os.makedirs(dir_path, exist_ok=True)
                if os.path.exists(dir_path):
                    self.log_success(f"Directorio verificado: {dir_path}")
                else:
                    self.log_error(f"No se pudo crear directorio: {dir_path}")
                    return False
            except Exception as e:
                self.log_error(f"Error con directorio {dir_path}: {str(e)}")
                return False
        
        return True
    
    def check_existing_embeddings(self) -> bool:
        """Verifica embeddings existentes"""
        logger.info("🔍 Verificando embeddings existentes...")
        
        connection = None
        try:
            connection = get_db_connection()
            if not connection:
                self.log_warning("No se pudo conectar para verificar embeddings")
                return True
            
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM face_embeddings WHERE active = TRUE")
            total_embeddings = cursor.fetchone()['total']
            cursor.close()
            
            if total_embeddings == 0:
                self.log_warning("No hay embeddings faciales generados aún")
                self.log_warning("Ejecute: python generate_face_embeddings.py --all")
            else:
                self.log_success(f"Embeddings existentes: {total_embeddings}")
            
            return True
            
        except Exception as e:
            self.log_warning(f"Error al verificar embeddings: {str(e)}")
            return True
        finally:
            close_connection(connection)
    
    def run_all_checks(self) -> bool:
        """Ejecuta todas las verificaciones"""
        logger.info("="*60)
        logger.info("🚀 INICIANDO VERIFICACIÓN DEL SISTEMA")
        logger.info("="*60)
        
        checks = [
            ("Variables de entorno", self.verify_environment),
            ("Dependencias", self.verify_dependencies),
            ("Directorios", self.verify_directories),
            ("Conexión base de datos", self.verify_database_connection),
            ("Datos de tripulantes", self.verify_tripulantes_data),
            ("Acceso a imágenes", self.verify_image_url_access),
            ("Embeddings existentes", self.check_existing_embeddings),
        ]
        
        for check_name, check_func in checks:
            try:
                check_func()
            except Exception as e:
                self.log_error(f"Error en verificación '{check_name}': {str(e)}")
        
        # Resumen final
        logger.info("="*60)
        logger.info("📊 RESUMEN DE VERIFICACIÓN")
        logger.info("="*60)
        logger.info(f"✅ Verificaciones exitosas: {self.checks_passed}")
        logger.info(f"❌ Verificaciones fallidas: {self.checks_failed}")
        logger.info(f"⚠️  Advertencias: {self.warnings}")
        logger.info("="*60)
        
        if self.checks_failed == 0:
            logger.info("🎉 ¡Sistema listo para generar embeddings!")
            logger.info("💡 Ejecute: python generate_face_embeddings.py --all")
            return True
        else:
            logger.error("❌ Hay problemas que deben resolverse antes de continuar")
            return False

def main():
    """Función principal"""
    try:
        verifier = SystemVerifier()
        success = verifier.run_all_checks()
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.warning("❌ Verificación interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error crítico: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()