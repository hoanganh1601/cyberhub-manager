-- Core organization, HR profiles, authentication/RBAC, store assignments, and audit log.

SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE stores (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    address VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT pk_stores PRIMARY KEY (id),
    CONSTRAINT uq_stores_code UNIQUE (code),
    CONSTRAINT chk_stores_code_not_blank CHECK (CHAR_LENGTH(TRIM(code)) > 0),
    CONSTRAINT chk_stores_name_not_blank CHECK (CHAR_LENGTH(TRIM(name)) > 0),
    CONSTRAINT chk_stores_address_not_blank CHECK (CHAR_LENGTH(TRIM(address)) > 0),
    CONSTRAINT chk_stores_status CHECK (status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE employee_profiles (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    home_store_id BIGINT UNSIGNED NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    employment_status VARCHAR(10) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT pk_employee_profiles PRIMARY KEY (id),
    CONSTRAINT uq_employee_profiles_code UNIQUE (code),
    CONSTRAINT fk_employee_profiles_store
        FOREIGN KEY (home_store_id) REFERENCES stores (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_employee_profiles_code_not_blank CHECK (CHAR_LENGTH(TRIM(code)) > 0),
    CONSTRAINT chk_employee_profiles_name_not_blank CHECK (CHAR_LENGTH(TRIM(full_name)) > 0),
    CONSTRAINT chk_employee_profiles_status CHECK (employment_status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE employees (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    profile_id BIGINT UNSIGNED NOT NULL,
    username VARCHAR(30) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    auth_version INT UNSIGNED NOT NULL DEFAULT 0,
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    password_changed_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT pk_employees PRIMARY KEY (id),
    CONSTRAINT uq_employees_profile UNIQUE (profile_id),
    CONSTRAINT uq_employees_username UNIQUE (username),
    CONSTRAINT fk_employees_profile
        FOREIGN KEY (profile_id) REFERENCES employee_profiles (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_employees_username_length CHECK (CHAR_LENGTH(username) BETWEEN 4 AND 30),
    CONSTRAINT chk_employees_password_hash_not_blank CHECK (CHAR_LENGTH(TRIM(password_hash)) > 0),
    CONSTRAINT chk_employees_role CHECK (
        role IN ('ADMIN', 'DIRECTOR', 'MANAGER', 'STAFF', 'KITCHEN')
    ),
    CONSTRAINT chk_employees_status CHECK (status IN ('ACTIVE', 'INACTIVE', 'LOCKED'))
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE employee_store_assignments (
    employee_id BIGINT UNSIGNED NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    granted_by BIGINT UNSIGNED NOT NULL,
    granted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_employee_store_assignments PRIMARY KEY (employee_id, store_id),
    CONSTRAINT fk_employee_assignments_employee
        FOREIGN KEY (employee_id) REFERENCES employees (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_employee_assignments_store
        FOREIGN KEY (store_id) REFERENCES stores (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_employee_assignments_granter
        FOREIGN KEY (granted_by) REFERENCES employees (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_employee_assignments_no_self_grant CHECK (granted_by <> employee_id)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE management_audit (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    employee_id BIGINT UNSIGNED NOT NULL,
    store_id BIGINT UNSIGNED NOT NULL,
    action VARCHAR(40) NOT NULL,
    entity_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_management_audit PRIMARY KEY (id),
    CONSTRAINT fk_management_audit_employee
        FOREIGN KEY (employee_id) REFERENCES employees (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_management_audit_store
        FOREIGN KEY (store_id) REFERENCES stores (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_management_audit_action_not_blank CHECK (CHAR_LENGTH(TRIM(action)) > 0)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;
