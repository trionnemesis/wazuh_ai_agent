#!/usr/bin/env python3
"""
Stage 3 Agentic Context Correlation - Deployment Verification Script

This script performs pre-deployment checks to ensure the Stage 3 implementation
is properly configured and ready for production use.

Run this script before deploying Stage 3 to production.
"""

import os
import sys
import asyncio
import logging
from typing import Dict, List, Any
import importlib.util

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Stage3DeploymentVerifier:
    """Deployment verification for Stage 3 Agentic Context Correlation"""
    
    def __init__(self):
        self.checks_passed = 0
        self.checks_failed = 0
        self.critical_failures = []
        
    def log_check(self, check_name: str, passed: bool, details: str = "", critical: bool = False):
        """Log deployment check results"""
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {check_name}")
        if details:
            logger.info(f"  Details: {details}")
        
        if passed:
            self.checks_passed += 1
        else:
            self.checks_failed += 1
            if critical:
                self.critical_failures.append(check_name)
    
    def check_environment_variables(self):
        """Check required environment variables"""
        print("🔧 Checking Environment Configuration...")
        
        required_vars = [
            'LLM_PROVIDER',
            'OPENSEARCH_URL',
            'OPENSEARCH_USER',
            'OPENSEARCH_PASSWORD'
        ]
        
        optional_vars = [
            'ANTHROPIC_API_KEY',
            'GOOGLE_API_KEY',
            'GEMINI_API_KEY'
        ]
        
        # Check required variables
        all_required_present = True
        for var in required_vars:
            if os.getenv(var):
                self.log_check(f"Environment Variable - {var}", True, "Present")
            else:
                self.log_check(f"Environment Variable - {var}", False, "Missing", critical=True)
                all_required_present = False
        
        # Check LLM provider specific keys
        llm_provider = os.getenv('LLM_PROVIDER', '').lower()
        if llm_provider == 'anthropic':
            has_anthropic_key = bool(os.getenv('ANTHROPIC_API_KEY'))
            self.log_check("Anthropic API Key", has_anthropic_key, 
                          "Required for Anthropic LLM provider", critical=True)
        elif llm_provider == 'gemini':
            has_gemini_key = bool(os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY'))
            self.log_check("Google/Gemini API Key", has_gemini_key,
                          "Required for Gemini LLM provider", critical=True)
        
        # Check for embedding service key
        has_embedding_key = bool(os.getenv('GOOGLE_API_KEY'))
        self.log_check("Google API Key for Embeddings", has_embedding_key,
                      "Required for Gemini embedding service", critical=True)
    
    def check_code_structure(self):
        """Check that all required Stage 3 functions are present"""
        print("\n🏗️ Checking Code Structure...")
        
        try:
            # Import main module
            from main import (
                determine_contextual_queries,
                execute_retrieval,
                format_multi_source_context,
                execute_vector_search,
                execute_keyword_time_search,
                process_single_alert,
                triage_new_alerts
            )
            
            self.log_check("Stage 3 Core Functions", True, "All required functions imported successfully")
            
            # Check function signatures
            import inspect
            
            # Check determine_contextual_queries signature
            sig = inspect.signature(determine_contextual_queries)
            expected_params = ['alert']
            actual_params = list(sig.parameters.keys())
            params_correct = all(param in actual_params for param in expected_params)
            self.log_check("determine_contextual_queries Signature", params_correct,
                          f"Expected {expected_params}, got {actual_params}")
            
            # Check execute_retrieval signature  
            sig = inspect.signature(execute_retrieval)
            expected_params = ['queries', 'alert_vector']
            actual_params = list(sig.parameters.keys())
            params_correct = all(param in actual_params for param in expected_params)
            self.log_check("execute_retrieval Signature", params_correct,
                          f"Expected {expected_params}, got {actual_params}")
            
        except ImportError as e:
            self.log_check("Stage 3 Import Test", False, f"Import error: {str(e)}", critical=True)
        except Exception as e:
            self.log_check("Code Structure Check", False, f"Unexpected error: {str(e)}", critical=True)
    
    def check_decision_engine_logic(self):
        """Test the decision engine logic"""
        print("\n🧠 Testing Decision Engine Logic...")
        
        try:
            from main import determine_contextual_queries
            
            # Test CPU alert
            cpu_alert = {
                '_source': {
                    'rule': {'description': 'High CPU usage detected'},
                    'agent': {'name': 'test-server'},
                    'timestamp': '2024-01-15T10:30:00Z'
                }
            }
            
            queries = determine_contextual_queries(cpu_alert)
            
            # Should have vector similarity + process query
            has_vector = any(q['type'] == 'vector_similarity' for q in queries)
            has_process = any('process' in q['description'].lower() for q in queries)
            
            self.log_check("CPU Alert Decision Logic", has_vector and has_process,
                          f"Generated {len(queries)} queries with vector and process correlation")
            
            # Test SSH alert
            ssh_alert = {
                '_source': {
                    'rule': {'description': 'SSH authentication failed'},
                    'agent': {'name': 'test-server'},
                    'timestamp': '2024-01-15T10:30:00Z'
                }
            }
            
            ssh_queries = determine_contextual_queries(ssh_alert)
            
            # Should have vector + cpu + network + ssh queries
            query_types = [q['description'].lower() for q in ssh_queries]
            has_ssh_vector = any('similar' in desc for desc in query_types)
            has_ssh_cpu = any('cpu' in desc for desc in query_types)
            has_ssh_network = any('network' in desc for desc in query_types)
            has_ssh_specific = any('ssh' in desc for desc in query_types)
            
            ssh_logic_correct = all([has_ssh_vector, has_ssh_cpu, has_ssh_network, has_ssh_specific])
            self.log_check("SSH Alert Decision Logic", ssh_logic_correct,
                          f"Generated {len(ssh_queries)} queries with comprehensive correlation")
            
        except Exception as e:
            self.log_check("Decision Engine Test", False, f"Error: {str(e)}", critical=True)
    
    def check_context_formatting(self):
        """Test context formatting functionality"""
        print("\n📊 Testing Context Formatting...")
        
        try:
            from main import format_multi_source_context
            
            # Test with mock data
            mock_context = {
                'similar_alerts': [
                    {
                        '_source': {
                            'rule': {'description': 'Test alert', 'level': 5},
                            'agent': {'name': 'test-host'},
                            'timestamp': '2024-01-15T10:30:00Z',
                            'ai_analysis': {'triage_report': 'Test analysis'}
                        },
                        '_score': 0.85
                    }
                ],
                'cpu_metrics': [
                    {
                        '_source': {
                            'rule': {'description': 'CPU utilization at 90%'},
                            'timestamp': '2024-01-15T10:30:00Z'
                        }
                    }
                ],
                'network_logs': [],
                'process_data': [],
                'ssh_logs': [],
                'web_metrics': []
            }
            
            formatted = format_multi_source_context(mock_context)
            
            # Check required keys are present
            required_keys = ['similar_alerts_context', 'system_metrics_context', 'process_context', 'network_context']
            all_keys_present = all(key in formatted for key in required_keys)
            
            self.log_check("Context Formatting Keys", all_keys_present,
                          f"All required context keys present: {list(formatted.keys())}")
            
            # Check content is properly formatted
            has_similar_content = 'Test alert' in formatted['similar_alerts_context']
            has_cpu_content = 'CPU utilization' in formatted['system_metrics_context']
            
            self.log_check("Context Content Formatting", has_similar_content and has_cpu_content,
                          "Context data properly formatted for LLM consumption")
            
        except Exception as e:
            self.log_check("Context Formatting Test", False, f"Error: {str(e)}", critical=True)
    
    async def check_embedding_service(self):
        """Test embedding service connectivity"""
        print("\n🔗 Testing Embedding Service...")
        
        try:
            from embedding_service import GeminiEmbeddingService
            
            embedding_service = GeminiEmbeddingService()
            
            # Test connection
            connection_ok = await embedding_service.test_connection()
            self.log_check("Embedding Service Connection", connection_ok,
                          "Google Gemini embedding service connectivity")
            
            if connection_ok:
                # Test vectorization
                test_text = "Test alert for vectorization"
                vector = await embedding_service.embed_query(test_text)
                
                vector_valid = isinstance(vector, list) and len(vector) > 0
                self.log_check("Embedding Service Vectorization", vector_valid,
                              f"Generated vector with {len(vector) if vector else 0} dimensions")
            
        except Exception as e:
            self.log_check("Embedding Service Test", False, f"Error: {str(e)}", critical=True)
    
    def check_prompt_template(self):
        """Check the enhanced prompt template"""
        print("\n📝 Checking Prompt Template...")
        
        try:
            from main import prompt_template
            
            # Get template string
            template_str = str(prompt_template)
            
            # Check for required sections
            required_sections = [
                'similar_alerts_context',
                'system_metrics_context',
                'process_context',
                'network_context',
                'alert_summary'
            ]
            
            all_sections_present = all(section in template_str for section in required_sections)
            self.log_check("Prompt Template Sections", all_sections_present,
                          f"All required sections present: {required_sections}")
            
            # Check for enhanced analysis instructions
            has_correlation_instruction = 'correlate' in template_str.lower()
            has_cross_reference_instruction = 'cross-referenc' in template_str.lower()
            
            enhanced_instructions = has_correlation_instruction and has_cross_reference_instruction
            self.log_check("Enhanced Analysis Instructions", enhanced_instructions,
                          "Template includes correlation and cross-reference instructions")
            
        except Exception as e:
            self.log_check("Prompt Template Check", False, f"Error: {str(e)}", critical=True)
    
    def check_fastapi_configuration(self):
        """Check FastAPI application configuration"""
        print("\n🚀 Checking FastAPI Configuration...")
        
        try:
            from main import app
            
            # Check app title
            expected_title = "Wazuh AI Triage Agent - Stage 3 Agentic Context Correlation"
            title_correct = app.title == expected_title
            self.log_check("FastAPI App Title", title_correct,
                          f"Expected: {expected_title}, Got: {app.title}")
            
            # Check routes
            routes = [route.path for route in app.routes]
            has_root_route = "/" in routes
            self.log_check("FastAPI Root Route", has_root_route,
                          f"Available routes: {routes}")
            
        except Exception as e:
            self.log_check("FastAPI Configuration Check", False, f"Error: {str(e)}")
    
    def generate_deployment_report(self):
        """Generate deployment readiness report"""
        print("\n" + "="*70)
        print("🎯 STAGE 3 AGENTIC CONTEXT CORRELATION DEPLOYMENT REPORT")
        print("="*70)
        
        total_checks = self.checks_passed + self.checks_failed
        success_rate = (self.checks_passed / total_checks * 100) if total_checks > 0 else 0
        
        print(f"Total Checks: {total_checks}")
        print(f"✅ Passed: {self.checks_passed}")
        print(f"❌ Failed: {self.checks_failed}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        # Deployment readiness assessment
        if self.critical_failures:
            print(f"\n🚨 CRITICAL FAILURES ({len(self.critical_failures)}):")
            for failure in self.critical_failures:
                print(f"  - {failure}")
            print("\n❌ DEPLOYMENT NOT RECOMMENDED")
            print("Fix critical issues before deploying to production.")
            return False
        
        elif self.checks_failed > 0:
            print(f"\n⚠️ NON-CRITICAL ISSUES ({self.checks_failed}):")
            print("Deployment possible but issues should be addressed.")
            print("\n🟡 DEPLOYMENT WITH CAUTION")
            return True
        
        else:
            print("\n🎉 ALL CHECKS PASSED!")
            print("✅ READY FOR PRODUCTION DEPLOYMENT")
            return True
        
        print("="*70)

async def main():
    """Main deployment verification function"""
    print("🚀 Starting Stage 3 Agentic Context Correlation Deployment Verification")
    print("="*70)
    
    verifier = Stage3DeploymentVerifier()
    
    # Run all verification checks
    verifier.check_environment_variables()
    verifier.check_code_structure()
    verifier.check_decision_engine_logic()
    verifier.check_context_formatting()
    await verifier.check_embedding_service()
    verifier.check_prompt_template()
    verifier.check_fastapi_configuration()
    
    # Generate deployment report
    deployment_ready = verifier.generate_deployment_report()
    
    # Return appropriate exit code
    if not deployment_ready and verifier.critical_failures:
        sys.exit(1)  # Critical failures
    elif verifier.checks_failed > 0:
        sys.exit(2)  # Non-critical issues
    else:
        sys.exit(0)  # All checks passed

if __name__ == "__main__":
    asyncio.run(main())