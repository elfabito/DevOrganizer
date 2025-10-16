# ClickUp Integration - Inicio Rápido ⚡

## 🎯 Setup en 3 Pasos

### 1️⃣ Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 2️⃣ Configurar Token de ClickUp

1. Obtén tu token desde: https://app.clickup.com/settings/apps
2. Crea un archivo `.env` en la raíz del proyecto
3. Agrega tu token:
```env
CLICKUP_API_TOKEN=tu_token_aqui
```
4. **Reinicia el servidor Flask** para que cargue el token

### 3️⃣ Usar la Integración
1. Abre un proyecto en DevOrganizer
2. Ve a la pestaña **"📋 ClickUp Task Plan"**
3. Scroll hasta **"🚀 Export to ClickUp"**
4. **Los workspaces se cargan automáticamente** ✨
5. Selecciona: Workspace → Space → List
6. Haz clic en **"✨ Create Tasks in ClickUp"**

## ✅ ¡Listo!

Tus tareas ahora están en ClickUp con:
- ✅ Prioridades asignadas
- ✅ Organizadas por fases (tags)
- ✅ Descripciones completas

---

**¿Problemas?** Lee el archivo `CLICKUP_INTEGRATION_README.md` para más detalles.
