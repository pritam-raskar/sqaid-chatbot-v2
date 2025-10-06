"""
Data adapters re-export module
Provides convenient imports for data adapters from tools
"""
from app.data_access.adapters.postgresql_adapter import PostgreSQLAdapter
from app.data_access.adapters.rest_adapter import RESTAdapter
from app.data.soap_adapter import SOAPAdapter

# Also create convenience aliases
postgres_adapter = PostgreSQLAdapter
rest_adapter = RESTAdapter
soap_adapter = SOAPAdapter

__all__ = [
    'PostgreSQLAdapter',
    'RESTAdapter',
    'SOAPAdapter',
    'postgres_adapter',
    'rest_adapter',
    'soap_adapter'
]
