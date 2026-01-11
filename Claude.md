# Claude Context - Ambacar Notification Service

> Contexto técnico y decisiones arquitectónicas del microservicio de notificaciones multi-canal para talleres automotrices Ambacar.

---

## Resumen del Proyecto

**Ambacar Notification Service** es un microservicio Django que orquesta notificaciones multi-canal (Email, WhatsApp, Push) para el flujo de servicio automotriz de talleres Ambacar.

**Problema que resuelve:**
- Envío automático de notificaciones a clientes y staff según la fase del servicio
- Soporte para múltiples canales con fallback automático
- Configuración personalizable por tipo de servicio y taller
- Sistema de preferencias de cliente para priorizar canales

**Stack Principal:**
- Django 5.x + DRF + drf-spectacular
- PostgreSQL (Supabase)
- Celery 5.3+ (Redis broker)
- Adaptadores: SMTP, Evolution API (WhatsApp), py-webpush

---

## Arquitectura

### Patrón: Hexagonal (Ports & Adapters)

```
Core Domain (apps/core/)
├── Ports: NotificationGateway, TemplateRenderer
├── Constants: NotificationChannel, NotificationStatus, EventType
└── Authentication: InternalAPIAuthentication (service-to-service)

Notifications (apps/notifications/)
├── Models: ServicePhase, ServiceType, OrchestrationConfig, PhaseChannelConfig
├── Adapters: email_adapter, whatsapp_adapter, push_adapter
├── Services: orchestration_engine, dispatch_service, template_service
└── Views: EventDispatchView, CatalogView

Analytics (apps/analytics/)
└── Views: Summary, Recent, Health

Synchronization (apps/synchronization/)
├── Views: Customer/Vehicle sync webhooks (Internal API)
└── Tasks: Async sync via Celery (cola "sync")
```

### Colas de Celery

1. **notifications**: Envío de notificaciones (async)
2. **sync**: Sincronización de datos desde servicio Core
3. **maintenance**: Tareas programadas (recordatorios)

**Worker comando:** `celery -A config worker -l info -Q notifications,sync,maintenance --pool=solo`

---

## Conceptos de Dominio

### 1. Service Phases (ServicePhase)

5 fases del flujo automotriz:

| Slug | Nombre | Orden |
|------|--------|-------|
| `phase-schedule` | Agendar Cita | 1 |
| `phase-reception` | Recepción | 2 |
| `phase-repair` | Reparación | 3 |
| `phase-quality` | Control Calidad | 4 |
| `phase-delivery` | Entrega | 5 |

### 2. Service Types (ServiceType)

5 tipos principales con subtipos opcionales:

| Slug | Nombre | Subtipos |
|------|--------|----------|
| `mantenimiento-preventivo` | Mantenimiento Preventivo | - |
| `averia-revision` | Avería/Revisión | frenos, diagnostico, alineacion |
| `colision-pintura` | Colisión/Pintura | siniestro, golpe, pintura |
| `avaluo-comercial` | Avalúo Comercial | - |
| `avaluo-mg` | Avalúo MG | - |

### 3. Orchestration Config (OrchestrationConfig)

Configuración de notificaciones por:
- **service_type**: Tipo de servicio
- **target**: "clients" o "staff"
- **taller_id**: Opcional para config específica de taller (null = global)

**Total en seed:** 10 configs (5 tipos × 2 targets)

### 4. Phase Channel Config (PhaseChannelConfig)

Matriz que vincula:
```
OrchestrationConfig → ServicePhase → NotificationChannel → NotificationTemplate
```

**Total en seed:** 150 configs (10 configs × 5 fases × 3 canales)

**Propiedades:**
- `enabled`: Si el canal está activo para esta fase
- `template`: Template a usar (puede ser null si no hay template)

---

## Decisiones Arquitectónicas Clave

### 1. Slugs vs UUIDs (Enero 2026)

**Decisión:** Usar **slugs** en lugar de UUIDs para identificar ServiceType y ServicePhase en API externa.

