# 🚀 Inicio Rápido - Dev Project Organizer

## Configuración en 3 Pasos

### 1️⃣ Instalar Dependencias

Instala las dependencias con:
```bash
pip install -r requirements.txt
```

Esto instalará Flask, Groq y python-dotenv.

✅ ¡Listo!

### 2️⃣ Configurar API Key de Groq (¡100% GRATIS!)

Obtén tu clave API GRATIS (sin tarjeta): https://console.groq.com/keys

**Opción A: Variable de Entorno (Recomendado)**

En PowerShell:
```powershell
$env:GROQ_API_KEY="tu-api-key-aqui"
```

En CMD:
```cmd
set GROQ_API_KEY=tu-api-key-aqui
```

**Opción B: Archivo .env**

1. Crea un archivo `.env` en la carpeta del proyecto
2. Agrega tu API key:
   ```
   GROQ_API_KEY=gsk-tu-clave-aqui
   ```

**Opción C: Directamente en el Código**

Edita `ai_service.py` línea 18:
```python
client = Groq(api_key="gsk-tu-api-key-aqui")
```

### 3️⃣ Ejecutar la Aplicación

```bash
python app.py
```

Abre tu navegador en: **http://127.0.0.1:5000**

---

## 📖 Cómo Usar

### Crear un Proyecto

1. Haz clic en **"Create Project"**
2. Ingresa el nombre y descripción del proyecto
3. Haz clic en **"Generate AI Analysis"**
4. Revisa las preguntas técnicas, stack recomendado y plan de tareas
5. Haz clic en **"Save Project"**

### Ver Proyectos

- Todos los proyectos se muestran en la página principal
- Haz clic en cualquier tarjeta para ver los detalles completos

### Eliminar Proyectos

- Abre un proyecto
- Haz clic en el botón **"Delete"**

---

## 🤖 Sobre la IA

La aplicación usa **Llama 3.3 70B** de Groq (¡100% GRATIS!) para generar:

- ✅ Preguntas técnicas categorizadas
- ✅ Recomendaciones de stack tecnológico
- ✅ Hitos clave del proyecto
- ✅ Plan de tareas estilo ClickUp

### Cambiar el Modelo

Edita `ai_service.py` línea 70:

```python
model="llama-3.3-70b-versatile",  # Rápido, potente y GRATIS
```

**Modelos disponibles (todos GRATIS):**
- `llama-3.3-70b-versatile` - Mejor balance ⚡ (recomendado)
- `llama-3.1-70b-versatile` - Muy rápido y capaz
- `mixtral-8x7b-32768` - Bueno para contextos largos
- `gemma2-9b-it` - Ligero y rápido

### ¿Por qué Groq?

- ✅ **100% GRATIS** - Sin tarjeta de crédito
- ✅ **ULTRA RÁPIDO** - El más rápido del mercado
- ✅ **POTENTE** - Llama 3.3 70B es muy capaz
- ✅ **Límites generosos** - Mucho más que otros servicios

---

## 💾 Almacenamiento

Los proyectos se guardan en `projects.json` en el mismo directorio.

Puedes:
- ✅ Hacer backup del archivo
- ✅ Compartirlo con otros
- ✅ Editarlo manualmente (es JSON válido)

---

## ⚠️ Solución de Problemas

### Error: "GROQ_API_KEY not set"

**Solución:** Configura tu API key (ver paso 2 arriba)

### Error: "Module not found"

**Solución:** Instala las dependencias:
```bash
pip install -r requirements.txt
```

### Error: "Port 5000 already in use"

**Solución:** Cambia el puerto en `app.py` línea 172:
```python
app.run(debug=True, host='127.0.0.1', port=5001)  # Cambia 5000 a 5001
```

### La IA no responde o da error

**Posibles causas:**
1. API key incorrecta
2. Límite de rate exceeded (espera unos minutos)
3. Problema de conexión a internet

**Solución:** Verifica tu API key en https://console.groq.com/keys

---

## 📁 Estructura del Proyecto

```
DevOrganizer/
├── app.py                 # Aplicación Flask principal
├── ai_service.py          # Integración con Groq API
├── storage.py             # Almacenamiento en JSON
├── templates/             # Plantillas HTML
│   ├── base.html
│   ├── index.html
│   ├── create.html
│   ├── project_detail.html
│   └── error.html
├── projects.json          # Datos (se crea automáticamente)
├── requirements.txt       # Dependencias
└── README.md             # Documentación completa
```

---

## 🎯 Próximos Pasos

1. **Personaliza el prompt de IA** en `ai_service.py` para ajustarlo a tus necesidades
2. **Modifica los estilos** en los templates HTML
3. **Agrega nuevas funcionalidades** según tus requerimientos

---

## 💡 Consejos

- Sé específico en las descripciones de proyectos para mejores resultados de IA
- Groq es 100% GRATIS - ¡úsalo sin preocuparte por costos!
- Haz backup de `projects.json` regularmente
- Groq es ultra rápido - las respuestas son casi instantáneas
- Más info sobre Groq: https://groq.com

---

**¡Disfruta organizando tus proyectos! 🚀**
