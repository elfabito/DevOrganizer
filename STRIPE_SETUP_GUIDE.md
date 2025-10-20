# 🔵 Guía Completa de Configuración de Stripe (2025)

## 📱 Paso 1: Crear Cuenta en Stripe

1. Ve a https://stripe.com
2. Click en "Sign up" (o "Registrarse")
3. Completa el formulario con tu email y contraseña
4. **Verifica tu email**
5. Una vez dentro, verás el Dashboard de Stripe

## 🔧 Paso 2: Activar Modo Test

**MUY IMPORTANTE**: Para desarrollo, SIEMPRE usa el **modo Test**.

1. En la esquina superior derecha del Dashboard, verás un toggle que dice **"Test mode"** o **"Modo de prueba"**
2. Asegúrate de que esté **ACTIVADO** (debe estar en azul/morado)
3. Verás un banner arriba que dice "Test mode" cuando esté activado

> 💡 **Tip**: En modo Test puedes usar tarjetas de prueba sin cargos reales

## 🔑 Paso 3: Obtener API Keys (Claves de API)

### Opción A: Búsqueda Rápida (Recomendado)
1. En la barra de búsqueda superior (tiene un ícono de lupa 🔍), escribe **"API keys"**
2. Click en "API keys" en los resultados
3. Verás la página de claves API

### Opción B: Menú Lateral
1. En el menú lateral izquierdo, busca el ícono **`</>`** o la opción **"Developers"** (Desarrolladores)
2. Click en "Developers"
3. En el submenú, click en **"API keys"**

### Copiar las Claves

En la página de API keys verás:

1. **Publishable key** (Clave publicable):
   ```
   pk_test_51Abc...xyz
   ```
   - Click en "Reveal test key" o el ícono del ojo 👁️
   - Click en el botón de copiar 📋
   - Pega en tu `.env` como `STRIPE_PUBLISHABLE_KEY=pk_test_...`

2. **Secret key** (Clave secreta):
   ```
   sk_test_51Abc...xyz
   ```
   - Click en "Reveal test key" o el ícono del ojo 👁️
   - Click en el botón de copiar 📋
   - **⚠️ IMPORTANTE**: Esta clave es SECRETA. NO la compartas ni la subas a GitHub
   - Pega en tu `.env` como `STRIPE_SECRET_KEY=sk_test_...`

## 💳 Paso 4: Crear el Producto "DevOrganizer Pro"

### 4.1 Ir a Products

**Opción A - Búsqueda:**
1. En la barra de búsqueda superior 🔍, escribe **"products"**
2. Click en "Products" o "Product catalog"

**Opción B - Menú:**
1. En el menú lateral izquierdo, busca **"Product catalog"** o **"Products"**
2. Click en "Products"

### 4.2 Crear el Producto

1. Click en el botón **"+ Add product"** o **"+ Create product"**

2. **Detalles del Producto:**
   ```
   Name: DevOrganizer Pro
   Description: Pro subscription for DevOrganizer with 30-day free trial
   ```

3. **Pricing (Precio):**
   - **Model**: "Standard pricing" (precio estándar)
   - **Price**: `4.00`
   - **Currency**: `USD` (dólares)
   - **Billing period**: `Monthly` (mensual) o `Recurring` → `Every 1 month`

4. **⚠️ NO agregues el free trial aquí** (lo haremos desde el código)
   - Si ves una opción de "Free trial" o "Trial period", **IGNÓRALA**
   - El trial de 30 días ya está configurado en el código de `stripe_service.py`

5. Click en **"Save product"** o **"Create product"**

### 4.3 Copiar el Price ID

Después de guardar:

1. En la página del producto, verás una sección llamada **"Pricing"** o **"API ID"**
2. Busca el **Price ID** (comienza con `price_...`):
   ```
   price_1Abc...xyz
   ```
