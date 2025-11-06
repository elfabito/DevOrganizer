"""
Script para actualizar un usuario a plan PRO en Redis
"""
import os
import json
from dotenv import load_dotenv
from storage_redis import get_redis_client

# Cargar variables de entorno
load_dotenv()

def main():
    # Conectar a Redis
    r = get_redis_client()
    
    print("🔍 Buscando usuarios en Redis...\n")
    
    # Buscar todos los usuarios
    user_keys = list(r.keys('user:*'))
    
    if not user_keys:
        print("❌ No se encontraron usuarios en Redis")
        return
    
    print(f"📊 Se encontraron {len(user_keys)} usuarios:\n")
    
    users_info = []
    for key in user_keys:
        raw = r.get(key)
        if raw:
            user_data = json.loads(raw)
            user_id = key.split(':')[1]
            users_info.append({
                'id': user_id,
                'email': user_data.get('email', 'N/A'),
                'name': user_data.get('name', 'N/A'),
                'plan_type': user_data.get('plan_type', 'N/A'),
                'subscription_status': user_data.get('subscription_status', 'N/A')
            })
            
            print(f"ID: {user_id}")
            print(f"  Name: {user_data.get('name', 'N/A')}")
            print(f"  Email: {user_data.get('email', 'N/A')}")
            print(f"  Plan Type: {user_data.get('plan_type', 'N/A')}")
            print(f"  Subscription Status: {user_data.get('subscription_status', 'N/A')}")
            print()
    
    # Preguntar qué usuario actualizar
    print("\n" + "="*60)
    email_to_update = input("📧 Ingresa el email del usuario a actualizar a PRO: ").strip()
    
    # Buscar el user_id por email
    user_id_key = r.get(f'user_email:{email_to_update}')
    
    if not user_id_key:
        print(f"❌ No se encontró usuario con email: {email_to_update}")
        return
    
    # Obtener datos actuales del usuario
    user_key = f'user:{user_id_key}'
    raw_user = r.get(user_key)
    
    if not raw_user:
        print(f"❌ No se pudieron obtener datos del usuario")
        return
    
    user_data = json.loads(raw_user)
    
    # Actualizar a PRO
    print(f"\n🔄 Actualizando usuario a plan PRO...")
    
    user_data['plan_type'] = 'pro'
    user_data['subscription_status'] = 'active'
    
    # Guardar cambios
    r.set(user_key, json.dumps(user_data))
    
    print(f"✅ Usuario actualizado exitosamente!")
    
    # Verificar
    updated_raw = r.get(user_key)
    updated_user = json.loads(updated_raw)
    
    print(f"\n📊 Datos actualizados:")
    print(f"  Name: {updated_user.get('name')}")
    print(f"  Email: {updated_user.get('email')}")
    print(f"  Plan Type: {updated_user.get('plan_type')}")
    print(f"  Subscription Status: {updated_user.get('subscription_status')}")
    print(f"\n✨ ¡Listo! Refresca la página para ver los cambios.")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
