# MovGR

API para información de movilidad urbana de Granada (bus y metro)

## Arquitectura

Esta API utiliza una arquitectura serverless con caché en DynamoDB para optimizar el rendimiento y reducir costes:

```
                    ┌─────────────────────────────────────────────┐
                    │                    AWS                       │
                    │                                              │
  EventBridge ──────┼──(cada 30s)──→ Scraper Lambda               │
                    │                      │                       │
                    │                      ▼                       │
                    │               DynamoDB Table                 │
                    │                      ▲                       │
                    │                      │                       │
  Mobile App ───────┼──→ API Gateway ──→ API Lambda (solo lectura) │
                    │                                              │
                    └─────────────────────────────────────────────┘
```

**Beneficios:**
- Respuestas ultra-rápidas (~50ms vs ~2-5s con scraping directo)
- Menor coste de Lambda (ejecución más corta)
- Reducción de carga en el servidor externo de metro
- Alta disponibilidad gracias a DynamoDB

## Instalación

Para instalar las dependencias, ejecutar:

```bash
poetry install
```

Puedes probar la API localmente con:

```bash
poetry run local
```

### Configuración

Copia `.env.example` a `.env` y ajusta los valores:

```bash
cp .env.example .env
```

Variables de entorno principales:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `USE_DYNAMODB` | Usar caché DynamoDB (true/false) | `true` |
| `AWS_REGION` | Región de AWS | `eu-west-1` |
| `DYNAMODB_TABLE_NAME` | Nombre de la tabla DynamoDB | `movgr-metro-arrivals` |
| `CORS_ORIGINS` | Orígenes CORS permitidos | `*` |

## Despliegue en AWS

### Requisitos previos

1. [AWS CLI](https://aws.amazon.com/cli/) configurado con credenciales
2. [SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
3. Python 3.12+

### Despliegue

```bash
# Construir el proyecto
sam build

# Desplegar (primera vez - modo guiado)
sam deploy --guided

# Despliegues posteriores
sam deploy
```

### Despliegue en desarrollo

```bash
sam deploy --config-env dev
```

### Probar localmente con DynamoDB Local

1. Iniciar DynamoDB Local:
```bash
docker run -p 8000:8000 amazon/dynamodb-local
```

2. Crear la tabla:
```bash
aws dynamodb create-table \
    --table-name movgr-metro-arrivals \
    --attribute-definitions AttributeName=pk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --endpoint-url http://localhost:8000
```

3. Configurar `.env`:
```
DYNAMODB_ENDPOINT_URL=http://localhost:8000
```

4. Ejecutar el scraper manualmente:
```bash
python -m src.scraper
```

5. Iniciar la API:
```bash
poetry run local
```

## Endpoints

### Metro

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/metro/paradas` | Lista de todas las paradas |
| GET | `/metro/llegadas` | Tiempos de llegada de todas las paradas |
| GET | `/metro/llegadas/{id_parada}` | Tiempos de llegada de una parada específica |

### Bus

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/bus/parada/{num_parada}` | Información de una parada |
| GET | `/bus/llegadas/{num_parada}` | Tiempos de llegada en una parada |

### Utilidad

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/` | Health check básico |
| GET | `/health` | Health check con información de datos |

## Documentación

Puedes acceder a la documentación interactiva de la API:
- Swagger UI: `/docs`
- ReDoc: `/redoc`

Producción: <https://movgr.apis.mianfg.me/docs>

## Status

Puedes ver el estado de la API en <https://status.mianfg.me/>.
