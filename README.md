# Ambacar Notification Service

Microservicio de orquestación de notificaciones multi-canal para talleres Ambacar.

## Stack Tecnológico

- **Framework**: Django 5.x + Django REST Framework
- **Base de Datos**: PostgreSQL (Supabase)
- **Colas**: Celery + Redis
- **Documentación**: drf-spectacular (Swagger/OpenAPI)
- **Arquitectura**: Hexagonal (Ports & Adapters)

## Canales de Notificación

- **Email**: SMTP (Django mail backend)
- **WhatsApp**: Evolution API
- **Push**: Web Push con VAPID (py-webpush)

## Configuración Rápida

### 1. Clonar y crear entorno virtual

```bash
cd ambacar-backend-notifications
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements/development.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus credenciales
```

#### Variables de Entorno Requeridas

Copiar `.env.example` a `.env` y configurar las siguientes variables:

##### Django Core
- `SECRET_KEY`: Clave secreta de Django (generar nueva para producción)
- `DEBUG`: True para desarrollo, False para producción
- `ALLOWED_HOSTS`: Lista de hosts permitidos separados por coma

##### Seguridad - API Interna
- `INTERNAL_API_SECRET_KEY`: Clave para autenticación service-to-service (endpoints `/api/internal/v1/`)

##### Base de Datos
- `DATABASE_URL`: URL de conexión PostgreSQL (formato: `postgresql://user:pass@host:port/dbname`)

##### Redis
- `REDIS_URL`: URL de conexión Redis (formato: `redis://user:pass@host:port/db`)

##### Email (SMTP)
- `EMAIL_BACKEND`: Backend de email (default: `django.core.mail.backends.smtp.EmailBackend`)
- `EMAIL_HOST`: Servidor SMTP
- `EMAIL_PORT`: Puerto SMTP (465 para SSL, 587 para TLS)
- `EMAIL_HOST_USER`: Usuario SMTP
- `EMAIL_HOST_PASSWORD`: Contraseña SMTP
- `EMAIL_USE_TLS`: true/false
- `EMAIL_USE_SSL`: true/false
- `DEFAULT_FROM_EMAIL`: Email remitente por defecto

##### WhatsApp (Evolution API)
- `EVOLUTION_API_URL`: URL de Evolution API
- `EVOLUTION_API_KEY`: API Key de Evolution
- `EVOLUTION_INSTANCE`: Nombre de la instancia
- `EVOLUTION_TIMEOUT`: Timeout en segundos (default: 100)

##### Push Notifications (VAPID)
- `VAPID_PUBLIC_KEY`: Clave pública VAPID (generar con: `npx web-push generate-vapid-keys`)
- `VAPID_PRIVATE_KEY`: Clave privada VAPID
- `VAPID_CONTACT_EMAIL`: Email de contacto para VAPID

##### Frontend
- `FRONTEND_URL`: URL del frontend para enlaces en emails

### 4. Ejecutar migraciones

```bash
python manage.py migrate
```

### 5. Cargar datos iniciales

```bash
python manage.py seed_initial_data
```

### 6. Ejecutar servidor de desarrollo

```bash
python manage.py runserver
```

### 7. Ejecutar Celery Worker (en otra terminal)

```bash
celery -A config worker -l info -Q notifications,sync,maintenance --pool=solo
```

### 8. Ejecutar Celery Beat (en otra terminal)

