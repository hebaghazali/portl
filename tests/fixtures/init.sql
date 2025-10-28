-- Portl test database initialization
-- Creates tables for integration tests

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Outbox table for transactional event delivery
CREATE TABLE IF NOT EXISTS portl_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id VARCHAR(255) NOT NULL,
    step_id VARCHAR(255) NOT NULL,
    delivery_type VARCHAR(50) NOT NULL,         -- 'api.call' | 'lambda.invoke'
    payload JSONB NOT NULL,
    idempotency_key VARCHAR(255) UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending|delivered|failed|dead_letter
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ,
    retry_count INT NOT NULL DEFAULT 0,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_outbox_pending 
ON portl_outbox(status, created_at) 
WHERE status = 'pending';

-- Test tables for DB executors
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inventory (
    sku VARCHAR(255) PRIMARY KEY,
    quantity INT NOT NULL DEFAULT 0,
    reserved INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sample test data
INSERT INTO inventory (sku, quantity) VALUES 
    ('WIDGET-001', 100),
    ('WIDGET-002', 50),
    ('WIDGET-003', 25)
ON CONFLICT (sku) DO NOTHING;

-- Audit log for testing compensation
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id VARCHAR(255) NOT NULL,
    step_id VARCHAR(255) NOT NULL,
    action VARCHAR(255) NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

