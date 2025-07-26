"""
Endpoints de reconocimiento facial
"""
import logging
import asyncio
import time
from datetime import datetime, date
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
    get_tripulante_by_field, get_planificacion_evento, create_marcacion
)
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/recognize", response_model=FacialRecognitionResponse)
async def recognize_face_and_mark_attendance(
    photo: UploadFile = File(...),
    id_evento: int = Form(...),
    latitud: Optional[float] = Form(0.0),
    longitud: Optional[float] = Form(0.0),
    usar_geolocalizacion: bool = Form(True),
    tipo_geolocalizacion: str = Form("verificar"),
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
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se detectó ningún rostro en la imagen. Asegúrese de que su rostro esté bien iluminado y visible."
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
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo procesar el rostro. Mejore la iluminación y posición frontal."
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
                detail="Rostro no reconocido. Verifique que esté registrado en el sistema."
            )
        
        best_match = matches[0]
        confidence = best_match['confidence']
        
        # Verificar confianza mínima
        if confidence < settings.FACE_CONFIDENCE_THRESHOLD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reconocimiento insuficiente. Mejore la iluminación y posición frontal."
            )
        
        # Verificar ambigüedad entre matches
        if len(matches) > 1:
            second_confidence = matches[1]['confidence']
            if (confidence - second_confidence) < 0.10:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Rostro ambiguo. Mejore la iluminación y posición frontal."
                )
        
        # Obtener información del tripulante
        crew_id = best_match['crew_id']
        tripulante = get_tripulante_by_field('crew_id', crew_id)
        
        if not tripulante:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tripulante reconocido pero no encontrado en el sistema."
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
                detail=f"El tripulante no está planificado para este evento."
            )
        
        planificacion_actual = planificacion[0]
        
        # TODO: Aquí se puede agregar validación de geolocalización si es necesario
        # if usar_geolocalizacion:
        #     # Implementar lógica de geolocalización
        #     pass
        
        # Determinar tipo de marcación (entrada o salida)
        fecha_actual = date.today()
        hora_actual = datetime.now().time()
        
        # Verificar si ya tiene marcación de entrada para hoy
        # (simplificado - en producción revisar la lógica completa)
        tipo_marcacion = 1  # Por defecto entrada
        
        # Crear datos de marcación
        marcacion_data = {
            'id_planificacion': planificacion_actual['id'],
            'id_evento': id_evento,
            'id_tripulante': tripulante['id_tripulante'],
            'crew_id': crew_id,
            'fecha_marcacion': fecha_actual,
            'hora_entrada': hora_actual if tipo_marcacion == 1 else None,
            'hora_salida': hora_actual if tipo_marcacion == 2 else None,
            'hora_marcacion': hora_actual,
            'lugar_marcacion': planificacion_actual.get('id_lugar', 1),
            'punto_control': 1,
            'procesado': '0',
            'tipo_marcacion': tipo_marcacion,
            'usuario': current_user.login,
            'transporte': 0.00,
            'alimentacion': 0.00
        }
        
        # Guardar marcación
        marcacion_id = create_marcacion(marcacion_data)
        if not marcacion_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al registrar la marcación."
            )
        
        # Preparar respuesta
        processing_time = time.time() - start_time
        tipo_texto = "Entrada" if tipo_marcacion == 1 else "Salida"
        
        tripulante_info = {
            'crew_id': crew_id,
            'nombres': tripulante['nombres'],
            'apellidos': tripulante['apellidos'],
            'nombre_completo': f"{tripulante['nombres']} {tripulante['apellidos']}",
            'departamento': tripulante['descripcion_departamento'],
            'cargo': tripulante['descripcion_cargo']
        }
        
        marcacion_info = {
            'id_marcacion': marcacion_id,
            'tipo_marcacion': tipo_texto,
            'fecha': fecha_actual.isoformat(),
            'hora': hora_actual.strftime('%H:%M:%S'),
            'evento': planificacion_actual.get('descripcion_evento', 'N/A')
        }
        
        message = f"{tipo_texto} registrada para {tripulante['nombres']} {tripulante['apellidos']} a las {hora_actual.strftime('%I:%M:%S %p')}"
        
        logger.info(f"Reconocimiento exitoso: {crew_id} - {message}")
        
        return FacialRecognitionResponse(
            success=True,
            message=message,
            tripulante_info=tripulante_info,
            marcacion_info=marcacion_info,
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