```bash
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

## Docker

El proyecto incluye 3 archivos de Docker Compose para diferentes propósitos:

### Desarrollo Local (Todos los servicios)

```bash
docker-compose up -d
```

Incluye: web, celery worker, celery beat, redis, postgresql

### Solo Worker (Producción)

```bash
docker-compose -f docker-compose.worker.yml up -d
```

Worker de Celery con colas: notifications, sync, maintenance (pool=solo)

### Solo Beat Scheduler (Producción)

```bash
docker-compose -f docker-compose.beat.yml up -d
```

Celery Beat para tareas programadas (usa DatabaseScheduler)

## Documentación API

- Swagger UI: http://localhost:8000/api/docs/
- ReDoc: http://localhost:8000/api/redoc/
- Schema JSON: http://localhost:8000/api/schema/

## Endpoints API

### API Externa (`/api/v1/`)

#### Events - Notification Dispatch

| Método | Endpoint | Descripción | Response Codes |
|--------|----------|-------------|----------------|
| POST | `/api/v1/notifications/events/dispatch/` | Disparar notificación basada en evento del flujo de servicio | `202` Accepted (notifications queued)<br>`400` Bad Request (service_type/customer not found, validation failed, missing context variables)<br>`500` Internal Server Error (template rendering errors, server failures) |

#### Catalog - Lookup Available Options

| Método | Endpoint | Descripción | Response Codes |
|--------|----------|-------------|----------------|
| GET | `/api/v1/notifications/catalog/` | Obtener catálogo completo de slugs (service_types y phases) para usar en dispatch | `200` OK |

#### Templates - Notification Template Management

| Método | Endpoint | Descripción | Response Codes |
|--------|----------|-------------|----------------|
| GET | `/api/v1/notifications/templates/` | Listar todas las plantillas de notificación con paginación | `200` OK |
| GET | `/api/v1/notifications/templates/{id}/` | Obtener detalles de una plantilla específica | `200` OK<br>`404` Not Found |
| POST | `/api/v1/notifications/templates/` | Crear una nueva plantilla de notificación | `201` Created<br>`400` Bad Request |
| PUT | `/api/v1/notifications/templates/{id}/` | Actualizar plantilla completa (todos los campos requeridos) | `200` OK<br>`400` Bad Request<br>`404` Not Found |
| PATCH | `/api/v1/notifications/templates/{id}/` | Actualizar parcialmente plantilla (solo campos provistos) | `200` OK<br>`400` Bad Request<br>`404` Not Found |
| DELETE | `/api/v1/notifications/templates/{id}/` | Eliminar una plantilla | `204` No Content<br>`404` Not Found |
| POST | `/api/v1/notifications/templates/preview/` | Vista previa de plantilla con contexto (incluye validación dinámica de variables) | `200` OK<br>`400` Bad Request (missing variables) |
| GET | `/api/v1/notifications/templates/variables/` | Listar todas las variables disponibles para templates | `200` OK |
| GET | `/api/v1/notifications/templates/for_context/` | Obtener plantilla filtrada por contexto (service_type + phase + channel + target + optional subtype) | `200` OK<br>`404` Not Found |

**Filtros disponibles** (GET list):
- `channel` - Filtrar por canal de notificación (email/whatsapp/push)
- `target` - Filtrar por audiencia objetivo (clients/staff)
- `service_type_id` - Filtrar por UUID de tipo de servicio
- `phase_id` - Filtrar por UUID de fase de servicio
- `taller_id` - Filtrar por UUID de taller (null para plantillas globales)
- `is_active` - Filtrar por estado activo (true/false)

#### Orchestration Configuration

##### Service Phases (Read-only)

| Método | Endpoint | Descripción | Response Codes |
|--------|----------|-------------|----------------|
| GET | `/api/v1/notifications/phases/` | Listar todas las fases de servicio ordenadas (5 fases del flujo) | `200` OK |
| GET | `/api/v1/notifications/phases/{id}/` | Obtener detalles de una fase específica | `200` OK<br>`404` Not Found |

##### Service Types (Read-only)

| Método | Endpoint | Descripción | Response Codes |
|--------|----------|-------------|----------------|
| GET | `/api/v1/notifications/service-types/` | Listar todos los tipos de servicio con sus subtipos | `200` OK |
| GET | `/api/v1/notifications/service-types/{id}/` | Obtener detalles de un tipo de servicio específico | `200` OK<br>`404` Not Found |

##### Orchestration Configs (Full CRUD)

| Método | Endpoint | Descripción | Response Codes |
|--------|----------|-------------|----------------|
| GET | `/api/v1/notifications/orchestration/` | Listar configuraciones de orquestación con paginación | `200` OK |
| GET | `/api/v1/notifications/orchestration/{id}/` | Obtener config de orquestación con settings de canales por fase | `200` OK<br>`404` Not Found |
| POST | `/api/v1/notifications/orchestration/` | Crear nueva configuración de orquestación | `201` Created<br>`400` Bad Request |
| PUT | `/api/v1/notifications/orchestration/{id}/` | Actualizar config completa (todos los campos requeridos) | `200` OK<br>`400` Bad Request<br>`404` Not Found |
| PATCH | `/api/v1/notifications/orchestration/{id}/` | Actualizar parcialmente config (solo campos provistos) | `200` OK<br>`400` Bad Request<br>`404` Not Found |
| DELETE | `/api/v1/notifications/orchestration/{id}/` | Eliminar configuración de orquestación | `204` No Content<br>`404` Not Found |
| POST | `/api/v1/notifications/orchestration/{id}/update_matrix/` | Actualizar en batch configuraciones de canales por fase (matriz completa) | `200` OK<br>`400` Bad Request<br>`404` Not Found |
| POST | `/api/v1/notifications/orchestration/{id}/initialize_phases/` | Crear configs por defecto de canales para todas las fases | `200` OK<br>`404` Not Found |

**Filtros disponibles** (GET list):
- `service_type_id` - Filtrar por UUID de tipo de servicio
- `target` - Filtrar por audiencia objetivo (clients/staff)
- `taller_id` - Filtrar por UUID de taller (null para configs globales)

#### Customers & Vehicles

##### Customer Contact Info (Full CRUD)

| Método | Endpoint | Descripción | Response Codes |
|--------|----------|-------------|----------------|
| GET | `/api/v1/notifications/customers/` | Listar todos los clientes con paginación y búsqueda | `200` OK |
| GET | `/api/v1/notifications/customers/{customer_id}/` | Obtener información detallada de un cliente | `200` OK<br>`404` Not Found |
| POST | `/api/v1/notifications/customers/` | Crear nuevo cliente | `201` Created<br>`400` Bad Request |
| PUT | `/api/v1/notifications/customers/{customer_id}/` | Actualizar cliente completo (todos los campos requeridos) | `200` OK<br>`400` Bad Request<br>`404` Not Found |
| PATCH | `/api/v1/notifications/customers/{customer_id}/` | Actualizar parcialmente cliente (solo campos provistos) | `200` OK<br>`400` Bad Request<br>`404` Not Found |
| DELETE | `/api/v1/notifications/customers/{customer_id}/` | Eliminar cliente | `204` No Content<br>`404` Not Found |
| GET | `/api/v1/notifications/customers/{customer_id}/preferences/` | Obtener preferencias de canales de notificación del cliente | `200` OK<br>`404` Not Found |
| POST | `/api/v1/notifications/customers/{customer_id}/update_preferences/` | Actualizar preferencias de canales (email, whatsapp, push con prioridad) | `200` OK<br>`400` Bad Request<br>`404` Not Found |
| GET | `/api/v1/notifications/customers/{customer_id}/vehicles/` | Listar todos los vehículos asociados al cliente | `200` OK<br>`404` Not Found |
| GET | `/api/v1/notifications/customers/{customer_id}/reminders/` | Listar recordatorios de mantenimiento del cliente | `200` OK<br>`404` Not Found |

**Filtros disponibles**:
- Paginación estándar y búsqueda por nombre/email/phone

**Filtros para reminders**:
- `status` - Filtrar por estado (pending/completed/cancelled)

##### Vehicles (Full CRUD)

| Método | Endpoint | Descripción | Response Codes |
|--------|----------|-------------|----------------|
| GET | `/api/v1/notifications/vehicles/` | Listar todos los vehículos con paginación | `200` OK |
| GET | `/api/v1/notifications/vehicles/{id}/` | Obtener información detallada de un vehículo | `200` OK<br>`404` Not Found |
| POST | `/api/v1/notifications/vehicles/` | Crear nuevo vehículo | `201` Created<br>`400` Bad Request |
| PUT | `/api/v1/notifications/vehicles/{id}/` | Actualizar vehículo completo (todos los campos requeridos) | `200` OK<br>`400` Bad Request<br>`404` Not Found |
| PATCH | `/api/v1/notifications/vehicles/{id}/` | Actualizar parcialmente vehículo (solo campos provistos) | `200` OK<br>`400` Bad Request<br>`404` Not Found |
| DELETE | `/api/v1/notifications/vehicles/{id}/` | Eliminar vehículo | `204` No Content<br>`404` Not Found |

**Filtros disponibles** (GET list):
- `customer_id` - Filtrar por UUID de cliente
- `plate` - Búsqueda por placa del vehículo

##### Maintenance Reminders (Full CRUD + Actions)

| Método | Endpoint | Descripción | Response Codes |
|--------|----------|-------------|----------------|
| GET | `/api/v1/notifications/reminders/` | Listar recordatorios de mantenimiento con paginación | `200` OK |
| GET | `/api/v1/notifications/reminders/{id}/` | Obtener detalles de un recordatorio específico | `200` OK<br>`404` Not Found |
| POST | `/api/v1/notifications/reminders/` | Crear nuevo recordatorio de mantenimiento | `201` Created<br>`400` Bad Request |
| PUT | `/api/v1/notifications/reminders/{id}/` | Actualizar recordatorio completo (todos los campos requeridos) | `200` OK<br>`400` Bad Request<br>`404` Not Found |
| PATCH | `/api/v1/notifications/reminders/{id}/` | Actualizar parcialmente recordatorio (solo campos provistos) | `200` OK<br>`400` Bad Request<br>`404` Not Found |
| DELETE | `/api/v1/notifications/reminders/{id}/` | Eliminar recordatorio | `204` No Content<br>`404` Not Found |
| POST | `/api/v1/notifications/reminders/{id}/complete/` | Marcar recordatorio como completado | `200` OK<br>`404` Not Found |

**Filtros disponibles** (GET list):
- `status` - Filtrar por estado (pending/completed/cancelled)
- `customer_id` - Filtrar por UUID de cliente
- `vehicle_id` - Filtrar por UUID de vehículo

#### Push Notifications - Web Push Management

| Método | Endpoint | Descripción | Response Codes |
|--------|----------|-------------|----------------|
| POST | `/api/v1/notifications/push/subscribe/` | Suscribir o actualizar suscripción push (desde PWA) | `201` Created<br>`400` Bad Request |
| DELETE | `/api/v1/notifications/push/subscribe/` | Cancelar suscripción push del cliente | `204` No Content<br>`404` Not Found |
| GET | `/api/v1/notifications/push/status/{customer_id}/` | Verificar si cliente tiene suscripción push activa | `200` OK<br>`404` Not Found |

#### Analytics - Notification Metrics & Health

| Método | Endpoint | Descripción | Response Codes |
|--------|----------|-------------|----------------|
| GET | `/api/v1/analytics/summary/` | Resumen agregado de estadísticas de notificaciones | `200` OK |
| GET | `/api/v1/analytics/recent/` | Obtener entradas recientes del log de notificaciones | `200` OK |
| GET | `/api/v1/analytics/health/` | Estado de salud de cada canal (email, whatsapp, push) en últimas 24h | `200` OK |

**Filtros disponibles**:
- **Summary:**
  - `days` - Número de días a analizar (default: 30)
- **Recent:**
  - `limit` - Número de logs recientes a retornar
  - `channel` - Filtrar por canal
  - `status` - Filtrar por estado

**Métricas incluidas en Summary:**
- Sent/delivered/failed counts
- Delivery rate percentage
- Average delivery time
- Breakdown by channel/status/event type
- Daily trends

#### Health Checks

| Método | Endpoint | Descripción | Response Codes |
|--------|----------|-------------|----------------|
| GET | `/api/v1/health/database/` | Verificar estado de conexión a PostgreSQL/Supabase | `200` OK<br>`503` Service Unavailable |

**Información incluida:**
- Connection status (healthy/unhealthy)
- Database engine, name, host, port, user
- PostgreSQL version
- Detection de Supabase (is_supabase flag)
- Connection pool settings (max_age, health_checks_enabled)

### API Interna (`/api/internal/v1/`) - Service-to-Service

**Autenticación requerida**: Header `X-Internal-Secret` con valor de `INTERNAL_API_SECRET_KEY`

#### Synchronization - Data Sync (Table Projection Pattern)

| Método | Endpoint | Descripción | Response Codes |
|--------|----------|-------------|----------------|
| POST | `/api/internal/v1/customers/sync/` | Webhook para sincronizar datos de clientes desde servicio Core | `202` Accepted (sync queued)<br>`400` Bad Request (invalid payload)<br>`401` Unauthorized (invalid API key) |
| POST | `/api/internal/v1/vehicles/sync/` | Webhook para sincronizar datos de vehículos desde servicio Core | `202` Accepted (sync queued)<br>`400` Bad Request (invalid payload)<br>`401` Unauthorized (invalid API key) |
| GET | `/api/internal/v1/tasks/{task_id}/status/` | Verificar estado de tarea Celery asíncrona por task_id | `200` OK<br>`404` Not Found (task not found) |

**Patrón**: Table Projection - sincronización asíncrona vía Celery (cola `sync`)

**Procesamiento:**
1. Request recibido → Validación de autenticación
2. Encolado → Celery task en cola `sync`
3. Procesamiento async → Crear/actualizar registro local
4. Sincronización → Datos disponibles para orquestación de notificaciones

### Notas sobre Health Checks

El servicio incluye endpoints de health check para monitoreo y validación de despliegues:

- **`/api/v1/analytics/health/`**: Verifica el estado de los canales de notificación (email, WhatsApp, push). Retorna tasas de éxito/fallo de las últimas 24 horas.
- **`/api/v1/health/database/`**: Verifica la conexión a PostgreSQL/Supabase. Retorna información detallada de la base de datos incluyendo versión, host, puerto, y detecta automáticamente si está conectado a Supabase. Útil para validar configuración después de despliegues en Coolify.

**Ejemplo de respuesta del database health check**:
```json
{
  "status": "healthy",
  "database": {
    "engine": "postgresql",
    "name": "postgres",
    "host": "aws-1-sa-east-1.pooler.supabase.com",
    "port": 6543,
    "user": "postgres.nnllhshzqyummzyotyiv",
    "version": "PostgreSQL 15.1 on x86_64-pc-linux-gnu...",
    "is_supabase": true
  },
  "connection": {
    "max_age": 600,
    "health_checks_enabled": true
  }
}
```

## Tipos de Servicio y Fases

### Fases del Servicio (ServicePhase)

El flujo de servicio está dividido en 5 fases:

1. **Agendar Cita** (`phase-schedule`) - Programación de la cita inicial
2. **Recepción** (`phase-reception`) - Recepción del vehículo en taller
3. **Reparación** (`phase-repair`) - Proceso de reparación/mantenimiento
4. **Control de Calidad** (`phase-quality`) - Revisión y validación del trabajo
5. **Entrega** (`phase-delivery`) - Vehículo listo para entrega al cliente

### Tipos de Servicio (ServiceType)

#### Tipos Principales

1. **Avalúo Comercial** (`avaluo-comercial`)
2. **Avería/Revisión** (`averia-revision`)
   - Subtipos:
     - Frenos (`averia-frenos`)
     - Diagnóstico (`averia-diagnostico`)
     - Alineación (`averia-alineacion`)
3. **Colisión/Pintura** (`colision-pintura`)
   - Subtipos:
     - Siniestro (`colision-siniestro`)
     - Golpe (`colision-golpe`)
     - Pintura (`colision-pintura`)
4. **Mantenimiento Preventivo** (`mantenimiento-preventivo`)
5. **Avalúo MG** (`avaluo-mg`)

### Comando Seed

Los datos iniciales (fases, tipos de servicio, plantillas, orquestación) se cargan con:

```bash
python manage.py seed_initial_data

