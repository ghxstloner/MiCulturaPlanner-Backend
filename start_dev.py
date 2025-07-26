"""
Script para iniciar el servidor en modo desarrollo
"""
import os
import sys

# Agregar el directorio del proyecto al path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def main():
    print("🚀 Iniciando CulturaConnect Facial Recognition API en modo desarrollo...")
    print("=" * 60)
    
    # Verificar que existe el archivo .env
    env_file = os.path.join(project_root, ".env")
    if not os.path.exists(env_file):
        print("❌ Error: No se encontró el archivo .env")
        print("Cree el archivo .env con la configuración necesaria.")
        return
    
    # Verificar que existen los directorios necesarios
    for directory in ["temp_uploads", "logs"]:
        dir_path = os.path.join(project_root, directory)
        os.makedirs(dir_path, exist_ok=True)
    
    # Importar y ejecutar la aplicación
    try:
        from app.main import main as app_main
        app_main()
    except KeyboardInterrupt:
        print("\n👋 Servidor detenido por el usuario")
    except Exception as e:
        print(f"\n❌ Error al iniciar el servidor: {str(e)}")

if __name__ == "__main__":
    main()