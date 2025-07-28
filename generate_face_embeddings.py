#!/usr/bin/env python3
"""
Script para generar face embeddings de todos los tripulantes activos.

Este script descarga las imágenes desde el servidor remoto y genera
los embeddings faciales para el sistema de reconocimiento.

Uso: python generate_face_embeddings.py [--force] [--crew-id CREW_ID]
"""

import os
import sys
import argparse
import logging
import tempfile
import requests
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin
import time

# Agregar el directorio del proyecto al path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app.core.config import settings
from app.db.database import get_db_connection, close_connection
from app.utils.face_recognition import extract_face_embedding, preprocess_image, cleanup_temp_file
from app.utils.face_embeddings import save_face_embedding, get_face_embedding_by_crew_id

# Configurar logging específico para este script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/generate_embeddings.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class EmbeddingGenerator:
    def __init__(self):
        self.base_url = settings.IMAGE_BASE_URL
        self.session = requests.Session()
        self.session.timeout = 30
        self.success_count = 0
        self.error_count = 0
        self.skipped_count = 0
        
    def get_active_tripulantes(self, crew_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Obtiene todos los tripulantes activos de la base de datos.
        
        Args:
            crew_id: Si se especifica, solo obtiene ese tripulante
            
        Returns:
            Lista de tripulantes con sus datos
        """
        connection = None
        try:
            connection = get_db_connection()
            if not connection:
                logger.error("No se pudo conectar a la base de datos")
                return []
            
            cursor = connection.cursor()
            
            if crew_id:
                query = """
                SELECT crew_id, nombres, apellidos, imagen, id_tripulante
                FROM tripulantes 
                WHERE crew_id = %s AND estatus = 1 AND imagen IS NOT NULL AND imagen != ''
                """
                cursor.execute(query, (crew_id,))
            else:
                query = """
                SELECT crew_id, nombres, apellidos, imagen, id_tripulante
                FROM tripulantes 
                WHERE estatus = 1 AND imagen IS NOT NULL AND imagen != ''
                ORDER BY crew_id
                """
                cursor.execute(query)
            
            tripulantes = cursor.fetchall()
            cursor.close()
            
            logger.info(f"Encontrados {len(tripulantes)} tripulantes activos con imagen")
            return tripulantes
            
        except Exception as e:
            logger.error(f"Error al obtener tripulantes: {str(e)}")
            return []
        finally:
            close_connection(connection)
    
    def build_image_url(self, crew_id: str, imagen: str) -> str:
        """
        Construye la URL completa de la imagen.
        
        Args:
            crew_id: ID del tripulante
            imagen: Nombre del archivo de imagen
            
        Returns:
            URL completa de la imagen
        """
        # Formato: https://echcarst.myscriptcase.com/scriptcase9/file/img/Cultura/789123/FAED(1).jpg
        return f"{self.base_url}/{crew_id}/{imagen}"
    
    def download_image(self, url: str, crew_id: str) -> Optional[str]:
        """
        Descarga una imagen desde una URL y la guarda temporalmente.
        
        Args:
            url: URL de la imagen
            crew_id: ID del tripulante (para logs)
            
        Returns:
            Ruta al archivo temporal o None si falla
        """
        temp_path = None
        try:
            logger.debug(f"Descargando imagen para crew_id {crew_id}: {url}")
            
            # Crear directorio temporal si no existe
            os.makedirs(settings.TEMP_UPLOAD_PATH, exist_ok=True)
            
            # Descargar imagen
            response = self.session.get(url, stream=True)
            response.raise_for_status()
            
            # Verificar que el contenido sea una imagen
            content_type = response.headers.get('content-type', '').lower()
            if not any(img_type in content_type for img_type in ['image/jpeg', 'image/jpg', 'image/png']):
                logger.warning(f"Tipo de contenido no válido para {crew_id}: {content_type}")
                return None
            
            # Guardar en archivo temporal
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.jpg',
                prefix=f'crew_{crew_id}_',
                dir=settings.TEMP_UPLOAD_PATH
            ) as tmp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp_file.write(chunk)
                temp_path = tmp_file.name
            
            # Verificar que el archivo se descargó correctamente
            if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                logger.error(f"Error: archivo descargado vacío para crew_id {crew_id}")
                cleanup_temp_file(temp_path)
                return None
            
            logger.debug(f"Imagen descargada exitosamente para {crew_id}: {temp_path}")
            return temp_path
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al descargar imagen para crew_id {crew_id}: {str(e)}")
            cleanup_temp_file(temp_path)
            return None
        except Exception as e:
            logger.error(f"Error inesperado al descargar imagen para crew_id {crew_id}: {str(e)}")
            cleanup_temp_file(temp_path)
            return None
    
    def process_tripulante(self, tripulante: Dict[str, Any], force: bool = False) -> bool:
        """
        Procesa un tripulante individual para generar su embedding.
        
        Args:
            tripulante: Datos del tripulante
            force: Si True, regenera el embedding aunque ya exista
            
        Returns:
            True si se procesó exitosamente, False en caso contrario
        """
        crew_id = tripulante['crew_id']
        nombres = tripulante['nombres']
        apellidos = tripulante['apellidos']
        imagen = tripulante['imagen']
        
        logger.info(f"Procesando tripulante {crew_id}: {nombres} {apellidos}")
        
        try:
            # Verificar si ya existe embedding (solo si no es forzado)
            if not force:
                existing = get_face_embedding_by_crew_id(crew_id)
                if existing:
                    logger.info(f"Embedding ya existe para {crew_id}, saltando (use --force para regenerar)")
                    self.skipped_count += 1
                    return True
            
            # Construir URL de la imagen
            image_url = self.build_image_url(crew_id, imagen)
            logger.debug(f"URL de imagen: {image_url}")
            
            # Descargar imagen
            temp_image_path = self.download_image(image_url, crew_id)
            if not temp_image_path:
                logger.error(f"No se pudo descargar la imagen para {crew_id}")
                self.error_count += 1
                return False
            
            try:
                # Preprocesar imagen para mejorar detección
                processed_image_path = preprocess_image(temp_image_path)
                
                # Extraer embedding
                embedding = extract_face_embedding(
                    processed_image_path,
                    model_name="Facenet512",
                    detector_backend="mtcnn"
                )
                
                if embedding is None:
                    logger.error(f"No se pudo extraer embedding para {crew_id}")
                    self.error_count += 1
                    return False
                
                # Guardar embedding en la base de datos
                embedding_id = save_face_embedding(
                    crew_id=crew_id,
                    embedding=embedding,
                    modelo="Facenet512",
                    confidence=1.0,
                    imagen_path=image_url
                )
                
                if embedding_id:
                    logger.info(f"✅ Embedding generado exitosamente para {crew_id} (ID: {embedding_id})")
                    self.success_count += 1
                    return True
                else:
                    logger.error(f"❌ Error al guardar embedding para {crew_id}")
                    self.error_count += 1
                    return False
                    
            finally:
                # Limpiar archivos temporales
                cleanup_temp_file(temp_image_path)
                if processed_image_path != temp_image_path:
                    cleanup_temp_file(processed_image_path)
                
        except Exception as e:
            logger.error(f"Error inesperado procesando {crew_id}: {str(e)}")
            self.error_count += 1
            return False
    
    def generate_all_embeddings(self, crew_id: Optional[str] = None, force: bool = False):
        """
        Genera embeddings para todos los tripulantes activos.
        
        Args:
            crew_id: Si se especifica, solo procesa ese tripulante
            force: Si True, regenera embeddings existentes
        """
        logger.info("🚀 Iniciando generación de face embeddings")
        logger.info(f"Base URL: {self.base_url}")
        logger.info(f"Modo forzado: {'Sí' if force else 'No'}")
        
        start_time = time.time()
        
        # Obtener tripulantes
        tripulantes = self.get_active_tripulantes(crew_id)
        
        if not tripulantes:
            logger.warning("No se encontraron tripulantes para procesar")
            return
        
        total_tripulantes = len(tripulantes)
        logger.info(f"📋 Procesando {total_tripulantes} tripulante(s)")
        
        # Procesar cada tripulante
        for i, tripulante in enumerate(tripulantes, 1):
            crew_id_actual = tripulante['crew_id']
            logger.info(f"[{i}/{total_tripulantes}] Procesando {crew_id_actual}...")
            
            try:
                self.process_tripulante(tripulante, force)
            except KeyboardInterrupt:
                logger.warning("❌ Proceso interrumpido por el usuario")
                break
            except Exception as e:
                logger.error(f"Error crítico procesando {crew_id_actual}: {str(e)}")
                self.error_count += 1
                continue
            
            # Pequeña pausa entre procesamientos
            time.sleep(0.5)
        
        # Resumen final
        end_time = time.time()
        duration = end_time - start_time
        
        logger.info("="*60)
        logger.info("📊 RESUMEN FINAL")
        logger.info("="*60)
        logger.info(f"✅ Exitosos: {self.success_count}")
        logger.info(f"❌ Errores: {self.error_count}")
        logger.info(f"⏭️  Saltados: {self.skipped_count}")
        logger.info(f"📋 Total procesados: {self.success_count + self.error_count + self.skipped_count}")
        logger.info(f"⏱️  Tiempo total: {duration:.2f} segundos")
        logger.info(f"⚡ Promedio: {duration/total_tripulantes:.2f} seg/tripulante")
        logger.info("="*60)
        
        if self.error_count > 0:
            logger.warning(f"⚠️  Se encontraron {self.error_count} errores. Revise los logs para más detalles.")
        
        if self.success_count > 0:
            logger.info(f"🎉 ¡Proceso completado! {self.success_count} embeddings generados exitosamente.")

def main():
    """Función principal del script"""
    parser = argparse.ArgumentParser(
        description="Genera face embeddings para tripulantes activos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python generate_face_embeddings.py                    # Procesar todos los tripulantes
  python generate_face_embeddings.py --force            # Regenerar todos los embeddings
  python generate_face_embeddings.py --crew-id 789123   # Procesar solo un tripulante
  python generate_face_embeddings.py --crew-id 789123 --force  # Regenerar un tripulante específico
        """
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Regenera embeddings existentes (por defecto: solo procesa nuevos)'
    )
    
    parser.add_argument(
        '--crew-id',
        type=str,
        help='Procesa solo el tripulante con este crew_id'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Habilita logging debug detallado'
    )
    
    args = parser.parse_args()
    
    # Configurar nivel de logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Modo debug habilitado")
    
    # Verificar configuración
    if not settings.IMAGE_BASE_URL:
        logger.error("❌ IMAGE_BASE_URL no está configurado en el archivo .env")
        sys.exit(1)
    
    # Crear directorio de logs si no existe
    os.makedirs('logs', exist_ok=True)
    
    try:
        # Crear generador y ejecutar
        generator = EmbeddingGenerator()
        generator.generate_all_embeddings(
            crew_id=args.crew_id,
            force=args.force
        )
        
    except KeyboardInterrupt:
        logger.warning("❌ Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error crítico: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()