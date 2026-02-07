from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # AWS Configuration (uses AWS_DEFAULT_REGION or falls back to eu-west-1)
    aws_region: str | None = None  # None = use boto3's default region detection
    dynamodb_table_name: str = "movgr-metro-arrivals"
    dynamodb_endpoint_url: str | None = None  # For local development with DynamoDB Local

    # Data source configuration
    use_dynamodb: bool = True  # Set to False to use direct scraping (legacy mode)

    # In-memory cache TTL (seconds) - reduces DynamoDB reads for warm Lambda instances
    memory_cache_ttl: int = 5

    # Scraper configuration
    scrape_timeout: int = 10
    metro_source_url: str = "https://metropolitanogranada.es/MGhorariosreal.asp"

    # CORS
    cors_origins: str | None = None

    # API Gateway configuration
    # Stage name for API Gateway - used by Mangum to strip the base path
    api_stage: str | None = None  # Set via ENVIRONMENT in Lambda


@lru_cache
def get_settings() -> Settings:
    return Settings()
