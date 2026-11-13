-- Dedicated POS and stock staff roles. Existing assignments stay unchanged.
ALTER TABLE employees DROP CHECK chk_employees_role;
ALTER TABLE employees ADD CONSTRAINT chk_employees_role
    CHECK (role IN ('ADMIN', 'MANAGER', 'STAFF', 'KITCHEN', 'INVENTORY'));
