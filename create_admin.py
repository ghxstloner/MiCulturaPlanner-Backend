"""
Script para crear un usuario administrador
"""
import sys
import os
import hashlib

# Agregar el directorio del proyecto al path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app.db.database import get_db_connection, close_connection

def create_admin_user():
    """Crea un usuario administrador"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            print("❌ Error: No se pudo conectar a la base de datos")
            return False
        
        cursor = connection.cursor()
        
        # Datos del administrador
        login = input("Ingrese el login del administrador: ").strip()
        password = input("Ingrese la contraseña: ").strip()
        name = input("Ingrese el nombre completo: ").strip()
        email = input("Ingrese el email: ").strip()
        
        if not all([login, password, name, email]):
            print("❌ Error: Todos los campos son obligatorios")
            return False
        
        # Hash de la contraseña (SHA256 como en el sistema original)
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Verificar si el usuario ya existe
        cursor.execute("SELECT login FROM sec_users WHERE login = %s", (login,))
        if cursor.fetchone():
            print(f"❌ Error: El usuario {login} ya existe")
            return False
        
        # Insertar usuario
        query = """
        INSERT INTO sec_users (login, pswd, name, email, active, priv_admin, id_aerolinea)
        VALUES (%s, %s, %s, %s, 'Y', 'Y', 0)
        """
        
        cursor.execute(query, (login, password_hash, name, email))
        
        # Asignar al grupo de administradores (grupo_id = 1)
        cursor.execute(
            "INSERT INTO sec_users_groups (login, group_id) VALUES (%s, 1)",
            (login,)
        )
        
        connection.commit()
        cursor.close()
        
        print(f"✅ Usuario administrador '{login}' creado exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error al crear usuario: {str(e)}")
        if connection:
            connection.rollback()
        return False
    finally:
        close_connection(connection)

if __name__ == "__main__":
    print("🔐 Creador de Usuario Administrador - CulturaConnect")
    print("=" * 50)
    
    success = create_admin_user()
    
    if success:
        print("\n✅ ¡Usuario administrador creado con éxito!")
        print("Ya puede usar las credenciales para acceder a la API.")
    else:
        print("\n❌ No se pudo crear el usuario administrador.")
        print("Verifique los datos y la conexión a la base de datos.")