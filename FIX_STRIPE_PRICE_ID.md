# 🔴 ERROR ENCONTRADO: Price ID Incorrecto

## 🐛 Problema

Tu `.env` tiene:
```bash
STRIPE_PRICE_ID_PRO=prod_TGo6SWXWlLjk4c  ❌
```

**Esto es un PRODUCT ID, no un PRICE ID.**

- Product IDs empiezan con: `prod_...`
- Price IDs empiezan con: `price_...` ✅

## ✅ Solución

Necesitas obtener el **Price ID** de tu producto en Stripe.

### Opción 1: Desde Stripe Dashboard (Recomendado)

1. **Ve a Products**:
   - https://dashboard.stripe.com/test/products
   - O busca "products" en la barra de búsqueda

2. **Encuentra "DevOrganizer Pro"**:
   - Deberías ver tu producto con ID `prod_TGo6SWXWlLjk4c`

3. **Click en el producto**

4. **En la sección "Pricing"**:
   - Verás una tabla con los precios
   - Busca el precio de **$4.00 USD / month**
   - A la derecha verás un ID que empieza con `price_...`
   - Ejemplo: `price_1ABC123xyz456def`

5. **Copia ese Price ID**

6. **Actualiza tu `.env`**:
   ```bash
   STRIPE_PRICE_ID_PRO=price_TU_PRICE_ID_AQUI
   ```

### Opción 2: Usando Stripe CLI (Si lo tienes instalado)

```bash
stripe prices list --product prod_TGo6SWXWlLjk4c
```

Esto te mostrará todos los precios del producto. Busca el que sea:
- Amount: `400` (que son $4.00 en centavos)
- Currency: `usd`
- Recurring interval: `month`

Copia el ID que empieza con `price_`.

### Opción 3: Si NO tienes un precio, créalo

Si tu producto `prod_TGo6SWXWlLjk4c` NO tiene un precio asociado:

1. **Ve al producto en Stripe Dashboard**

2. **Click en "Add another price"**

3. **Configura**:
   - Price: `4.00`
   - Currency: `USD`
   - Billing period: `Monthly`

4. **Guarda**

5. **Copia el Price ID** que se generó

---

## 🧪 Cómo Verificar que Funcione

Después de actualizar el `.env`:

1. **Reinicia tu servidor Flask**:
   ```bash
   # Detén el servidor (Ctrl+C)
   # Vuelve a iniciarlo
   python app.py
   ```

2. **Prueba el botón "Upgrade to Pro"**:
   - Deberías ser redirigido a Stripe Checkout
   - Verás un formulario pidiendo tarjeta
   - Arriba dirá "DevOrganizer Pro - $4.00 / month"

3. **Usa tarjeta de prueba**:
   ```
   Número: 4242 4242 4242 4242
   CVC: 123
   Fecha: 12/34
   ```

---

## 📸 Captura de Pantalla de Referencia

Cuando veas el producto en Stripe Dashboard, deberías ver algo así:

```
Product Details
├─ Name: DevOrganizer Pro
├─ ID: prod_TGo6SWXWlLjk4c
└─ Pricing
   └─ $4.00 USD / month
      └─ ID: price_1ABC123xyz456def  ← ESTE ES EL QUE NECESITAS
```

---

## ⚠️ Importante

**NO uses el Product ID (`prod_...`)**
**SÍ usa el Price ID (`price_...`)**

El Product es el "contenedor" (DevOrganizer Pro).
El Price es el "precio específico" ($4/mes).

Un producto puede tener múltiples precios (ej: $4/mes, $40/año, etc.).

---

## 🚀 Después de Arreglar

Tu `.env` debe verse así:

```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_51SK9O7FFxJzTw9wtPCQqZA7dBg21Kx4T55fCVEaZ5hhXxg2JZIbZROS9IzUS1xy4nlB8itLedzJvP9C8qCTvHkCG00QIlNUeBf
STRIPE_PUBLISHABLE_KEY=pk_test_51SK9O7FFxJzTw9wtIXOhSmYaOata7Ef1JeghNxnIKRsi3fjvpRtjM5zASNEtWFMPby19bXcQ6TsNawAXdgxG3pfr00HXC92oxl
STRIPE_WEBHOOK_SECRET=whsec_qsmGXQUzKTLoN69Z2IyokWvkvxb3TpLD
STRIPE_PRICE_ID_PRO=price_TU_PRICE_ID_AQUI  ← Actualiza esto
APP_URL=http://127.0.0.1:5000
```

---

## 🎯 Siguiente Paso

1. Ve a Stripe Dashboard → Products
2. Copia el Price ID (empieza con `price_`)
3. Actualiza tu `.env`
4. Reinicia Flask
5. Prueba "Upgrade to Pro" de nuevo

¡Debería funcionar! 🚀
