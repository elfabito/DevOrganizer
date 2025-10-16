# ClickUp Integration - Guía Completa

## 📋 Descripción

Esta integración permite exportar las tareas generadas por IA directamente a tu workspace de ClickUp, facilitando la gestión de proyectos sin necesidad de copiar y pegar manualmente.

## 🚀 Características

- ✅ Conexión directa con la API de ClickUp usando tu token personal
- ✅ Selección dinámica de Workspace, Space y List
- ✅ Creación automática de tareas con prioridades
- ✅ Organización por fases usando tags
- ✅ Manejo de errores con mensajes claros
- ✅ Interfaz visual intuitiva

## 🔧 Configuración Inicial

### 1. Instalar Dependencias

Ejecuta el siguiente comando para instalar las nuevas dependencias:

```bash
pip install -r requirements.txt
```

O instala manualmente:

```bash
pip install requests>=2.31.0
```

### 2. Obtener tu Token de ClickUp

1. Ve a [ClickUp Settings → Apps](https://app.clickup.com/settings/apps)
2. Haz clic en **"Generate"** en la sección "API Token"
3. Copia el token generado

### 3. Configurar el Token (Opcional)

Tienes dos opciones para configurar tu token:

#### Opción A: Archivo .env (Recomendado para uso frecuente)

1. Crea un archivo `.env` en la raíz del proyecto
2. Agrega tu token:

```env
CLICKUP_API_TOKEN=tu_token_aqui
```

#### Opción B: Ingreso manual en la interfaz (Más flexible)

Simplemente ingresa tu token en el campo de la interfaz cada vez que quieras exportar tareas.

## 📖 Cómo Usar

### Paso 1: Generar un Proyecto con Tareas

1. Ve a **"Create New Project"**
2. Completa el nombre y descripción
3. Haz clic en **"Generate AI Plan"**
4. Guarda el proyecto

### Paso 2: Exportar a ClickUp

1. Abre el proyecto guardado
2. Ve a la pestaña **"📋 ClickUp Task Plan"**
3. Desplázate hasta la sección **"🚀 Export to ClickUp"**
4. Sigue estos pasos:

   **a) Conectar con ClickUp:**
   - Ingresa tu token de API
   - Haz clic en **"Connect"**

   **b) Seleccionar Workspace:**
   - Elige tu workspace de la lista desplegable

   **c) Seleccionar Space (Proyecto):**
   - Elige el espacio donde quieres crear las tareas

   **d) Seleccionar List:**
   - Elige la lista específica dentro del espacio

   **e) Crear Tareas:**
   - Haz clic en **"✨ Create Tasks in ClickUp"**
   - Espera la confirmación

### Paso 3: Verificar en ClickUp

