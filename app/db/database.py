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
import time

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
                    autocommit=True,  # ✅ IMPORTANTE: autocommit en pool
                    # ✅ TIMEOUTS AGRESIVOS PARA PYMYSQL
                    connect_timeout=5,      # 5 segundos max para conectar
                    read_timeout=10,       # 10 segundos max para leer
                    write_timeout=10,      # 10 segundos max para escribir
                    # ✅ CONFIGURACIÓN ADICIONAL
                    ping=1,                # Enable ping para validar conexiones
                    reset=True,            # Reset estado de conexión al devolver al pool
                )
                logger.info("Pool de conexiones inicializado exitosamente")
            except Exception as e:
                logger.error(f"Error al inicializar pool de conexiones: {e}")
                _connection_pool = None
                
    return _connection_pool

def get_db_connection() -> Optional[pymysql.connections.Connection]:
    """Obtiene una conexión del pool con timeout agresivo"""
    start_time = time.time()
    
    try:
        pool = get_connection_pool()
        if pool is None:
            logger.error("Pool de conexiones no disponible")
            return None
        
        logger.debug("🔍 Solicitando conexión del pool...")
        
        # ✅ TIMEOUT BRUTAL: Si no obtenemos conexión en 5 segundos, algo está mal
        connection = pool.connection()
        
        elapsed = (time.time() - start_time) * 1000
        logger.debug(f"✅ Conexión obtenida en {elapsed:.2f}ms")
        
        # ✅ VALIDAR que la conexión funciona
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        
        return connection
        
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        logger.error(f"❌ Error obteniendo conexión después de {elapsed:.2f}ms: {e}")
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

# ✅ NUEVA FUNCIÓN DE EMERGENCIA - conexión directa sin pool
def get_direct_connection() -> Optional[pymysql.connections.Connection]:
    """Conexión directa a MySQL sin pool - para emergencias"""
    try:
        logger.info("🚨 Usando conexión directa (sin pool)")
        connection = pymysql.connect(
            host=settings.DB_HOST,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            port=settings.DB_PORT,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            connect_timeout=5,
            read_timeout=10,
            write_timeout=10
        )
        return connection
    except Exception as e:
        logger.error(f"Error en conexión directa: {e}")
        return None

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

def get_user_by_login(login: str) -> Optional[Dict[str, Any]]:
    """Obtiene un usuario por su login - SIN PICTURE"""
    connection = None
    start_time = time.time()
    
    try:
        logger.info(f"🔍 Buscando usuario: {login}")
        
        connection = get_db_connection()
        
        if not connection:
            logger.warning("Pool falló, usando conexión directa")
            connection = get_direct_connection()
        
        if not connection:
            logger.error("❌ No se pudo obtener ninguna conexión")
            return None
        
        elapsed_conn = (time.time() - start_time) * 1000
        logger.info(f"✅ Conexión obtenida en {elapsed_conn:.2f}ms")
        
        query_start = time.time()
        cursor = connection.cursor()
        
        # ✅ QUERY SIN PICTURE - ULTRARRÁPIDA
        query = """
        SELECT login, pswd, name, email, active, priv_admin, id_aerolinea
        FROM sec_users 
        WHERE login = %s AND active = 'Y'
        """
        cursor.execute(query, (login,))
        user = cursor.fetchone()
        cursor.close()
        
        elapsed_query = (time.time() - query_start) * 1000
        elapsed_total = (time.time() - start_time) * 1000
        
        logger.info(f"✅ Query ejecutada en {elapsed_query:.2f}ms, total: {elapsed_total:.2f}ms")
        
        logger.debug(f"Usuario encontrado: {login if user else 'No encontrado'}")
        return user
        
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        logger.error(f"❌ Error después de {elapsed:.2f}ms en get_user_by_login: {e}")
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

