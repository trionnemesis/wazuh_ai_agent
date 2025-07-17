# Wazuh AI Agent - Stage 2: Core RAG Implementation

## Overview

This document outlines the implementation of Stage 2 for the Wazuh AI Agent, which focuses on implementing core Retrieval-Augmented Generation (RAG) functionality. Building upon the vectorization system from Stage 1, Stage 2 enables the AI agent to perform k-Nearest Neighbor searches to find similar historical alerts and use them to provide more context-aware analysis.

## Key Improvements

### 1. Enhanced Retrieval Module

**Function: `find_similar_alerts(query_vector: List[float], k: int = 5)`**
- Performs k-NN searches on OpenSearch using cosine similarity
- Targets the `alert_embedding` field in the `wazuh-alerts-*` index
- Filters results to only include historically analyzed alerts
- Returns the top `k` most similar alert documents
- Includes comprehensive error handling and logging

### 2. Updated Prompt Template

The prompt template has been restructured to support historical context:

```python
prompt_template = ChatPromptTemplate.from_template(
    """You are a senior security analyst. Analyze the new Wazuh alert below, using the provided historical context from similar past alerts to inform your assessment.

    **Relevant Historical Alerts:**
    {historical_context}

    **New Wazuh Alert to Analyze:**
    {alert_summary}

    **Your Analysis Task:**
    1. Briefly summarize the new event.
    2. Assess its risk level (Critical, High, Medium, Low, Informational), considering any patterns from the historical context.
    3. Provide a clear, context-aware recommendation that references relevant patterns from similar past alerts.

    **Your Triage Report:**
    """
)
```

### 3. Context Formatting Function

**Function: `format_historical_context(alerts: List[Dict[Any, Any]]) -> str`**
- Formats retrieved historical alerts into a readable string
- Includes key information: timestamp, host, rule description, previous AI analysis, similarity score
- Truncates long analysis reports to maintain prompt efficiency
- Handles empty result sets gracefully

### 4. Integrated Workflow

**Function: `process_single_alert(alert: Dict[Any, Any]) -> None`**

The new workflow follows this sequence:
1. **Fetch**: Get the new alert data
2. **Vectorize**: Generate embeddings for the new alert
3. **Retrieve**: Find similar historical alerts using k-NN search
4. **Format**: Create readable historical context
5. **Analyze**: Invoke LLM with both current alert and historical context
6. **Update**: Store results and embeddings in OpenSearch

## Technical Implementation Details

### k-NN Search Query Structure

```json
{
  "size": k,
  "query": {
    "bool": {
      "must": [
        {
          "knn": {
            "alert_embedding": {
              "vector": query_vector,
              "k": k
            }
          }
        }
      ],
      "filter": [
        {
          "exists": {
            "field": "ai_analysis"
          }
        }
      ]
    }
  }
}
```

### Enhanced Logging

The implementation includes comprehensive logging:
- k-NN query execution details
- Number of similar alerts found
- Processing status for each alert
- Error handling and debugging information

### Data Storage

Each processed alert now stores:
- `ai_analysis.triage_report`: LLM-generated analysis
- `ai_analysis.provider`: LLM provider used
- `ai_analysis.timestamp`: Processing timestamp
- `ai_analysis.similar_alerts_count`: Number of historical alerts used
- `alert_embedding`: Vector representation for future retrievals

## Benefits and Expected Improvements

### 1. Context-Aware Analysis

Instead of analyzing alerts in isolation, the system now considers:
- Historical patterns from similar alerts
- Previous analysis outcomes
- Temporal patterns and frequency analysis
- Host-specific behavior patterns

### 2. Enhanced Threat Detection

Example improvements:
- **Before**: "SSH login failed"
- **After**: "This is the third SSH login failure from IP 1.2.3.4 in the last hour based on similar historical alerts, indicating a potential brute-force attempt"

### 3. Consistent Decision Making

By referencing historical analysis, the system provides:
- More consistent risk assessments
- Better pattern recognition
- Reduced false positives through historical context
- Learning from past decisions

## Configuration and Requirements

### Environment Variables

The system continues to use the existing environment variables:
- `LLM_PROVIDER`: Choose between 'gemini' or 'anthropic'
- `GEMINI_API_KEY`: Required if using Gemini
- `ANTHROPIC_API_KEY`: Required if using Anthropic
- `GOOGLE_API_KEY`: Required for embedding service
- `OPENSEARCH_URL`, `OPENSEARCH_USER`, `OPENSEARCH_PASSWORD`: OpenSearch connection

### Dependencies

No additional dependencies required beyond Stage 1 implementation.

## Performance Considerations

### 1. Search Efficiency

- k-NN searches are optimized for the most relevant historical alerts
- Default k=5 provides good context without overwhelming the prompt
- Filtering ensures only analyzed alerts are retrieved

### 2. Memory Management

- Historical context is truncated to prevent token overflow
- Vector storage is efficient using OpenSearch's native capabilities
- Parallel processing capabilities maintained

### 3. Scalability

- Asynchronous processing maintained throughout
- Error handling prevents single alert failures from affecting others
- Configurable batch sizes and intervals

## Monitoring and Validation

### 1. Logging Metrics

Monitor these key metrics:
- Number of similar alerts found per new alert
- k-NN search execution times
- Analysis quality improvements
- Error rates in retrieval process

### 2. Quality Validation

Expected improvements in analysis reports:
- Explicit references to historical patterns
- More specific risk assessments
- Context-aware recommendations
- Pattern-based threat identification

## Future Enhancements

Potential Stage 3 improvements:
1. **Dynamic k-value selection** based on alert type
2. **Temporal weighting** for more recent alerts
3. **Multi-factor similarity** combining rule, host, and temporal factors
4. **Feedback learning** from analyst corrections
5. **Advanced clustering** for alert pattern discovery

## Conclusion

Stage 2 successfully transforms the Wazuh AI Agent from a simple alert analyzer into a sophisticated RAG-enabled system that learns from historical patterns. The implementation provides the foundation for more intelligent, context-aware security analysis while maintaining the efficiency and reliability established in Stage 1.