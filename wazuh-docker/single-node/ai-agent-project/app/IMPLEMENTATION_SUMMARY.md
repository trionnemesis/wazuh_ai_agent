# Wazuh AI Agent - Stage 1: Foundational Vectorization Implementation

## Overview

This document provides a comprehensive summary of the implemented foundational vectorization layer for the Wazuh AI Agent. The system has been successfully refactored to include semantic vectorization using Google's Gemini Embedding model, laying the groundwork for a future Retrieval-Augmented Generation (RAG) system.

## Architecture

### Core Components

1. **main.py** - Refactored modular main program
2. **embedding_service.py** - Gemini Embedding service wrapper
3. **setup_index_template.py** - OpenSearch index template setup utility
4. **wazuh-alerts-vector-template.json** - JSON definition of the index template

### Data Flow

```
New Wazuh Alert → Vectorization → Similar Alert Search → LLM Analysis → Store Results + Vector
```

## Key Features Implemented

### 1. Modular Design in main.py

The main.py file has been completely refactored into single-responsibility async functions:

- **`query_new_alerts()`** - Fetches unanalyzed alerts from OpenSearch
- **`vectorize_alert()`** - Converts alert content to semantic vectors
- **`find_similar_alerts()`** - Performs vector-based similarity search
- **`build_context()`** - Constructs analysis context from similar alerts
- **`analyze_alert()`** - Invokes the LLM for alert analysis
- **`update_alert_with_analysis()`** - Writes both analysis and vector back to OpenSearch
- **`process_single_alert()`** - Orchestrates the complete pipeline for one alert
- **`ensure_index_template()`** - Ensures proper index template exists

### 2. GeminiEmbeddingService Class

The `embedding_service.py` implements a robust embedding service with:

#### Key Methods:
- **`embed_documents(texts: List[str]) -> List[List[float]]`** - Batch document embedding
- **`embed_query(text: str) -> List[float]`** - Single text embedding
- **`embed_alert_content(alert_source: Dict) -> List[float]`** - Specialized alert vectorization

#### Features:
- **Error Handling** - Exponential backoff retry mechanism
- **MRL Support** - Configurable vector dimensions (1-768)
- **Text Preprocessing** - Automatic cleaning and truncation
- **Connection Testing** - Built-in health check functionality

### 3. OpenSearch Index Template

The index template `wazuh-alerts-vector-template` includes:

```json
{
  "mappings": {
    "properties": {
      "alert_vector": {
        "type": "dense_vector",
        "dims": 768,
        "index": true,
        "similarity": "cosine",
        "index_options": {
          "type": "hnsw",
          "m": 16,
          "ef_construction": 512
        }
      },
      "ai_analysis": {
        "type": "object",
        "properties": {
          "triage_report": {"type": "text"},
          "provider": {"type": "keyword"},
          "timestamp": {"type": "date"},
          "risk_level": {"type": "keyword"},
          "vector_dimension": {"type": "integer"},
          "processing_time_ms": {"type": "integer"}
        }
      }
    }
  }
}
```

## Environment Configuration

### Required Environment Variables

```bash
# Gemini API Configuration
export GOOGLE_API_KEY="your-gemini-api-key"

# OpenSearch Configuration
export OPENSEARCH_URL="https://wazuh.indexer:9200"
export OPENSEARCH_USER="admin"
export OPENSEARCH_PASSWORD="SecretPassword"

# LLM Configuration
export LLM_PROVIDER="anthropic"  # or "gemini"
export ANTHROPIC_API_KEY="your-anthropic-key"  # if using anthropic
```

### Optional Configuration

```bash
# Embedding Configuration
export EMBEDDING_MODEL="models/text-embedding-004"
export EMBEDDING_DIMENSION="768"  # 1-768 for MRL
export EMBEDDING_MAX_RETRIES="3"
export EMBEDDING_RETRY_DELAY="1.0"
```

## Deployment and Usage

### 1. Setup Index Template

```bash
cd wazuh-docker/single-node/ai-agent-project/app
python setup_index_template.py
```

### 2. Start the Agent