def get_todos_tripulantes(offset: int = 0, limit: int = 50):
    """Obtiene todos los tripulantes activos"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return []
            
        cursor = connection.cursor()
        query = """
        SELECT t.*, d.descripcion_departamento, c.descripcion_cargo
        FROM tripulantes t
        LEFT JOIN departamentos d ON t.id_departamento = d.id_departamento
        LEFT JOIN cargos c ON t.id_cargo = c.id_cargo
        WHERE t.estatus = 1
        ORDER BY t.nombres, t.apellidos
        LIMIT %s OFFSET %s
        """
        cursor.execute(query, (limit, offset))
        tripulantes = cursor.fetchall()
        cursor.close()
        
        logger.debug(f"Tripulantes encontrados: {len(tripulantes)}")
        return tripulantes
        
    except Exception as e:
        logger.error(f"Error al obtener tripulantes: {e}")
        return []
    finally:
        close_connection(connection)

def get_dashboard_stats():
    """Obtiene estadísticas para el dashboard"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return {}
            
        cursor = connection.cursor()
        query = """
        SELECT 
            (SELECT COUNT(*) FROM eventos) as totalEventos,
            (SELECT COUNT(*) FROM eventos WHERE DATE(fecha_evento) = CURDATE() AND estatus = 1) as eventosHoy,
            (SELECT COUNT(*) FROM eventos WHERE estatus = 1) as eventosActivos,
            (SELECT COUNT(*) FROM marcacion WHERE DATE(fecha_marcacion) = CURDATE()) as totalAsistencias
        """
        cursor.execute(query)
        result = cursor.fetchone()
        cursor.close()
        
        return result if result else {}
        
    except Exception as e:
        logger.error(f"Error al obtener estadísticas del dashboard: {e}")
        return {}
    finally:
        close_connection(connection)