3. Click en el botón de copiar 📋
4. Pega en tu `.env` como:
   ```
   STRIPE_PRICE_ID_PRO=price_1Abc...xyz
   ```

## 🎣 Paso 5: Configurar Webhooks

Los webhooks permiten que Stripe notifique a tu app cuando ocurren eventos (pago exitoso, suscripción cancelada, etc.)

### 5.1 Encontrar Webhooks

**Opción A - Búsqueda (MÁS FÁCIL):**
1. En la barra de búsqueda superior 🔍, escribe **"webhooks"**
2. Click en "Webhooks" en los resultados

**Opción B - Menú:**
1. En el menú lateral, busca **"Developers"** (ícono `</>`)
2. Click en "Developers"
3. En el submenú, click en **"Webhooks"**

**URL Directa:**
- https://dashboard.stripe.com/test/webhooks

### 5.2 Agregar Endpoint

1. Click en **"+ Add endpoint"** o **"+ Add an endpoint"**

2. **Endpoint URL**:
   - **Para desarrollo local**:
     ```
     http://127.0.0.1:5000/webhook
     ```
     > ⚠️ Nota: Para local, necesitarás usar Stripe CLI (ver abajo)

   - **Para producción (Render)**:
     ```
     https://tu-app-name.onrender.com/webhook
     ```

3. **Description** (opcional):
   ```
   DevOrganizer subscription webhooks
   ```

4. **Events to send**:
   - Click en **"Select events"** o **"+ Select events to listen to"**
   - En la búsqueda, encuentra y selecciona estos eventos:
     ```
     ✅ checkout.session.completed
     ✅ customer.subscription.created
     ✅ customer.subscription.updated
     ✅ customer.subscription.deleted
     ✅ invoice.payment_succeeded
     ✅ invoice.payment_failed
     ```
   - Click en **"Add events"**

5. Click en **"Add endpoint"**

### 5.3 Copiar el Signing Secret

Después de crear el webhook:

1. En la página del webhook, busca la sección **"Signing secret"**
2. Click en **"Reveal"** o **"Click to reveal"**
3. Verás un secreto que comienza con `whsec_...`:
   ```
   whsec_abc123xyz...
   ```
4. Click en copiar 📋
5. Pega en tu `.env` como:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_abc123xyz...
   ```

## 🧪 Paso 6: Testing con Stripe CLI (Desarrollo Local)

Para probar webhooks localmente, necesitas Stripe CLI:

### Instalar Stripe CLI

**Windows:**
```bash
# Con Scoop
scoop install stripe

# O descarga desde:
https://github.com/stripe/stripe-cli/releases
```

**Mac:**
```bash
brew install stripe/stripe-cli/stripe
```

**Linux:**
```bash
# Descarga desde:
https://github.com/stripe/stripe-cli/releases
```

### Usar Stripe CLI

1. **Login en Stripe:**
   ```bash
   stripe login
   ```
   - Se abrirá tu navegador para autorizar

2. **Escuchar webhooks localmente:**
   ```bash
   stripe listen --forward-to localhost:5000/webhook
   ```
   - Esto creará un webhook secret temporal
   - **Copia el `whsec_...` que aparece** y úsalo en tu `.env` local

3. **Probar eventos:**
   En otra terminal:
   ```bash
   stripe trigger checkout.session.completed
   ```

## ✅ Paso 7: Verificar tu `.env`

Tu archivo `.env` debe verse así:

```bash
# Stripe Configuration (TEST MODE)
STRIPE_SECRET_KEY=sk_test_51Abc...xyz
STRIPE_PUBLISHABLE_KEY=pk_test_51Abc...xyz
STRIPE_WEBHOOK_SECRET=whsec_abc123...xyz
STRIPE_PRICE_ID_PRO=price_1Abc...xyz

