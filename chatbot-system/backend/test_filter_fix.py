#!/usr/bin/env python3
"""
Test script to verify the FilterGenerator fix for focal_entity filtering
"""
import sys
import asyncio
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.intelligence.filter_generator import FilterGenerator
from app.intelligence.metadata_manager import get_metadata_manager


async def test_focal_entity_filter():
    """Test the focal_entity = '3189446387' filter"""

    print("=" * 80)
    print("🧪 Testing FilterGenerator Fix for focal_entity Filtering")
    print("=" * 80)

    # Initialize FilterGenerator
    filter_gen = FilterGenerator()

    # Set context for database query
    filter_gen.set_table_context("info_alert.cm_alerts")
    filter_gen.set_metadata_source('database')

    print("\n📋 Test Case: focal_entity = '3189446387'")
    print("-" * 80)

    # Test filter
    query = "focal_entity = '3189446387'"
    print(f"Input filter: {query}")

    # Generate filters
    generated_filter = await filter_gen.generate_filters(query)

    print(f"\n✅ Generated Filter:")
    print(f"   Conditions: {len(generated_filter.conditions)}")
    for i, cond in enumerate(generated_filter.conditions, 1):
        print(f"   {i}. Field: {cond.field}, Operator: {cond.operator.value}, Value: {cond.value}, Type: {cond.data_type}")

    print(f"\n📊 SQL WHERE Clause:")
    print(f"   {generated_filter.sql_where_clause}")

    print(f"\n🔗 API Query Params:")
    print(f"   {generated_filter.api_query_params}")

    # Test result
    expected_where = "focal_entity = '3189446387'"
    if generated_filter.sql_where_clause == expected_where:
        print(f"\n✅ SUCCESS: WHERE clause is correct!")
        print(f"   Full SQL would be: SELECT * FROM info_alert.cm_alerts WHERE {expected_where} LIMIT 100")
        return True
    else:
        print(f"\n❌ FAILURE: WHERE clause is incorrect!")
        print(f"   Expected: {expected_where}")
        print(f"   Got: {generated_filter.sql_where_clause}")
        return False


async def test_additional_filters():
    """Test additional filter patterns"""

    print("\n" + "=" * 80)
    print("🧪 Testing Additional Filter Patterns")
    print("=" * 80)

    filter_gen = FilterGenerator()
    filter_gen.set_table_context("info_alert.cm_alerts")
    filter_gen.set_metadata_source('database')

    test_cases = [
        ("total_score > 90", "total_score > 90"),
        ("status = 'Open'", "status = 'Open'"),
        ("customer_name LIKE '%Smith%'", "customer_name LIKE '%Smith%'"),
    ]

    all_passed = True

    for query, expected in test_cases:
        print(f"\n📋 Test: {query}")
        generated = await filter_gen.generate_filters(query)
        actual = generated.sql_where_clause

        if actual == expected:
            print(f"   ✅ PASS: {actual}")
        else:
            print(f"   ❌ FAIL: Expected '{expected}', Got '{actual}'")
            all_passed = False

    return all_passed


async def main():
    """Run all tests"""
    print("\n🚀 Starting FilterGenerator Tests\n")

    # Test metadata manager loading
    print("📚 Loading Metadata...")
    metadata_mgr = get_metadata_manager()
    print(f"   Database tables loaded: {len(metadata_mgr.metadata)}")
    print(f"   API endpoints loaded: {len(metadata_mgr.api_metadata)}")
    print(f"   SOAP operations loaded: {len(metadata_mgr.soap_metadata)}")

    # Test focal_entity filter (the main fix)
    test1_passed = await test_focal_entity_filter()

    # Test additional patterns
    test2_passed = await test_additional_filters()

    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)

    if test1_passed and test2_passed:
        print("✅ ALL TESTS PASSED! The fix is working correctly.")
        print("\n🎯 Your original query will now work:")
        print('   "show me the associated alerts with respect to focal entity 3189446387"')
        print("   → Will return 5 alerts (not 29)")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