**Razón:**
- El servicio **Core** de Ambacar tiene su propio catálogo de tipos/fases
- Frontend no debe consultar Notifications para obtener UUIDs → acoplamiento
- Slugs son inmutables, legibles, y sirven como "contrato" entre servicios
- Patrón: "Slugs as Contract" para microservicios

**Endpoint agregado:** `GET /api/v1/notifications/catalog/`
- Retorna todos los slugs disponibles
- Core y Notifications comparten los mismos slugs por convención
- No hay sincronización en runtime → desacoplamiento total

**Ejemplos:**
- `service_type_id: "mantenimiento-preventivo"` (antes era UUID)
- `phase_id: "phase-schedule"` (antes era UUID)

### 2. OrchestrationConfig en Seed (Enero 2026)

**Problema:** El seed solo creaba ServicePhase, ServiceType y Templates, pero NO OrchestrationConfig ni PhaseChannelConfig. Esto causaba error: "No orchestration config found".

**Solución:** Agregado método `_seed_orchestration_configs()` que crea:
- 10 OrchestrationConfig (5 tipos × 2 targets)
- 150 PhaseChannelConfig (matriz completa)
- Vincula templates existentes automáticamente

### 3. Internal API (Service-to-Service)

**Autenticación:** Header `X-Internal-Secret` con valor de `INTERNAL_API_SECRET_KEY`

**Endpoints:**
- `POST /api/internal/v1/customers/sync/`
- `POST /api/internal/v1/vehicles/sync/`

**Patrón:** Table Projection
- Core envía datos vía webhook
- Notifications crea/actualiza copia local async (cola "sync")
- No hay dependencia en tiempo de consulta

### 4. Redis en Producción (Coolify)

**Problema:** Redis interno de Coolify tiene problemas de DNS.

**Solución:** Usar **Upstash Redis** (externo) con TLS:

```python
REDIS_URL = "rediss://user:pass@host:port"  # SSL habilitado

# config/settings/base.py
# noinspection PyUnresolvedReferences
CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_NONE}
# noinspection PyUnresolvedReferences
CELERY_REDIS_BACKEND_USE_SSL = {"ssl_cert_reqs": ssl.CERT_NONE}
```

### 5. HTTP Status Codes en Dispatch

**Antes:** Siempre retornaba 202 (incluso con errores)

**Ahora:**
- **202 Accepted**: Notificaciones encoladas correctamente
- **400 Bad Request**: service_type no encontrado, customer no encontrado, validación fallida
- **500 Internal Server Error**: Errores del servidor (template rendering, etc.)

---

## Flujo de Orquestación (Dispatch)

```
1. POST /api/v1/notifications/events/dispatch/
   {
     "service_type_id": "mantenimiento-preventivo",  // slug
     "phase_id": "phase-schedule",                    // slug
     "customer_id": "CLI-001",
     "target": "clients",
     "context": {"nombre": "Carlos", "placa": "ABC123", ...}
   }

2. OrchestrationEngine.process_event()
   ├─ Buscar ServiceType por slug
   ├─ Buscar ServicePhase por slug
   ├─ Buscar OrchestrationConfig (service_type + target)
   ├─ Obtener PhaseChannelConfig habilitados
   ├─ Obtener CustomerChannelPreference (prioridad)
   └─ Resolver canales finales (preferencias + disponibles)

3. Para cada canal:
   ├─ Renderizar template con contexto ({{Nombre}}, {{Placa}}, etc.)
   ├─ Encolar tarea Celery → dispatch_service.queue_notification()
   └─ Registrar en NotificationLog

4. Celery worker (cola "notifications"):
   ├─ send_notification_task ejecuta el adapter correspondiente
   ├─ Fallback: 3 reintentos con exponential backoff
   └─ Si falla 3 veces → intenta siguiente canal en prioridad (10 min delay)
```

---

## Endpoints Críticos

