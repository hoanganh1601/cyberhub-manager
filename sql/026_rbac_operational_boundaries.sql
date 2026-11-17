-- Expand without rewriting existing credentials, roles or business records.
CREATE TABLE employee_profiles (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    employee_id BIGINT UNSIGNED NULL,
    code VARCHAR(20) NOT NULL,
    home_store_id BIGINT UNSIGNED NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    employment_status VARCHAR(10) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_employee_profiles_employee UNIQUE (employee_id),
    CONSTRAINT uq_employee_profiles_code UNIQUE (code),
    CONSTRAINT fk_employee_profiles_employee FOREIGN KEY (employee_id) REFERENCES employees(id),
    CONSTRAINT fk_employee_profiles_store FOREIGN KEY (home_store_id) REFERENCES stores(id),
    CONSTRAINT chk_employee_profiles_status CHECK (employment_status IN ('ACTIVE','INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO employee_profiles(employee_id,code,home_store_id,full_name,employment_status)
SELECT id,code,store_id,full_name,'ACTIVE' FROM employees;

CREATE TABLE employee_store_assignments (
    employee_id BIGINT UNSIGNED NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    granted_by BIGINT UNSIGNED NOT NULL,
    granted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (employee_id,store_id),
    CONSTRAINT fk_employee_assignments_employee FOREIGN KEY (employee_id) REFERENCES employees(id),
    CONSTRAINT fk_employee_assignments_store FOREIGN KEY (store_id) REFERENCES stores(id),
    CONSTRAINT fk_employee_assignments_granter FOREIGN KEY (granted_by) REFERENCES employees(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE customer_store_links (
    customer_id BIGINT UNSIGNED NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    source VARCHAR(24) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (customer_id,store_id),
    CONSTRAINT fk_customer_links_customer FOREIGN KEY (customer_id) REFERENCES customers(id),
    CONSTRAINT fk_customer_links_store FOREIGN KEY (store_id) REFERENCES stores(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Only derive links from a recorded visit or invoice; never guess from a home store.
INSERT INTO customer_store_links(customer_id,store_id,source)
SELECT DISTINCT customer_id,store_id,'INVOICE' FROM invoices;
INSERT IGNORE INTO customer_store_links(customer_id,store_id,source)
SELECT DISTINCT u.customer_id,m.store_id,'SESSION'
FROM usage_sessions u JOIN machines m ON m.id=u.machine_id;

CREATE TABLE supplier_payable_approvals (
    payable_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    approved_by BIGINT UNSIGNED NOT NULL,
    approved_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note VARCHAR(255) NOT NULL,
    CONSTRAINT fk_payable_approval_payable FOREIGN KEY (payable_id) REFERENCES supplier_payables(id),
    CONSTRAINT fk_payable_approval_employee FOREIGN KEY (approved_by) REFERENCES employees(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
