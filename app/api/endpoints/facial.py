"""
Endpoints de reconocimiento facial
"""
import logging
import asyncio
import time
from datetime import datetime, date, timedelta
from typing import Optional
from fastapi import APIRouter, File, Form, UploadFile, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from app.schemas.facial import (
    FacialRecognitionResponse, EmbeddingCreateRequest, EmbeddingCreateResponse
)
from app.schemas.responses import StandardResponse
from app.utils.auth import get_current_active_user
from app.models.user import User
from app.utils.face_recognition import (
    extract_face_embedding, save_temp_image, cleanup_temp_file, 
    validate_image_file, detect_faces_count
)
from app.utils.face_embeddings import (
    save_face_embedding, find_best_face_matches, get_face_embedding_by_crew_id
)
from app.db.database import (
    get_tripulante_by_field, get_planificacion_evento, create_marcacion, 
    verificar_marcacion_existente, get_marcacion_reciente_tripulante,
    update_planificacion_estatus
)
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

def format_time_field(time_field):
    """Convierte timedelta o time a string HH:MM:S"""
    if time_field is None:
        return None
    
    if isinstance(time_field, timedelta):
        total_seconds = int(time_field.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        try:
            return time_field.strftime('%H:%M:%S')
        except AttributeError:
            return str(time_field)

def format_time_display(time_field):
    """Convierte a formato 12 horas con AM/PM"""
    if time_field is None:
        return 'N/A'
    
    if isinstance(time_field, timedelta):
        total_seconds = int(time_field.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours == 0:
            hour_12 = 12
            am_pm = 'AM'
        elif hours < 12:
            hour_12 = hours
            am_pm = 'AM'
        elif hours == 12:
            hour_12 = 12
            am_pm = 'PM'
        else:
            hour_12 = hours - 12
            am_pm = 'PM'
            
        return f"{hour_12:02d}:{minutes:02d}:{seconds:02d} {am_pm}"
    else:
        try:
            return time_field.strftime('%I:%M:%S %p')
        except AttributeError:
            return str(time_field)

@router.post("/recognize", response_model=FacialRecognitionResponse)
async def recognize_face_and_mark_attendance(
    photo: UploadFile = File(...),
    id_evento: int = Form(...),
    current_user: User = Depends(get_current_active_user)
):
    """
    Reconoce un rostro y registra la marcación de asistencia
    """
    start_time = time.time()
    temp_file_path = None
    
    try:
        logger.info(f"Iniciando reconocimiento facial para evento {id_evento} por usuario {current_user.login}")
        
        # Validar archivo de imagen
        image_content = await photo.read()
        if not validate_image_file(image_content):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Archivo de imagen inválido o formato no soportado"
            )
        
        # Guardar imagen temporalmente
        temp_file_path = save_temp_image(image_content, "recognition_")
        
        # Verificar que hay exactamente un rostro
        faces_count = detect_faces_count(temp_file_path)
        if faces_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mejora la luz para acertar el reconocimiento facial"
            )
        elif faces_count > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se detectaron múltiples rostros. Asegúrese de que solo aparezca una persona en la imagen."
            )
        
        # Extraer embedding facial
        embedding = await asyncio.to_thread(extract_face_embedding, temp_file_path)
        if embedding is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mejora la luz para acertar el reconocimiento facial"
            )
        
        # Buscar coincidencias en la base de datos
        matches = find_best_face_matches(
            embedding, 
            threshold=settings.FACE_DISTANCE_THRESHOLD,
            limit=5
        )
        
        if not matches:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mejora la luz para acertar el reconocimiento facial"
            )
        
        best_match = matches[0]
        confidence = best_match['confidence']
        
        # Verificar confianza mínima
        if confidence < settings.FACE_CONFIDENCE_THRESHOLD:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mejora la luz para acertar el reconocimiento facial"
            )
        
        # Verificar ambigüedad entre matches
        if len(matches) > 1:
            second_confidence = matches[1]['confidence']
            if (confidence - second_confidence) < 0.10:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Mejora la luz para acertar el reconocimiento facial"
                )
        
        # Obtener información del tripulante
        crew_id = best_match['crew_id']
        tripulante = get_tripulante_by_field('crew_id', crew_id)
        
        if not tripulante:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mejora la luz para acertar el reconocimiento facial"
            )
        
        if tripulante['estatus'] != 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tripulante {tripulante['nombres']} {tripulante['apellidos']} no está activo."
            )
        
        # Verificar que esté planificado para este evento
        planificacion = get_planificacion_evento(id_evento, tripulante['id_tripulante'])
        if not planificacion:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"El colaborador {tripulante['nombres']} {tripulante['apellidos']} con la posición {crew_id} no está planificado para este evento."
            )
        
        planificacion_actual = planificacion[0]
        
        # Determinar tipo de marcación basado en marcaciones previas
        fecha_actual = date.today()
        hora_actual = datetime.now().time()
        
        # Verificar marcaciones existentes para hoy
        marcacion_existente = verificar_marcacion_existente(
            tripulante['id_tripulante'], 
            id_evento, 
            fecha_actual
        )
        
        if marcacion_existente:
            # Ya existe marcación, determinar si es entrada o salida
            if marcacion_existente.get('hora_entrada') and not marcacion_existente.get('hora_salida'):
                # Ya tiene entrada, esta será salida
                tipo_marcacion = 2
                tipo_texto = "Salida"
            else:
                # Ya tiene ambas, actualizar salida
                tipo_marcacion = 2
                tipo_texto = "Salida"
        else:
            # Primera marcación del día
            tipo_marcacion = 1
            tipo_texto = "Entrada"
        
        # Crear datos de marcación
        marcacion_data = {
            'id_planificacion': planificacion_actual['id'],
            'id_evento': id_evento,
            'id_tripulante': tripulante['id_tripulante'],
            'crew_id': crew_id,
            'fecha_marcacion': fecha_actual,
            'hora_entrada': hora_actual if tipo_marcacion == 1 else marcacion_existente.get('hora_entrada'),
            'hora_salida': hora_actual if tipo_marcacion == 2 else None,
            'hora_marcacion': hora_actual,
            'lugar_marcacion': planificacion_actual.get('id_lugar', 1),
            'punto_control': 1,
            'procesado': '1' if tipo_marcacion == 2 else '0',  # Marcar como procesado cuando es salida
            'tipo_marcacion': tipo_marcacion,
            'usuario': current_user.login,
            'transporte': 0.00,
            'alimentacion': 0.00
        }
        
        # Guardar o actualizar marcación
        if marcacion_existente:
            # Actualizar marcación existente
            from app.db.database import update_marcacion
            marcacion_id = update_marcacion(marcacion_existente['id_marcacion'], marcacion_data)
        else:
            # Crear nueva marcación
            marcacion_id = create_marcacion(marcacion_data)
        
        if not marcacion_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al registrar la marcación."
            )
        
        # Si es la segunda marcación (salida), actualizar el estatus de la planificación
        if tipo_marcacion == 2:
            # Actualizar estatus de planificación de 'P' (Pendiente) a 'R' (Realizado)
            estatus_actualizado = update_planificacion_estatus(
                planificacion_actual['id'], 
                'R'
            )
            if not estatus_actualizado:
                logger.warning(f"No se pudo actualizar estatus de planificación {planificacion_actual['id']}")
            else:
                logger.info(f"Estatus de planificación {planificacion_actual['id']} actualizado a 'R'")
        
        # Preparar respuesta con mensajes específicos
        processing_time = time.time() - start_time
        
        tripulante_info = {
            'crew_id': crew_id,
            'nombres': tripulante['nombres'],
            'apellidos': tripulante['apellidos'],
            'nombre_completo': f"{tripulante['nombres']} {tripulante['apellidos']}",
            'departamento': tripulante.get('descripcion_departamento', 'N/A'),
            'cargo': tripulante.get('descripcion_cargo', 'N/A')
        }
        
        # Formatear hora para el mensaje
        hora_formatted = format_time_display(datetime.combine(fecha_actual, hora_actual))
        
        # Crear mensaje específico según el tipo de marcación
        if tipo_marcacion == 1:
            # Primera marcación (entrada)
            message = f"Marcación a la hora de inicio del evento {hora_formatted}"
        else:
            # Segunda marcación (salida) 
            message = f"Marcación de finalización del evento"
        
        marcacion_info = {
            'id_marcacion': marcacion_id,
            'tipo_marcacion': tipo_texto,
            'fecha': fecha_actual.isoformat(),
            'hora': format_time_field(datetime.combine(fecha_actual, hora_actual)),
            'evento': planificacion_actual.get('descripcion_evento', 'N/A')
        }
        
        # Agregar matches encontrados para debug
        matches_info = []
        for match in matches:
            matches_info.append({
                'crew_id': match['crew_id'],
                'nombres': match['nombres'],
                'apellidos': match['apellidos'],
                'confidence': match['confidence'],
                'distance': match['distance'],
                'id_tripulante': match['id_tripulante']
            })
        
        logger.info(f"Reconocimiento exitoso: {crew_id} - {message}")
        
        return FacialRecognitionResponse(
            success=True,
            message=message,
            tripulante_info=tripulante_info,
            marcacion_info=marcacion_info,
            matches_found=matches_info,
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en reconocimiento facial: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor durante el reconocimiento."
        )
    finally:
        # Limpiar archivo temporal
        if temp_file_path:
            cleanup_temp_file(temp_file_path)

