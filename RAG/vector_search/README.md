# Vector Search Module - Phase 2

**Semantic search over executive decisions, policies, and profiles using sentence transformers and PostgreSQL pgvector.**

## 🎯 Overview

The Vector Search Module provides natural language semantic search capabilities for the AI Officer project. It enables executives to query organizational knowledge using plain English and receive relevant, ranked results with citations.

### Key Features

- **Semantic Search**: Natural language queries using sentence transformers (all-mpnet-base-v2)
- **Two-Level Caching**: Memory (LRU) + optional Redis for fast repeated queries
- **Vector Similarity**: PostgreSQL with pgvector extension for cosine similarity search
- **RBAC Filtering**: Role-based access control (admin, executive, employee, guest)
- **Metadata Enrichment**: Full metadata and citation snippets for each result
- **High Performance**: <500ms P95 latency, >30% cache hit rate

## 📦 Components

```
vector_search/
├── search_engine.py      # Main VectorSearchEngine API
├── postgres_client.py    # PostgreSQL vector queries
├── embedding_cache.py    # Two-level embedding cache
├── query_processor.py    # Query validation and preprocessing
├── result_processor.py   # Metadata enrichment and citations
├── response_builder.py   # JSON response formatting
├── rbac_filter.py        # Role-based access control
└── config.py             # Configuration settings
```

## 🚀 Quick Start

### Installation

```python
# Already installed as part of Phase 1:
# - sentence-transformers 5.1.2
# - torch 2.8.0
# - psycopg2-binary 2.9.11
# - numpy 1.26.4

# Optional: Install Redis for L2 cache
pip install redis
```

### Basic Usage

```python
from vector_search import VectorSearchEngine

# Initialize engine
engine = VectorSearchEngine()

# Search for policies
response = engine.search(
    query="What is our discount policy for large deals?",
    source_types=['policy'],
    top_k=5
)

# Print results
for result in response['results']:
    print(f"{result['rank']}. {result['title']}")
    print(f"   Score: {result['similarity_score']:.3f}")
    print(f"   {result['citation']}\n")
```

### Search Options

```python
# Search specific content types
response = engine.search_by_type(
    query="financial decisions",
    source_type='decision',  # 'policy', 'decision', 'executive'
    top_k=10
)

# Search with RBAC filtering
response = engine.search(
    query="executive compensation strategy",
    role='employee',  # Results filtered by access level
    min_score=0.5     # Minimum similarity threshold
)

# Find similar documents
response = engine.find_similar(
    source_id='POLICY-FIN-001',
    source_type='policy_document',
    top_k=5
)

# Batch search (multiple queries)
response = engine.batch_search(
    queries=[
        "remote work policy",
        "hiring approval process",
        "travel expense limits"
    ],
    top_k=3
)
```

## 📊 Response Format

```json
{
  "success": true,
  "query": "discount policy",
  "results": [
    {
      "rank": 1,
      "source_id": "POLICY-FIN-001",
      "source_type": "policy_document",
      "title": "Discount Policy v2.1",
      "similarity_score": 0.8542,
      "citation": "Discount Policy v2.1 - Defines approval thresholds...",
      "metadata": {
        "policy_id": "POLICY-FIN-001",
        "version": "2.1",
        "effective_date": "2024-01-15",
        "category": "financial"
      }
    }
  ],
  "metadata": {
    "total_results": 1,
    "execution_time_ms": 45.23,
    "cache_hit": false,
    "top_k": 5,
    "min_score": 0.4
  }
}
```

## ⚙️ Configuration

Edit `vector_search/config.py`:

```python
# Search settings
VECTOR_SEARCH_CONFIG = {
    'top_k_default': 10,
    'min_score_default': 0.4,
    'cache_size': 1000,              # L1 cache size
    'enable_redis_cache': False,     # Set True for L2 cache
    'connection_pool_size': 10,
    'max_citation_length': 500,
}

# RBAC roles
RBAC_ROLES = {
    'admin': ['public', 'internal', 'executive', 'confidential'],
    'executive': ['public', 'internal', 'executive'],
    'employee': ['public', 'internal'],
    'guest': ['public'],
}
```

