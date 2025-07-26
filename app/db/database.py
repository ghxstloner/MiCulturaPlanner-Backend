"""
Gestión de conexiones a la base de datos MySQL para CulturaConnect.
Incluye pooling de conexiones y funciones de base de datos específicas.
"""
import pymysql
import logging
from typing import Optional, Dict, Any, List
from dbutils.pooled_db import PooledDB
import threading
from app.core.config import settings

logger = logging.getLogger(__name__)

# Pool de conexiones global
_connection_pool = None
_pool_lock = threading.Lock()

def get_connection_pool() -> Optional[PooledDB]:
    """Obtiene o crea el pool de conexiones de manera thread-safe"""
    global _connection_pool
    
    with _pool_lock:
        if _connection_pool is None:
            try:
                logger.info("Inicializando pool de conexiones a la base de datos")
                _connection_pool = PooledDB(
                    creator=pymysql,
                    maxconnections=20,
                    mincached=2,
                    maxcached=5,
                    blocking=True,
                    host=settings.DB_HOST,
                    user=settings.DB_USER,
                    password=settings.DB_PASSWORD,
                    database=settings.DB_NAME,
                    port=settings.DB_PORT,
                    charset='utf8mb4',
                    cursorclass=pymysql.cursors.DictCursor,
                    autocommit=False
                )
                logger.info("Pool de conexiones inicializado exitosamente")
            except Exception as e:
                logger.error(f"Error al inicializar pool de conexiones: {e}")
                _connection_pool = None
                
    return _connection_pool

def get_db_connection() -> Optional[pymysql.connections.Connection]:
    """Obtiene una conexión del pool"""
    try:
        pool = get_connection_pool()
        if pool is None:
            logger.error("Pool de conexiones no disponible")
            return None
            
        connection = pool.connection()
        logger.debug("Conexión obtenida del pool")
        return connection
        
    except Exception as e:
        logger.error(f"Error al obtener conexión del pool: {e}")
        return None

def close_connection(connection: Optional[pymysql.connections.Connection]):
    """Cierra una conexión de manera segura"""
    if connection:
        try:
            if not connection._closed:
                connection.close()
                logger.debug("Conexión cerrada y devuelta al pool")
        except Exception as e:
            logger.warning(f"Error al cerrar conexión: {e}")

def test_connection() -> bool:
    """Prueba la conexión a la base de datos"""
    connection = None
    try:
        connection = get_db_connection()
        if connection is None:
            return False
            
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        
        logger.info("Conexión a base de datos verificada exitosamente")
        return result is not None
        
    except Exception as e:
        logger.error(f"Error al probar conexión: {e}")
        return False
    finally:
        close_connection(connection)

# --- Funciones específicas del negocio ---

def get_user_by_login(login: str) -> Optional[Dict[str, Any]]:
    """Obtiene un usuario por su login"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        query = """
        SELECT login, pswd, name, email, active, priv_admin, id_aerolinea
        FROM sec_users 
        WHERE login = %s AND active = 'Y'
        """
        cursor.execute(query, (login,))
        user = cursor.fetchone()
        cursor.close()
        
        logger.debug(f"Usuario encontrado: {login if user else 'No encontrado'}")
        return user
        
    except Exception as e:
        logger.error(f"Error al obtener usuario {login}: {e}")
        return None
    finally:
        close_connection(connection)

def get_tripulante_by_field(field: str, value: Any) -> Optional[Dict[str, Any]]:
    """Obtiene un tripulante por cédula, crew_id o id"""
    if field not in ['identidad', 'crew_id', 'id_tripulante']:
        raise ValueError(f"Campo {field} no válido")
        
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        query = f"""
        SELECT 
            t.id_tripulante, t.crew_id, t.nombres, t.apellidos, 
            t.identidad, t.email, t.celular, t.imagen, t.estatus,
            t.id_departamento, t.id_cargo,
            d.descripcion_departamento, c.descripcion_cargo
        FROM tripulantes t
        LEFT JOIN departamentos d ON t.id_departamento = d.id_departamento
        LEFT JOIN cargos c ON t.id_cargo = c.id_cargo
        WHERE t.{field} = %s AND t.estatus = 1
        """
        cursor.execute(query, (value,))
        tripulante = cursor.fetchone()
        cursor.close()
        
        logger.debug(f"Tripulante encontrado por {field}={value}: {tripulante['nombres'] if tripulante else 'No encontrado'}")
        return tripulante
        
    except Exception as e:
        logger.error(f"Error al obtener tripulante por {field}={value}: {e}")
        return None
    finally:
        close_connection(connection)

def get_eventos_activos() -> List[Dict[str, Any]]:
    """Obtiene eventos activos"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return []
            
        cursor = connection.cursor()
        query = """
        SELECT 
            e.id_evento, e.fecha_evento, e.hora_inicio, e.hora_fin,
            e.descripcion_evento, e.id_departamento,
            l.descripcion_lugar, d.descripcion_departamento,
            p.descripcion as pais_nombre
        FROM eventos e
        LEFT JOIN lugar_evento l ON e.id_lugar = l.id_lugar_evento
        LEFT JOIN departamentos d ON e.id_departamento = d.id_departamento
        LEFT JOIN paises p ON e.id_pais = p.id_pais
        WHERE e.estatus = 1
        ORDER BY e.fecha_evento DESC, e.hora_inicio ASC
        """
        cursor.execute(query)
        eventos = cursor.fetchall()
        cursor.close()
        
        logger.debug(f"Eventos activos encontrados: {len(eventos)}")
        return eventos
        
    except Exception as e:
        logger.error(f"Error al obtener eventos activos: {e}")
        return []
    finally:
        close_connection(connection)