@router.post("/create-embedding", response_model=EmbeddingCreateResponse)
async def create_face_embedding(
    photo: UploadFile = File(...),
    crew_id: str = Form(...),
    modelo: str = Form("Facenet512"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Crea un embedding facial para un tripulante
    """
    temp_file_path = None
    
    try:
        logger.info(f"Creando embedding para crew_id {crew_id} por usuario {current_user.login}")
        
        # Verificar que el tripulante existe
        tripulante = get_tripulante_by_field('crew_id', crew_id)
        if not tripulante:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tripulante con crew_id {crew_id} no encontrado."
            )
        
        # Validar imagen
        image_content = await photo.read()
        if not validate_image_file(image_content):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Archivo de imagen inválido."
            )
        
        # Guardar temporalmente
        temp_file_path = save_temp_image(image_content, f"embedding_{crew_id}_")
        
        # Verificar un solo rostro
        faces_count = detect_faces_count(temp_file_path)
        if faces_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se detectó rostro en la imagen."
            )
        elif faces_count > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se detectaron múltiples rostros. Use una imagen con una sola persona."
            )
        
        # Extraer embedding
        embedding = await asyncio.to_thread(extract_face_embedding, temp_file_path, modelo)
        if embedding is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo extraer el embedding facial."
            )
        
        # Guardar en base de datos
        embedding_id = save_face_embedding(
            crew_id=crew_id,
            embedding=embedding,
            modelo=modelo,
            confidence=1.0,
            imagen_path=photo.filename
        )
        
        if not embedding_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al guardar el embedding en la base de datos."
            )
        
        tripulante_info = {
            'crew_id': crew_id,
            'nombres': tripulante['nombres'],
            'apellidos': tripulante['apellidos'],
            'nombre_completo': f"{tripulante['nombres']} {tripulante['apellidos']}"
        }
        
        message = f"Embedding facial creado exitosamente para {tripulante['nombres']} {tripulante['apellidos']}"
        
        logger.info(f"Embedding creado: ID {embedding_id} para crew_id {crew_id}")
        
        return EmbeddingCreateResponse(
            success=True,
            message=message,
            embedding_id=embedding_id,
            tripulante_info=tripulante_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al crear embedding: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al crear embedding."
        )
    finally:
        if temp_file_path:
            cleanup_temp_file(temp_file_path)

@router.get("/embedding/{crew_id}", response_model=StandardResponse)
async def get_embedding_info(
    crew_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtiene información del embedding de un tripulante
    """
    try:
        embedding_data = get_face_embedding_by_crew_id(crew_id)
        
        if not embedding_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró embedding para crew_id {crew_id}."
            )
        
        # Obtener info del tripulante
        tripulante = get_tripulante_by_field('crew_id', crew_id)
        
        response_data = {
            'embedding_id': embedding_data['id'],
            'crew_id': embedding_data['crew_id'],
            'modelo': embedding_data['modelo'],
            'confidence': float(embedding_data['confidence']),
            'active': embedding_data['active'],
            'created_at': embedding_data['created_at'].isoformat() if embedding_data['created_at'] else None,
            'updated_at': embedding_data['updated_at'].isoformat() if embedding_data['updated_at'] else None,
            'tripulante': {
                'nombres': tripulante['nombres'] if tripulante else 'N/A',
                'apellidos': tripulante['apellidos'] if tripulante else 'N/A'
            } if tripulante else None
        }
        
        return StandardResponse(
            success=True,
            message="Información del embedding obtenida exitosamente",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener embedding para {crew_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener información del embedding."
        )