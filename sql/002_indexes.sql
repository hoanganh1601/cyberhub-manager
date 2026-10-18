-- CYB-6 / HA-02 - Indexes for CyberHub Manager.
-- Target database: MySQL 8.4.
-- Run after 001_initial_schema.sql.

-- Customers: search and sort by full name.
CREATE INDEX idx_customers_full_name
    ON customers (full_name);

-- Employees: filter by store and status.
CREATE INDEX idx_employees_store_status
    ON employees (store_id, status);

-- Machines: dashboard filters by store, archive flag and status.
CREATE INDEX idx_machines_store_active_status
    ON machines (store_id, is_active, status);

-- Usage sessions: machine history.
CREATE INDEX idx_usage_sessions_machine_started_at
    ON usage_sessions (machine_id, started_at);

-- Usage sessions: customer history.
CREATE INDEX idx_usage_sessions_customer_started_at
    ON usage_sessions (customer_id, started_at);

-- Usage sessions: filter by status and start time.
CREATE INDEX idx_usage_sessions_status_started_at
    ON usage_sessions (status, started_at);

-- Account transactions: account balance history.
CREATE INDEX idx_account_transactions_account_created_at
    ON account_transactions (account_id, created_at);

-- Invoices: revenue by store, status and date.
CREATE INDEX idx_invoices_store_status_created_at
    ON invoices (store_id, status, created_at);

-- Invoices: customer invoice history.
CREATE INDEX idx_invoices_customer_created_at
    ON invoices (customer_id, created_at);

-- Allow at most one ACTIVE session per machine.
CREATE UNIQUE INDEX uq_usage_sessions_active_machine
    ON usage_sessions (active_machine_id);

-- Allow at most one ACTIVE session per customer.
CREATE UNIQUE INDEX uq_usage_sessions_active_customer
    ON usage_sessions (active_customer_id);