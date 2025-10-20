# ✅ Arreglo del Botón "Home" en Navbar

## 🎯 Problema

El botón "🏠 Home" en el navbar tenía comportamiento inconsistente:
- Usuario NO logueado → iba a `/web_signup` ❌
- Usuario logueado → iba a `/` ✅

**Debería ser:**
- Usuario NO logueado → `/home` (landing page)
- Usuario logueado → `/` (dashboard)

## ✅ Solución

Modificado `templates/base.html` línea 464:

**Antes:**
```html
<a href="{{ url_for('web_signup' if not current_user else 'index') }}" class="btn btn-secondary">🏠 Home</a>
```

**Ahora:**
```html
<a href="{{ url_for('landing_page' if not current_user else 'index') }}" class="btn btn-secondary">🏠 Home</a>
```

## 🎯 Comportamiento Actual

| Usuario | Click en "🏠 Home" | Destino |
|---------|-------------------|---------|
| NO logueado | → | `/home` (landing page) ✅ |
| Logueado | → | `/` (dashboard) ✅ |

## 🧪 Cómo Probar

### Test 1: Usuario NO logueado
```bash
1. Cierra sesión o abre ventana incógnito
2. Ve a cualquier página pública (ej: /web_login)
3. Click en "🏠 Home" en el navbar
4. ✅ Deberías llegar a /home (landing page)
```

### Test 2: Usuario logueado
```bash
1. Inicia sesión
2. Ve a cualquier página (ej: /create)
3. Click en "🏠 Home" en el navbar
4. ✅ Deberías llegar a / (dashboard)
```

## ✅ Resultado

El botón "Home" ahora es consistente y lleva al usuario al lugar correcto según su estado de autenticación.
