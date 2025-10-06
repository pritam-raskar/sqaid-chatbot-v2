#!/usr/bin/env python3
"""
PostgreSQL Schema to YAML Configuration Generator
Reads database configuration from .env file
Uses REAL database metadata only - never generates imaginary columns
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import yaml
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv


class InlineListDumper(yaml.SafeDumper):
    """Custom YAML dumper that formats lists inline"""
    pass

def represent_list(dumper, data):
    """Represent lists in flow style (inline)"""
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

# Register the custom list representer
InlineListDumper.add_representer(list, represent_list)


class RealPostgresSchemaAnalyzer:
    """
    Analyzes PostgreSQL schema using ONLY actual database metadata.
    Never generates imaginary columns or structure.
    """
    
    def __init__(self, host: str, database: str, user: str, password: str, port: int = 5432):
        """Initialize database connection"""
        try:
            print(f"Connecting to {database} at {host}:{port}...")
            self.conn = psycopg2.connect(
                host=host,
                database=database,
                user=user,
                password=password,
                port=port,
                connect_timeout=10
            )
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            print(f"✓ Connected to database: {database}")
        except Exception as e:
            print(f"✗ Failed to connect to database: {e}")
            sys.exit(1)
    
    def test_connection(self) -> bool:
        """Test if we can query the database"""
        try:
            self.cursor.execute("SELECT 1")
            return True
        except Exception as e:
            print(f"✗ Database connection test failed: {e}")
            return False
    
    def get_tables_and_views(self, schema: str) -> List[Dict[str, Any]]:
        """Get all tables and views in the schema - REAL DATA ONLY"""
        query = """
            SELECT 
                table_name,
                table_type
            FROM information_schema.tables
            WHERE table_schema = %s
            AND table_type IN ('BASE TABLE', 'VIEW')
            ORDER BY table_name;
        """
        try:
            self.cursor.execute(query, (schema,))
            results = self.cursor.fetchall()
            print(f"✓ Found {len(results)} tables/views in schema '{schema}'")
            return results
        except Exception as e:
            print(f"✗ Failed to get tables: {e}")
            return []
    
    def get_columns(self, schema: str, table: str) -> List[Dict[str, Any]]:
        """Get REAL columns for a table with their actual metadata"""
        query = """
            SELECT 
                c.column_name,
                c.data_type,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                c.is_nullable,
                c.column_default,
                c.udt_name,
                col_description((quote_ident(c.table_schema)||'.'||quote_ident(c.table_name))::regclass, c.ordinal_position) as column_comment
            FROM information_schema.columns c
            WHERE c.table_schema = %s
            AND c.table_name = %s
            ORDER BY c.ordinal_position;
        """
        try:
            self.cursor.execute(query, (schema, table))
            return self.cursor.fetchall()
        except Exception as e:
            print(f"  ✗ Failed to get columns for {table}: {e}")
            return []
    
    def get_enum_values(self, udt_name: str) -> Optional[List[str]]:
        """Get actual enum values from database"""
        query = """
            SELECT e.enumlabel
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = %s
            ORDER BY e.enumsortorder;
        """
        try:
            self.cursor.execute(query, (udt_name,))
            results = self.cursor.fetchall()
            if results:
                return [r['enumlabel'] for r in results]
        except Exception as e:
            pass
        return None
    
    def get_primary_key(self, schema: str, table: str) -> Optional[str]:
        """Get REAL primary key column(s) for a table"""
        query = """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = (quote_ident(%s)||'.'||quote_ident(%s))::regclass
            AND i.indisprimary
            ORDER BY a.attnum;
        """
        try:
            self.cursor.execute(query, (schema, table))
            results = self.cursor.fetchall()
            if results:
                return results[0]['attname'] if len(results) == 1 else ','.join([r['attname'] for r in results])
        except Exception as e:
            pass
        return None
    
    def get_foreign_keys(self, schema: str, table: str) -> List[Dict[str, Any]]:
        """Get REAL foreign key relationships"""
        query = """
            SELECT
                kcu.column_name,
                ccu.table_schema AS foreign_table_schema,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                tc.constraint_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = %s
            AND tc.table_name = %s;
        """
        try:
            self.cursor.execute(query, (schema, table))
            return self.cursor.fetchall()
        except Exception as e:
            return []
    
    def get_referenced_by(self, schema: str, table: str) -> List[Dict[str, Any]]:
        """Get tables that reference this table via foreign keys"""
        query = """
            SELECT DISTINCT
                tc.table_schema,
                tc.table_name,
                kcu.column_name,
                ccu.column_name AS referenced_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND ccu.table_schema = %s
            AND ccu.table_name = %s;
        """
        try:
            self.cursor.execute(query, (schema, table))
            return self.cursor.fetchall()
        except Exception as e:
            return []
    
    def generate_keywords_from_actual_data(self, table_name: str, columns: List[Dict]) -> List[str]:
        """Generate keywords based on REAL column names and table name"""
        keywords = set()
        
        # Add table name parts
        table_lower = table_name.lower().replace('cm_', '').replace('_', ' ')
        keywords.update(table_lower.split())
        
        # Add keywords based on actual column names and table context
        table_lower_full = table_name.lower()
        
        if 'alert' in table_lower_full:
            keywords.update(['alert', 'notification', 'warning', 'incident', 'event', 'trigger'])
            if 'type' in table_lower_full:
                keywords.update(['alarm', 'message', 'severity', 'category', 'classification'])
            else:
                keywords.update(['alarm', 'message', 'severity', 'emergency'])
        
        if 'case' in table_lower_full:
            keywords.update(['case', 'ticket', 'issue', 'problem', 'support', 'request', 'incident'])
            if not 'alert' in table_lower_full:
                keywords.update(['service request', 'bug', 'task', 'work item', 'assignment'])
        
        if 'user' in table_lower_full and 'role' not in table_lower_full:
            keywords.update(['user', 'person', 'employee', 'member', 'account', 'profile', 'team', 'people', 'staff', 'operator', 'admin', 'contact', 'assignee'])
        
        if 'role' in table_lower_full:
            if 'mapping' in table_lower_full or 'user' in table_lower_full:
                keywords.update(['user role', 'role mapping', 'role assignment', 'permission', 'access', 'user access', 'role membership', 'authorization', 'user permission'])
            else:
                keywords.update(['role', 'permission', 'access level', 'user role', 'security role', 'access rights', 'privileges', 'authorization', 'admin', 'operator', 'viewer'])
        
        if 'type' in table_lower_full:
            keywords.update(['type', 'category', 'classification'])
        
        # Add from column names
        for col in columns:
            col_name = col['column_name'].lower()
            if 'status' in col_name:
                keywords.add('status')
            if 'priority' in col_name:
                keywords.add('priority')
            if 'workflow' in col_name:
                keywords.add('workflow')
            if 'step' in col_name:
                keywords.add('step')
        
        return sorted(list(keywords))
    
    def generate_description_from_actual_data(self, table_name: str, columns: List[Dict]) -> str:
        """Generate description based on REAL table structure"""
        col_names = {col['column_name'].lower() for col in columns}
        table_lower = table_name.lower()
        
        # cm_alerts
        if table_name == 'cm_alerts':
            return "Alert records, system notifications, incident alerts, warning messages, and triggered events. This table stores all alert instances generated by the system including their status, severity, timestamps, and associated metadata. Use this when user asks about alerts, notifications, warnings, incidents, triggered events, alert history, or active alerts."
        
        # cm_alert_type
        elif table_name == 'cm_alert_type':
            return "Alert type definitions, alert categories, alert classifications, and alert configuration templates. This lookup table defines different types of alerts in the system including their properties, default severity levels, escalation rules, and notification settings. Use this when user asks about alert types, alert categories, alert classifications, types of alerts available, alert configurations, or what kinds of alerts exist in the system."
        
        # cm_case
        elif table_name == 'cm_case':
            return "Case management records, support tickets, issue tracking, problem reports, service requests, and incident cases. This table contains all case lifecycle information including status, priority, assignments, resolution details, and case history. Use this when user asks about cases, tickets, issues, problems, support requests, case status, open cases, resolved cases, case assignments, or case history."
        
        # cm_users
        elif table_name == 'cm_users':
            return "User accounts, system users, team members, employees, operators, administrators, and user profiles. This table stores all user information including authentication details, contact information, user preferences, and account status. Use this when user asks about users, people, team members, employees, operators, user accounts, user profiles, user information, who is assigned, contact details, or staff information."
        
        # cm_roles
        elif table_name == 'cm_roles':
            return "Role definitions, user roles, permission groups, access levels, and security roles. This table defines all available roles in the system including their permissions, access rights, responsibilities, and role hierarchy. Use this when user asks about roles, permissions, access levels, user types, role definitions, what roles exist, role permissions, or security groups."
        
        # cm_user_roles_mapping
        elif table_name == 'cm_user_roles_mapping':
            return "User-role relationship mapping, role assignments, user permissions mapping, and access control associations. This junction table manages the many-to-many relationship between users and roles, allowing users to have multiple roles and roles to be assigned to multiple users. Use this when user asks about user roles, role assignments, who has what role, user permissions, access levels, role membership, or user-role relationships."
        
        # Generic descriptions for other tables
        elif 'workflow' in table_lower:
            return f"Workflow configuration and management. Contains workflow definitions, steps, transitions, and execution tracking. Use this when querying workflow information, process flows, or workflow execution status."
        
        elif 'step' in table_lower:
            return f"Workflow step definitions and execution tracking. Contains information about individual steps in workflows including their status, assignments, and completion details. Use this when querying workflow steps or process stages."
        
        elif 'mapping' in table_lower or 'junction' in table_lower:
            entities = table_name.replace('cm_', '').replace('_mapping', '').replace('_', ' and ')
            return f"Relationship mapping table managing associations between {entities}. This junction table enables many-to-many relationships. Use this for queries about {entities} relationships and associations."
        
        elif 'type' in table_lower or 'category' in table_lower:
            entity = table_name.replace('cm_', '').replace('_type', '').replace('_', ' ')
            return f"Type definitions and categories for {entity}. This lookup table contains classification and configuration data. Use this when querying {entity} types, categories, or classifications."
        
        elif 'audit' in table_lower or 'log' in table_lower:
            return f"Audit trail and logging records. Tracks changes, actions, and events in the system for compliance and tracking purposes. Use this when querying system activity, change history, or audit information."
        
        else:
            entity = table_name.replace('cm_', '').replace('_', ' ')
            return f"Data table for {entity}. Contains {len(columns)} columns of information related to {entity}. Use this when querying {entity} information."
    
    def generate_column_description(self, table_name: str, column_name: str, data_type: str, column_comment: Optional[str]) -> str:
        """Generate detailed description for a column"""
        if column_comment:
            return column_comment
        
        col_lower = column_name.lower()
        table_lower = table_name.lower()
        
        # ID fields
        if col_lower == 'id':
            return f"Unique identifier for the {table_name.replace('cm_', '').replace('_', ' ')} record"
        elif col_lower.endswith('_id'):
            ref_entity = col_lower.replace('_id', '').replace('_', ' ')
            if col_lower == 'alert_id' and 'alert' in table_lower:
                return "Unique identifier for the alert"
            elif col_lower == 'case_id' and 'case' in table_lower:
                return "Unique identifier for the case"
            elif col_lower == 'user_id' and 'user' in table_lower:
                return "Unique identifier for the user"
            elif col_lower == 'role_id' and 'role' in table_lower:
                return "Unique identifier for the role"
            elif 'type' in col_lower:
                return f"Foreign key reference to {ref_entity} definition"
            elif col_lower == 'owner_id':
                return "User ID of the owner or person responsible"
            elif col_lower == 'created_by':
                return "User ID of the person who created this record"
            elif col_lower == 'updated_by':
                return "User ID of the person who last updated this record"
            elif col_lower == 'assigned_to':
                return "User ID of the person assigned to this item"
            else:
                return f"Foreign key reference to {ref_entity}"
        
        # Name fields
        elif col_lower.endswith('_name'):
            entity = col_lower.replace('_name', '').replace('_', ' ')
            return f"Name of the {entity}"
        elif col_lower == 'name':
            return "Name"
        
        # Code/identifier fields
        elif col_lower.endswith('_code') or col_lower.endswith('_slug'):
            entity = col_lower.replace('_code', '').replace('_slug', '').replace('_', ' ')
            return f"Unique code or identifier for the {entity}"
        
        # Number/count fields
        elif col_lower.endswith('_number'):
            entity = col_lower.replace('_number', '').replace('_', ' ')
            return f"Human-readable {entity} number"
        
        # Status and state
        elif col_lower == 'status':
            return f"Current status of the {table_name.replace('cm_', '').replace('_', ' ')} in its lifecycle"
        elif col_lower == 'priority':
            return "Priority level indicating urgency"
        elif col_lower == 'severity':
            return "Severity level indicating impact"
        
        # Scores
        elif 'score' in col_lower:
            return "Calculated risk or relevance score"
        
        # Boolean flags
        elif col_lower.startswith('is_'):
            condition = col_lower.replace('is_', '').replace('_', ' ')
            return f"Flag indicating whether {condition}"
        elif col_lower.startswith('has_'):
            condition = col_lower.replace('has_', '').replace('_', ' ')
            return f"Flag indicating if it has {condition}"
        
        # Timestamps
        elif col_lower == 'created_at':
            return "Timestamp when the record was created"
        elif col_lower == 'updated_at':
            return "Timestamp of the last update to the record"
        elif col_lower == 'deleted_at':
            return "Timestamp when the record was soft deleted"
        elif col_lower.endswith('_at'):
            event = col_lower.replace('_at', '').replace('_', ' ')
            return f"Timestamp when {event}"
        elif col_lower.endswith('_date'):
            event = col_lower.replace('_date', '').replace('_', ' ')
            return f"Date for {event}"
        
        # Description and details
        elif col_lower == 'description':
            return "Detailed description"
        elif col_lower == 'details':
            return "Additional details and information"
        elif col_lower == 'notes':
            return "Additional notes or comments"
        elif col_lower == 'resolution':
            return "Description of how the issue was resolved"
        
        # Contact information
        elif 'email' in col_lower:
            return "Email address"
        elif 'phone' in col_lower:
            return "Phone number"
        elif 'address' in col_lower:
            return "Address information"
        
        # Organization/hierarchy
        elif col_lower.startswith('org_'):
            entity = col_lower.replace('org_', '').replace('_', ' ')
            return f"Organization {entity}"
        elif 'branch' in col_lower:
            return "Branch identifier or information"
        elif 'department' in col_lower:
            return "Department information"
        
        # Workflow related
        elif 'workflow' in col_lower:
            return "Workflow identifier or information"
        elif 'step' in col_lower:
            return "Workflow step identifier or information"
        elif 'transition' in col_lower:
            return "Workflow transition information"
        
        # JSON/complex fields
        elif data_type in ['jsonb', 'json']:
            entity = col_lower.replace('_', ' ')
            return f"JSON object containing {entity}"
        
        # Default
        else:
            return f"{column_name.replace('_', ' ').title()}"
    
    def map_postgres_type(self, col: Dict) -> Dict[str, Any]:
        """Map PostgreSQL type to YAML format using REAL data"""
        pg_type = col['data_type']
        udt_name = col['udt_name']
        
        # Check if it's an enum
        enum_values = None
        if pg_type == 'USER-DEFINED':
            enum_values = self.get_enum_values(udt_name)
        
        if enum_values:
            return {
                'type': 'enum',
                'possible_values': enum_values,
                'case_sensitive': False
            }
        
        # Map standard types
        type_map = {
            'bigint': 'integer',
            'integer': 'integer',
            'smallint': 'integer',
            'character varying': 'varchar',
            'text': 'text',
            'boolean': 'boolean',
            'numeric': 'numeric',
            'double precision': 'numeric',
            'real': 'numeric',
            'timestamp without time zone': 'timestamp',
            'timestamp with time zone': 'timestamp',
            'date': 'date',
            'time': 'time',
            'jsonb': 'jsonb',
            'json': 'json',
            'uuid': 'uuid'
        }
        
        return {'type': type_map.get(pg_type, pg_type)}
    
    def generate_yaml_config(self, schema: str, table_filter: List[str] = None, output_file: str = None) -> Dict:
        """Generate YAML config using ONLY real database data"""
        
        if not self.test_connection():
            print("Cannot proceed without database connection")
            return {}
        
        print(f"\n=== Analyzing schema: {schema} ===\n")
        
        tables_data = self.get_tables_and_views(schema)
        
        if not tables_data:
            print(f"✗ No tables found in schema '{schema}'")
            return {}
        
        # Filter tables if specified
        if table_filter:
            tables_data = [t for t in tables_data if t['table_name'] in table_filter]
            print(f"✓ Filtered to {len(tables_data)} tables: {', '.join(table_filter)}\n")
        
        config = {'tables': []}
        
        for table_info in tables_data:
            table_name = table_info['table_name']
            print(f"Processing: {table_name}")
            
            # Get REAL columns
            columns = self.get_columns(schema, table_name)
            if not columns:
                print(f"  ✗ No columns found, skipping table\n")
                continue
            
            print(f"  ✓ Found {len(columns)} columns")
            
            # Get REAL relationships
            primary_key = self.get_primary_key(schema, table_name)
            foreign_keys = self.get_foreign_keys(schema, table_name)
            referenced_by = self.get_referenced_by(schema, table_name)
            
            # Build searchable columns from REAL column names
            searchable_columns = [col['column_name'] for col in columns]
            
            # Build common joins from REAL foreign keys
            common_joins = []
            for fk in foreign_keys:
                common_joins.append({
                    'table': fk['foreign_table_name'],
                    'schema': fk['foreign_table_schema'],
                    'join_on': f"{fk['column_name']} = {fk['foreign_column_name']}",
                    'description': f"Join with {fk['foreign_table_name'].replace('cm_', '').replace('_', ' ')} to get related information"
                })
            
            for ref in referenced_by:
                common_joins.append({
                    'table': ref['table_name'],
                    'schema': ref['table_schema'],
                    'join_on': f"{ref['referenced_column_name']} = {ref['column_name']}",
                    'description': f"Join with {ref['table_name'].replace('cm_', '').replace('_', ' ')} to get related records"
                })
            
            # Build column metadata from REAL columns - MATCHING EXACT FORMAT
            column_metadata = {}
            for col in columns:
                col_meta = {}
                
                # Type first (matching your format)
                type_info = self.map_postgres_type(col)
                col_meta['type'] = type_info['type']
                
                # Description second
                col_meta['description'] = self.generate_column_description(
                    table_name,
                    col['column_name'],
                    col['data_type'],
                    col['column_comment']
                )
                
                # Then nullable
                col_meta['nullable'] = col['is_nullable'] == 'YES'
                
                # Add enum values if exists
                if 'possible_values' in type_info:
                    col_meta['possible_values'] = type_info['possible_values']
                    col_meta['case_sensitive'] = type_info['case_sensitive']
                
                # Add max length for varchar
                if col['character_maximum_length']:
                    col_meta['max_length'] = col['character_maximum_length']
                
                # Add range for numeric if it looks like a score
                if col['data_type'] in ['numeric', 'double precision'] and 'score' in col['column_name'].lower():
                    col_meta['range'] = [0, 1000]
                
                column_metadata[col['column_name']] = col_meta
            
            # Build table config in exact order
            table_config = {
                'name': table_name,
                'schema': schema,
                'description': self.generate_description_from_actual_data(table_name, columns),
                'keywords': self.generate_keywords_from_actual_data(table_name, columns),
            }
            
            # Add primary key if exists
            if primary_key:
                table_config['primary_key'] = primary_key
            
            # Add searchable columns
            table_config['searchable_columns'] = searchable_columns
            
            # Add common joins if any
            if common_joins:
                table_config['common_joins'] = common_joins
            
            # Add column metadata
            table_config['column_metadata'] = column_metadata
            
            config['tables'].append(table_config)
            print(f"  ✓ Configuration generated\n")
        
        # Write to file if specified
        if output_file:
            try:
                with open(output_file, 'w') as f:
                    yaml.dump(config, f, Dumper=InlineListDumper, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120)
                print(f"✓ Configuration written to: {output_file}")
            except Exception as e:
                print(f"✗ Failed to write file: {e}")
        
        return config
    
    def close(self):
        """Close database connection"""
        try:
            self.cursor.close()
            self.conn.close()
            print("\n✓ Database connection closed")
        except Exception as e:
            print(f"✗ Error closing connection: {e}")


def load_env_config() -> Dict[str, Any]:
    """Load database configuration from .env file"""
    # Try to find .env file in project root
    current_dir = Path(__file__).resolve().parent
    
    # Go up directories to find .env file
    env_paths = [
        current_dir / '.env',  # Same directory
        current_dir.parent / '.env',  # Parent directory (utilities -> backend)
        current_dir.parent.parent / '.env',  # Two levels up (backend -> chatbot-system)
        Path.cwd() / '.env',  # Current working directory
    ]
    
    env_file = None
    for path in env_paths:
        if path.exists():
            env_file = path
            break
    
    if env_file:
        print(f"✓ Found .env file at: {env_file}")
        load_dotenv(env_file)
    else:
        print("⚠ No .env file found, will try environment variables")
        load_dotenv()  # Try to load from environment
    
    # Read configuration
    config = {
        'host': os.getenv('POSTGRES_HOST'),
        'port': int(os.getenv('POSTGRES_PORT', '5432')),
        'database': os.getenv('POSTGRES_DB'),
        'user': os.getenv('POSTGRES_USER'),
        'password': os.getenv('POSTGRES_PASSWORD'),
    }
    
    # Validate configuration
    missing = [k for k, v in config.items() if v is None]
    if missing:
        print(f"✗ Missing environment variables: {', '.join(missing)}")
        print("\nRequired environment variables:")
        print("  - POSTGRES_HOST")
        print("  - POSTGRES_PORT")
        print("  - POSTGRES_DB")
        print("  - POSTGRES_USER")
        print("  - POSTGRES_PASSWORD")
        sys.exit(1)
    
    return config


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate YAML configuration from REAL PostgreSQL schema metadata (reads from .env)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Database connection is read from .env file with these variables:
  POSTGRES_HOST
  POSTGRES_PORT
  POSTGRES_DB
  POSTGRES_USER
  POSTGRES_PASSWORD

Examples:
  # Generate for all tables in info_alert schema
  python postgre_real_schema_analyzer.py --schema info_alert --output config.yaml
  
  # Generate for specific tables only
  python postgre_real_schema_analyzer.py --schema info_alert --tables cm_alerts cm_case cm_users --output config.yaml
        '''
    )
    
    parser.add_argument('--schema', default='info_alert', help='Schema name to analyze (default: info_alert)')
    parser.add_argument('--tables', nargs='+', help='Specific tables to include (optional, analyzes all if not specified)')
    parser.add_argument('--output', default='schema_config.yaml', help='Output YAML file (default: schema_config.yaml)')
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print("PostgreSQL Schema to YAML Configuration Generator")
    print("Using REAL database metadata only")
    print(f"{'='*60}\n")
    
    try:
        # Load configuration from .env
        db_config = load_env_config()
        
        print(f"Database: {db_config['database']}")
        print(f"Host: {db_config['host']}")
        print(f"Port: {db_config['port']}")
        print(f"User: {db_config['user']}\n")
        
        analyzer = RealPostgresSchemaAnalyzer(
            host=db_config['host'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password'],
            port=db_config['port']
        )
        
        config = analyzer.generate_yaml_config(
            schema=args.schema,
            table_filter=args.tables,
            output_file=args.output
        )
        
        print(f"\n{'='*60}")
        print("Summary:")
        print(f"{'='*60}")
        print(f"Tables processed: {len(config.get('tables', []))}")
        for table in config.get('tables', []):
            print(f"  • {table['name']}: {len(table['column_metadata'])} columns")
        print(f"{'='*60}\n")
        
        analyzer.close()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()