# Forzar recreación de datos existentes:
python manage.py seed_initial_data --force
```

Este comando crea:
- 5 fases de servicio (con slugs: `phase-schedule`, `phase-reception`, `phase-repair`, `phase-quality`, `phase-delivery`)
- 5 tipos de servicio principales (con slugs: `mantenimiento-preventivo`, `averia-revision`, `colision-pintura`, `avaluo-comercial`, `avaluo-mg`)
- 6 subtipos
- 40+ plantillas de notificación (Email, WhatsApp, Push) para diferentes combinaciones de servicio/fase
- 10 OrchestrationConfig (5 tipos x 2 targets: clients/staff)
- 150 PhaseChannelConfig (matriz de canales por fase)

## Ejemplo de Catalog

El endpoint de catálogo retorna los slugs disponibles para usar en dispatch:

```bash
curl http://localhost:8000/api/v1/notifications/catalog/
```

**Respuesta:**
```json
{
  "service_types": [
    {"slug": "mantenimiento-preventivo", "name": "Mantenimiento Preventivo", "icon": "Settings"},
    {"slug": "averia-revision", "name": "Avería/Revisión", "icon": "AlertTriangle", "subtypes": [
      {"slug": "averia-frenos", "name": "Frenos", "icon": "Circle"},
      {"slug": "averia-diagnostico", "name": "Diagnóstico", "icon": "Search"}
    ]},
    "..."
  ],
  "phases": [
    {"slug": "phase-schedule", "name": "Agendar Cita", "icon": "Calendar", "order": 1},
    {"slug": "phase-reception", "name": "Recepción", "icon": "ClipboardCheck", "order": 2},
    "..."
  ]
}
```

## Ejemplo de Dispatch

```bash
curl -X POST http://localhost:8000/api/v1/notifications/events/dispatch/ \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "appointment_scheduled",
    "service_type_id": "mantenimiento-preventivo",
    "phase_id": "phase-schedule",
    "customer_id": "customer-001",
    "target": "clients",
    "context": {
      "nombre": "Carlos Mendoza",
      "placa": "ABC123",
      "vehiculo": "Haval H6 2024",
      "fecha": "20 de Enero, 2026",
      "hora": "14:30"
    }
  }'