### API Externa (`/api/v1/`)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/notifications/events/dispatch/` | POST | Disparar notificación por evento |
| `/notifications/catalog/` | GET | Obtener slugs de service_types y phases |
| `/notifications/orchestration/` | GET/POST/PUT/DELETE | CRUD de configs de orquestación |
| `/notifications/customers/` | GET/POST/PUT/DELETE | CRUD de clientes |
| `/notifications/templates/` | GET/POST/PUT/DELETE | CRUD de templates |
| `/analytics/summary/` | GET | Métricas de notificaciones |
| `/analytics/health/` | GET | Estado de salud de canales |
| `/health/database/` | GET | Health check de PostgreSQL/Supabase |
| `/health/redis/` | GET | Health check de Redis (Celery broker) |

### API Interna (`/api/internal/v1/`)

Requiere header: `X-Internal-Secret: <INTERNAL_API_SECRET_KEY>`

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/customers/sync/` | POST | Sincronizar datos de cliente desde Core |
| `/vehicles/sync/` | POST | Sincronizar datos de vehículo desde Core |
| `/tasks/{task_id}/status/` | GET | Estado de tarea async de sync |

---

## Variables de Entorno Críticas

### Seguridad
```bash
SECRET_KEY=<django-secret>
INTERNAL_API_SECRET_KEY=<shared-secret-with-core>
```

### Base de Datos
```bash
DATABASE_URL=postgresql://user:pass@host:port/dbname
```

### Redis (Upstash en producción)
```bash
REDIS_URL=rediss://user:pass@host:port/db  # rediss:// para SSL
```

### Email (SMTP)
```bash
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=notifications@ambacar.com
EMAIL_HOST_PASSWORD=<app-password>
EMAIL_USE_TLS=true
```

### WhatsApp (Evolution API)
```bash
EVOLUTION_API_URL=https://evolution.ambacar.com
EVOLUTION_API_KEY=<api-key>
EVOLUTION_INSTANCE=ambacar-main
```

### Push (VAPID)
```bash
VAPID_PUBLIC_KEY=<generar-con-web-push>
VAPID_PRIVATE_KEY=<generar-con-web-push>
VAPID_CONTACT_EMAIL=admin@ambacar.com
```

---

## Comandos Útiles

### Desarrollo Local

```bash
# Servidor Django
python manage.py runserver

# Celery worker (todas las colas)
celery -A config worker -l info -Q notifications,sync,maintenance --pool=solo

# Celery beat (tareas programadas)
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Crear datos iniciales
python manage.py seed_initial_data --force
```

### Producción (Docker Compose)

```bash
# Web + worker + beat (todo en uno - desarrollo)
docker-compose up -d

# Solo worker (producción)
docker-compose -f docker-compose.worker.yml up -d

