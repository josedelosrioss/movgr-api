# MovGR

API para información de movilidad urbana de Granada (bus y metro)

## Instalación

Para instalar las dependencias, ejecutar:

```
poetry install
```

Puedes probar la API localmente con:

```
poetry run local
```

## Ejecución

Actualmente, esta API se encuentra alojada en AWS Lambda y se puede acceder a ella a través de <https://movgr.apis.mianfg.me/>. Más información sobre cómo hacer este despliegue en [la wiki](https://github.com/mianfg/movgr-api/wiki/Deploy-to-AWS).

## Despliegue con AWS CLI

Puedes desplegar la infraestructura y el código sin SAM CLI usando solo `aws`:

```bash
chmod +x scripts/deploy-aws-cli.sh
AWS_PROFILE=tu-perfil AWS_REGION=eu-west-1 \
  scripts/deploy-aws-cli.sh \
  --s3-bucket tu-bucket-deploy \
  --stack-name movgr-api \
  --environment prod
```

Requisitos:

- `aws` configurado con credenciales válidas
- Python 3.10 disponible localmente
- Un bucket S3 para `aws cloudformation package`

El script empaqueta las dependencias en `.aws-cli-build/`, sube los artefactos a S3 y ejecuta `aws cloudformation deploy` sobre [template.yaml](/home/usuario/metrogrx/movgr-api/template.yaml).

## Documentación

Puedes acceder a la documentación de la API [aquí](https://movgr.apis.mianfg.me/docs).

## Status

Puedes ver el estado de la API en <https://status.mianfg.me/>.
