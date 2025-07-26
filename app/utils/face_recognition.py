"""
Utilidades para reconocimiento facial usando DeepFace
"""
import os
import json
import numpy as np
import tempfile
import logging
from typing import Optional, List, Dict, Any, Tuple
from deepface import DeepFace
from scipy.spatial.distance import cosine
import cv2
from app.core.config import settings

logger = logging.getLogger(__name__)

class FaceRecognitionError(Exception):
    """Excepción personalizada para errores de reconocimiento facial"""
    pass

def extract_face_embedding(
    image_path: str, 
    model_name: str = "Facenet512",
    detector_backend: str = "mtcnn"
) -> Optional[np.ndarray]:
    """
    Extrae el embedding facial de una imagen.
    
    Args:
        image_path: Ruta a la imagen
        model_name: Modelo a utilizar (Facenet512, VGG-Face, etc.)
        detector_backend: Backend para detección (mtcnn, opencv, etc.)
    
    Returns:
        Vector de embedding como numpy array o None si falla
    """
    try:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Imagen no encontrada: {image_path}")
        
        logger.debug(f"Extrayendo embedding de {image_path} con modelo {model_name}")
        
        # Extraer representación facial
        embedding_objs = DeepFace.represent(
            img_path=image_path,
            model_name=model_name,
            detector_backend=detector_backend,
            enforce_detection=False,  # Más permisivo
            align=True
        )
        
        if not embedding_objs or len(embedding_objs) == 0:
            logger.warning(f"No se detectaron rostros en {image_path}")
            return None
        
        # Tomar el primer rostro detectado
        embedding = embedding_objs[0]["embedding"]
        embedding_array = np.array(embedding, dtype=np.float32)
        
        logger.debug(f"Embedding extraído exitosamente, shape: {embedding_array.shape}")
        return embedding_array
        
    except Exception as e:
        logger.error(f"Error al extraer embedding: {str(e)}")
        return None

def preprocess_image(image_path: str) -> str:
    """
    Preprocesa una imagen para mejorar la detección facial.
    
    Args:
        image_path: Ruta a la imagen original
    
    Returns:
        Ruta a la imagen procesada
    """
    try:
        # Leer imagen
        img = cv2.imread(image_path)
        if img is None:
            return image_path
        
        # Convertir a RGB (OpenCV usa BGR)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Redimensionar si es muy grande (mantener ratio)
        height, width = img_rgb.shape[:2]
        max_dimension = 1024
        
        if max(height, width) > max_dimension:
            if height > width:
                new_height = max_dimension
                new_width = int((width * max_dimension) / height)
            else:
                new_width = max_dimension
                new_height = int((height * max_dimension) / width)
            
            img_rgb = cv2.resize(img_rgb, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        # Mejorar contraste usando CLAHE
        lab = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        
        enhanced = cv2.merge([l, a, b])
        enhanced_rgb = cv2.cvtColor(enhanced, cv2.COLOR_LAB2RGB)
        
        # Guardar imagen procesada
        processed_path = f"{os.path.splitext(image_path)[0]}_processed.jpg"
        enhanced_bgr = cv2.cvtColor(enhanced_rgb, cv2.COLOR_RGB2BGR)
        cv2.imwrite(processed_path, enhanced_bgr)
        
        logger.debug(f"Imagen procesada guardada en: {processed_path}")
        return processed_path
        
    except Exception as e:
        logger.error(f"Error al procesar imagen: {str(e)}")
        return image_path  # Devolver original si hay error

def calculate_face_distance(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """
    Calcula la distancia coseno entre dos embeddings faciales.
    
    Args:
        embedding1: Primer embedding
        embedding2: Segundo embedding
    
    Returns:
        Distancia coseno (0-2, donde 0 es idéntico)
    """
    try:
        return cosine(embedding1, embedding2)
    except Exception as e:
        logger.error(f"Error al calcular distancia: {str(e)}")
        return 2.0  # Máxima distancia en caso de error

def verify_face_match(
    embedding1: np.ndarray, 
    embedding2: np.ndarray, 
    threshold: float = None
) -> Tuple[bool, float, float]:
    """
    Verifica si dos embeddings pertenecen a la misma persona.
    
    Args:
        embedding1: Primer embedding
        embedding2: Segundo embedding  
        threshold: Umbral de distancia (usa config si es None)
    
    Returns:
        Tupla (es_match, confidence, distance)
    """
    if threshold is None:
        threshold = settings.FACE_DISTANCE_THRESHOLD
    
    distance = calculate_face_distance(embedding1, embedding2)
    confidence = max(0.0, min(1.0, 1.0 - (distance / 2.0)))  # Normalizar a 0-1
    is_match = distance <= threshold and confidence >= settings.FACE_CONFIDENCE_THRESHOLD
    
    logger.debug(f"Verificación facial: distance={distance:.4f}, confidence={confidence:.4f}, match={is_match}")
    
    return is_match, confidence, distance

def save_temp_image(image_content: bytes, prefix: str = "facial_") -> str:
    """
    Guarda una imagen temporalmente para procesamiento.
    
    Args:
        image_content: Contenido binario de la imagen
        prefix: Prefijo para el nombre del archivo
    
    Returns:
        Ruta al archivo temporal
    """
    try:
        # Crear directorio temporal si no existe
        os.makedirs(settings.TEMP_UPLOAD_PATH, exist_ok=True)
        
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix='.jpg',
            prefix=prefix,
            dir=settings.TEMP_UPLOAD_PATH
        ) as tmp_file:
            tmp_file.write(image_content)
            temp_path = tmp_file.name
        
        logger.debug(f"Imagen temporal guardada: {temp_path}")
        return temp_path
        
    except Exception as e:
        logger.error(f"Error al guardar imagen temporal: {str(e)}")
        raise FaceRecognitionError(f"No se pudo guardar la imagen: {str(e)}")

def cleanup_temp_file(file_path: str):
    """
    Elimina un archivo temporal de manera segura.
    
    Args:
        file_path: Ruta al archivo a eliminar
    """
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Archivo temporal eliminado: {file_path}")
    except Exception as e:
        logger.warning(f"No se pudo eliminar archivo temporal {file_path}: {str(e)}")

def detect_faces_count(image_path: str) -> int:
    """
    Cuenta el número de rostros detectados en una imagen.
    
    Args:
        image_path: Ruta a la imagen
    
    Returns:
        Número de rostros detectados
    """
    try:
        faces = DeepFace.extract_faces(
            img_path=image_path,
            detector_backend="mtcnn",
            enforce_detection=False
        )
        count = len(faces) if faces else 0
        logger.debug(f"Rostros detectados en {image_path}: {count}")
        return count
        
    except Exception as e:
        logger.error(f"Error al detectar rostros: {str(e)}")
        return 0

def validate_image_file(image_content: bytes) -> bool:
    """
    Valida si el contenido es una imagen válida.
    
    Args:
        image_content: Contenido binario de la imagen
    
    Returns:
        True si es una imagen válida, False en caso contrario
    """
    try:
        # Verificar tamaño mínimo
        if len(image_content) < 1000:  # Muy pequeña
            return False
        
        # Verificar tamaño máximo
        if len(image_content) > settings.MAX_UPLOAD_SIZE:
            return False
        
        # Verificar headers de imagen comunes
        image_headers = [
            b'\xff\xd8\xff',  # JPEG
            b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a',  # PNG
            b'\x47\x49\x46\x38',  # GIF
        ]
        
        for header in image_headers:
            if image_content.startswith(header):
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error al validar imagen: {str(e)}")
        return False