# Solo beat (producción)
docker-compose -f docker-compose.beat.yml up -d
```

### Migraciones

```bash
# Crear migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Ver estado de migraciones
python manage.py showmigrations
```

---

## Variables de Template

Templates usan sintaxis `{{Variable}}` (case-sensitive):

| Variable | Ejemplo |
|----------|---------|
| `{{Nombre}}` | Carlos Mendoza |
| `{{Placa}}` | ABC123 |
| `{{Vehículo}}` | Haval H6 2024 |
| `{{Fase}}` | Recepción |
| `{{Fecha}}` | 20 de Enero, 2026 |
| `{{Hora}}` | 14:30 |
| `{{Orden}}` | OT-2025-001 |
| `{{Técnico}}` | Juan Pérez |
| `{{Taller}}` | Ambacar Service |

---

## Troubleshooting Común

### 1. Error: "No orchestration config found"

**Causa:** Falta OrchestrationConfig para ese service_type + target.

**Solución:**
```bash
python manage.py seed_initial_data --force
```

### 2. Error: "ServiceType not found with slug: X"

**Causa:** El slug no existe en la base de datos.

**Verificar:**
```bash
curl http://localhost:8000/api/v1/notifications/catalog/
```

**Solución:** Usar slug válido del catálogo o ejecutar seed.

### 3. Celery tasks no se ejecutan

**Verificar:**
1. Redis está corriendo: `redis-cli ping` → debe retornar "PONG"
2. Worker está activo: `celery -A config inspect active`
3. Worker está escuchando colas correctas: verificar `-Q notifications,sync,maintenance`

### 4. Notificaciones retornan 202 pero no se envían

**Verificar:**
1. Logs del worker: `celery -A config worker -l debug`
2. Estado de tarea: `GET /api/internal/v1/tasks/{task_id}/status/`
3. Credenciales de adaptadores (SMTP, Evolution API, VAPID)

### 5. Error: "is not a valid uuid" al hacer dispatch

**Causa:** Estás enviando un slug pero el código espera UUID (versión antigua).

**Solución:** Asegúrate de tener la última versión con soporte de slugs:
- `orchestration_engine.py` debe buscar por `ServiceType.objects.filter(slug=...)`
- Migración `0002_add_slug_to_service_models.py` debe estar aplicada

### 6. Variables de template no se renderizan (aparecen literalmente como {{Variable}})

**Síntoma:** Las notificaciones muestran `{{Vehículo}}` o `{{Nombre}}` literalmente en lugar del valor real.

**Causa:** Variable con caracteres Unicode (acentos) que el regex no puede capturar.

**Solución aplicada (Enero 2026):**
- Actualizado regex en `template_service.py` para soportar Unicode
- Ahora funciona con: `{{Vehículo}}`, `{{Año}}`, `{{Técnico}}`, etc.

**Verificar:**
```bash
# Las variables en el contexto deben coincidir (case-insensitive)
# ✅ CORRECTO: context = {"vehiculo": "Toyota"} → renderiza {{Vehículo}}
# ✅ CORRECTO: context = {"nombre": "Carlos"} → renderiza {{Nombre}}
# ❌ INCORRECTO: context = {"auto": "Toyota"} → NO renderiza {{Vehículo}}
```

**Depuración:**
1. Verificar que el contexto incluya la variable (sin acento, lowercase)
2. Logs del worker: buscar "Rendering template" para ver contexto enviado
3. Probar template desde admin: Ver preview de template con datos de ejemplo

### 7. Alto consumo de comandos Redis (Upstash)

**Síntoma:** 80K+ comandos en pocas horas, principalmente PING/PUBLISH.

**Causas:**
1. **Múltiples instancias de Beat** → Tareas programadas ejecutándose varias veces
2. **Heartbeat muy frecuente** → Workers envían PING cada 2s (default)
3. **Tareas periódicas innecesarias** → `retry_failed_notifications` se ejecuta aunque no haya nada

**Solución (ya implementada en Enero 2026):**

✅ **Configuración optimizada en `config/settings/base.py`:**
```python
CELERY_BROKER_HEARTBEAT = 240  # 4 minutos (era 2s, máximo seguro para Upstash)
CELERY_TASK_SEND_SENT_EVENT = False  # Deshabilitar eventos
CELERY_WORKER_SEND_TASK_EVENTS = False
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
```

✅ **Tarea optimizada con early return:**
- `retry_failed_notifications` ahora revisa si hay notificaciones pendientes antes de procesar
- Frecuencia reducida de cada 15 min → cada 1 hora

✅ **Deployment correcto en Coolify:**
```
IMPORTANTE: Solo debe haber 1 instancia de Beat corriendo

✅ CORRECTO (3 instancias separadas):
- ambacar-notifications-web (Django)
- ambacar-notifications-worker (Celery worker)
- ambacar-notifications-beat (Celery beat) ← SOLO UNA

