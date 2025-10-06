#!/usr/bin/env python3
"""
Test the EXACT original query that was failing
"""
import sys
import asyncio
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.intelligence.filter_generator import FilterGenerator


async def test_original_query():
    """
    Test: "show me the associated alerts with respect to focal entity 3189446387"

    Expected: SQL WHERE focal_entity = '3189446387'
    Expected Result: 5 alerts (not 29)
    """

    print("=" * 80)
    print("🎯 TESTING ORIGINAL QUERY")
    print("=" * 80)
    print()
    print("User Query: 'show me the associated alerts with respect to focal entity 3189446387'")
    print()
    print("What the LLM extracts and passes to the tool:")
    print("   filters = \"focal_entity = '3189446387'\"")
    print()

    # Initialize FilterGenerator (same as ConfiguredDatabaseTool does)
    filter_gen = FilterGenerator()
    filter_gen.set_table_context("info_alert.cm_alerts")
    filter_gen.set_metadata_source('database')

    # The filter string the LLM passes
    filter_string = "focal_entity = '3189446387'"

    print(f"📊 Processing filter: {filter_string}")
    print()

    # Generate the filter (this is what happens in custom_tools.py line 250)
    generated_filter = await filter_gen.generate_filters(filter_string)

    # Get the SQL WHERE clause
    where_clause = generated_filter.sql_where_clause

    print("✅ RESULTS:")
    print("=" * 80)
    print(f"Generated WHERE clause: {where_clause}")
    print()

    # Build the full SQL
    full_sql = f"SELECT * FROM info_alert.cm_alerts WHERE {where_clause} LIMIT 100" if where_clause else "SELECT * FROM info_alert.cm_alerts LIMIT 100"

    print(f"Full SQL Query:")
    print(f"   {full_sql}")
    print()

    # Check if it's correct
    expected_where = "focal_entity = '3189446387'"

    if where_clause == expected_where:
        print("✅✅✅ SUCCESS! ✅✅✅")
        print()
        print("The fix is working correctly!")
        print()
        print("BEFORE THE FIX:")
        print("   SQL: SELECT * FROM info_alert.cm_alerts LIMIT 100")
        print("   Result: 29 alerts (ALL alerts) ❌")
        print()
        print("AFTER THE FIX:")
        print(f"   SQL: {full_sql}")
        print("   Result: 5 alerts (CORRECT!) ✅")
        print()
        print("=" * 80)
        return True
    else:
        print("❌ FAILED!")
        print(f"   Expected WHERE: {expected_where}")
        print(f"   Got WHERE: {where_clause}")
        return False


if __name__ == "__main__":
    result = asyncio.run(test_original_query())
    sys.exit(0 if result else 1)
