"""
Gestión de conexiones a la base de datos MySQL para CulturaConnect.
Incluye pooling de conexiones y funciones de base de datos específicas.
"""
import pymysql
import logging
from typing import Optional, Dict, Any, List
from dbutils.pooled_db import PooledDB
import threading
from datetime import date
from app.core.config import settings
import base64

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
        SELECT login, pswd, name, email, active, priv_admin, id_aerolinea, picture
        FROM sec_users 
        WHERE login = %s AND active = 'Y'
        """
        cursor.execute(query, (login,))
        user = cursor.fetchone()
        cursor.close()
        
        if user and user.get('picture'):
            # Convertir bytes a base64 si es necesario
            if isinstance(user['picture'], bytes):
                user['picture'] = base64.b64encode(user['picture']).decode('utf-8')
            # Si ya es string, dejarlo como está
            elif not isinstance(user['picture'], str):
                user['picture'] = None
        
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
            e.descripcion_evento, e.id_departamento, e.estatus,
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

def get_todos_eventos(offset: int = 0, limit: int = 20, filtro_fecha: str = None) -> List[Dict[str, Any]]:
    """Obtiene todos los eventos con paginación y filtros opcionales"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return []
            
        cursor = connection.cursor()
        
        # Query base
        query = """
        SELECT 
            e.id_evento, e.fecha_evento, e.hora_inicio, e.hora_fin,
            e.descripcion_evento, e.id_departamento, e.estatus,
            l.descripcion_lugar, d.descripcion_departamento,
            p.descripcion as pais_nombre
        FROM eventos e
        LEFT JOIN lugar_evento l ON e.id_lugar = l.id_lugar_evento
        LEFT JOIN departamentos d ON e.id_departamento = d.id_departamento
        LEFT JOIN paises p ON e.id_pais = p.id_pais
        WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros de fecha
        if filtro_fecha == 'presente':
            query += " AND DATE(e.fecha_evento) = CURDATE()"
        elif filtro_fecha == 'futuro':
            query += " AND DATE(e.fecha_evento) > CURDATE()"
        elif filtro_fecha == 'pasado':
            query += " AND DATE(e.fecha_evento) < CURDATE()"
        
        query += " ORDER BY e.fecha_evento DESC, e.hora_inicio ASC"
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        eventos = cursor.fetchall()
        cursor.close()
        
        logger.debug(f"Eventos encontrados: {len(eventos)} (offset: {offset}, limit: {limit})")
        return eventos
        
    except Exception as e:
        logger.error(f"Error al obtener eventos: {e}")
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
            p.id, p.id_evento, p.id_tripulante, t.crew_id,
            p.fecha_vuelo, p.hora_entrada, p.hora_salida, p.estatus,
            t.nombres, t.apellidos, t.identidad, t.imagen,
            e.descripcion_evento, e.fecha_evento,
            l.descripcion_lugar,
            m.hora_entrada as marcacion_hora_entrada,
            m.hora_salida as marcacion_hora_salida,
            m.procesado,
            CASE 
                WHEN p.estatus = 'R' THEN 1
                WHEN m.procesado = 1 THEN 1
                ELSE 0
            END as procesado_final
        FROM planificacion p
        INNER JOIN tripulantes t ON p.id_tripulante = t.id_tripulante
        INNER JOIN eventos e ON p.id_evento = e.id_evento
        LEFT JOIN lugar_evento l ON p.id_lugar = l.id_lugar_evento
        LEFT JOIN marcacion m ON p.id = m.id_planificacion
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

def verificar_marcacion_existente(id_tripulante: int, id_evento: int, fecha: date) -> Optional[Dict[str, Any]]:
    """Verifica si ya existe una marcación para el tripulante en el evento y fecha específicos"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        query = """
        SELECT id_marcacion, hora_entrada, hora_salida, tipo_marcacion
        FROM marcacion 
        WHERE id_tripulante = %s AND id_evento = %s AND fecha_marcacion = %s
        LIMIT 1
        """
        cursor.execute(query, (id_tripulante, id_evento, fecha))
        marcacion = cursor.fetchone()
        cursor.close()
        
        return marcacion
        
    except Exception as e:
        logger.error(f"Error al verificar marcación existente: {e}")
        return None
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

def update_marcacion(marcacion_id: int, marcacion_data: Dict[str, Any]) -> Optional[int]:
    """Actualiza una marcación existente"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        
        # Construir query de actualización dinámicamente
        update_fields = []
        params = []
        
        for field, value in marcacion_data.items():
            if field not in ['id_marcacion'] and value is not None:
                update_fields.append(f"{field} = %s")
                params.append(value)
        
        if not update_fields:
            return marcacion_id
            
        query = f"""
        UPDATE marcacion 
        SET {', '.join(update_fields)}
        WHERE id_marcacion = %s
        """
        params.append(marcacion_id)
        
        cursor.execute(query, params)
        connection.commit()
        cursor.close()
        
        logger.info(f"Marcación actualizada ID: {marcacion_id}")
        return marcacion_id
        
    except Exception as e:
        logger.error(f"Error al actualizar marcación: {e}")
        if connection:
            connection.rollback()
        return None
    finally:
        close_connection(connection)

def get_marcacion_reciente_tripulante(id_tripulante: int, id_evento: int) -> Optional[Dict[str, Any]]:
    """Obtiene la marcación más reciente de un tripulante para un evento"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return None
            
        cursor = connection.cursor()
        query = """
        SELECT id_marcacion, fecha_marcacion, hora_entrada, hora_salida, tipo_marcacion
        FROM marcacion 
        WHERE id_tripulante = %s AND id_evento = %s
        ORDER BY fecha_marcacion DESC, hora_marcacion DESC
        LIMIT 1
        """
        cursor.execute(query, (id_tripulante, id_evento))
        marcacion = cursor.fetchone()
        cursor.close()
        
        return marcacion
        
    except Exception as e:
        logger.error(f"Error al obtener marcación reciente: {e}")
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

def update_planificacion_estatus(id_planificacion: int, nuevo_estatus: str) -> bool:
    """Actualiza el estatus de una planificación"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return False
            
        cursor = connection.cursor()
        
        query = """
        UPDATE planificacion 
        SET estatus = %s
        WHERE id = %s
        """
        
        cursor.execute(query, (nuevo_estatus, id_planificacion))
        rows_affected = cursor.rowcount
        connection.commit()
        cursor.close()
        
        if rows_affected > 0:
            logger.info(f"Estatus de planificación {id_planificacion} actualizado a {nuevo_estatus}")
            return True
        else:
            logger.warning(f"No se pudo actualizar estatus de planificación {id_planificacion}")
            return False
        
    except Exception as e:
        logger.error(f"Error al actualizar estatus de planificación: {e}")
        if connection:
            connection.rollback()
        return False
    finally:
        close_connection(connection)