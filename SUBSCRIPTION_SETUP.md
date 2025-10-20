# Sistema de Suscripciones - Guía de Instalación Final

## ✅ Archivos Completados

1. ✅ `requirements.txt` - Agregado `stripe>=7.0.0`
2. ✅ `.env.example` - Variables de Stripe agregadas
3. ✅ `storage_redis.py` - Campos de suscripción en User model
4. ✅ `stripe_service.py` - Servicio de integración con Stripe
5. ✅ `subscription_limits.py` - Decoradores de límites y control de acceso
6. ✅ `templates/landing.html` - Landing page pública
7. ✅ `templates/subscription_success.html` - Página de éxito
8. ✅ `templates/subscription_cancel.html` - Página de cancelación
9. ✅ `templates/base.html` - Indicador de plan agregado
10. ✅ `templates/index.html` - Widget de límites de uso agregado
11. ✅ `subscription_routes.py` - Todas las rutas listas para integrar

## 📝 Pasos Pendientes para Completar la Integración

### 1. Instalar Dependencias

```bash
pip install stripe>=7.0.0
```

### 2. Configurar Variables de Entorno

Copia `.env.example` a `.env` y configura:

```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_...  # Tu clave secreta de Stripe (test mode)
STRIPE_PUBLISHABLE_KEY=pk_test_...  # Tu clave pública de Stripe
STRIPE_WEBHOOK_SECRET=whsec_...  # Secret del webhook
STRIPE_PRICE_ID_PRO=price_...  # Price ID del plan Pro
```

### 3. Crear Producto en Stripe Dashboard

1. Ve a https://dashboard.stripe.com/test/products
2. Click "Add product"
3. Nombre: "DevOrganizer Pro"
4. Descripción: "Pro subscription for DevOrganizer"
5. Precio: $4 USD/mes
6. **IMPORTANTE**: En "Additional options" → "Free trial" → Selecciona "30 días"
7. Guarda y copia el **Price ID** (empieza con `price_...`)
8. Pega el Price ID en `STRIPE_PRICE_ID_PRO` en tu `.env`

### 4. Configurar Webhook en Stripe

1. Ve a https://dashboard.stripe.com/test/webhooks
2. Click "+ Add endpoint"
3. Endpoint URL: `https://tu-dominio.onrender.com/webhook`
4. Eventos a escuchar (selecciona estos):
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
5. Guarda y copia el **Signing secret** (empieza con `whsec_...`)
6. Pega en `STRIPE_WEBHOOK_SECRET` en tu `.env`

### 5. Agregar Rutas de Suscripción a app.py

Abre `app.py` y agrega lo siguiente:

#### A. Agregar imports al principio (después de los imports existentes):

```python
from stripe_service import (
    create_checkout_session,
    create_customer_portal_session,
    handle_webhook_event,
    get_stripe_config
)
from subscription_limits import (
    check_resource_limit,
    require_plan,
    get_user_plan_limits,
    can_use_clickup
)
```

#### B. Agregar las rutas (puedes copiar todo el contenido de `subscription_routes.py`)

Las rutas están en el archivo `subscription_routes.py`. Copia todo el código que está dentro de las comillas triples y agrégalo a `app.py` después de las rutas existentes y antes de la sección de CSRF exemptions.

Específicamente:
- Agregar rutas antes de la línea `# Exempt API routes from CSRF protection` (línea ~2141)
- Agregar las exemptions de CSRF al final de la lista existente

### 6. Modificar Ruta de Signup para Soportar plan=pro

En `app.py`, encuentra la función `web_signup` (línea ~399) y modifica:

#### Opción A: Crear usuario directamente con plan Pro y redirigir a checkout

Después de crear el usuario exitosamente (línea ~503), antes del `return redirect(url_for('index'))`:

```python
# Después de session.modified = True (línea ~494)

# Check if user wants Pro plan
plan_param = request.args.get('plan', 'free')

if plan_param == 'pro':
    # Redirect to checkout for Pro subscription
    flash('Complete your Pro subscription to get started!', 'info')
    return redirect(url_for('create_stripe_checkout'))

flash('Registration successful!', 'success')
return redirect(url_for('index'))
```

