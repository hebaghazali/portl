"""
Pytest configuration file.
"""

import pytest
import psycopg2
import os


@pytest.fixture(scope="session")
def postgres_connection():
    """
    Provide a Postgres connection for integration tests.
    
    Requires docker-compose.test.yml to be running:
        docker-compose -f docker-compose.test.yml up -d
    """
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        database=os.getenv("POSTGRES_DB", "portl_test"),
        user=os.getenv("POSTGRES_USER", "portl_test"),
        password=os.getenv("POSTGRES_PASSWORD", "portl_test")
    )
    
    # Set autocommit off - we want explicit transaction control
    conn.autocommit = False
    
    yield conn
    
    conn.close()


@pytest.fixture
def clean_db(postgres_connection):
    """
    Clean database before each test.
    
    Truncates all test tables and resets sequences.
    """
    cursor = postgres_connection.cursor()
    
    # Truncate tables (CASCADE removes dependent rows)
    cursor.execute("""
        TRUNCATE TABLE orders, inventory, portl_outbox, audit_log CASCADE;
    """)
    
    # Reset inventory to known state
    cursor.execute("""
        INSERT INTO inventory (sku, quantity, reserved) VALUES 
            ('WIDGET-001', 100, 0),
            ('WIDGET-002', 50, 0),
            ('WIDGET-003', 25, 0)
        ON CONFLICT (sku) DO UPDATE 
        SET quantity = EXCLUDED.quantity, reserved = 0;
    """)
    
    postgres_connection.commit()
    cursor.close()
    
    yield
    
    # Rollback any uncommitted changes after test
    postgres_connection.rollback()
