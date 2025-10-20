"""
Script para verificar la configuración de Stripe
Ejecuta esto para ver si Stripe está configurado correctamente
"""
import os
from dotenv import load_dotenv

load_dotenv('.env')

print("\n" + "="*60)
print("  VERIFICACIÓN DE CONFIGURACIÓN DE STRIPE")
print("="*60 + "\n")

# Verificar variables de entorno
stripe_secret = os.getenv('STRIPE_SECRET_KEY')
stripe_public = os.getenv('STRIPE_PUBLISHABLE_KEY')
stripe_webhook = os.getenv('STRIPE_WEBHOOK_SECRET')
stripe_price = os.getenv('STRIPE_PRICE_ID_PRO')

print("1. STRIPE_SECRET_KEY:")
if stripe_secret:
    print(f"   ✅ Configurado: {stripe_secret[:20]}...{stripe_secret[-10:]}")
else:
    print("   ❌ NO configurado")

print("\n2. STRIPE_PUBLISHABLE_KEY:")
if stripe_public:
    print(f"   ✅ Configurado: {stripe_public[:20]}...{stripe_public[-10:]}")
else:
    print("   ❌ NO configurado")

print("\n3. STRIPE_WEBHOOK_SECRET:")
if stripe_webhook:
    print(f"   ✅ Configurado: {stripe_webhook[:15]}...")
else:
    print("   ❌ NO configurado")

print("\n4. STRIPE_PRICE_ID_PRO:")
if stripe_price:
    if stripe_price.startswith('price_'):
        print(f"   ✅ Configurado: {stripe_price}")
        print(f"   ✅ Formato correcto (empieza con 'price_')")
    elif stripe_price.startswith('prod_'):
        print(f"   ❌ ERROR: {stripe_price}")
        print(f"   ❌ Esto es un PRODUCT ID, no un PRICE ID")
    else:
        print(f"   ❌ ERROR: {stripe_price}")
        print(f"   ❌ Formato desconocido")
else:
    print("   ❌ NO configurado")

print("\n" + "="*60)

# Intentar importar stripe y probar conexión
try:
    import stripe
    stripe.api_key = stripe_secret

    print("\n5. PROBANDO CONEXIÓN CON STRIPE:")

    # Intentar obtener el precio
    if stripe_price and stripe_price.startswith('price_'):
        try:
            price = stripe.Price.retrieve(stripe_price)
            print(f"   ✅ Precio encontrado en Stripe")
            print(f"   ✅ Producto: {price.product}")
            print(f"   ✅ Monto: ${price.unit_amount / 100:.2f} {price.currency.upper()}")
            print(f"   ✅ Recurrencia: {price.recurring.interval}")
        except Exception as e:
            print(f"   ❌ ERROR al obtener precio: {str(e)}")
    else:
        print("   ⏭️  Saltado (Price ID no válido)")

except ImportError:
    print("\n5. STRIPE MODULE:")
    print("   ❌ Stripe no está instalado")
    print("   💡 Ejecuta: pip install stripe>=7.0.0")
except Exception as e:
    print(f"\n5. ERROR AL PROBAR STRIPE:")
    print(f"   ❌ {str(e)}")

print("\n" + "="*60)
print("  FIN DE LA VERIFICACIÓN")
print("="*60 + "\n")