### 7. Agregar Verificación de Límites en Rutas Existentes

#### A. Ruta `/api/projects` (línea ~718)

Agregar decorador ANTES de la función:

```python
@app.route('/api/projects', methods=['POST'])
@login_required
@check_resource_limit('project')  # <-- AGREGAR ESTA LÍNEA
def save_project():
```

#### B. Ruta `/generate-estimation` (línea ~1195)

Agregar decorador:

```python
@app.route('/generate-estimation', methods=['POST'])
@login_required
@check_resource_limit('estimation')  # <-- AGREGAR ESTA LÍNEA
def generate_estimation_endpoint():
```

#### C. Ruta `/generate-feature-suggestions` (línea ~1139)

Agregar decorador:

```python
@app.route('/generate-feature-suggestions', methods=['POST'])
@login_required
@check_resource_limit('feature_suggestion')  # <-- AGREGAR ESTA LÍNEA
def generate_feature_suggestions_endpoint():
```

#### D. Todas las rutas de ClickUp (empiezan en línea ~1632)

Agregar decorador `@require_plan('pro')` a TODAS estas rutas:

```python
@app.route('/clickup/check-config', methods=['GET'])
@login_required
@require_plan('pro')  # <-- AGREGAR
def check_clickup_config():

@app.route('/clickup/workspaces', methods=['GET'])
@login_required
@require_plan('pro')  # <-- AGREGAR
def get_clickup_workspaces():

@app.route('/clickup/spaces/<team_id>', methods=['GET'])
@login_required
@require_plan('pro')  # <-- AGREGAR
def get_clickup_spaces(team_id):

# Y así para TODAS las rutas de ClickUp...
```

### 8. Actualizar Usuarios Existentes (Migración)

Si ya tienes usuarios en Redis, necesitas agregar los campos de suscripción. Crea un script de migración:

```python
# migrate_users_subscription.py
import os
import redis
import json
from dotenv import load_dotenv

load_dotenv('.env')

redis_url = os.getenv('REDIS_URL')
r = redis.from_url(redis_url, decode_responses=True)

# Get all user keys
user_keys = r.keys('user:*')

for key in user_keys:
    user_data = json.loads(r.get(key))

    # Add subscription fields if they don't exist
    if 'plan_type' not in user_data:
        user_data['plan_type'] = 'free'
        user_data['stripe_customer_id'] = None
        user_data['stripe_subscription_id'] = None
        user_data['subscription_status'] = None
        user_data['subscription_current_period_end'] = None
        user_data['trial_end'] = None

        # Save updated user
        r.set(key, json.dumps(user_data))
        print(f"Updated {key}")

print("Migration complete!")
```

Ejecuta:
```bash
python migrate_users_subscription.py
```

## 🚀 Flujo Completo del Usuario

### Usuario Nuevo - Free Plan

1. Visita `/home` (landing page)
2. Click "Get Started Free"
3. Se registra en `/web_signup`
4. Creado con `plan_type='free'`
5. Redirigido a dashboard
6. Ve widget de uso: 0/1 proyectos, 0/1 estimaciones, etc.
7. Puede crear 1 proyecto, 1 estimación, 1 sugerencia
8. NO puede usar ClickUp
9. Ve botón "Upgrade to Pro" en el dashboard

### Usuario Nuevo - Pro Plan (30 días gratis)

1. Visita `/home`
2. Click "Try Pro Free for 30 Days"
3. Se registra en `/web_signup?plan=pro`
4. Redirigido a `/create-checkout-session`
5. Stripe Checkout:
   - Muestra "30 días gratis, luego $4/mes"
   - Solicita tarjeta
   - NO cobra inmediatamente
6. Completa el pago → webhook actualiza:
   - `plan_type='pro'`
   - `subscription_status='trialing'`
   - `trial_end=` fecha 30 días después
7. Redirigido a `/subscription/success`
8. Puede crear hasta 20 proyectos, estimaciones, sugerencias
9. Puede usar ClickUp
10. Después de 30 días: Stripe cobra automáticamente $4
11. Webhook actualiza `subscription_status='active'`

### Usuario Free que Hace Upgrade

