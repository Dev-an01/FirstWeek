# Embedding Service Microservice

A standalone FastAPI service for handling incremental embedding updates with queue-based processing, version management, and monitoring.

## Overview

The Embedding Service is a microservice that provides incremental embedding updates without requiring full regeneration of all embeddings. It integrates with the main RAG system through a REST API and supports:

- **Incremental Updates**: Only process changed documents using similarity-based change detection
- **Queue-based Processing**: Redis/Celery for scalable asynchronous processing
- **Version Management**: Track embedding versions with rollback capability
- **Monitoring**: Real-time metrics and health monitoring
- **Fallback Support**: Graceful degradation to local embedding generation

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI      │    │     Celery       │    │     Redis       │
│   Application   │◄──►│    Worker Pool    │◄──►│   Broker/Cache  │
│   (Port 8001)  │    │   (Async Tasks)   │    │   (Port 6379)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────┐    ┌──────────────────┐
│  PostgreSQL     │    │   Version Manager │
│   Vector DB    │    │   (Snapshots)    │
│   (Embeddings)  │    │   (Rollback)      │
└─────────────────┘    └──────────────────┘
```

## Features

### Incremental Processing
- **Change Detection**: Uses cosine similarity to detect significant content changes
- **Selective Updates**: Only processes documents that have actually changed
- **Configurable Thresholds**: Adjustable similarity thresholds for change detection

### Queue-based Architecture
- **Priority Queues**: High, normal, and low priority queues
- **Batch Processing**: Efficient handling of multiple documents
- **Retry Logic**: Automatic retry with exponential backoff
- **Scalable Workers**: Horizontal scaling with multiple Celery workers

### Version Management
- **Snapshots**: Automatic version snapshots after batch processing
- **Rollback**: Safe rollback to previous versions
- **Metadata Tracking**: Complete audit trail of changes
- **Cleanup**: Automatic cleanup of expired versions

### Monitoring & Metrics
- **Real-time Metrics**: Processing times, success rates, queue sizes
- **Health Checks**: Component-level health monitoring
- **Prometheus Export**: Compatible with monitoring systems
- **Performance Alerts**: Configurable threshold-based alerts

## API Endpoints

### Document Operations

#### POST /embeddings/documents
Embed a single document.

```json
{
  "source_id": "POLICY-HR-001",
  "source_type": "policy",
  "content": "Document content here...",
  "metadata": {
    "title": "HR Policy v2.1",
    "department": "Human Resources"
  },
  "priority": "normal",
  "force_update": false,
  "version": "2.1"
}
```

#### POST /embeddings/batch
Embed multiple documents in batch.

```json
{
  "documents": [
    {
      "source_id": "POLICY-HR-001",
      "source_type": "policy",
      "content": "Policy content..."
    }
  ],
  "batch_id": "batch_2024_01_15_001",
  "priority": "normal"
}
```

#### POST /embeddings/incremental
Process incremental updates with change detection.

```json
{
  "documents": [
    {
      "source_id": "POLICY-HR-001",
      "source_type": "policy",
      "content": "Updated policy content...",
      "version": "2.2"
    }
  ],
  "change_detection": true,
  "similarity_threshold": 0.95,
  "priority": "high"
}
```

### Version Management

#### GET /embeddings/version
Get version history.

#### GET /embeddings/version/current
Get current version information.

#### POST /embeddings/version/snapshot
Create manual version snapshot.

#### POST /embeddings/rollback
Rollback to previous version.

```json
{
  "target_version": "v20240115_103000_abc12345",
  "source_ids": ["POLICY-HR-001", "DECISION-TECH-042"],
  "confirm": true
}
```

### Task Management

#### GET /tasks/{task_id}
Get task status and progress.

#### DELETE /tasks/{task_id}
Cancel or terminate a task.

#### GET /tasks
Get queue status and active tasks.

### Monitoring

#### GET /health
Service health check with component status.

#### GET /metrics
Current processing metrics.

#### GET /metrics/prometheus
Prometheus-compatible metrics export.

#### GET /alerts
Recent performance alerts.

## Configuration

### Environment Variables

```bash
# Service Configuration
EMBEDDING_SERVICE_HOST=0.0.0.0
EMBEDDING_SERVICE_PORT=8001
EMBEDDING_SERVICE_DEBUG=false

# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ai_officer
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=1

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j123

# Processing Configuration
EMBEDDING_SERVICE_ASYNC=true
EMBEDDING_SERVICE_TIMEOUT=30
EMBEDDING_SERVICE_RETRIES=3
```

### Key Settings

- **Change Detection Threshold**: Default 0.95 similarity
- **Batch Size**: Default 50 documents per batch
- **Version Retention**: Default 30 days
- **Max Versions**: Default 10 versions per document
- **Queue Priorities**: Critical (10), High (8), Normal (5), Low (2)

## Deployment

### Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f embedding-service

# Scale workers
docker-compose up -d --scale celery-worker=4
```