```bash
python main.py
```

### 3. Verify Operation

```bash
# Health check
curl http://localhost:8000/health

# Verify vectorization
python verify_vectorization.py
```

## Verification in Wazuh Dashboard

After the agent runs successfully, you can verify the implementation by:

1. **Navigate to Wazuh Dashboard** → Discover
2. **Select index pattern**: `wazuh-alerts-*`
3. **Add filter**: `ai_analysis:*`
4. **Check fields**:
   - `alert_vector`: Array of 768 floating-point numbers
   - `ai_analysis.triage_report`: AI analysis text
   - `ai_analysis.provider`: LLM provider used
   - `ai_analysis.vector_dimension`: Vector dimensions

## Technical Specifications

### Vector Configuration
- **Model**: Google text-embedding-004
- **Dimensions**: 768 (configurable 1-768 with MRL)
- **Similarity**: Cosine similarity
- **Index Type**: HNSW for high-performance similarity search

### Processing Pipeline
1. **Alert Retrieval**: Queries OpenSearch for unanalyzed alerts
2. **Vectorization**: Converts alert content to 768-dimensional vectors
3. **Similarity Search**: Finds up to 5 similar historical alerts using vector search
4. **Context Building**: Constructs analysis context from similar alerts
5. **LLM Analysis**: Processes alert with contextual information
6. **Storage**: Updates OpenSearch with both analysis and vector data

### Error Handling
- **Retry Mechanism**: Exponential backoff for API failures
- **Graceful Degradation**: Continue processing other alerts if one fails
- **Fallback Strategies**: Basic text fallback for vectorization failures
- **Comprehensive Logging**: Detailed logging for debugging and monitoring

## Performance Considerations

### Batch Processing
- Processes up to 10 alerts per job execution
- Runs every 60 seconds via scheduler
- Individual alert failures don't stop batch processing

### Memory Usage
- Each 768-dimensional vector: ~3KB storage
- Efficient HNSW indexing for fast similarity search
- Configurable dimensions for memory optimization

### API Limits
- Text truncation to 8000 characters for Gemini API
- Built-in retry mechanisms for rate limiting
- Connection pooling for OpenSearch operations

## Monitoring and Health Checks

### Health Check Endpoint
The `/health` endpoint provides comprehensive status information:

```json
{
  "status": "healthy",
  "opensearch": "connected",
  "opensearch_cluster": "wazuh-cluster",
  "embedding_service": "working",
  "vector_dimension": 768,
  "llm_provider": "anthropic",
  "embedding_model": "models/text-embedding-004"
}
```

### Logging
- **INFO**: General operation status
- **DEBUG**: Detailed vectorization and processing information
- **WARNING**: Non-fatal errors and fallback usage
- **ERROR**: Critical failures requiring attention

## Future Enhancements

This foundational vectorization layer enables future developments:

1. **Advanced RAG Features**:
   - Complex retrieval strategies
   - Multi-modal data support
   - Real-time similarity search APIs

2. **Performance Optimizations**:
   - Batch vectorization improvements
   - Index optimization strategies
   - Caching mechanisms

3. **Analytics and Monitoring**:
   - Vector similarity analytics
   - Processing performance metrics
   - Alert pattern analysis dashboards

## Acceptance Criteria Verification

✅ **Modular Design**: Code is organized into single-responsibility functions
✅ **Embedding Service**: Complete `GeminiEmbeddingService` with error handling
✅ **Index Template**: Proper OpenSearch template with vector field mapping
✅ **Integration**: Full workflow integration with vectorization
✅ **Dashboard Visibility**: Alerts show populated `alert_vector` fields
✅ **Stable Operation**: Process runs continuously without errors

## Conclusion

The foundational vectorization layer has been successfully implemented with:

- Clean, modular architecture following Python best practices
- Robust error handling and retry mechanisms
- Comprehensive configuration options
- Full integration with existing Wazuh alert processing
- Proper OpenSearch index template configuration
- Health monitoring and verification tools

The system is now ready for production use and provides a solid foundation for future RAG enhancements.