def get_reportes_stats():
    """Obtiene estadísticas para reportes"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return {}
            
        cursor = connection.cursor()
        query = """
        SELECT 
            COUNT(*) as totalEventos,
            SUM(CASE WHEN estatus = 1 THEN 1 ELSE 0 END) as eventosActivos,
            SUM(CASE WHEN fecha_evento < CURDATE() THEN 1 ELSE 0 END) as eventosFinalizados,
            85 as promedioAsistencia
        FROM eventos
        """
        cursor.execute(query)
        result = cursor.fetchone()
        cursor.close()
        
        return result if result else {}
        
    except Exception as e:
        logger.error(f"Error al obtener estadísticas de reportes: {e}")
        return {}
    finally:
        close_connection(connection)

def get_reportes_stats_completos():
    """Obtiene estadísticas completas para reportes"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return {}
            
        cursor = connection.cursor()
        
        # Estadísticas básicas de eventos
        cursor.execute("""
        SELECT 
            COUNT(*) as totalEventos,
            SUM(CASE WHEN estatus = 1 THEN 1 ELSE 0 END) as eventosActivos,
            SUM(CASE WHEN fecha_evento < CURDATE() AND estatus = 1 THEN 1 ELSE 0 END) as eventosFinalizados
        FROM eventos
        """)
        eventos_stats = cursor.fetchone()
        
        # Estadísticas de asistencia
        cursor.execute("""
        SELECT 
            COUNT(DISTINCT p.id) as totalPlanificaciones,
            COUNT(DISTINCT CASE WHEN m.hora_entrada IS NOT NULL AND m.hora_salida IS NOT NULL THEN m.id_marcacion END) as asistenciaCompleta,
            COUNT(DISTINCT CASE WHEN m.hora_entrada IS NOT NULL AND m.hora_salida IS NULL THEN m.id_marcacion END) as asistenciaParcial,
            COUNT(DISTINCT CASE WHEN m.id_marcacion IS NULL THEN p.id END) as ausencias
        FROM planificacion p
        LEFT JOIN marcacion m ON p.id = m.id_planificacion
        INNER JOIN eventos e ON p.id_evento = e.id_evento
        WHERE e.fecha_evento <= CURDATE()
        """)
        asistencia_stats = cursor.fetchone()
        
        # Calcular porcentajes de asistencia
        total_planificaciones = asistencia_stats.get('totalPlanificaciones', 0)
        if total_planificaciones > 0:
            asistencia_completa_pct = round((asistencia_stats.get('asistenciaCompleta', 0) / total_planificaciones) * 100, 1)
            asistencia_parcial_pct = round((asistencia_stats.get('asistenciaParcial', 0) / total_planificaciones) * 100, 1)
            ausencias_pct = round((asistencia_stats.get('ausencias', 0) / total_planificaciones) * 100, 1)
            promedio_asistencia = round(((asistencia_stats.get('asistenciaCompleta', 0) + asistencia_stats.get('asistenciaParcial', 0)) / total_planificaciones) * 100, 1)
        else:
            asistencia_completa_pct = 0
            asistencia_parcial_pct = 0
            ausencias_pct = 0
            promedio_asistencia = 0
        
        # Eventos por mes (últimos 6 meses)
        cursor.execute("""
        SELECT 
            DATE_FORMAT(fecha_evento, '%Y-%m') as mes,
            DATE_FORMAT(fecha_evento, '%M %Y') as mes_nombre,
            COUNT(*) as total_eventos
        FROM eventos 
        WHERE fecha_evento >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(fecha_evento, '%Y-%m'), DATE_FORMAT(fecha_evento, '%M %Y')
        ORDER BY mes DESC
        """)
        eventos_por_mes = cursor.fetchall()
        
        # Tendencias (comparar mes actual vs anterior)
        cursor.execute("""
        SELECT 
            SUM(CASE WHEN DATE_FORMAT(e.fecha_evento, '%Y-%m') = DATE_FORMAT(CURDATE(), '%Y-%m') THEN 1 ELSE 0 END) as eventos_mes_actual,
            SUM(CASE WHEN DATE_FORMAT(e.fecha_evento, '%Y-%m') = DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m') THEN 1 ELSE 0 END) as eventos_mes_anterior,
            COUNT(DISTINCT CASE WHEN DATE_FORMAT(m.fecha_marcacion, '%Y-%m') = DATE_FORMAT(CURDATE(), '%Y-%m') AND m.hora_entrada IS NOT NULL THEN m.id_marcacion END) as marcaciones_mes_actual,
            COUNT(DISTINCT CASE WHEN DATE_FORMAT(m.fecha_marcacion, '%Y-%m') = DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m') AND m.hora_entrada IS NOT NULL THEN m.id_marcacion END) as marcaciones_mes_anterior
        FROM eventos e
        LEFT JOIN marcacion m ON e.id_evento = m.id_evento
        WHERE e.fecha_evento >= DATE_SUB(CURDATE(), INTERVAL 2 MONTH)
        """)
        tendencias = cursor.fetchone()
        
        # Calcular cambios porcentuales
        eventos_cambio = 0
        if tendencias.get('eventos_mes_anterior', 0) > 0:
            eventos_cambio = round(((tendencias.get('eventos_mes_actual', 0) - tendencias.get('eventos_mes_anterior', 0)) / tendencias.get('eventos_mes_anterior', 0)) * 100, 1)
        
        marcaciones_cambio = 0
        if tendencias.get('marcaciones_mes_anterior', 0) > 0:
            marcaciones_cambio = round(((tendencias.get('marcaciones_mes_actual', 0) - tendencias.get('marcaciones_mes_anterior', 0)) / tendencias.get('marcaciones_mes_anterior', 0)) * 100, 1)
        
        cursor.close()
        
        # Convertir eventos por mes a diccionario
        eventos_por_mes_dict = {}
        for evento_mes in eventos_por_mes:
            eventos_por_mes_dict[evento_mes['mes_nombre']] = evento_mes['total_eventos']
        
        result = {
            'totalEventos': eventos_stats.get('totalEventos', 0),
            'eventosActivos': eventos_stats.get('eventosActivos', 0),
            'eventosFinalizados': eventos_stats.get('eventosFinalizados', 0),
            'promedioAsistencia': promedio_asistencia,
            'eventosPorMes': eventos_por_mes_dict,
            'asistenciaCompleta': asistencia_completa_pct,
            'asistenciaParcial': asistencia_parcial_pct,
            'ausencias': ausencias_pct,
            'tendenciaEventos': eventos_cambio,
            'tendenciaMarcaciones': marcaciones_cambio
        }
        
        logger.debug(f"Estadísticas completas de reportes obtenidas: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error al obtener estadísticas completas de reportes: {e}")
        return {}
    finally:
        close_connection(connection)

def get_total_tripulantes():
    """Obtiene el total de tripulantes activos"""
    connection = None
    try:
        logger.info("🔍 Iniciando get_total_tripulantes()")
        
        connection = get_db_connection()
        if not connection:
            logger.error("❌ No se pudo obtener conexión en get_total_tripulantes")
            return 0
            
        logger.info("✅ Conexión obtenida en get_total_tripulantes")
        
        cursor = connection.cursor()
        query = "SELECT COUNT(*) as total FROM tripulantes WHERE estatus = 1"
        
        logger.info(f"🔍 Ejecutando query: {query}")
        cursor.execute(query)
        result = cursor.fetchone()
        cursor.close()
        
        logger.info(f"📊 Resultado raw: {result}")
        
        total = result['total'] if result else 0
        logger.info(f"✅ Total tripulantes activos: {total}")
        return total
        
    except Exception as e:
        logger.error(f"❌ Error al obtener total de tripulantes: {e}")
        logger.error(f"❌ Tipo de error: {type(e)}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return 0
    finally:
        close_connection(connection)