def get_planificacion_evento(id_evento: int, id_tripulante: int = None) -> List[Dict[str, Any]]:
    """Obtiene la planificación de un evento"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return []
            
        cursor = connection.cursor()
        base_query = """
        SELECT 
            p.id, p.id_evento, p.id_tripulante, p.crew_id,
            p.fecha_vuelo, p.hora_entrada, p.hora_salida, p.estatus,
            t.nombres, t.apellidos, t.identidad,
            e.descripcion_evento, e.fecha_evento,
            l.descripcion_lugar
        FROM planificacion p
        INNER JOIN tripulantes t ON p.id_tripulante = t.id_tripulante
        INNER JOIN eventos e ON p.id_evento = e.id_evento
        LEFT JOIN lugar_evento l ON p.id_lugar = l.id_lugar_evento
        WHERE p.id_evento = %s
        """
        
        params = [id_evento]
        if id_tripulante:
            base_query += " AND p.id_tripulante = %s"
            params.append(id_tripulante)
            
        base_query += " ORDER BY p.hora_entrada ASC"
        
        cursor.execute(base_query, params)
        planificacion = cursor.fetchall()
        cursor.close()
        
        logger.debug(f"Planificación encontrada para evento {id_evento}: {len(planificacion)} registros")
        return planificacion
        
    except Exception as e:
        logger.error(f"Error al obtener planificación del evento {id_evento}: {e}")
        return []
    finally:
        close_connection(connection)

def create_marcacion(marcacion_data: Dict[str, Any]) -> Optional[int]:
    """Crea una nueva marcación"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        
        query = """
        INSERT INTO marcacion (
            id_planificacion, id_evento, id_tripulante, crew_id,
            fecha_marcacion, hora_entrada, hora_salida, hora_marcacion,
            lugar_marcacion, punto_control, procesado, tipo_marcacion,
            usuario, transporte, alimentacion
        ) VALUES (
            %(id_planificacion)s, %(id_evento)s, %(id_tripulante)s, %(crew_id)s,
            %(fecha_marcacion)s, %(hora_entrada)s, %(hora_salida)s, %(hora_marcacion)s,
            %(lugar_marcacion)s, %(punto_control)s, %(procesado)s, %(tipo_marcacion)s,
            %(usuario)s, %(transporte)s, %(alimentacion)s
        )
        """
        
        cursor.execute(query, marcacion_data)
        marcacion_id = cursor.lastrowid
        connection.commit()
        cursor.close()
        
        logger.info(f"Marcación creada con ID: {marcacion_id}")
        return marcacion_id
        
    except Exception as e:
        logger.error(f"Error al crear marcación: {e}")
        if connection:
            connection.rollback()
        return None
    finally:
        close_connection(connection)

def get_marcaciones_recientes(limit: int = 10) -> List[Dict[str, Any]]:
    """Obtiene las marcaciones más recientes"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return []
            
        cursor = connection.cursor()
        query = """
        SELECT 
            m.id_marcacion, m.crew_id, m.fecha_marcacion, 
            m.hora_entrada, m.hora_salida, m.tipo_marcacion,
            t.nombres, t.apellidos,
            e.descripcion_evento,
            l.descripcion_lugar
        FROM marcacion m
        INNER JOIN tripulantes t ON m.id_tripulante = t.id_tripulante
        INNER JOIN eventos e ON m.id_evento = e.id_evento
        LEFT JOIN lugar_evento l ON m.lugar_marcacion = l.id_lugar_evento
        ORDER BY m.fecha_marcacion DESC, 
                 GREATEST(IFNULL(m.hora_entrada, '00:00:00'), 
                         IFNULL(m.hora_salida, '00:00:00')) DESC
        LIMIT %s
        """
        cursor.execute(query, (limit,))
        marcaciones = cursor.fetchall()
        cursor.close()
        
        logger.debug(f"Marcaciones recientes obtenidas: {len(marcaciones)}")
        return marcaciones
        
    except Exception as e:
        logger.error(f"Error al obtener marcaciones recientes: {e}")
        return []
    finally:
        close_connection(connection)