❌ INCORRECTO:
- Tener Beat habilitado en múltiples instancias
- Correr "docker-compose up" en múltiples servidores
```

**Resultado esperado:**
- **Antes:** 88K comandos/12h (~7,333/hora)
- **Después:** ~1.5K comandos/12h (~125/hora) → **Reducción de ~98%**

**Desglose de comandos/hora optimizados:**
- Heartbeat PING: 15/h (era 1,800/h con 2s interval)
- Task events: 0/h (era ~500/h, ahora deshabilitados)
- Retry task: 2/h (era ~96/h con 15min interval)
- Overhead normal: ~108/h (queuing, results, connections)

### 8. Worker se reinicia constantemente en Coolify (después de migrar de Upstash a Redis local)

**Síntoma:**
- Worker reinicia cada 30-50 minutos en Coolify
- Health check de Redis muestra estado "healthy" con conexión exitosa
- Notificaciones se quedan encoladas y nunca se procesan
- Logs muestran múltiples inicios del worker sin mensajes de error claros

**Causa:**
Configuraciones optimizadas para **Upstash Redis con SSL** (`rediss://`) son incompatibles con **Redis local sin SSL** (`redis://`):

1. **`--without-heartbeat` en worker command**: Deshabilita heartbeats, causando que Redis local cierre conexiones idle por timeout
2. **`socket_keepalive_options` agresivas**: Configuradas para conexiones SSL/TLS remotas, no funcionan bien con Redis local
3. **Health check HTTP en Coolify**: Worker es un proceso CLI sin servidor HTTP, Coolify lo detecta como "unhealthy"

**Solución (Enero 2026):**

✅ **1. Actualizar `docker-compose.worker.yml`:**
```yaml
# ANTES (optimizado para Upstash SSL):
command: 'celery -A config worker -l info -Q notifications,sync,maintenance --pool=solo --without-gossip --without-mingle --without-heartbeat'

# DESPUÉS (compatible con Redis local):
command: 'celery -A config worker -l info -Q notifications,sync,maintenance --pool=solo --without-gossip --without-mingle'
```
**Cambio:** Removido `--without-heartbeat` para permitir heartbeats normales con Redis local.

✅ **2. Configuración adaptativa en `config/settings/base.py`:**

**Heartbeat adaptativo:**
```python
# Detectar tipo de Redis por URL
_redis_url = os.environ.get("REDIS_URL", "")
if _redis_url.startswith("rediss://"):
    CELERY_BROKER_HEARTBEAT = 240  # 4 min para Upstash SSL
else:
    CELERY_BROKER_HEARTBEAT = 60  # 1 min para Redis local
```

**Transport options adaptativas:**
```python
if _redis_url.startswith("rediss://"):
    # Upstash con SSL: keepalive agresivo para SSL/TLS
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        'visibility_timeout': 3600,
        'socket_timeout': 30,
        'socket_connect_timeout': 30,
        'socket_keepalive': True,
        'socket_keepalive_options': {
            socket.TCP_KEEPIDLE: 30,
            socket.TCP_KEEPINTVL: 10,
            socket.TCP_KEEPCNT: 3,
        },
        'max_connections': 5,
    }
else:
    # Redis local: configuración simple y estable
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        'visibility_timeout': 3600,
        'socket_timeout': 120,  # Timeout más largo para conexiones estables
        'socket_connect_timeout': 10,
        'max_connections': 10,  # Sin límites estrictos de tier
    }
```

✅ **3. Desactivar Health Check HTTP en Coolify (CRÍTICO):**

**Problema:** Coolify intenta hacer health checks HTTP al Worker, pero el Worker es un proceso CLI sin servidor HTTP.

**Pasos en Coolify UI:**
1. Ir a recurso `ambacar-notifications-worker`
2. Pestaña **"Configuration"** o **"Health Check"**
3. **Deshabilitar** el health check HTTP o configurar correctamente:
   - **Opción 1 (Recomendada):** Deshabilitar health check completamente (Worker no necesita HTTP)
   - **Opción 2:** Cambiar a health check tipo "process" que verifique que el proceso `celery` esté corriendo
4. Guardar y redesplegar

