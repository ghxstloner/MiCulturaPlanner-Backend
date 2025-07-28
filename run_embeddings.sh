#!/bin/bash

# Script para ejecutar la generación de face embeddings
# Uso: ./run_embeddings.sh [opciones]

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para mostrar ayuda
show_help() {
    echo -e "${BLUE}=== CulturaConnect Face Embeddings Generator ===${NC}"
    echo ""
    echo "Uso: $0 [OPCIÓN]"
    echo ""
    echo "Opciones:"
    echo "  -h, --help                    Muestra esta ayuda"
    echo "  -a, --all                     Genera embeddings para todos los tripulantes"
    echo "  -f, --force                   Regenera embeddings existentes"
    echo "  -c, --crew-id CREW_ID         Procesa solo un tripulante específico"
    echo "  -d, --debug                   Habilita logging detallado"
    echo ""
    echo "Ejemplos:"
    echo "  $0 --all                      # Procesar todos los tripulantes nuevos"
    echo "  $0 --all --force              # Regenerar todos los embeddings"
    echo "  $0 --crew-id 789123           # Procesar solo el tripulante 789123"
    echo "  $0 --crew-id 789123 --force   # Regenerar embedding del tripulante 789123"
    echo ""
}

# Función para verificar requisitos
check_requirements() {
    echo -e "${BLUE}🔍 Verificando requisitos...${NC}"
    
    # Verificar Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 no está instalado${NC}"
        exit 1
    fi
    
    # Verificar archivo .env
    if [ ! -f ".env" ]; then
        echo -e "${RED}❌ Archivo .env no encontrado${NC}"
        exit 1
    fi
    
    # Verificar que el entorno virtual existe
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}⚠️  Entorno virtual no encontrado. Creando...${NC}"
        python3 -m venv venv
    fi
    
    echo -e "${GREEN}✅ Requisitos verificados${NC}"
}

# Función para activar entorno virtual
activate_venv() {
    echo -e "${BLUE}🔧 Activando entorno virtual...${NC}"
    
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    elif [ -f "venv/Scripts/activate" ]; then
        source venv/Scripts/activate
    else
        echo -e "${RED}❌ No se pudo activar el entorno virtual${NC}"
        exit 1
    fi
    
    # Instalar dependencias si es necesario
    pip install -q -r requirements.txt
    
    echo -e "${GREEN}✅ Entorno virtual activado${NC}"
}

# Función principal
main() {
    local FORCE=""
    local CREW_ID=""
    local DEBUG=""
    local PROCESS_ALL=""
    
    # Procesar argumentos
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -a|--all)
                PROCESS_ALL="true"
                shift
                ;;
            -f|--force)
                FORCE="--force"
                shift
                ;;
            -c|--crew-id)
                CREW_ID="--crew-id $2"
                shift 2
                ;;
            -d|--debug)
                DEBUG="--debug"
                shift
                ;;
            *)
                echo -e "${RED}❌ Opción desconocida: $1${NC}"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Verificar que se especificó alguna acción
    if [[ -z "$PROCESS_ALL" && -z "$CREW_ID" ]]; then
        echo -e "${RED}❌ Debe especificar --all o --crew-id${NC}"
        show_help
        exit 1
    fi
    
    # Mostrar banner
    echo -e "${GREEN}"
    echo "================================================="
    echo "  CulturaConnect Face Embeddings Generator"
    echo "================================================="
    echo -e "${NC}"
    
    # Verificar requisitos
    check_requirements
    
    # Activar entorno virtual
    activate_venv
    
    # Construir comando
    local CMD="python generate_face_embeddings.py"
    
    if [[ -n "$FORCE" ]]; then
        CMD="$CMD $FORCE"
    fi
    
    if [[ -n "$CREW_ID" ]]; then
        CMD="$CMD $CREW_ID"
    fi
    
    if [[ -n "$DEBUG" ]]; then
        CMD="$CMD $DEBUG"
    fi
    
    echo -e "${BLUE}🚀 Ejecutando: $CMD${NC}"
    echo ""
    
    # Ejecutar comando
    eval $CMD
    
    local EXIT_CODE=$?
    
    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}🎉 ¡Proceso completado exitosamente!${NC}"
    else
        echo -e "${RED}❌ El proceso terminó con errores (código: $EXIT_CODE)${NC}"
    fi
    
    return $EXIT_CODE
}

# Verificar que estamos en el directorio correcto
if [ ! -f "generate_face_embeddings.py" ]; then
    echo -e "${RED}❌ Este script debe ejecutarse desde el directorio raíz del proyecto${NC}"
    exit 1
fi

# Ejecutar función principal con todos los argumentos
main "$@"