```

**Nota:** Los campos `service_type_id` y `phase_id` ahora usan **slugs** en lugar de UUIDs.
Los slugs disponibles se pueden consultar en el endpoint `/api/v1/notifications/catalog/`.

## Variables de Plantilla

Las plantillas soportan las siguientes variables de contexto:

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `{{Nombre}}` | Nombre del cliente | Carlos Mendoza |
| `{{Placa}}` | Placa del vehículo | ABC123 |
| `{{Vehículo}}` | Marca y modelo del vehículo | Haval H6 2024 |
| `{{Fase}}` | Fase actual del servicio | Recepción |
| `{{Fecha}}` | Fecha programada | 20 de Enero, 2026 |
| `{{Hora}}` | Hora programada | 14:30 |
| `{{Orden}}` | Número de orden de trabajo | OT-2025-001 |
| `{{Técnico}}` | Técnico asignado | Juan Pérez |
| `{{Taller}}` | Nombre del taller | Ambacar Service |

**Nota**: Las variables son case-sensitive y deben usarse exactamente como se muestran (con tildes y mayúsculas).

## Flujo de Orquestación

1. **Evento recibido** → POST `/api/v1/notifications/events/dispatch/`
   - Parámetros: `event_type`, `service_type_id`, `phase_id`, `customer_id`, `target`, `context`

2. **Buscar configuración** → `OrchestrationConfig` para `service_type + phase + target`
   - Si no existe configuración, se rechaza la solicitud

3. **Resolver preferencias** → `CustomerChannelPreference` ordenadas por prioridad
   - Canales disponibles: Email, WhatsApp, Push
   - Prioridad del cliente determina orden de intento

4. **Renderizar plantilla** → Reemplazar `{{variables}}` con contexto
   - Usa `NotificationTemplate` específica para servicio/fase/canal/target
   - Soporta plantillas por subtipo (opcional)

5. **Encolar tarea** → Celery task `send_notification_task` (async)
   - Cola: `notifications`
   - Timeout configurable por canal

6. **Enviar notificación** → Adapter correspondiente
   - Email: SMTP (Django mail backend)
   - WhatsApp: Evolution API
   - Push: Web Push con VAPID

7. **Fallback automático** → En caso de fallo
   - Reintentos automáticos con exponential backoff (max 3 reintentos)
   - Tras 3 fallos, intenta siguiente canal en orden de prioridad
   - Todo se registra en `NotificationLog` para analytics

### Tareas Programadas (Celery Beat)

- **Diario 8:00 AM**: Verificar recordatorios de mantenimiento (`check_maintenance_reminders`)
- **Cada 15 minutos**: Reintentar notificaciones fallidas (`retry_failed_notifications`)

## Módulo de Sincronización (Service-to-Service)

El microservicio implementa el patrón **Table Projection** para sincronizar datos desde otros servicios (ej. servicio Core de Ambacar).

### Endpoints Internos

- `POST /api/internal/v1/customers/sync/` - Sincronizar datos de clientes
- `POST /api/internal/v1/vehicles/sync/` - Sincronizar datos de vehículos

### Autenticación

Todos los endpoints internos requieren el header de autenticación:

```bash
X-Internal-Secret: <INTERNAL_API_SECRET_KEY>
```

### Ejemplo de Sincronización

```bash
curl -X POST http://localhost:8000/api/internal/v1/customers/sync/ \
  -H "Content-Type: application/json" \
  -H "X-Internal-Secret: your-secret-key" \
  -d '{
    "customer_id": "customer-001",
    "name": "Carlos Mendoza",
    "email": "carlos@example.com",
    "phone": "+593991234567"
  }'