**Verificación después de aplicar:**
```bash
# 1. Verificar que el worker no se reinicie después de 5-10 minutos
# 2. Health check de Redis debe seguir mostrando "healthy"
curl https://your-app.com/api/v1/health/redis/

# 3. Disparar una notificación de prueba
curl -X POST https://your-app.com/api/v1/notifications/events/dispatch/ \
  -H "Content-Type: application/json" \
  -d '{
    "service_type_id": "mantenimiento-preventivo",
    "phase_id": "phase-schedule",
    "customer_id": "CLI-001",
    "target": "clients",
    "context": {...}
  }'

# 4. Verificar que la notificación se procese (queue notifications debe bajar de 2 → 0)
curl https://your-app.com/api/v1/health/redis/
# "queues": { "notifications": 0 }  ← debe ser 0 después de procesarse
```

**Resultado esperado:**
- ✅ Worker NO se reinicia automáticamente
- ✅ Notificaciones encoladas se procesan correctamente
- ✅ Health check de Redis sigue mostrando "healthy"
- ✅ Queue `notifications` pasa de 2 → 0 después de procesar

---

## Estructura de Archivos Importante

```
apps/
├── core/
│   ├── ports/notification_gateway.py          # Interfaz para adapters
│   ├── constants.py                            # Enums (Channel, Status, EventType)
│   └── authentication.py                       # InternalAPIAuthentication
│
├── notifications/
│   ├── models/
│   │   ├── orchestration.py                    # ServicePhase, ServiceType, OrchestrationConfig
│   │   ├── templates.py                        # NotificationTemplate
│   │   ├── customers.py                        # CustomerContactInfo, Preferences
│   │   └── logs.py                             # NotificationLog
│   │
│   ├── services/
│   │   ├── orchestration_engine.py             # Motor principal de orquestación
│   │   ├── dispatch_service.py                 # Encolado y fallback
│   │   └── template_service.py                 # Renderizado de templates
│   │
│   ├── adapters/
│   │   ├── email_adapter.py                    # SMTP
│   │   ├── whatsapp_adapter.py                 # Evolution API
│   │   └── push_adapter.py                     # Web Push + VAPID
│   │
│   ├── views/
│   │   ├── events.py                           # EventDispatchView (POST dispatch)
│   │   ├── catalog.py                          # CatalogView (GET slugs)
│   │   └── orchestration.py                    # CRUD de configs
│   │
│   ├── tasks.py                                # Celery tasks (send_notification_task)
│   └── management/commands/
│       └── seed_initial_data.py                # Seed de datos iniciales
│
├── analytics/
│   └── views.py                                # Summary, Recent, Health
│
└── synchronization/
    ├── views.py                                # Customer/Vehicle sync (Internal API)
    └── tasks.py                                # Async sync tasks (cola "sync")
```

---

## Documentación API

- **Swagger UI**: `http://localhost:8000/api/docs/`
- **ReDoc**: `http://localhost:8000/api/redoc/`
- **Schema JSON**: `http://localhost:8000/api/schema/`

---

## Historial de Cambios Importantes

### Enero 2026
- ✅ Agregado soporte de **slugs** para ServiceType y ServicePhase
- ✅ Creado endpoint `/catalog/` para consultar slugs
- ✅ Seed ahora crea **OrchestrationConfig** y **PhaseChannelConfig**
- ✅ Mejorados HTTP status codes en dispatch (202/400/500)
- ✅ Migrado a Upstash Redis (SSL) para producción en Coolify
- ✅ **Optimización crítica de Redis** (reducción de 90%+ en comandos):
  - Heartbeat aumentado de 2s → 4 minutos (máximo seguro para Upstash timeout 310s)
  - Eventos de tareas deshabilitados (task events)
  - `retry_failed_notifications` con early return y frecuencia 15min → 1h
  - Documentación de deployment correcto (1 sola instancia de Beat)
- ✅ Activado `CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS` para prevenir duplicados
- ✅ **Bug crítico corregido**: Canales deshabilitados (`enabled=false`) ahora se respetan correctamente
  - Problema: `_resolve_channels()` enviaba notificaciones a canales explícitamente deshabilitados por el cliente
  - Solución: Query de canales deshabilitados antes de agregar canales por defecto
  - Impacto: Cumplimiento de preferencias de usuario y compliance de privacidad
