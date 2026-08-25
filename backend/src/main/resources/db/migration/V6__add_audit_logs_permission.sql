-- Insert the new permission for audit logs
INSERT INTO permissions (id, name, description) VALUES
('audit_logs:read', 'Read Audit Logs', 'View system audit logs')
ON CONFLICT (id) DO NOTHING;

-- In a real scenario we might map this to a specific role ID, but since role IDs are UUIDs generated per tenant,
-- the tenant admin will need to assign this permission to roles via the Role Management UI.
-- For the built-in system admin, we could seed it here if we had a static system admin role.
