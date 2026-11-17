-- Extend the allowed roles without modifying any existing employee assignment.
-- A separate, reviewed account mapping and CYBERHUB_RBAC_POLICY=separated
-- are required before legacy ADMIN business grants can be retired.
ALTER TABLE employees DROP CHECK chk_employees_role;
ALTER TABLE employees ADD CONSTRAINT chk_employees_role
    CHECK (role IN ('ADMIN', 'DIRECTOR', 'MANAGER', 'STAFF', 'KITCHEN', 'INVENTORY'));