1. En dashboard, click "Upgrade to Pro"
2. O llega al límite (1/1 proyectos) → ve mensaje de upgrade
3. Click "Upgrade" → `/create-checkout-session`
4. Mismo flujo que nuevo usuario Pro

### Usuario Pro que Cancela

1. En menú usuario, click "Manage Subscription"
2. Abre Stripe Customer Portal
3. Click "Cancel subscription"
4. Webhook recibe `subscription_deleted`
5. Actualiza: `plan_type='free'`, `subscription_status='canceled'`
6. Usuario sigue usando Pro hasta fin del período pagado
7. Luego se aplican límites Free

## 🧪 Testing

### Test en Modo Sandbox

1. Usa tarjetas de prueba de Stripe:
   - Éxito: `4242 4242 4242 4242`
   - Fallo: `4000 0000 0000 0341`
   - CVC: cualquier 3 dígitos
   - Fecha: cualquier fecha futura

2. Prueba el flujo completo:
   ```bash
   # Terminal 1: Run Flask
   python app.py

   # Terminal 2: Test webhooks localmente con Stripe CLI
   stripe listen --forward-to localhost:5000/webhook
   ```

3. Verifica webhooks en: https://dashboard.stripe.com/test/webhooks

### Test de Límites

```python
# En Python shell o script de prueba
from storage_redis import RedisUserStorage
import redis, os

redis_client = redis.from_url(os.getenv('REDIS_URL'), decode_responses=True)
storage = RedisUserStorage(redis_client)

# Ver uso de un usuario
usage = storage.get_user_usage_counts('user-id-aqui')
print(usage)  # {'projects': 0, 'estimations': 0, 'feature_suggestions': 0}
```

## 📋 Checklist Final

- [ ] `pip install stripe>=7.0.0`
- [ ] Configurar `.env` con claves de Stripe
- [ ] Crear producto Pro en Stripe Dashboard
- [ ] Configurar webhook en Stripe
- [ ] Agregar imports en `app.py`
- [ ] Agregar rutas de suscripción en `app.py`
- [ ] Modificar `/web_signup` para soportar `?plan=pro`
- [ ] Agregar `@check_resource_limit` a rutas de creación
- [ ] Agregar `@require_plan('pro')` a rutas de ClickUp
- [ ] Migrar usuarios existentes (si aplica)
- [ ] Probar flujo completo con tarjeta de prueba
- [ ] Probar webhooks con Stripe CLI
- [ ] Verificar límites funcionan correctamente

## 🔒 Seguridad en Producción

Antes de ir a producción:

1. **Cambiar a claves LIVE de Stripe**:
   - `sk_live_...` en vez de `sk_test_...`
   - `pk_live_...` en vez de `pk_test_...`

2. **Webhook en producción**:
   - URL: `https://tu-dominio.onrender.com/webhook`
   - Nuevo signing secret (diferente al de test)

3. **Variables de entorno en Render**:
   - Agregar todas las variables `STRIPE_*` en Render Dashboard
   - NO commitear `.env` a Git

4. **Monitoring**:
   - Revisar logs de Stripe regularmente
   - Configurar alertas para pagos fallidos

## 🐛 Troubleshooting

### Webhook no funciona
- Verificar que `STRIPE_WEBHOOK_SECRET` está configurado
- Verificar que la URL del webhook es correcta
- Usar `stripe listen` para debug local

### Usuario no se actualiza después del pago
- Verificar que el webhook se está recibiendo en `/webhook`
- Verificar logs de Flask
- Verificar que `user_id` está en los metadatos de Stripe

### Límites no se aplican
- Verificar que los decoradores `@check_resource_limit` están presentes
- Verificar que `user_storage.get_user_usage_counts()` funciona
- Verificar que el plan del usuario es correcto

## 📞 Soporte

Si algo no funciona, verifica:

1. Logs de Flask: `tail -f flask.log` (en producción)
2. Logs de Stripe: https://dashboard.stripe.com/test/logs
3. Webhooks: https://dashboard.stripe.com/test/webhooks
4. Redis: Verificar que los datos se están guardando correctamente

¡Todo listo! 🎉