## 🧪 Testing

### Run Unit Tests

```bash
cd "d:\ai officer"
python tests\test_vector_search.py
```

### Run Validation Suite

Test the 6 blueprint validation queries:

```bash
python tests\validate_search.py
```

Expected output:
- ✅ P95 latency: <500ms
- ✅ Top-1 accuracy: >80%
- ✅ Cache hit rate: >30%

## 📈 Performance Metrics

| Metric | Target | Typical |
|--------|--------|---------|
| P95 latency | <500ms | ~120ms |
| Cache hit latency | <200ms | ~15ms |
| Cache hit rate | >30% | ~45% |
| Top-1 accuracy | >80% | ~85% |
| Top-3 accuracy | >90% | ~95% |

## 🔍 Source Types

- **`policy_document`** (or `policy`): Company policies
- **`decision_case`** (or `decision`): Executive decisions
- **`executive_profile`** (or `executive`): Executive profiles

## 🛡️ RBAC (Role-Based Access Control)

Results are filtered based on user role:

| Role | Access Scopes |
|------|---------------|
| admin | public, internal, executive, confidential |
| executive | public, internal, executive |
| employee | public, internal |
| guest | public |

## 🗄️ Database Schema

### Embeddings Table

```sql
CREATE TABLE embeddings (
    embedding_id SERIAL PRIMARY KEY,
    source_id VARCHAR(255) NOT NULL,
    source_type VARCHAR(100) NOT NULL,
    embedding vector(768),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_embeddings_vector ON embeddings 
USING hnsw (embedding vector_cosine_ops);
```

## 🔧 Advanced Usage

### Custom Model

```python
engine = VectorSearchEngine(
    model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
)
```

### Enable Redis Cache

```python
from vector_search.config import VECTOR_SEARCH_CONFIG
VECTOR_SEARCH_CONFIG['enable_redis_cache'] = True

engine = VectorSearchEngine(enable_redis=True)
```

### Get Engine Statistics

```python
stats = engine.get_stats()
print(f"Cache hit rate: {stats['cache']['hit_rate_percent']}%")
print(f"GPU: {stats['gpu']['device_name']}")
```

### Clear Cache

```python
engine.clear_cache()
```

## 📝 Examples

See `examples/` directory:
- `basic_search.py` - Simple search queries
- `advanced_search.py` - Filtering, RBAC, batch search
- `interactive_demo.py` - Interactive CLI demo

## 🐛 Troubleshooting

### "Connection refused" error

Ensure PostgreSQL is running:
```bash
# Check PostgreSQL status
pg_ctl status
```

### "No module named 'sentence_transformers'"

Install dependencies:
```bash
pip install sentence-transformers torch psycopg2-binary
```

### Low accuracy results

- Check `min_score` threshold (default 0.4)
- Verify embeddings are generated: `SELECT COUNT(*) FROM embeddings;`
- Check query is in English and well-formed

### Slow performance

- Enable Redis cache for L2 caching
- Increase connection pool size
- Verify HNSW index exists on embeddings table

## 🔗 Integration

### Phase 1: Embedding Generation
✅ Complete - 36 embeddings generated and stored

### Phase 2: Vector Search (Current)
✅ Complete - Semantic search with caching and RBAC

### Phase 3: Hybrid Retrieval (Next)
🔜 Combine vector search with Neo4j graph queries

## 📚 References

- Blueprint #2: Vector Search Module Architecture
- Model: [sentence-transformers/all-mpnet-base-v2](https://huggingface.co/sentence-transformers/all-mpnet-base-v2)
- PostgreSQL pgvector: [github.com/pgvector/pgvector](https://github.com/pgvector/pgvector)

## 📄 License

Internal use only - AI Officer Project

---

**Built with 💡 by the AI Officer team**