### Standalone Docker

```bash
# Build image
docker build -t embedding-service .

# Run container
docker run -d \
  --name embedding-service \
  -p 8001:8001 \
  -e POSTGRES_HOST=postgres \
  -e REDIS_HOST=redis \
  embedding-service
```

### Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start service
python -m embedding_service.main

# Start Celery worker (separate terminal)
celery -A embedding_service.celery_app worker --loglevel=info

# Start Celery beat (separate terminal)
celery -A embedding_service.celery_app beat --loglevel=info
```

## Integration with Main RAG

### Configuration

Add to your main RAG `.env` file:

```bash
# Enable embedding service integration
EMBEDDING_SERVICE_ENABLED=true
EMBEDDING_SERVICE_URL=http://localhost:8001
EMBEDDING_SERVICE_ASYNC=true
EMBEDDING_SERVICE_TIMEOUT=30
EMBEDDING_SERVICE_RETRIES=3

# Enable fallback (recommended)
EMBEDDING_FALLBACK_ENABLED=true
```

### Usage

The main RAG system will automatically use the embedding service when configured:

1. **Query Processing**: Vector search queries use the service for embedding generation
2. **Fallback Support**: Local embedding generation if service is unavailable
3. **Health Monitoring**: Automatic health checks and fallback activation
4. **Performance Tracking**: Metrics collection for both service and fallback

## Monitoring

### Key Metrics

- **Processing Rate**: Embeddings per second
- **Success Rate**: Percentage of successful embeddings
- **Queue Size**: Number of pending tasks
- **Processing Time**: Average time per embedding
- **Memory Usage**: System memory consumption
- **Error Rate**: Percentage of failed operations

### Health Checks

- **Service Health**: Overall service status
- **Component Health**: Database, Redis, Celery workers
- **Performance Health**: Response times and error rates
- **Resource Health**: Memory and CPU usage

### Alerts

- **Performance Thresholds**: Configurable performance alerts
- **Resource Limits**: Memory and CPU usage alerts
- **Queue Overload**: Alert when queue size exceeds threshold
- **Error Rate**: Alert when error rate exceeds threshold

## Troubleshooting

### Common Issues

1. **Service Unavailable**
   - Check service health: `curl http://localhost:8001/health`
   - Verify Redis connection: `redis-cli ping`
   - Check Celery workers: `celery -A embedding_service.celery_app inspect active`

2. **High Memory Usage**
   - Reduce batch size in configuration
   - Scale horizontally with more workers
   - Check for memory leaks in embedding model

3. **Slow Processing**
   - Check GPU availability and utilization
   - Verify network connectivity to databases
   - Monitor queue sizes and worker performance

### Debug Mode

Enable debug logging:

```bash
export EMBEDDING_SERVICE_DEBUG=true
export LOG_LEVEL=DEBUG
```

### Performance Tuning

1. **Batch Size**: Adjust based on available memory
2. **Worker Count**: Scale based on CPU cores
3. **Queue Priorities**: Use for time-critical updates
4. **Change Threshold**: Balance between sensitivity and performance

## Security

### Authentication

- **API Keys**: Configure API key authentication (future)
- **Network Security**: Use internal networks for service communication
- **Database Security**: Use connection pooling and SSL

### Access Control

- **CORS**: Configured for allowed origins
- **Rate Limiting**: Per-IP rate limits (future)
- **Request Validation**: Input validation and sanitization

## Development

### Project Structure

```
embedding_service/
├── __init__.py              # Package initialization
├── main.py                   # FastAPI application
├── config.py                 # Configuration management
├── models.py                 # Pydantic data models
├── embedding_service.py       # Core embedding logic
├── version_manager.py         # Version control logic
├── celery_app.py            # Celery tasks and configuration
├── metrics.py               # Monitoring and metrics
├── embedding_client.py       # Client for main RAG integration
├── requirements.txt          # Python dependencies
├── Dockerfile              # Container configuration
├── docker-compose.yml       # Multi-service deployment
└── README.md               # This documentation
```

### Contributing

1. **Code Style**: Follow PEP 8 and existing patterns
2. **Testing**: Add unit tests for new features
3. **Documentation**: Update API docs and README
4. **Error Handling**: Proper exception handling and logging

### Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=embedding_service tests/

# Run integration tests
pytest tests/integration/
```

## License

This project is part of the AI Officer RAG system. See main project license for details.