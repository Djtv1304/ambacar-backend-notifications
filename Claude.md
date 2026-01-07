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
- ✅ Documentación mejorada para `update_preferences()` y `complete()`

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