```

**Respuesta**: 202 Accepted (procesamiento asíncrono en cola `sync`)

### Procesamiento

1. Request recibido → Validación de autenticación
2. Encolado → Celery task en cola `sync`
3. Procesamiento async → Crear/actualizar registro local
4. Sincronización → Datos disponibles para orquestación de notificaciones

## Arquitectura

### Patrón: Hexagonal (Ports & Adapters)

```
apps/
├── core/                           # Núcleo - Abstracciones compartidas
│   ├── ports/                      # Interfaces (NotificationGateway, TemplateRenderer)
│   ├── constants.py                # Enums (NotificationChannel, NotificationStatus, EventType)
│   ├── authentication.py           # Autenticación para API interna
│   └── models.py                   # Modelos base (UUIDModel)
│
├── notifications/                  # Orquestación de notificaciones
│   ├── models/                     # Modelos de dominio
│   │   ├── orchestration.py        # ServicePhase, ServiceType, OrchestrationConfig
│   │   ├── templates.py            # NotificationTemplate
│   │   ├── channels.py             # TallerChannelConfig, PushSubscription
│   │   ├── customers.py            # CustomerContactInfo, CustomerChannelPreference
│   │   ├── vehicles.py             # Vehicle, MaintenanceReminder
│   │   └── logs.py                 # NotificationLog
│   │
│   ├── adapters/                   # Implementaciones de canales (Ports)
│   │   ├── email_adapter.py        # SMTP
│   │   ├── whatsapp_adapter.py     # Evolution API
│   │   └── push_adapter.py         # Web Push + VAPID
│   │
│   ├── services/                   # Lógica de negocio
│   │   ├── orchestration_engine.py # Motor de orquestación
│   │   ├── dispatch_service.py     # Encolado y fallback
│   │   └── template_service.py     # Renderizado de plantillas
│   │
│   ├── views/                      # API REST (DRF)
│   │   ├── events.py               # Dispatch de eventos
│   │   ├── templates.py            # CRUD plantillas
│   │   ├── orchestration.py        # Configuración
│   │   ├── customers.py            # Clientes y vehículos
│   │   └── push_subscription.py    # Suscripciones push
│   │
│   ├── tasks.py                    # Tareas de Celery
│   └── management/commands/        # Comandos de gestión
│       └── seed_initial_data.py    # Seed de datos iniciales
│
├── analytics/                      # Métricas y reportes
│   └── views.py                    # Summary, Recent, Health
│
└── synchronization/                # Sincronización service-to-service
    ├── views.py                    # API interna (webhooks)
    └── tasks.py                    # Tareas de sincronización async