# Application URL
APP_URL=http://127.0.0.1:5000
```

## 🚀 Paso 8: Probar el Sistema

### 8.1 Iniciar la Aplicación

```bash
python app.py
```

### 8.2 Probar el Flujo de Suscripción

1. **Ve a la landing page:**
   ```
   http://127.0.0.1:5000/home
   ```

2. **Click en "Try Pro Free for 30 Days"**

3. **Regístrate** con un email de prueba

4. **Serás redirigido a Stripe Checkout**

5. **Usa una tarjeta de prueba:**
   ```
   Número: 4242 4242 4242 4242
   CVC: 123
   Fecha: 12/34 (cualquier fecha futura)
   Código postal: 12345
   ```

6. **Completa el pago**

7. **Verifica que fuiste redirigido** a `/subscription/success`

8. **Ve al dashboard** y verifica que:
   - Ves el badge "Pro" en tu nombre
   - El widget de uso muestra "0/20" en todos los límites

### 8.3 Verificar en Stripe Dashboard

1. Ve a **"Customers"** en Stripe Dashboard
2. Deberías ver tu cliente creado
3. Click en el cliente
4. Verifica que tiene una suscripción activa con status **"trialing"**

## 🔄 Paso 9: Webhooks en Producción (Render)

Cuando despliegues a Render:

1. **Actualizar `.env` en Render:**
   - Ve a tu app en Render Dashboard
   - Click en "Environment"
   - Agrega todas las variables `STRIPE_*`
   - Actualiza `APP_URL` a tu dominio de Render

2. **Crear nuevo webhook para producción:**
   - En Stripe Dashboard → Webhooks
   - Agrega endpoint con tu URL de Render:
     ```
     https://tu-app.onrender.com/webhook
     ```
   - Copia el nuevo `whsec_...` y actualízalo en Render

3. **Cambiar a claves LIVE** (cuando estés listo para producción):
   - En Stripe, desactiva "Test mode"
   - Copia las claves `sk_live_...` y `pk_live_...`
   - Actualiza en Render
   - Crea el producto Pro en modo LIVE
   - Crea el webhook en modo LIVE

## 🐛 Troubleshooting

### "No such price"
- Verifica que el `STRIPE_PRICE_ID_PRO` sea correcto
- Asegúrate de estar en el mismo modo (test/live) que el precio

### "Webhook signature verification failed"
- Verifica que `STRIPE_WEBHOOK_SECRET` sea el correcto
- Para local, usa Stripe CLI
- Para producción, usa el secret del webhook de producción

### "Invalid API key"
- Verifica que las claves empiecen con `sk_test_` (test) o `sk_live_` (producción)
- Asegúrate de no tener espacios antes/después de las claves

### El trial no aparece
- El trial de 30 días se configura automáticamente desde `stripe_service.py`
- No necesitas configurarlo en Stripe Dashboard
- Verifica que el código tenga `trial_period_days: 30`

## 📊 Resumen de URLs Importantes

| Recurso | URL |
|---------|-----|
| Dashboard Principal | https://dashboard.stripe.com |
| API Keys (Test) | https://dashboard.stripe.com/test/apikeys |
| Products (Test) | https://dashboard.stripe.com/test/products |
| Webhooks (Test) | https://dashboard.stripe.com/test/webhooks |
| Customers (Test) | https://dashboard.stripe.com/test/customers |
| Subscriptions (Test) | https://dashboard.stripe.com/test/subscriptions |
| Stripe CLI Download | https://github.com/stripe/stripe-cli/releases |

## 🎉 ¡Listo!

Tu sistema de suscripciones con Stripe está configurado. Ahora puedes:

✅ Aceptar suscripciones con trial de 30 días
✅ Cobrar $4/mes automáticamente
✅ Recibir eventos de Stripe en tiempo real
✅ Gestionar clientes y suscripciones desde Stripe Dashboard

---

**¿Necesitas ayuda?**
- Documentación oficial: https://stripe.com/docs
- Stripe Discord: https://stripe.com/community