- ✅ **Optimización avanzada de Redis/Celery** (segunda fase - reducción adicional ~53%):
  - `CELERY_BROKER_TRANSPORT_OPTIONS`: Configuración completa con:
    - `visibility_timeout: 3600` (1h, default de Celery, apropiado para tareas <30min)
    - `socket_timeout/socket_connect_timeout: 30s` (estabilidad con SSL)
    - `socket_keepalive: True` con TCP_KEEPIDLE/KEEPINTVL/KEEPCNT usando constantes correctas de `socket` module
    - `max_connections: 5` (conservador para límites de Upstash: 3 instancias × 5 = 15 conexiones concurrentes)
  - `CELERY_TASK_TRACK_STARTED = False`: Deshabilitado tracking de inicio de tareas (reduce PUBLISH)
  - Worker flags: `--without-gossip --without-mingle --without-heartbeat` (reduce comunicación inter-worker)
  - `CELERY_RESULT_EXPIRES`: Resultados expiran en 24h automáticamente
  - `CELERY_BROKER_POOL_LIMIT: 5` (alineado con max_connections)
  - Campo `inferred_status` en analytics: Muestra "pending_or_in_progress" cuando sent_at es null
  - Impacto: BRPOP -95%, PUBLISH -41%, total ~130K → 61K comandos/día
  - **Fix importante:** Corregido `socket_keepalive_options` para usar constantes de socket correctas (`socket.TCP_KEEPIDLE` en lugar de números 1,2,3) evitando "Error 22: Invalid argument"
- ✅ Documentación mejorada para `update_preferences()` y `complete()`
- ✅ **Fix crítico de renderizado de templates**: Soporte para caracteres Unicode en variables
  - Problema: Variables con acentos como `{{Vehículo}}` no se renderizaban (aparecían literalmente en WhatsApp/Email)
  - Causa: Regex `\{\{(\w+)\}\}` solo capturaba ASCII [a-zA-Z0-9_], no caracteres con acento
  - Solución: Actualizado regex a `\{\{([^\{\}\s]+)\}\}` para soportar cualquier caracter Unicode excepto llaves y espacios
  - Impacto: Templates ahora funcionan correctamente con variables como {{Vehículo}}, {{Año}}, {{Técnico}}, etc.
  - Archivo modificado: `apps/notifications/services/template_service.py`
- ✅ **Normalización Unicode accent-insensitive en template matching**:
  - Problema: `{{Vehículo}}` (con acento) no matcheaba con context key `"Vehiculo"` (sin acento)
  - Causa: Lowercase comparison `"vehículo"` != `"vehiculo"` (acentos no se normalizaban)
  - Solución: Agregado método `_normalize()` usando `unicodedata.normalize('NFD')` para remover acentos antes de comparar
  - Ahora funciona: Template `{{Vehículo}}` + Context `{"Vehiculo": "..."}` → ✅ Match correcto
  - Archivos modificados: `template_service.py`, `orchestration_engine.py`
- ✅ **Auto-enriquecimiento conservador de contexto**:
  - Implementado enriquecimiento SOLO de `Nombre` del cliente si falta en el context
  - NO se auto-enriquecen campos ambiguos: `vehiculo`, `taller`, `placa` (cliente puede tener múltiples vehículos/talleres)
  - Context del request SIEMPRE tiene precedencia sobre auto-enriquecimiento
  - Método: `OrchestrationEngine._enrich_context_minimal()`
  - Archivo modificado: `apps/notifications/services/orchestration_engine.py`
