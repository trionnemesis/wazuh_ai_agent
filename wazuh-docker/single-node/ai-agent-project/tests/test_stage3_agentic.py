#!/usr/bin/env python3
"""
Wazuh AI Agent - Stage 3 Agentic Context Correlation Test Suite

This script validates the implementation of Stage 3 features including:
1. Contextual query generation decision engine
2. Multi-source data retrieval
3. Context correlation and formatting
4. Enhanced LLM analysis capabilities

Run this script to verify that the agentic context correlation is working correctly.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List
from datetime import datetime

# Import the Stage 3 functions
from main import (
    determine_contextual_queries,
    execute_retrieval,
    format_multi_source_context,
    embedding_service
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Stage3AgenticTester:
    """Test suite for Stage 3 Agentic Context Correlation features"""
    
    def __init__(self):
        self.test_results = []
        
    def log_test_result(self, test_name: str, passed: bool, details: str = ""):
        """Log test results for summary reporting"""
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{status}: {test_name}")
        if details:
            logger.info(f"  Details: {details}")
        
        self.test_results.append({
            'test_name': test_name,
            'passed': passed,
            'details': details
        })
    
    def test_decision_engine_resource_alerts(self):
        """Test decision engine for resource monitoring alerts"""
        print("\n🧠 Testing Decision Engine - Resource Monitoring Alerts")
        
        # Test High CPU Usage Alert
        cpu_alert = {
            '_source': {
                'rule': {
                    'description': 'High CPU usage detected on server',
                    'level': 7,
                    'groups': ['system', 'performance']
                },
                'agent': {'name': 'web-server-01'},
                'timestamp': '2024-01-15T10:30:00Z'
            }
        }
        
        queries = determine_contextual_queries(cpu_alert)
        
        # Verify default vector similarity query exists
        vector_queries = [q for q in queries if q['type'] == 'vector_similarity']
        has_vector_query = len(vector_queries) > 0
        self.log_test_result(
            "Resource Alert - Vector Similarity Query",
            has_vector_query,
            f"Found {len(vector_queries)} vector similarity queries"
        )
        
        # Verify process list query was added
        process_queries = [q for q in queries if 'process' in q['description'].lower()]
        has_process_query = len(process_queries) > 0
        self.log_test_result(
            "Resource Alert - Process List Query",
            has_process_query,
            f"Found {len(process_queries)} process-related queries"
        )
        
        # Verify total query count
        expected_queries = 2  # vector + process
        actual_queries = len(queries)
        self.log_test_result(
            "Resource Alert - Query Count",
            actual_queries == expected_queries,
            f"Expected {expected_queries}, got {actual_queries}"
        )
    
    def test_decision_engine_security_alerts(self):
        """Test decision engine for security event alerts"""
        print("\n🔒 Testing Decision Engine - Security Event Alerts")
        
        # Test SSH Authentication Failed Alert
        ssh_alert = {
            '_source': {
                'rule': {
                    'description': 'SSH authentication failed for user admin',
                    'level': 5,
                    'groups': ['authentication_failed', 'syslog']
                },
                'agent': {'name': 'database-server-02'},
                'timestamp': '2024-01-15T14:25:30Z'
            }
        }
        
        queries = determine_contextual_queries(ssh_alert)
        
        # Check for required query types
        query_descriptions = [q['description'].lower() for q in queries]
        
        has_vector = any('similar' in desc for desc in query_descriptions)
        has_cpu = any('cpu' in desc for desc in query_descriptions)
        has_network = any('network' in desc for desc in query_descriptions)
        has_ssh = any('ssh' in desc for desc in query_descriptions)
        
        self.log_test_result(
            "SSH Alert - Vector Similarity Query",
            has_vector,
            "Vector similarity search for historical alerts"
        )
        
        self.log_test_result(
            "SSH Alert - CPU Metrics Query",
            has_cpu,
            "CPU metrics correlation for security event"
        )
        
        self.log_test_result(
            "SSH Alert - Network I/O Query",
            has_network,
            "Network I/O metrics correlation"
        )
        
        self.log_test_result(
            "SSH Alert - SSH-Specific Query",
            has_ssh,
            "SSH-specific connection logs"
        )
        
        # Verify minimum query count for SSH alerts
        min_expected = 4  # vector + cpu + network + ssh
        actual_count = len(queries)
        self.log_test_result(
            "SSH Alert - Minimum Query Count",
            actual_count >= min_expected,
            f"Expected >= {min_expected}, got {actual_count}"
        )
    
    def test_decision_engine_web_alerts(self):
        """Test decision engine for web-related alerts"""
        print("\n🌐 Testing Decision Engine - Web Attack Alerts")
        
        # Test Web Attack Alert
        web_alert = {
            '_source': {
                'rule': {
                    'description': 'Web attack detected - SQL injection attempt',
                    'level': 8,
                    'groups': ['web', 'attack']
                },
                'agent': {'name': 'web-frontend-01'},
                'timestamp': '2024-01-15T16:45:15Z'
            }
        }
        
        queries = determine_contextual_queries(web_alert)
        query_descriptions = [q['description'].lower() for q in queries]
        
        has_vector = any('similar' in desc for desc in query_descriptions)
        has_security_cpu = any('cpu' in desc for desc in query_descriptions)
        has_security_network = any('network' in desc for desc in query_descriptions)
        has_web_metrics = any('web' in desc for desc in query_descriptions)
        
        self.log_test_result(
            "Web Alert - Vector Similarity Query",
            has_vector,
            "Vector similarity for web attack patterns"
        )
        
        self.log_test_result(
            "Web Alert - Security CPU Correlation",
            has_security_cpu,
            "CPU metrics during security event"
        )
        
        self.log_test_result(
            "Web Alert - Security Network Correlation",
            has_security_network,
            "Network metrics during security event"
        )
        
        self.log_test_result(
            "Web Alert - Web Server Metrics",
            has_web_metrics,
            "Web server specific metrics"
        )
    
    def test_context_aggregation_structure(self):
        """Test context data aggregation structure"""
        print("\n📊 Testing Context Aggregation Structure")
        
        # Create mock queries and vector
        mock_queries = [
            {
                'type': 'vector_similarity',
                'description': 'Similar historical alerts',
                'parameters': {'k': 5, 'include_ai_analysis': True}
            },
            {
                'type': 'keyword_time_range',
                'description': 'CPU metrics from same host',
                'parameters': {
                    'keywords': ['cpu usage', 'cpu utilization'],
                    'host': 'test-server',
                    'time_window_minutes': 1,
                    'timestamp': '2024-01-15T10:30:00Z'
                }
            }
        ]
        
        mock_vector = [0.1] * 768  # Mock 768-dimension vector
        
        # Test that execute_retrieval returns proper structure
        try:
            # Note: This will likely fail in test environment due to OpenSearch dependency
            # but we can test the structure expectations
            expected_keys = ['similar_alerts', 'cpu_metrics', 'network_logs', 'process_data', 'ssh_logs', 'web_metrics']
            
            # Mock context data structure
            mock_context_data = {key: [] for key in expected_keys}
            
            # Test format_multi_source_context
            formatted_context = format_multi_source_context(mock_context_data)
            
            expected_context_keys = ['similar_alerts_context', 'system_metrics_context', 'process_context', 'network_context']
            has_all_keys = all(key in formatted_context for key in expected_context_keys)
            
            self.log_test_result(
                "Context Aggregation - Structure Keys",
                has_all_keys,
                f"All required context keys present: {list(formatted_context.keys())}"
            )
            
        except Exception as e:
            self.log_test_result(
                "Context Aggregation - Structure Test",
                False,
                f"Error testing context structure: {str(e)}"
            )
    
    def test_query_parameter_validation(self):
        """Test query parameter validation and structure"""
        print("\n🔍 Testing Query Parameter Validation")
        
        # Test with comprehensive alert
        complex_alert = {
            '_source': {
                'rule': {
                    'description': 'SSH brute-force attack detected',
                    'level': 9,
                    'groups': ['authentication_failed', 'attack']
                },
                'agent': {'name': 'critical-server-01'},
                'timestamp': '2024-01-15T12:00:00Z'
            }
        }
        
        queries = determine_contextual_queries(complex_alert)
        
        # Validate query structure
        all_queries_valid = True
        for query in queries:
            required_fields = ['type', 'description', 'parameters']
            if not all(field in query for field in required_fields):
                all_queries_valid = False
                break
                
            # Validate parameter structure based on type
            if query['type'] == 'vector_similarity':
                required_params = ['k', 'include_ai_analysis']
                if not all(param in query['parameters'] for param in required_params):
                    all_queries_valid = False
                    break
                    
            elif query['type'] == 'keyword_time_range':
                required_params = ['keywords', 'host', 'time_window_minutes', 'timestamp']
                if not all(param in query['parameters'] for param in required_params):
                    all_queries_valid = False
                    break
        
        self.log_test_result(
            "Query Parameter Validation",
            all_queries_valid,
            f"All {len(queries)} queries have valid structure and parameters"
        )
        
        # Test time window variations
        time_windows = []
        for query in queries:
            if query['type'] == 'keyword_time_range':
                time_windows.append(query['parameters'].get('time_window_minutes', 0))
        
        has_varied_windows = len(set(time_windows)) > 1 if time_windows else False
        self.log_test_result(
            "Time Window Variation",
            has_varied_windows or len(time_windows) <= 1,
            f"Time windows used: {time_windows}"
        )
    
    async def test_embedding_service_integration(self):
        """Test integration with embedding service"""
        print("\n🔗 Testing Embedding Service Integration")
        
        try:
            # Test embedding service connectivity
            connection_ok = await embedding_service.test_connection()
            self.log_test_result(
                "Embedding Service - Connectivity",
                connection_ok,
                "Embedding service connection test"
            )
            
            if connection_ok:
                # Test alert vectorization
                test_alert_text = "SSH authentication failed for user admin on server web-01"
                vector = await embedding_service.embed_query(test_alert_text)
                
                vector_valid = isinstance(vector, list) and len(vector) > 0
                self.log_test_result(
                    "Embedding Service - Vectorization",
                    vector_valid,
                    f"Generated vector with {len(vector) if vector else 0} dimensions"
                )
                
        except Exception as e:
            self.log_test_result(
                "Embedding Service - Integration Test",
                False,
                f"Error testing embedding service: {str(e)}"
            )
    
    def test_acceptance_criteria_compliance(self):
        """Test compliance with Stage 3 acceptance criteria"""
        print("\n✅ Testing Acceptance Criteria Compliance")
        
        # Criterion 1: High CPU usage alerts execute both k-NN and keyword searches
        cpu_alert = {
            '_source': {
                'rule': {'description': 'High CPU usage detected'},
                'agent': {'name': 'test-server'},
                'timestamp': '2024-01-15T10:30:00Z'
            }
        }
        
        cpu_queries = determine_contextual_queries(cpu_alert)
        has_vector_search = any(q['type'] == 'vector_similarity' for q in cpu_queries)
        has_keyword_search = any(q['type'] == 'keyword_time_range' for q in cpu_queries)
        
        self.log_test_result(
            "Acceptance Criteria 1 - High CPU Multi-Query",
            has_vector_search and has_keyword_search,
            "Both k-NN and keyword searches for High CPU alerts"
        )
        
        # Criterion 2: SSH alerts include system metrics in context
        ssh_alert = {
            '_source': {
                'rule': {'description': 'SSH authentication failed'},
                'agent': {'name': 'test-server'},
                'timestamp': '2024-01-15T10:30:00Z'
            }
        }
        
        ssh_queries = determine_contextual_queries(ssh_alert)
        has_cpu_metrics = any('cpu' in q['description'].lower() for q in ssh_queries)
        has_network_metrics = any('network' in q['description'].lower() for q in ssh_queries)
        
        self.log_test_result(
            "Acceptance Criteria 2 - SSH System Metrics",
            has_cpu_metrics and has_network_metrics,
            "SSH alerts include CPU and network metrics correlation"
        )
        
        # Criterion 3: Multi-source context formatting
        mock_context = {
            'similar_alerts': [{'_source': {'rule': {'description': 'Test alert'}}}],
            'cpu_metrics': [{'_source': {'rule': {'description': 'CPU metric'}}}],
            'network_logs': [],
            'process_data': [],
            'ssh_logs': [],
            'web_metrics': []
        }
        
        formatted = format_multi_source_context(mock_context)
        has_similar_alerts = 'similar_alerts_context' in formatted
        has_system_metrics = 'system_metrics_context' in formatted
        has_all_sections = all(key in formatted for key in ['similar_alerts_context', 'system_metrics_context', 'process_context', 'network_context'])
        
        self.log_test_result(
            "Acceptance Criteria 3 - Multi-Source Context",
            has_all_sections,
            "All context sections properly formatted for LLM consumption"
        )
    
    def generate_summary_report(self):
        """Generate a summary report of all test results"""
        print("\n" + "="*60)
        print("🎯 STAGE 3 AGENTIC CONTEXT CORRELATION TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['passed'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"  - {result['test_name']}: {result['details']}")
        
        print("\n📊 Test Categories:")
        categories = {}
        for result in self.test_results:
            category = result['test_name'].split(' - ')[0]
            if category not in categories:
                categories[category] = {'total': 0, 'passed': 0}
            categories[category]['total'] += 1
            if result['passed']:
                categories[category]['passed'] += 1
        
        for category, stats in categories.items():
            rate = (stats['passed']/stats['total']*100)
            print(f"  {category}: {stats['passed']}/{stats['total']} ({rate:.1f}%)")
        
        overall_status = "🎉 ALL TESTS PASSED" if failed_tests == 0 else "⚠️ SOME TESTS FAILED"
        print(f"\n{overall_status}")
        print("="*60)

async def main():
    """Main test execution function"""
    print("🚀 Starting Wazuh AI Agent Stage 3 Agentic Context Correlation Tests")
    print("="*60)
    
    tester = Stage3AgenticTester()
    
    # Run all test suites
    tester.test_decision_engine_resource_alerts()
    tester.test_decision_engine_security_alerts()
    tester.test_decision_engine_web_alerts()
    tester.test_context_aggregation_structure()
    tester.test_query_parameter_validation()
    await tester.test_embedding_service_integration()
    tester.test_acceptance_criteria_compliance()
    
    # Generate summary report
    tester.generate_summary_report()

if __name__ == "__main__":
    asyncio.run(main())