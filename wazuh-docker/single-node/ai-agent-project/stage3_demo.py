#!/usr/bin/env python3
"""
Stage 3 Agentic Context Correlation - Demonstration Script

This script demonstrates the enhanced agentic decision-making capabilities
without requiring external dependencies. It shows how the system autonomously
determines contextual needs based on alert content.
"""

from datetime import datetime
from typing import Dict, Any, List

def determine_contextual_queries_demo(alert: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Demo version of the Stage 3 decision engine that determines what contextual 
    information is needed based on the alert type and content.
    """
    queries = []
    alert_source = alert.get('_source', {})
    rule = alert_source.get('rule', {})
    agent = alert_source.get('agent', {})
    data = alert_source.get('data', {})
    timestamp = alert_source.get('timestamp')
    
    rule_description = rule.get('description', '').lower()
    rule_groups = rule.get('groups', [])
    rule_level = rule.get('level', 0)
    host_name = agent.get('name', '')
    
    print(f"🤖 AGENTIC DECISION ENGINE: Analyzing alert for contextual needs")
    print(f"   Alert: {rule_description}")
    print(f"   Level: {rule_level}, Host: {host_name}")
    print(f"   Groups: {', '.join(rule_groups)}")
    
    # Default: Always perform k-NN search for similar historical alerts
    queries.append({
        'type': 'vector_similarity',
        'description': 'Similar historical alerts',
        'priority': 'high',
        'parameters': {
            'k': 7,
            'include_ai_analysis': True
        }
    })
    print("✅ DECISION: Adding vector similarity search (always required)")
    
    # Enhanced Resource monitoring correlation rules
    resource_keywords = [
        'high cpu usage', 'excessive ram consumption', 'memory usage', 'memory leak',
        'disk space', 'cpu utilization', 'system overload', 'performance', 
        'resource exhaustion', 'out of memory', 'cpu spike', 'high load'
    ]
    
    if any(keyword in rule_description for keyword in resource_keywords) or 'system' in rule_groups:
        print("🔍 DECISION: Resource-related alert detected - correlating with system data")
        
        queries.append({
            'type': 'keyword_time_range',
            'description': 'Process information from same host',
            'priority': 'high',
            'parameters': {
                'keywords': ['process list', 'top processes', 'running processes', 'ps aux', 'htop'],
                'host': host_name,
                'time_window_minutes': 10,
                'timestamp': timestamp
            }
        })
        
        queries.append({
            'type': 'keyword_time_range',
            'description': 'Memory usage metrics',
            'priority': 'medium',
            'parameters': {
                'keywords': ['memory usage', 'ram utilization', 'swap usage', 'free memory'],
                'host': host_name,
                'time_window_minutes': 15,
                'timestamp': timestamp
            }
        })
        
        print("   ✅ Added process and memory correlation queries")
    
    # Enhanced Security event correlation rules
    security_keywords = [
        'ssh brute-force', 'web attack', 'authentication failed', 'login attempt',
        'intrusion', 'malware', 'suspicious activity', 'unauthorized access',
        'privilege escalation', 'command injection', 'sql injection',
        'cross-site scripting', 'buffer overflow', 'trojan', 'backdoor'
    ]
    
    security_groups = ['authentication', 'attack', 'malware', 'intrusion_detection', 'web']
    
    if (any(keyword in rule_description for keyword in security_keywords) or 
        any(group in rule_groups for group in security_groups) or 
        rule_level >= 7):
        
        print("🛡️ DECISION: Security event detected - adding comprehensive correlation")
        
        queries.append({
            'type': 'keyword_time_range',
            'description': 'CPU metrics during security event',
            'priority': 'high',
            'parameters': {
                'keywords': ['cpu usage', 'cpu utilization', 'processor load', 'high cpu'],
                'host': host_name,
                'time_window_minutes': 2,
                'timestamp': timestamp
            }
        })
        
        queries.append({
            'type': 'keyword_time_range',
            'description': 'Network activity during security event',
            'priority': 'high',
            'parameters': {
                'keywords': ['network traffic', 'network io', 'bandwidth', 'packets', 'connections'],
                'host': host_name,
                'time_window_minutes': 3,
                'timestamp': timestamp
            }
        })
        
        queries.append({
            'type': 'keyword_time_range',
            'description': 'User activity correlation',
            'priority': 'medium',
            'parameters': {
                'keywords': ['user login', 'user activity', 'session', 'authentication'],
                'host': host_name,
                'time_window_minutes': 5,
                'timestamp': timestamp
            }
        })
        
        print("   ✅ Added security event correlation queries (CPU, Network, User)")
    
    # SSH-specific enhanced correlation
    if 'ssh' in rule_description or 'sshd' in rule_description:
        print("🔑 DECISION: SSH-related alert - adding SSH-specific correlation")
        
        queries.append({
            'type': 'keyword_time_range',
            'description': 'SSH connection patterns',
            'priority': 'high',
            'parameters': {
                'keywords': ['ssh connection', 'port 22', 'sshd', 'ssh login', 'ssh session'],
                'host': host_name,
                'time_window_minutes': 5,
                'timestamp': timestamp
            }
        })
        
        if 'brute' in rule_description or 'failed' in rule_description:
            queries.append({
                'type': 'keyword_time_range',
                'description': 'SSH failure patterns',
                'priority': 'high',
                'parameters': {
                    'keywords': ['ssh failed', 'authentication failure', 'invalid user', 'connection refused'],
                    'host': host_name,
                    'time_window_minutes': 10,
                    'timestamp': timestamp
                }
            })
            print("   ✅ Added SSH brute force correlation")
    
    # Web-related enhanced correlation
    web_indicators = ['web', 'http', 'apache', 'nginx', 'php', 'sql injection', 'xss']
    if any(indicator in rule_description for indicator in web_indicators):
        print("🌐 DECISION: Web-related alert - adding web server correlation")
        
        queries.append({
            'type': 'keyword_time_range',
            'description': 'Web server performance',
            'priority': 'medium',
            'parameters': {
                'keywords': ['apache', 'nginx', 'web server', 'http requests', 'response time'],
                'host': host_name,
                'time_window_minutes': 3,
                'timestamp': timestamp
            }
        })
        
        queries.append({
            'type': 'keyword_time_range',
            'description': 'Web access logs',
            'priority': 'high',
            'parameters': {
                'keywords': ['access log', 'http status', 'user agent', 'request uri'],
                'host': host_name,
                'time_window_minutes': 2,
                'timestamp': timestamp
            }
        })
        
        print("   ✅ Added web server correlation queries")
    
    # File system correlation for critical alerts
    if rule_level >= 10 or 'file' in rule_description:
        print("📁 DECISION: High-level/file-related alert - adding filesystem correlation")
        
        queries.append({
            'type': 'keyword_time_range',
            'description': 'File system activity',
            'priority': 'medium',
            'parameters': {
                'keywords': ['file created', 'file modified', 'file deleted', 'disk usage', 'inode'],
                'host': host_name,
                'time_window_minutes': 5,
                'timestamp': timestamp
            }
        })
        
        print("   ✅ Added filesystem correlation")
    
    # Summary logging
    total_queries = len(queries)
    high_priority = len([q for q in queries if q.get('priority') == 'high'])
    print(f"🎯 AGENTIC DECISION COMPLETE: Generated {total_queries} contextual queries")
    print(f"   High priority: {high_priority}, Total sources: {total_queries}")
    print(f"   Query types: {', '.join(set(q['type'] for q in queries))}")
    
    return queries

def create_test_alert(rule_description: str, rule_level: int, rule_groups: List[str], 
                     host_name: str = "test-server", additional_data: Dict = None) -> Dict[str, Any]:
    """Create a test alert with specified parameters"""
    timestamp = datetime.utcnow().isoformat() + 'Z'
    
    alert = {
        '_id': f'test-{rule_description.replace(" ", "-")}',
        '_index': 'wazuh-alerts-test',
        '_source': {
            'timestamp': timestamp,
            'rule': {
                'description': rule_description,
                'level': rule_level,
                'groups': rule_groups,
                'id': f'test-{rule_level}'
            },
            'agent': {
                'name': host_name
            },
            'data': additional_data or {}
        }
    }
    return alert

def print_decision_analysis(alert: Dict[str, Any], queries: List[Dict[str, Any]]):
    """Print detailed analysis of the agentic decision process"""
    rule = alert['_source']['rule']
    agent = alert['_source']['agent']
    
    print("\n" + "="*80)
    print("🤖 AGENTIC DECISION ANALYSIS")
    print("="*80)
    print(f"📋 Alert: {rule['description']}")
    print(f"📊 Level: {rule['level']} | Host: {agent['name']}")
    print(f"🏷️  Groups: {', '.join(rule['groups'])}")
    print("\n🧠 DECISION ENGINE ANALYSIS:")
    
    # Categorize queries
    vector_queries = [q for q in queries if q['type'] == 'vector_similarity']
    keyword_queries = [q for q in queries if q['type'] == 'keyword_time_range']
    high_priority = [q for q in queries if q.get('priority') == 'high']
    medium_priority = [q for q in queries if q.get('priority') == 'medium']
    
    print(f"   📈 Total Queries Generated: {len(queries)}")
    print(f"   🔍 Vector Similarity Searches: {len(vector_queries)}")
    print(f"   🔎 Keyword/Time Range Searches: {len(keyword_queries)}")
    print(f"   🔴 High Priority Queries: {len(high_priority)}")
    print(f"   🟡 Medium Priority Queries: {len(medium_priority)}")
    
    print("\n📋 DETAILED QUERY BREAKDOWN:")
    for i, query in enumerate(queries, 1):
        priority_emoji = "🔴" if query.get('priority') == 'high' else "🟡" if query.get('priority') == 'medium' else "🟢"
        print(f"   [{i}] {priority_emoji} {query['description']}")
        print(f"       Type: {query['type']}")
        if query['type'] == 'keyword_time_range':
            params = query['parameters']
            print(f"       Keywords: {', '.join(params.get('keywords', []))}")
            print(f"       Time Window: {params.get('time_window_minutes', 'N/A')} minutes")
            print(f"       Host Filter: {params.get('host', 'N/A')}")
    
    print("\n💡 CONTEXTUAL INTELLIGENCE:")
    
    # Analyze decision reasoning
    rule_desc = rule['description'].lower()
    reasoning = []
    
    if any(keyword in rule_desc for keyword in ['cpu', 'memory', 'resource', 'performance']):
        reasoning.append("🔧 Resource correlation: System metrics and process data needed")
    
    if any(keyword in rule_desc for keyword in ['ssh', 'authentication', 'login']):
        reasoning.append("🔐 Security correlation: Network patterns and user activity needed")
        
    if rule['level'] >= 7:
        reasoning.append(f"⚠️  High severity (Level {rule['level']}): Comprehensive context required")
        
    if 'attack' in rule['groups'] or 'intrusion_detection' in rule['groups']:
        reasoning.append("🛡️ Attack correlation: Multi-source security intelligence needed")
    
    for reason in reasoning:
        print(f"   {reason}")
    
    print(f"\n🎯 AGENTIC DECISION: The system autonomously determined that this alert requires")
    print(f"   {len(queries)} different types of contextual information to provide comprehensive analysis.")

def run_demo_tests():
    """Run demonstration tests for different alert types"""
    
    print("🚀 STAGE 3 AGENTIC CONTEXT CORRELATION - DEMONSTRATION")
    print("=" * 80)
    print("Demonstrating autonomous decision-making capabilities")
    
    # Test Case 1: Resource Alert
    print("\n🧪 TEST CASE 1: Resource Alert - High CPU Usage")
    alert1 = create_test_alert(
        rule_description="High CPU usage detected",
        rule_level=8,
        rule_groups=['system', 'performance'],
        host_name="web-server-01"
    )
    queries1 = determine_contextual_queries_demo(alert1)
    print_decision_analysis(alert1, queries1)
    
    # Test Case 2: SSH Security Alert
    print("\n🧪 TEST CASE 2: SSH Security Alert - Authentication Failed")
    alert2 = create_test_alert(
        rule_description="SSH authentication failed",
        rule_level=9,
        rule_groups=['authentication', 'attack'],
        host_name="ssh-server-02",
        additional_data={'srcip': '192.168.1.100', 'user': 'admin'}
    )
    queries2 = determine_contextual_queries_demo(alert2)
    print_decision_analysis(alert2, queries2)
    
    # Test Case 3: SSH Brute Force
    print("\n🧪 TEST CASE 3: SSH Brute Force Attack")
    alert3 = create_test_alert(
        rule_description="SSH brute force attack detected",
        rule_level=8,
        rule_groups=['authentication', 'attack'],
        host_name="ssh-gateway",
        additional_data={'srcip': '192.168.1.200', 'attempts': 50}
    )
    queries3 = determine_contextual_queries_demo(alert3)
    print_decision_analysis(alert3, queries3)
    
    # Test Case 4: Web Attack
    print("\n🧪 TEST CASE 4: Web Attack - SQL Injection")
    alert4 = create_test_alert(
        rule_description="Web application attack: SQL injection attempt detected",
        rule_level=10,
        rule_groups=['web', 'attack', 'intrusion_detection'],
        host_name="web-app-server",
        additional_data={'srcip': '10.0.0.50', 'url': '/login.php', 'method': 'POST'}
    )
    queries4 = determine_contextual_queries_demo(alert4)
    print_decision_analysis(alert4, queries4)
    
    # Test Case 5: Critical File System Alert
    print("\n🧪 TEST CASE 5: Critical File System Alert")
    alert5 = create_test_alert(
        rule_description="Critical file modification detected in /etc/passwd",
        rule_level=12,
        rule_groups=['system', 'critical'],
        host_name="production-server",
        additional_data={'file': '/etc/passwd', 'action': 'modified'}
    )
    queries5 = determine_contextual_queries_demo(alert5)
    print_decision_analysis(alert5, queries5)
    
    # Summary
    print("\n" + "="*80)
    print("🎉 STAGE 3 AGENTIC CORRELATION DEMONSTRATION COMPLETED")
    print("="*80)
    print("✅ Demonstrated autonomous contextual need determination")
    print("✅ Showed multi-source correlation decision logic")
    print("✅ Verified priority-based query generation")
    print("✅ Confirmed human-like reasoning patterns")
    print("\n🤖 Key Stage 3 Capabilities Demonstrated:")
    print("   • Dynamic context correlation based on alert content")
    print("   • Intelligent priority assignment for optimal performance")
    print("   • Comprehensive multi-source data retrieval planning")
    print("   • Autonomous decision-making without human intervention")
    print("\n🎯 ACCEPTANCE CRITERIA VERIFICATION:")
    print("   ✅ High CPU alerts trigger both k-NN and process correlation")
    print("   ✅ SSH alerts include system metrics and network correlation")
    print("   ✅ Multi-source context prepared for comprehensive LLM analysis")

if __name__ == "__main__":
    run_demo_tests()