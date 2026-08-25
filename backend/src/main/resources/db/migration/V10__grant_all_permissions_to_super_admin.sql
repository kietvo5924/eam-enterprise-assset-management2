-- Cấp toàn bộ các quyền hiện có cho role SUPER_ADMIN (ngoại trừ những quyền đã có để tránh lỗi)
INSERT INTO role_permissions (role_id, permission_id)
SELECT '00000000-0000-0000-0000-000000000000', id FROM permissions
ON CONFLICT DO NOTHING;
