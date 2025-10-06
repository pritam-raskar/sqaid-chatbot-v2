"""
Test PostgreSQL connection with schema-qualified table names
"""
import asyncio
import os
from dotenv import load_dotenv
from app.data_access.adapters.postgresql_adapter import PostgreSQLAdapter

# Load environment variables
load_dotenv()

async def test_connection():
    """Test PostgreSQL connection with schema-qualified table name"""

    # Get connection parameters from environment
    config = {
        'host': os.getenv('POSTGRES_HOST'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'db': os.getenv('POSTGRES_DB'),  # Use 'db' instead of 'database' per adapter code
        'user': os.getenv('POSTGRES_USER'),
        'password': os.getenv('POSTGRES_PASSWORD')
    }

    print("=" * 60)
    print("Testing PostgreSQL Connection with Schema-Qualified Names")
    print("=" * 60)
    print(f"Host: {config['host']}")
    print(f"Database: {config['db']}")
    print(f"User: {config['user']}")
    print()

    # Create adapter with config
    adapter = PostgreSQLAdapter(config=config)

    try:
        # Connect to database
        print("Connecting to PostgreSQL...")
        await adapter.connect()
        print("✓ Connected successfully!")
        print()

        # Test 1: Query with schema-qualified table name (info_alert.cm_alerts)
        print("Test 1: Querying info_alert.cm_alerts table")
        print("-" * 60)
        query = "SELECT * FROM info_alert.cm_alerts LIMIT 5"
        print(f"Query: {query}")
        results = await adapter.execute_query(query)
        print(f"✓ Query successful! Retrieved {len(results)} rows")
        if results:
            print(f"  Columns: {list(results[0].keys())}")
        print()

        # Test 2: Get table info for schema-qualified table
        print("Test 2: Getting table info for info_alert.cm_alerts")
        print("-" * 60)
        table_info = await adapter.get_table_info("info_alert.cm_alerts")
        print(f"✓ Table info retrieved!")
        print(f"  Table: {table_info.get('table_name')}")
        print(f"  Schema: {table_info.get('schema_name', 'N/A')}")
        print(f"  Columns: {len(table_info.get('columns', []))}")
        if table_info.get('columns'):
            print(f"  Sample columns: {', '.join([col['name'] for col in table_info['columns'][:5]])}")
        print()

        # Test 3: Query cm_users table
        print("Test 3: Querying info_alert.cm_users table")
        print("-" * 60)
        query = "SELECT * FROM info_alert.cm_users LIMIT 3"
        print(f"Query: {query}")
        results = await adapter.execute_query(query)
        print(f"✓ Query successful! Retrieved {len(results)} rows")
        if results:
            print(f"  Columns: {list(results[0].keys())}")
        print()

        print("=" * 60)
        print("✓ All tests passed! Schema-qualified tables work correctly.")
        print("=" * 60)

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Disconnect
        await adapter.disconnect()
        print("\nDisconnected from PostgreSQL")

if __name__ == "__main__":
    asyncio.run(test_connection())