- ✅ **Validación DINÁMICA de variables de template** (Arquitectura híbrida):
  - **Problema identificado**: Validación estática con lista hardcoded no se adapta a templates creados desde frontend
  - **Solución**: Arquitectura híbrida de 2 capas:
    1. **Validación mínima en `events.py`** (fast-fail): Solo 3 campos universales (nombre, vehiculo, placa)
    2. **Validación dinámica en `orchestration_engine.py`** (completa): Extrae variables de templates reales y valida contra context
  - **Método `_validate_template_variables()`**:
    - Extrae TODAS las variables de templates habilitados usando `template_service.get_variables()`
    - Valida que todas las variables extraídas existan en `enriched_context` (accent-insensitive)
    - Ejecuta DESPUÉS de enriquecimiento y ANTES de renderizado
    - Retorna `400 Bad Request` con lista de variables faltantes si la validación falla
  - **Endpoint `preview` en `templates.py`**:
    - También implementa validación dinámica para prevenir errores de rendering
    - Extrae variables del template body y valida contra context provisto
    - Retorna error claro si faltan variables antes de intentar renderizar
  - **Ventajas**:
    - ✅ Se adapta automáticamente cuando se agregan nuevas variables a templates
    - ✅ No requiere actualizar código cuando cambian templates
    - ✅ Valida EXACTAMENTE lo que el template necesita (no más, no menos)
    - ✅ Previene notificaciones con placeholders `{{Variable}}` vacíos
  - **Archivos modificados**:
    - `apps/notifications/services/orchestration_engine.py` (validación principal)
    - `apps/notifications/views/events.py` (validación mínima universal)
    - `apps/notifications/views/templates.py` (validación en preview endpoint)
- ✅ **Health check de Redis** (`/api/v1/health/redis/`):
  - Endpoint para verificar conectividad a Redis (Celery broker) desde servicios Web/Worker/Beat
  - Retorna: estado de conexión, latencia PING, longitud de colas (notifications, sync, maintenance), connection pool settings
  - Útil para validar configuración de Redis en Coolify después de despliegues
  - Archivos creados: `apps/core/views.py` (RedisHealthView), actualizado `apps/core/urls.py`
- ✅ **Soporte dual Redis: Upstash SSL + Redis local** (Configuración adaptativa):
  - **Problema**: Configuraciones optimizadas para Upstash Redis con SSL (`rediss://`) causaban reinicios constantes del Worker al migrar a Redis local (`redis://`) en Coolify
  - **Síntomas**: Worker reiniciaba cada 30-50 min, notificaciones encoladas no se procesaban, health check mostraba "healthy" pero logs sin errores claros
  - **Causa raíz**:
    - `--without-heartbeat` en worker command causaba timeouts con Redis local
    - `socket_keepalive_options` agresivas optimizadas para SSL/TLS remotas incompatibles con Redis local
    - Coolify con health check HTTP en Worker (proceso CLI sin HTTP) → "unhealthy" → restart loop
  - **Solución**:
    - Removido `--without-heartbeat` de `docker-compose.worker.yml` (permite heartbeats normales)
    - Configuración adaptativa en `base.py` detecta `rediss://` vs `redis://`:
      - **Upstash SSL**: `CELERY_BROKER_HEARTBEAT = 240s`, socket keepalive agresivo, `max_connections = 5`
      - **Redis local**: `CELERY_BROKER_HEARTBEAT = 60s`, timeouts largos (120s), sin keepalive TCP, `max_connections = 10`
    - Documentado cómo desactivar health check HTTP en Coolify para Worker
  - **Impacto**: Worker estable sin reinicios, notificaciones procesadas correctamente, compatible con ambos tipos de Redis
  - **Archivos modificados**: `docker-compose.worker.yml`, `config/settings/base.py`, `CLAUDE.md` (troubleshooting #8)

### Diciembre 2025
- ✅ Implementado patrón Table Projection (sincronización async)
- ✅ Agregado health check de base de datos (`/api/v1/health/database/`)
- ✅ Configuración de colas Celery por tipo de tarea

---

## Contacto y Recursos

**Repositorio:** ambacar-backend-notifications
**Documentación completa:** Ver `README.md`
**Owner:** Ambacar
**Última actualización:** Enero 2026
