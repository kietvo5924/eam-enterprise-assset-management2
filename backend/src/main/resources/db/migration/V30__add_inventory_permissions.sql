INSERT INTO permissions (id, name, description) VALUES ('inventory:read', 'View Inventory', 'Can view spare parts inventory') ON CONFLICT (id) DO NOTHING;
INSERT INTO permissions (id, name, description) VALUES ('inventory:create', 'Create Inventory', 'Can add new spare parts to inventory') ON CONFLICT (id) DO NOTHING;
INSERT INTO permissions (id, name, description) VALUES ('inventory:update', 'Update Inventory', 'Can update existing spare parts') ON CONFLICT (id) DO NOTHING;
INSERT INTO permissions (id, name, description) VALUES ('inventory:delete', 'Delete Inventory', 'Can delete spare parts') ON CONFLICT (id) DO NOTHING;

-- Grant to system:admin role
INSERT INTO role_permissions (role_id, permission_id)
SELECT id, 'inventory:read' FROM roles WHERE name = 'System Admin'
ON CONFLICT (role_id, permission_id) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT id, 'inventory:create' FROM roles WHERE name = 'System Admin'
ON CONFLICT (role_id, permission_id) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT id, 'inventory:update' FROM roles WHERE name = 'System Admin'
ON CONFLICT (role_id, permission_id) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT id, 'inventory:delete' FROM roles WHERE name = 'System Admin'
ON CONFLICT (role_id, permission_id) DO NOTHING;
