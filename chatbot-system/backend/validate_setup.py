#!/usr/bin/env python3
"""
Validation script to check if all SOAP and Database configurations are ready
"""
import sys
import os
from pathlib import Path

# Add the current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_yaml_validity():
    """Test if YAML files are valid"""
    print("=" * 60)
    print("TEST 1: YAML File Validity")
    print("=" * 60)

    try:
        import yaml

        # Test SOAP endpoints YAML
        soap_path = Path(__file__).parent / "config" / "soap_endpoints.yaml"
        print(f"\n✓ Checking: {soap_path}")
        if not soap_path.exists():
            print(f"  ✗ File not found!")
            return False

        with open(soap_path) as f:
            soap_config = yaml.safe_load(f)
        print(f"  ✓ Valid YAML")
        print(f"  ✓ Found {len(soap_config.get('soap_endpoints', []))} SOAP endpoints")

        # Test Database schemas YAML
        db_path = Path(__file__).parent / "config" / "database_schemas.yaml"
        print(f"\n✓ Checking: {db_path}")
        if not db_path.exists():
            print(f"  ✗ File not found!")
            return False

        with open(db_path) as f:
            db_config = yaml.safe_load(f)
        print(f"  ✓ Valid YAML")
        print(f"  ✓ Found {len(db_config.get('databases', {}))} database configurations")

        # Test REST endpoints YAML
        rest_path = Path(__file__).parent / "app" / "config" / "api_endpoints.yaml"
        print(f"\n✓ Checking: {rest_path}")
        if not rest_path.exists():
            print(f"  ✗ File not found!")
            return False

        with open(rest_path) as f:
            rest_config = yaml.safe_load(f)
        print(f"  ✓ Valid YAML")
        print(f"  ✓ Found {len(rest_config.get('endpoints', []))} REST endpoints")

        return True

    except Exception as e:
        print(f"\n✗ YAML validation failed: {e}")
        return False


def test_imports():
    """Test if all Python modules can be imported"""
    print("\n" + "=" * 60)
    print("TEST 2: Python Module Imports")
    print("=" * 60)

    try:
        print("\n✓ Testing SOAP endpoint loader...")
        from app.config.soap_endpoint_loader import (
            SOAPEndpointLoader,
            SOAPEndpointDefinition,
            get_soap_endpoint_loader
        )
        print("  ✓ SOAP endpoint loader imports OK")

        print("\n✓ Testing database schema loader...")
        from app.config.database_schema_loader import (
            DatabaseSchemaLoader,
            TableDefinition,
            get_database_schema_loader
        )
        print("  ✓ Database schema loader imports OK")

        print("\n✓ Testing tool initializer...")
        from app.intelligence.tool_initializer import ToolInitializer
        print("  ✓ Tool initializer imports OK")

        print("\n✓ Testing config package...")
        from app.config import (
            get_soap_endpoint_loader,
            get_database_schema_loader,
            get_endpoint_loader
        )
        print("  ✓ Config package imports OK")

        return True

    except Exception as e:
        print(f"\n✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_loaders():
    """Test if loaders can instantiate and load configurations"""
    print("\n" + "=" * 60)
    print("TEST 3: Configuration Loaders")
    print("=" * 60)

    try:
        from app.config import (
            get_soap_endpoint_loader,
            get_database_schema_loader,
            get_endpoint_loader
        )

        # Test REST endpoint loader
        print("\n✓ Testing REST endpoint loader...")
        rest_loader = get_endpoint_loader()
        rest_endpoints = rest_loader.get_all_endpoints()
        print(f"  ✓ Loaded {len(rest_endpoints)} REST endpoints")
        for ep in rest_endpoints[:3]:
            print(f"    - {ep.name}: {ep.description[:50]}...")

        # Test SOAP endpoint loader
        print("\n✓ Testing SOAP endpoint loader...")
        soap_loader = get_soap_endpoint_loader()
        soap_endpoints = soap_loader.get_all_endpoints()
        print(f"  ✓ Loaded {len(soap_endpoints)} SOAP endpoints")
        for ep in soap_endpoints:
            print(f"    - {ep.name} ({ep.operation}): {ep.description[:50]}...")

        # Test database schema loader
        print("\n✓ Testing database schema loader...")
        db_loader = get_database_schema_loader()
        all_dbs = db_loader.get_all_databases()
        print(f"  ✓ Loaded {len(all_dbs)} database configurations")

        for db_type, db_config in all_dbs.items():
            print(f"\n  Database: {db_type}")
            print(f"    Tables: {len(db_config.tables)}")
            for table in db_config.tables[:3]:
                print(f"      - {table.name}: {table.description[:50]}...")

        return True

    except Exception as e:
        print(f"\n✗ Loader test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_initializer():
    """Test if tool initializer can be instantiated"""
    print("\n" + "=" * 60)
    print("TEST 4: Tool Initializer")
    print("=" * 60)

    try:
        from app.intelligence.tool_registry import ToolRegistry
        from app.intelligence.tool_initializer import ToolInitializer

        print("\n✓ Creating tool registry...")
        registry = ToolRegistry()
        print("  ✓ Tool registry created")

        print("\n✓ Creating tool initializer...")
        initializer = ToolInitializer(
            tool_registry=registry,
            embeddings=None,
            config_path=None
        )
        print("  ✓ Tool initializer created")
        print(f"  ✓ Config path: {initializer.config_path}")

        return True

    except Exception as e:
        print(f"\n✗ Tool initializer test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validation tests"""
    print("\n" + "=" * 60)
    print("SOAP & DATABASE CONFIGURATION VALIDATION")
    print("=" * 60)

    results = []

    # Run all tests
    results.append(("YAML Validity", test_yaml_validity()))
    results.append(("Python Imports", test_imports()))
    results.append(("Configuration Loaders", test_loaders()))
    results.append(("Tool Initializer", test_tool_initializer()))

    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:8} - {test_name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED - Ready to start service!")
    else:
        print("✗ SOME TESTS FAILED - Fix issues before starting")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
