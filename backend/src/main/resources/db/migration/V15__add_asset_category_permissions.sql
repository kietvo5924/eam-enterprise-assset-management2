INSERT INTO permissions (id, name, description) VALUES
('asset_category:read', 'Read Asset Categories', 'View asset categories'),
('asset_category:create', 'Create Asset Category', 'Create new asset categories'),
('asset_category:update', 'Update Asset Category', 'Update existing asset categories'),
('asset_category:delete', 'Delete Asset Category', 'Soft delete asset categories')
ON CONFLICT (id) DO NOTHING;

-- Grant to Tenant Admin and Super Admin roles
INSERT INTO role_permissions (role_id, permission_id)
SELECT id, 'asset_category:read' FROM roles WHERE name IN ('TENANT_ADMIN', 'SUPER_ADMIN')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT id, 'asset_category:create' FROM roles WHERE name IN ('TENANT_ADMIN', 'SUPER_ADMIN')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT id, 'asset_category:update' FROM roles WHERE name IN ('TENANT_ADMIN', 'SUPER_ADMIN')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT id, 'asset_category:delete' FROM roles WHERE name IN ('TENANT_ADMIN', 'SUPER_ADMIN')
ON CONFLICT DO NOTHING;
