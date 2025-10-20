# 🚦 Flujo de Rutas - DevOrganizer

## Cambio Implementado

✅ **Los usuarios no autenticados ahora son redirigidos a la landing page `/home`**

---

## 📋 Flujo de Navegación

### Usuario NO Autenticado

1. **Visita `/` (raíz)**
   ```
   / → detecta que no hay sesión → redirect /home
   ```

2. **Visita `/home` (landing page)**
   ```
   /home → muestra landing page con planes Free y Pro
   ```

3. **Click en "Sign up" o "Get Started Free"**
   ```
   /home → /web_signup → registra usuario → redirect /
   ```

4. **Click en "Try Pro Free for 30 Days"**
   ```
   /home → /web_signup?plan=pro → registra usuario → redirect /create-checkout-session
   ```

### Usuario Autenticado

1. **Visita `/` (raíz)**
   ```
   / → detecta sesión activa → muestra dashboard (index.html)
   ```

2. **Visita `/home` (landing page)**
   ```
   /home → detecta sesión activa → redirect /
   ```
   *Los usuarios logueados no pueden ver la landing page*

---

## 🔐 Rutas Públicas vs Privadas

### ✅ Rutas Públicas (No requieren login)

| Ruta | Descripción |
|------|-------------|
| `/home` | Landing page con pricing |
| `/web_login` | Página de login |
| `/web_signup` | Página de registro |
| `/subscription/cancel` | Página cuando cancela checkout |
| `/webhook` | Webhook de Stripe (sin auth) |

### 🔒 Rutas Privadas (Requieren login)

| Ruta | Descripción | Decorador |
|------|-------------|-----------|
| `/` | Dashboard principal | Check manual |
| `/create` | Crear proyecto | `@login_required` |
| `/project/<id>` | Ver proyecto | `@login_required` |
| `/api/projects` | Guardar proyecto | `@login_required` + `@check_resource_limit('project')` |
| `/generate-estimation` | Crear estimación | `@login_required` + `@check_resource_limit('estimation')` |
| `/generate-feature-suggestions` | Crear sugerencia | `@login_required` + `@check_resource_limit('feature_suggestion')` |
| `/create-checkout-session` | Iniciar pago Pro | `@login_required` |
| `/create-portal-session` | Gestionar suscripción | `@login_required` + `@require_plan('pro')` |
| `/subscription/success` | Confirmación de pago | `@login_required` |
| `/clickup/*` | Todas las rutas ClickUp | `@login_required` + `@require_plan('pro')` |

---

## 🎯 Casos de Uso

### Caso 1: Usuario nuevo visita la app por primera vez

```
1. Escribe: devorganizer.com
2. → Redirigido a /home (landing page)
3. Ve opciones de Free y Pro
4. Click "Get Started Free"
5. → /web_signup
6. Completa registro
7. → Redirigido a / (dashboard)
8. Ve widget con límites 0/1
```

### Caso 2: Usuario nuevo quiere plan Pro

```
1. Escribe: devorganizer.com
2. → Redirigido a /home (landing page)
3. Click "Try Pro Free for 30 Days"
4. → /web_signup?plan=pro
5. Completa registro
6. → Redirigido a /create-checkout-session
7. Stripe Checkout aparece
8. Ingresa tarjeta (trial 30 días, sin cobro)
9. → Redirigido a /subscription/success
10. Click "Start Creating Projects"
11. → / (dashboard)
12. Ve widget con límites 0/20
```

### Caso 3: Usuario autenticado intenta ver landing

```
1. Usuario logueado escribe: devorganizer.com/home
2. → /home detecta sesión activa
3. → Redirigido a / (dashboard)
```

### Caso 4: Usuario no autenticado intenta acceder al dashboard

```
1. Usuario sin sesión escribe: devorganizer.com
2. → / detecta que no hay sesión
3. → Redirigido a /home (landing page)
```

---

## 🔄 Código Implementado

### En `/` (app.py línea 180-190)

```python
@app.route('/')
def index():
    """
    Home page - displays list of all projects and estimations for the current user
    Redirects to landing page if not logged in
    """
    # If user is not logged in, redirect to landing page
    if 'user_id' not in session:
        return redirect(url_for('landing_page'))

    # ... resto del código del dashboard
```

### En `/home` (app.py línea 2024-2030)

```python
@app.route('/home')
def landing_page():
    '''Landing page for non-authenticated users'''
    # If user is already logged in, redirect to dashboard
    if 'user_id' in session:
        return redirect(url_for('index'))

    return render_template('landing.html')
```

---

## ✅ Beneficios de Este Flujo

1. ✅ **Primera impresión profesional**: Usuarios nuevos ven landing page con pricing
2. ✅ **Evita confusión**: No hay redirección a login cuando no tienen cuenta
3. ✅ **Call-to-action claro**: Botones grandes "Get Started Free" y "Try Pro"
4. ✅ **No interrumpe usuarios logueados**: Si ya tienen sesión, van directo al dashboard
5. ✅ **SEO-friendly**: `/home` puede ser la página pública indexable

---

## 🧪 Cómo Probar

### Test 1: Usuario no autenticado
```bash
1. Cierra sesión o abre ventana incógnito
2. Ve a http://127.0.0.1:5000/
3. ✅ Deberías ver la landing page (/home)
4. ✅ NO deberías ver login ni dashboard
```

### Test 2: Usuario autenticado
```bash
1. Inicia sesión
2. Ve a http://127.0.0.1:5000/
3. ✅ Deberías ver el dashboard con tus proyectos
4. Ahora ve a http://127.0.0.1:5000/home
5. ✅ Deberías ser redirigido de vuelta al dashboard (/)
```

### Test 3: Registro desde landing
```bash
1. Sin sesión, ve a /home
2. Click "Get Started Free"
3. Completa formulario de registro
4. ✅ Deberías llegar al dashboard (/)
5. ✅ Deberías ver "Free Plan" en tu navbar
```

### Test 4: Registro Pro desde landing
```bash
1. Sin sesión, ve a /home
2. Click "Try Pro Free for 30 Days"
3. Completa formulario de registro
4. ✅ Deberías ver Stripe Checkout
5. Usa tarjeta de prueba: 4242 4242 4242 4242
6. ✅ Deberías llegar a /subscription/success
7. Click "Start Creating Projects"
8. ✅ Deberías ver dashboard con "Pro Plan"
```

---

## 📝 Notas Técnicas

### ¿Por qué no usar @login_required en /?

El decorador `@login_required` redirige a `/web_login` por defecto. Queríamos redirigir a `/home` en su lugar para mostrar la landing page.

Opciones consideradas:
1. ✅ **Elegida**: Quitar `@login_required` de `/` y hacer check manual → Redirige a `/home`
2. ❌ Modificar `@login_required` para redirigir a `/home` → Afectaría todas las demás rutas
3. ❌ Crear un nuevo decorador `@redirect_to_landing` → Innecesario para un solo caso

### Seguridad

- La ruta `/` NO tiene `@login_required` pero hace un check manual de sesión
- Si no hay sesión → redirect a landing (público)
- Si hay sesión → muestra dashboard (privado)
- No hay riesgo de seguridad porque el check de sesión se hace antes de cualquier lógica

---

## 🚀 Resultado Final

Ahora tu aplicación tiene un flujo profesional:

```
Usuario Nuevo → Landing Page → Registro → Dashboard
Usuario Logueado → Dashboard directamente
```

¡Exactamente como apps SaaS profesionales! 🎉
