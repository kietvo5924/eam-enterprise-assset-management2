-- Assign the 'audit_logs:read' permission to all roles named 'Tenant Admin'
INSERT INTO role_permissions (role_id, permission_id)
SELECT id, 'audit_logs:read'
FROM roles
WHERE name = 'Tenant Admin'
ON CONFLICT DO NOTHING;
