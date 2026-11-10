-- Extend machine categories without changing previously assigned STANDARD/VIP machines.
ALTER TABLE machine_room_types DROP CHECK chk_machine_room_type;
ALTER TABLE machine_room_types ADD CONSTRAINT chk_machine_room_type
    CHECK (room_type IN ('STANDARD', 'VIP', 'COUPLE', 'SUPER_VIP'));
