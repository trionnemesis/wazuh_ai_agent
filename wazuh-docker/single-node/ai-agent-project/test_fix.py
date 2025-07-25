#!/usr/bin/env python3
"""
Test script to verify the scheduler fix for the timeout context manager error
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

async def test_scheduler_fix():
    """Test the scheduler with the async job wrapper"""
    print("Testing scheduler fix...")
    
    try:
        # Import the scheduler module
        from core.scheduler import async_job_wrapper
        
        print("✓ Successfully imported async_job_wrapper")
        
        # Try to run the async job wrapper
        print("Attempting to run async_job_wrapper...")
        await async_job_wrapper()
        
        print("✓ async_job_wrapper executed successfully!")
        
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

async def test_opensearch_client():
    """Test that the opensearch client can be created in async context"""
    print("\nTesting OpenSearch client...")
    
    try:
        from services.opensearch_service import get_opensearch_client
        
        print("✓ Successfully imported get_opensearch_client")
        
        # Try to get the client
        print("Attempting to get OpenSearch client...")
        client = await get_opensearch_client()
        
        print("✓ OpenSearch client created successfully!")
        
        # Try a simple operation
        print("Testing client connection...")
        info = await client.info()
        print(f"✓ Connected to OpenSearch: {info.get('version', {}).get('number', 'unknown')}")
        
        # Close the client
        await client.close()
        
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

async def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing GraphRAG Alert Triage Scheduler Fix")
    print("=" * 60)
    
    # Test 1: OpenSearch client
    opensearch_ok = await test_opensearch_client()
    
    # Test 2: Scheduler async wrapper
    if opensearch_ok:
        scheduler_ok = await test_scheduler_fix()
    else:
        print("\n⚠️  Skipping scheduler test due to OpenSearch client issues")
        scheduler_ok = False
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print(f"  OpenSearch Client: {'✓ PASS' if opensearch_ok else '✗ FAIL'}")
    print(f"  Scheduler Fix: {'✓ PASS' if scheduler_ok else '✗ FAIL'}")
    print("=" * 60)
    
    return opensearch_ok and scheduler_ok

if __name__ == "__main__":
    # Run the async main function
    success = asyncio.run(main())
    sys.exit(0 if success else 1)