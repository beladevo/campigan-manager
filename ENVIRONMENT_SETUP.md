# Environment Variables Setup Guide

This document explains how to properly configure environment variables for the Solara AI Mini System.

## Overview

The system uses a centralized approach to environment variable management with proper validation and secure handling of sensitive data.

## Quick Setup

1. **Copy the global environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Set your Gemini API key:**
   Edit `.env` and replace `your_gemini_api_key_here` with your actual Gemini API key.

3. **Start the system:**
   ```bash
   docker-compose up --build
   ```

## Service-Specific Configuration

### Global Variables (`.env`)
Used by Docker Compose to inject variables into containers:
- `GEMINI_API_KEY` - **Required**: Your Google Gemini API key

### NestJS Service
**Location:** `nestjs-service/.env.example`

**Required Variables:**
- `RABBITMQ_URL` - RabbitMQ connection string

**Optional Variables:**
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` - Database configuration
- `NODE_ENV` - Environment (development/production)
- `PORT` - Server port (default: 3000)
- `LOG_LEVEL` - Logging level

### Python Generator
**Location:** `python-generator/.env.example`

**Required Variables:**
- `GEMINI_API_KEY` - Google Gemini API key for AI generation

**Optional Variables:**
- `GEMINI_TEXT_MODEL` - Text generation model name
- `GEMINI_IMAGE_MODEL` - Image generation model name
- `SERVER_HOST`, `SERVER_PORT` - Server configuration
- `OUTPUT_DIR` - Directory for generated files
- `LOG_LEVEL` - Logging level

### Python Worker
**Location:** `python-worker/.env.example`

**Required Variables:**
- `RABBITMQ_URL` - RabbitMQ connection string

**Optional Variables:**
- `GENERATOR_URL` - Python Generator service URL
- `RABBITMQ_TIMEOUT` - Connection timeout in seconds
- `LOG_LEVEL` - Logging level
- `HEALTH_CHECK_INTERVAL` - Health check frequency in seconds

## Security Features

### ✅ **Implemented Security Measures:**

1. **No Hardcoded Secrets:** All sensitive values are loaded from environment variables
2. **Centralized Configuration:** Each service has a dedicated config module with validation
3. **Startup Validation:** Critical environment variables are validated at application startup
4. **Secure Logging:** Sensitive values are masked in log output (e.g., passwords in URLs)
5. **Service Isolation:** Each service only receives the environment variables it needs

### 🔒 **Environment Variable Validation:**

**NestJS Service:**
- Validates `RABBITMQ_URL` at startup
- Provides clear error messages for missing variables

**Python Generator:**
- Validates `GEMINI_API_KEY` is present and not placeholder value
- Fails fast with descriptive error messages

**Python Worker:**
- Validates `RABBITMQ_URL` is present
- Warns if `GENERATOR_URL` is missing (uses default)

## Development vs Production

### Development (Docker Compose)
- Uses `.env` file for sensitive variables
- Default values for non-sensitive configuration
- Services communicate via Docker network names

### Production Deployment
- Use container orchestration environment variable injection
- Override default values with production-specific configuration
- Use secrets management for sensitive variables

## Troubleshooting

### Common Issues:

1. **"Missing required environment variables"**
   - Check that all required variables are set in your `.env` file
   - Ensure no variables have placeholder values like `your_api_key_here`

2. **"Failed to connect to RabbitMQ"**
   - Verify `RABBITMQ_URL` format: `amqp://user:password@host:port`
   - Check that RabbitMQ service is running

3. **"Gemini API client initialization failed"**
   - Verify your `GEMINI_API_KEY` is valid
   - Check API key permissions and quotas

### Debug Commands:

```bash
# Check environment variables in running containers
docker-compose exec nestjs-service env | grep -E "(POSTGRES|RABBITMQ)"
docker-compose exec python-generator env | grep GEMINI
docker-compose exec python-worker env | grep -E "(RABBITMQ|GENERATOR)"

# View service logs
docker-compose logs nestjs-service
docker-compose logs python-generator  
docker-compose logs python-worker
```

## Best Practices

1. **Never commit `.env` files** - Add to `.gitignore`
2. **Use strong passwords** in production environments
3. **Rotate API keys** regularly
4. **Use least privilege** - only provide necessary environment variables to each service
5. **Monitor for leaked secrets** in logs and error messages
6. **Use container orchestration secrets** in production (Kubernetes, Docker Swarm)

## Environment Variable Reference

| Variable | Service | Required | Description |
|----------|---------|----------|-------------|
| `GEMINI_API_KEY` | python-generator | ✅ | Google Gemini API key |
| `RABBITMQ_URL` | nestjs-service, python-worker | ✅ | RabbitMQ connection string |
| `POSTGRES_HOST` | nestjs-service | ❌ | Database host |
| `POSTGRES_PORT` | nestjs-service | ❌ | Database port |
| `POSTGRES_USER` | nestjs-service | ❌ | Database username |
| `POSTGRES_PASSWORD` | nestjs-service | ❌ | Database password |
| `POSTGRES_DB` | nestjs-service | ❌ | Database name |
| `GENERATOR_URL` | python-worker | ❌ | Python Generator service URL |
| `NODE_ENV` | nestjs-service | ❌ | Node.js environment |
| `LOG_LEVEL` | All services | ❌ | Logging level |