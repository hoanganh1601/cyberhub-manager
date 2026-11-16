-- Complete machine incident and maintenance workflow.
CREATE TABLE machine_incidents (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(24) NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    machine_id BIGINT UNSIGNED NOT NULL,
    reported_by BIGINT UNSIGNED NOT NULL,
    assigned_to BIGINT UNSIGNED NULL,
    severity VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'REPORTED',
    title VARCHAR(120) NOT NULL,
    description VARCHAR(1000) NOT NULL,
    resolution VARCHAR(1000) NULL,
    labor_cost BIGINT UNSIGNED NOT NULL DEFAULT 0,
    parts_cost BIGINT UNSIGNED NOT NULL DEFAULT 0,
    reported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME NULL,
    completed_at DATETIME NULL,
    verified_at DATETIME NULL,
    verified_by BIGINT UNSIGNED NULL,
    CONSTRAINT uq_machine_incidents_code UNIQUE (code),
    CONSTRAINT fk_incidents_store FOREIGN KEY (store_id) REFERENCES stores(id),
    CONSTRAINT fk_incidents_machine FOREIGN KEY (machine_id) REFERENCES machines(id),
    CONSTRAINT fk_incidents_reporter FOREIGN KEY (reported_by) REFERENCES employees(id),
    CONSTRAINT fk_incidents_assignee FOREIGN KEY (assigned_to) REFERENCES employees(id),
    CONSTRAINT fk_incidents_verifier FOREIGN KEY (verified_by) REFERENCES employees(id),
    CONSTRAINT chk_incidents_severity CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    CONSTRAINT chk_incidents_status CHECK (status IN ('REPORTED','ASSIGNED','IN_PROGRESS','WAITING_PARTS','COMPLETED','VERIFIED','CANCELLED')),
    CONSTRAINT chk_incidents_cost CHECK (labor_cost <= 1000000000 AND parts_cost <= 1000000000),
    INDEX idx_incidents_store_status (store_id, status, reported_at),
    INDEX idx_incidents_machine_history (machine_id, reported_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE machine_incident_parts (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    incident_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(120) NOT NULL,
    quantity INT UNSIGNED NOT NULL,
    unit_cost BIGINT UNSIGNED NOT NULL,
    CONSTRAINT fk_incident_parts_incident FOREIGN KEY (incident_id) REFERENCES machine_incidents(id),
    CONSTRAINT chk_incident_parts_quantity CHECK (quantity BETWEEN 1 AND 1000),
    CONSTRAINT chk_incident_parts_cost CHECK (unit_cost <= 1000000000)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE machine_incident_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    incident_id BIGINT UNSIGNED NOT NULL,
    employee_id BIGINT UNSIGNED NOT NULL,
    from_status VARCHAR(20) NULL,
    to_status VARCHAR(20) NOT NULL,
    note VARCHAR(500) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_incident_events_incident FOREIGN KEY (incident_id) REFERENCES machine_incidents(id),
    CONSTRAINT fk_incident_events_employee FOREIGN KEY (employee_id) REFERENCES employees(id),
    INDEX idx_incident_events_history (incident_id, created_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
