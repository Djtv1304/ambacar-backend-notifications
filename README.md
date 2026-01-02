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

### 7. Ejecutar Celery (en otra terminal)

```bash
celery -A config worker -l info
```

## Docker

```bash
docker-compose up -d
```

## Documentación API

- Swagger UI: http://localhost:8000/api/docs/
- ReDoc: http://localhost:8000/api/redoc/
- Schema JSON: http://localhost:8000/api/schema/

## Endpoints Principales

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/notifications/events/dispatch/` | Disparar notificación |
| GET/POST | `/api/v1/notifications/templates/` | Gestión de plantillas |
| GET | `/api/v1/notifications/phases/` | Fases de servicio |
| GET | `/api/v1/notifications/service-types/` | Tipos de servicio |
| GET/POST | `/api/v1/notifications/orchestration/` | Configuración de orquestación |
| GET/POST | `/api/v1/notifications/customers/` | Info de clientes |
| POST | `/api/v1/notifications/push/subscribe/` | Suscripción Push |
| GET | `/api/v1/analytics/summary/` | Analytics |

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

## Variables de Plantilla

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `{{Nombre}}` | Nombre del cliente | Carlos Mendoza |
| `{{Placa}}` | Placa del vehículo | ABC123 |
| `{{Vehículo}}` | Marca y modelo | Haval H6 2024 |
| `{{Fase}}` | Fase actual | Recepción |
| `{{Fecha}}` | Fecha programada | 20 de Enero, 2026 |
| `{{Hora}}` | Hora programada | 14:30 |
| `{{Orden}}` | Número de orden | OT-2025-001 |
| `{{Técnico}}` | Técnico asignado | Juan Pérez |
| `{{Taller}}` | Nombre del taller | Ambacar Service |

## Arquitectura

```
apps/
├── core/                    # Modelos base, constantes, ports
│   └── ports/               # Interfaces (NotificationGateway, TemplateRenderer)
├── notifications/
│   ├── models/              # Modelos de datos
│   ├── adapters/            # Implementaciones (Email, WhatsApp, Push)
│   ├── services/            # Lógica de negocio
│   ├── views/               # API endpoints
│   └── tasks.py             # Celery tasks
└── analytics/               # Métricas y reportes
```

## Flujo de Orquestación

1. **Evento recibido** → POST `/events/dispatch/`
2. **Buscar configuración** → OrchestrationConfig para service_type + phase
3. **Resolver preferencias** → CustomerChannelPreference ordenadas por prioridad
4. **Renderizar plantilla** → Reemplazar `{{variables}}` con contexto
5. **Encolar tarea** → Celery task para envío async
6. **Enviar notificación** → Adapter correspondiente (Email/WhatsApp/Push)
7. **Fallback automático** → Si falla, reintenta en siguiente canal tras 10 min

## Licencia

Propiedad de Ambacar - Todos los derechos reservados.
