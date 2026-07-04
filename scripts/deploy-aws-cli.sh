#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/.aws-cli-build"
PACKAGE_DIR="$BUILD_DIR/package"
DEPLOY_TEMPLATE="$BUILD_DIR/template.aws-cli.yaml"
PACKAGED_TEMPLATE="$BUILD_DIR/packaged-template.yaml"

STACK_NAME="movgr-api"
ENVIRONMENT="prod"
S3_BUCKET=""
CORS_ORIGINS="*"
METRO_MAX_STALE_SECONDS="300"
PYTHON_BIN="${PYTHON_BIN:-python3.10}"

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy-aws-cli.sh --s3-bucket <bucket> [options]

Required:
  --s3-bucket <bucket>           S3 bucket used by aws cloudformation package

Optional:
  --stack-name <name>            CloudFormation stack name (default: movgr-api)
  --environment <env>            Template Environment parameter (default: prod)
  --cors-origins <origins>       CORS_ORIGINS value (default: *)
  --metro-max-stale-seconds <n>  MetroMaxStaleSeconds parameter (default: 300)
  --python-bin <path>            Python interpreter used to build the package
  --help                         Show this help

Environment:
  AWS_PROFILE / AWS_REGION / AWS_DEFAULT_REGION are passed through to aws CLI.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --s3-bucket)
      S3_BUCKET="$2"
      shift 2
      ;;
    --stack-name)
      STACK_NAME="$2"
      shift 2
      ;;
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --cors-origins)
      CORS_ORIGINS="$2"
      shift 2
      ;;
    --metro-max-stale-seconds)
      METRO_MAX_STALE_SECONDS="$2"
      shift 2
      ;;
    --python-bin)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$S3_BUCKET" ]]; then
  echo "--s3-bucket is required" >&2
  usage >&2
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required" >&2
  exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python interpreter not found: $PYTHON_BIN" >&2
  exit 1
fi

rm -rf "$BUILD_DIR"
mkdir -p "$PACKAGE_DIR"

"$PYTHON_BIN" -m pip install -r "$ROOT_DIR/requirements.txt" --target "$PACKAGE_DIR" >/dev/null
cp -R "$ROOT_DIR/src" "$PACKAGE_DIR/src"

env ROOT_DIR="$ROOT_DIR" DEPLOY_TEMPLATE="$DEPLOY_TEMPLATE" PACKAGE_DIR="$PACKAGE_DIR" \
  "$PYTHON_BIN" - <<'PY'
from pathlib import Path
import os

root_dir = Path(os.environ["ROOT_DIR"])
template_path = root_dir / "template.yaml"
deploy_template_path = Path(os.environ["DEPLOY_TEMPLATE"])
package_dir = Path(os.environ["PACKAGE_DIR"])

content = template_path.read_text(encoding="utf-8")
relative_package_dir = os.path.relpath(
    package_dir,
    start=deploy_template_path.parent,
)
content = content.replace("CodeUri: .", f"CodeUri: {relative_package_dir}")
deploy_template_path.write_text(content, encoding="utf-8")
PY

aws cloudformation package \
  --template-file "$DEPLOY_TEMPLATE" \
  --s3-bucket "$S3_BUCKET" \
  --output-template-file "$PACKAGED_TEMPLATE"

aws cloudformation deploy \
  --template-file "$PACKAGED_TEMPLATE" \
  --stack-name "$STACK_NAME" \
  --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
  --no-fail-on-empty-changeset \
  --parameter-overrides \
    Environment="$ENVIRONMENT" \
    CorsOrigins="$CORS_ORIGINS" \
    MetroRefreshSeconds="15" \
    MetroMaxStaleSeconds="$METRO_MAX_STALE_SECONDS"

API_URL="$(
  aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
    --output text
)"

echo "Deployment complete"
echo "Stack: $STACK_NAME"
echo "API URL: $API_URL"