1. Abre [ClickUp](https://app.clickup.com)
2. Ve al espacio y lista que seleccionaste
3. Verás todas las tareas organizadas con:
   - ✅ Nombres descriptivos
   - ✅ Prioridades (High, Medium, Low)
   - ✅ Tags por fase
   - ✅ Descripciones detalladas

## 🏗️ Estructura de las Tareas Creadas

Cada tarea incluye:

- **Nombre:** El nombre de la tarea tal como fue generado por IA
- **Descripción:** Incluye el nombre de la fase y detalles adicionales
- **Prioridad:** Mapeada automáticamente:
  - `high` → Urgent/High en ClickUp
  - `medium` → Normal en ClickUp
  - `low` → Low en ClickUp
- **Tags:** Nombre de la fase para fácil filtrado

## 🔒 Seguridad

- ⚠️ **NUNCA** compartas tu token de API públicamente
- ⚠️ El archivo `.env` está en `.gitignore` para evitar commits accidentales
- ⚠️ Si usas la opción de ingreso manual, el token solo se almacena en memoria durante la sesión

## 🛠️ Arquitectura Técnica

### Backend (Python/Flask)

**Archivo: `clickup_service.py`**
- Clase `ClickUpService` que maneja todas las interacciones con la API
- Métodos para obtener workspaces, spaces, lists
- Método para crear tareas individuales o en lote
- Manejo robusto de errores y timeouts

**Endpoints en `app.py`:**
- `GET /clickup/workspaces` - Obtiene lista de workspaces
- `GET /clickup/spaces/<team_id>` - Obtiene spaces de un workspace
- `GET /clickup/lists/<space_id>` - Obtiene listas de un space
- `POST /clickup/create-tasks` - Crea tareas desde las fases del proyecto

### Frontend (JavaScript)

**Funciones principales:**
- `loadClickUpWorkspaces()` - Carga y muestra workspaces
- `loadClickUpSpaces()` - Carga spaces del workspace seleccionado
- `loadClickUpLists()` - Carga listas del space seleccionado
- `createClickUpTasks()` - Envía las tareas a ClickUp

**UX Features:**
- Estados de carga ("Loading...")
- Mensajes de error claros
- Confirmación visual de éxito
- Diseño responsive y moderno

## 📊 API de ClickUp Utilizada

### Endpoints

1. **GET /team** - Lista de workspaces (teams)
2. **GET /team/{team_id}/space** - Spaces dentro de un workspace
3. **GET /space/{space_id}/list** - Listas dentro de un space
4. **POST /list/{list_id}/task** - Crear tarea en una lista

### Autenticación

Todas las peticiones incluyen el header:
```
Authorization: {tu_token}
```

## 🐛 Solución de Problemas

### Error: "Invalid ClickUp API token"

- Verifica que copiaste el token completo
- Genera un nuevo token en ClickUp Settings
- Asegúrate de no tener espacios al inicio o final

### Error: "Could not connect to ClickUp API"

- Verifica tu conexión a internet
- Revisa si ClickUp está disponible
- Intenta nuevamente en unos segundos

### Error: "Failed to create tasks"

- Verifica que seleccionaste una lista válida
- Asegúrate de tener permisos para crear tareas en ese espacio
- Revisa que el proyecto tenga tareas generadas

### Las tareas no aparecen en ClickUp

- Refresca la página de ClickUp
- Verifica que estás viendo la lista correcta
- Revisa los filtros activos en ClickUp

## 🔄 Flujo de Datos

```
1. Usuario ingresa token → Frontend
2. Frontend → Backend (/clickup/workspaces)
3. Backend → ClickUp API (GET /team)
4. ClickUp API → Backend (lista de workspaces)
5. Backend → Frontend (workspaces formateados)
6. Usuario selecciona workspace → Frontend
7. Frontend → Backend (/clickup/spaces/{team_id})
8. Backend → ClickUp API (GET /team/{team_id}/space)
9. ... (proceso similar para lists)
10. Usuario confirma → Frontend
11. Frontend → Backend (/clickup/create-tasks)
12. Backend → ClickUp API (POST /list/{list_id}/task) x N tareas
13. ClickUp API → Backend (confirmación)
14. Backend → Frontend (resumen de creación)
15. Frontend muestra mensaje de éxito
```

## 📝 Notas Adicionales

- La integración NO usa OAuth, solo API Token personal
- Las tareas se crean de forma secuencial para evitar rate limits
- Los errores individuales no detienen la creación de otras tareas
- El resumen final muestra cuántas tareas se crearon exitosamente

## 🎯 Próximas Mejoras Posibles

- [ ] Guardar configuración de workspace/space favorito
- [ ] Sincronización bidireccional (actualizar estado desde ClickUp)
- [ ] Asignación automática de tareas a miembros del equipo
- [ ] Estimación de tiempo por tarea
- [ ] Dependencias entre tareas
- [ ] Webhooks para notificaciones

## 📞 Soporte

Si encuentras algún problema o tienes sugerencias, puedes:
- Revisar los logs del servidor Flask
- Verificar la consola del navegador (F12)
- Consultar la [documentación oficial de ClickUp API](https://clickup.com/api)

---

**Versión:** 1.0.0  
**Última actualización:** Octubre 2025