```

### Tecnologías por Capa

- **API Layer**: Django REST Framework + drf-spectacular (OpenAPI)
- **Business Logic**: Django services (orchestration, dispatch, template)
- **Adapters**: SMTP, Evolution API, py-webpush
- **Task Queue**: Celery 5.3+ (Redis broker, 3 colas: notifications, sync, maintenance)
- **Storage**: PostgreSQL (Supabase), Redis
- **Deployment**: Docker + Gunicorn + Whitenoise

## Despliegue en Producción

### Requisitos

- PostgreSQL 15+ (recomendado: Supabase)
- Redis 7+
- Python 3.11+
- Variables de entorno configuradas (ver `.env.example`)

### Opción 1: Docker Compose (Recomendado)

#### Web Server

```bash
docker-compose up -d web
```

#### Celery Worker (separado)

```bash
docker-compose -f docker-compose.worker.yml up -d
```

#### Celery Beat (separado)

```bash
docker-compose -f docker-compose.beat.yml up -d
```

### Opción 2: Servicios Separados (Coolify, Railway, etc.)

#### Web Service

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

#### Worker Service

```bash
celery -A config worker -l info -Q notifications,sync,maintenance --pool=solo
```

#### Beat Service

```bash
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Migraciones y Datos Iniciales

```bash
# Aplicar migraciones
python manage.py migrate

# Cargar datos iniciales (fases, tipos, plantillas)
python manage.py seed_initial_data

# Recolectar archivos estáticos
python manage.py collectstatic --noinput
```

### Verificación de Salud

- API docs: `https://your-domain.com/api/docs/`
- Health check (canales): `https://your-domain.com/api/v1/analytics/health/`
- Health check (database): `https://your-domain.com/api/v1/health/database/`
- Admin panel: `https://your-domain.com/admin/`

## Licencia

Propiedad de Ambacar - Todos los derechos reservados.
