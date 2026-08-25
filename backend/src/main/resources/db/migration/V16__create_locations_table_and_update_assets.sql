-- V16__create_locations_table_and_update_assets.sql

CREATE TABLE IF NOT EXISTS locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    parent_id ltree,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID,
    updated_by UUID,
    CONSTRAINT fk_locations_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE INDEX IF NOT EXISTS idx_locations_tenant_id ON locations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_locations_parent_id ON locations USING GIST (parent_id);

-- Alter assets table
ALTER TABLE assets DROP COLUMN location;
ALTER TABLE assets ADD COLUMN location_id UUID;
ALTER TABLE assets ADD CONSTRAINT fk_assets_location FOREIGN KEY (location_id) REFERENCES locations(id);

-- Insert permissions for location management
INSERT INTO permissions (id, name, description) VALUES
('location:read', 'Read Locations', 'Read locations'),
('location:create', 'Create Location', 'Create locations'),
('location:update', 'Update Location', 'Update locations'),
('location:delete', 'Delete Location', 'Delete locations')
ON CONFLICT (id) DO NOTHING;

-- Assign to Super Admin and Tenant Admin
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.name IN ('SUPER_ADMIN', 'TENANT_ADMIN')
AND p.id LIKE 'location:%'
ON CONFLICT DO NOTHING;
