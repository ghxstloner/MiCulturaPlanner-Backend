"""
Gestión de embeddings faciales en la base de datos
"""
import json
import numpy as np
import logging
from typing import Optional, List, Dict, Any
from app.db.database import get_db_connection, close_connection
from app.utils.face_recognition import calculate_face_distance
from app.core.config import settings

logger = logging.getLogger(__name__)

def save_face_embedding(
    crew_id: str,
    embedding: np.ndarray,
    modelo: str = "Facenet512",
    confidence: float = 1.0,
    imagen_path: Optional[str] = None
) -> Optional[int]:
    """
    Guarda un embedding facial en la base de datos.
    
    Args:
        crew_id: ID del tripulante
        embedding: Vector de embedding facial
        modelo: Modelo utilizado para generar el embedding
        confidence: Confianza del embedding (0-1)
        imagen_path: Ruta a la imagen original
    
    Returns:
        ID del embedding guardado o None si hay error
    """
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            logger.error("No se pudo obtener conexión a la base de datos")
            return None
        
        cursor = connection.cursor()
        
        # Convertir embedding a JSON
        embedding_json = json.dumps(embedding.tolist())
        
        # Verificar si ya existe un embedding para este crew_id
        check_query = """
        SELECT id FROM face_embeddings 
        WHERE crew_id = %s AND active = TRUE 
        LIMIT 1
        """
        cursor.execute(check_query, (crew_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Actualizar embedding existente
            update_query = """
            UPDATE face_embeddings 
            SET embedding = %s, modelo = %s, confidence = %s, 
                imagen_path = %s, updated_at = NOW()
            WHERE id = %s
            """
            cursor.execute(update_query, (
                embedding_json, modelo, confidence, 
                imagen_path, existing['id']
            ))
            embedding_id = existing['id']
            logger.info(f"Embedding actualizado para crew_id {crew_id}")
            
        else:
            # Crear nuevo embedding
            insert_query = """
            INSERT INTO face_embeddings 
            (crew_id, embedding, modelo, confidence, imagen_path, active, created_at) 
            VALUES (%s, %s, %s, %s, %s, TRUE, NOW())
            """
            cursor.execute(insert_query, (
                crew_id, embedding_json, modelo, confidence, imagen_path
            ))
            embedding_id = cursor.lastrowid
            logger.info(f"Nuevo embedding creado para crew_id {crew_id}")
        
        connection.commit()
        cursor.close()
        return embedding_id
        
    except Exception as e:
        logger.error(f"Error al guardar embedding para {crew_id}: {str(e)}")
        if connection:
            connection.rollback()
        return None
    finally:
        close_connection(connection)

def find_best_face_matches(
    query_embedding: np.ndarray,
    threshold: float = None,
    limit: int = None
) -> List[Dict[str, Any]]:
    """
    Busca las mejores coincidencias faciales en la base de datos.
    
    Args:
        query_embedding: Embedding a comparar
        threshold: Umbral de distancia (usa config si es None)
        limit: Número máximo de resultados (usa config si es None)
    
    Returns:
        Lista de coincidencias ordenadas por similitud
    """
    if threshold is None:
        threshold = settings.FACE_DISTANCE_THRESHOLD
    if limit is None:
        limit = settings.MAX_FACE_MATCHES
    
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            logger.error("No se pudo obtener conexión a la base de datos")
            return []
        
        cursor = connection.cursor()
        
        # Obtener todos los embeddings activos
        query = """
        SELECT fe.id, fe.crew_id, fe.embedding, fe.confidence,
               t.nombres, t.apellidos, t.id_tripulante
        FROM face_embeddings fe
        INNER JOIN tripulantes t ON fe.crew_id = t.crew_id
        WHERE fe.active = TRUE AND t.estatus = 1
        """
        cursor.execute(query)
        stored_embeddings = cursor.fetchall()
        cursor.close()
        
        if not stored_embeddings:
            logger.warning("No se encontraron embeddings activos en la base de datos")
            return []
        
        matches = []
        
        # Comparar con cada embedding almacenado
        for record in stored_embeddings:
            try:
                stored_embedding_json = record['embedding']
                if isinstance(stored_embedding_json, bytes):
                    stored_embedding_json = stored_embedding_json.decode('utf-8')
                
                stored_embedding = np.array(json.loads(stored_embedding_json), dtype=np.float32)
                
                # Verificar dimensiones compatibles
                if stored_embedding.shape != query_embedding.shape:
                    logger.warning(f"Dimensiones incompatibles para crew_id {record['crew_id']}")
                    continue
                
                # Calcular distancia
                distance = calculate_face_distance(query_embedding, stored_embedding)
                confidence = max(0.0, min(1.0, 1.0 - (distance / 2.0)))
                
                # Solo incluir si cumple el umbral
                if distance <= threshold:
                    matches.append({
                        'embedding_id': record['id'],
                        'crew_id': record['crew_id'],
                        'id_tripulante': record['id_tripulante'],
                        'nombres': record['nombres'],
                        'apellidos': record['apellidos'],
                        'distance': float(distance),
                        'confidence': float(confidence),
                        'stored_confidence': float(record['confidence'])
                    })
                
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.warning(f"Error al procesar embedding para crew_id {record.get('crew_id', 'unknown')}: {str(e)}")
                continue
        
        # Ordenar por menor distancia (mayor similitud)
        matches.sort(key=lambda x: x['distance'])
        
        # Limitar resultados
        result = matches[:limit] if limit else matches
        
        logger.info(f"Encontradas {len(result)} coincidencias faciales de {len(stored_embeddings)} embeddings")
        
        return result
        
    except Exception as e:
        logger.error(f"Error en búsqueda de coincidencias faciales: {str(e)}")
        return []
    finally:
        close_connection(connection)

def get_face_embedding_by_crew_id(crew_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene el embedding facial de un tripulante específico.
    
    Args:
        crew_id: ID del tripulante
    
    Returns:
        Datos del embedding o None si no existe
    """
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return None
        
        cursor = connection.cursor()
        query = """
        SELECT id, crew_id, embedding, modelo, confidence, 
               active, created_at, updated_at
        FROM face_embeddings 
        WHERE crew_id = %s AND active = TRUE
        LIMIT 1
        """
        cursor.execute(query, (crew_id,))
        result = cursor.fetchone()
        cursor.close()
        
        return result
        
    except Exception as e:
        logger.error(f"Error al obtener embedding para crew_id {crew_id}: {str(e)}")
        return None
    finally:
        close_connection(connection)

def deactivate_face_embedding(crew_id: str) -> bool:
    """
    Desactiva el embedding facial de un tripulante.
    
    Args:
        crew_id: ID del tripulante
    
    Returns:
        True si se desactivó exitosamente, False en caso contrario
    """
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        query = """
        UPDATE face_embeddings 
        SET active = FALSE, updated_at = NOW()
        WHERE crew_id = %s AND active = TRUE
        """
        affected_rows = cursor.execute(query, (crew_id,))
        connection.commit()
        cursor.close()
        
        if affected_rows > 0:
            logger.info(f"Embedding desactivado para crew_id {crew_id}")
            return True
        else:
            logger.warning(f"No se encontró embedding activo para crew_id {crew_id}")
            return False
        
    except Exception as e:
        logger.error(f"Error al desactivar embedding para crew_id {crew_id}: {str(e)}")
        if connection:
            connection.rollback()
        return False
    finally:
        close_connection(connection)

def create_face_embeddings_table():
    """
    Crea la tabla face_embeddings si no existe.
    Esta función se puede ejecutar al iniciar la aplicación.
    """
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            logger.error("No se pudo crear tabla face_embeddings: sin conexión DB")
            return False
        
        cursor = connection.cursor()
        
        create_table_query = """
        CREATE TABLE IF NOT EXISTS face_embeddings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            crew_id VARCHAR(10) NOT NULL,
            embedding LONGTEXT NOT NULL,
            modelo VARCHAR(50) DEFAULT 'Facenet512',
            confidence DECIMAL(3,2) DEFAULT 1.00,
            imagen_path VARCHAR(255),
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_crew_id (crew_id),
            INDEX idx_active (active),
            INDEX idx_crew_active (crew_id, active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
        """
        
        cursor.execute(create_table_query)
        connection.commit()
        cursor.close()
        
        logger.info("Tabla face_embeddings verificada/creada exitosamente")
        return True
        
    except Exception as e:
        logger.error(f"Error al crear tabla face_embeddings: {str(e)}")
        if connection:
            connection.rollback()
        return False
    finally:
        close_connection(connection)