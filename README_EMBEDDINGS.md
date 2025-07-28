# Face Embeddings Generator

Este documento explica cómo usar el sistema de generación de embeddings faciales para el reconocimiento automático de tripulantes.

## 🎯 Propósito

El sistema genera embeddings faciales para todos los tripulantes activos, permitiendo el reconocimiento automático durante el marcado de asistencia en eventos.

## 📋 Requisitos Previos

1. **Python 3.8+** instalado
2. **Entorno virtual** configurado
3. **Base de datos MySQL** con las tablas necesarias
4. **Archivo .env** configurado correctamente
5. **Conexión a internet** para descargar imágenes

## ⚙️ Configuración

### 1. Configurar Variables de Entorno

Copie el archivo de ejemplo y configure sus valores:

```bash
cp .env.example .env
```

Asegúrese de configurar especialmente:

```env
# Configuración de base de datos
DB_HOST=localhost
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña
DB_NAME=tu_base_datos

# URL base para imágenes (CRÍTICO)
IMAGE_BASE_URL=https://echcarst.myscriptcase.com/scriptcase9/file/img/Cultura
```

### 2. Verificar Estructura de URLs

Las imágenes deben seguir el formato:
```
https://echcarst.myscriptcase.com/scriptcase9/file/img/Cultura/{crew_id}/{imagen}
```

Ejemplo:
```
https://echcarst.myscriptcase.com/scriptcase9/file/img/Cultura/789123/FAED(1).jpg
```

- `789123`: crew_id del tripulante
- `FAED(1).jpg`: nombre del archivo en el campo `imagen`

## 🚀 Uso del Script

### Opción 1: Script Automatizado (Recomendado)

```bash
# Procesar todos los tripulantes nuevos
./run_embeddings.sh --all

# Regenerar todos los embeddings (sobreescribir existentes)
./run_embeddings.sh --all --force

# Procesar solo un tripulante específico
./run_embeddings.sh --crew-id 789123

# Regenerar embedding de un tripulante específico
./run_embeddings.sh --crew-id 789123 --force

# Modo debug (logging detallado)
./run_embeddings.sh --all --debug
```

### Opción 2: Script Python Directo

```bash
# Activar entorno virtual
source venv/bin/activate  # Linux/Mac
# o
.\venv\Scripts\activate   # Windows

# Ejecutar script
python generate_face_embeddings.py --help

# Ejemplos de uso
python generate_face_embeddings.py                    # Todos los nuevos
python generate_face_embeddings.py --force            # Regenerar todos
python generate_face_embeddings.py --crew-id 789123   # Solo uno
python generate_face_embeddings.py --crew-id 789123 --force  # Regenerar uno
```

## 📊 Proceso Interno

El script realiza los siguientes pasos para cada tripulante:

1. **Consulta base de datos**: Obtiene tripulantes activos con imágenes
2. **Construye URL**: Forma la URL usando crew_id + imagen
3. **Descarga imagen**: Obtiene la imagen del servidor remoto
4. **Preprocesa imagen**: Mejora calidad para mejor detección
5. **Extrae embedding**: Usa DeepFace con modelo Facenet512
6. **Guarda en BD**: Almacena el embedding en tabla `face_embeddings`
7. **Limpia archivos**: Elimina archivos temporales

## 📈 Interpretación de Resultados

### Salida Exitosa
```
[1/10] Procesando 789123...
✅ Embedding generado exitosamente para 789123 (ID: 45)
```

### Salida con Errores
```
[2/10] Procesando 789124...
❌ Error al extraer embedding para 789124
```

### Resumen Final
```
📊 RESUMEN FINAL
================
✅ Exitosos: 8
❌ Errores: 2
⏭️  Saltados: 0
📋 Total procesados: 10
⏱️  Tiempo total: 120.50 segundos
⚡ Promedio: 12.05 seg/tripulante
```

## 🔧 Solución de Problemas

### Error: "Imagen no encontrada"
**Causa**: La URL de la imagen no es accesible
**Solución**: 
- Verificar que `IMAGE_BASE_URL` esté correctamente configurado
- Comprobar que el archivo existe en el servidor
- Verificar permisos de acceso

### Error: "No se detectaron rostros"
**Causa**: La imagen no contiene rostros reconocibles
**Solución**:
- Verificar calidad de la imagen
- Asegurar que la imagen contenga un rostro claro
- Considerar usar `--force` para regenerar

### Error: "Conexión a base de datos"
**Causa**: Problemas de conectividad con MySQL
**Solución**:
- Verificar configuración en `.env`
- Comprobar que el servicio MySQL esté corriendo
- Verificar credenciales de acceso

### Error: "Módulo no encontrado"
**Causa**: Dependencias no instaladas
**Solución**:
```bash
pip install -r requirements.txt
```

## 📋 Tabla de Base de Datos

El script crea/actualiza la tabla `face_embeddings`:

```sql
CREATE TABLE face_embeddings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    crew_id VARCHAR(10) NOT NULL,
    embedding LONGTEXT NOT NULL,
    modelo VARCHAR(50) DEFAULT 'Facenet512',
    confidence DECIMAL(3,2) DEFAULT 1.00,
    imagen_path VARCHAR(255),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## 🔄 Mantenimiento

### Regeneración Periódica
Se recomienda regenerar embeddings cuando:
- Se actualicen fotos de tripulantes
- Se cambien parámetros del modelo
- Se detecten problemas de reconocimiento

### Monitoreo
Revise regularmente los logs en:
- `logs/generate_embeddings.log`: Log específico del script
- `logs/app.log`: Log general de la aplicación

### Limpieza
El script limpia automáticamente archivos temporales, pero verifique periódicamente:
- Directorio `temp_uploads/`
- Archivos con sufijo `_processed.jpg`

## 🎛️ Configuración Avanzada

### Ajustar Parámetros del Modelo

En `app/core/config.py`:

```python
# Umbrales de reconocimiento
FACE_CONFIDENCE_THRESHOLD: float = 0.70  # Mínima confianza (0-1)
FACE_DISTANCE_THRESHOLD: float = 0.4     # Máxima distancia coseno
MAX_FACE_MATCHES: int = 5                 # Máximos matches a retornar
```

### Cambiar Modelo de IA

En el script, puede cambiar el modelo usado:

```python
# Modelos disponibles: Facenet512, VGG-Face, OpenFace, etc.
extract_face_embedding(
    image_path, 
    model_name="Facenet512",  # ← Cambiar aquí
    detector_backend="mtcnn"
)
```

## 🔒 Consideraciones de Seguridad

1. **Proteger .env**: Nunca commite el archivo `.env` al repositorio
2. **Credenciales de BD**: Use credenciales específicas con permisos mínimos
3. **URLs de imágenes**: Verifique que las URLs sean confiables
4. **Logs**: Los logs pueden contener información sensible

## 📞 Soporte

Para problemas específicos:

1. **Revise los logs** en `logs/generate_embeddings.log`
2. **Use modo debug** con `--debug`
3. **Verifique configuración** en `.env`
4. **Pruebe con un solo tripulante** usando `--crew-id`