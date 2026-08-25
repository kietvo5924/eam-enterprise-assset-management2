CREATE TABLE pm_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    trigger_type VARCHAR(50) NOT NULL, -- TIME, USAGE, METER
    interval_value NUMERIC,
    interval_unit VARCHAR(50), -- DAYS, WEEKS, MONTHS (only for TIME)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID
);

CREATE INDEX idx_pm_plans_tenant_id ON pm_plans(tenant_id);

INSERT INTO permissions (id, name, description) VALUES
('pm_plan:read', 'Read PM Plans', 'Allow viewing preventive maintenance plans'),
('pm_plan:create', 'Create PM Plan', 'Allow creating preventive maintenance plans'),
('pm_plan:update', 'Update PM Plan', 'Allow updating preventive maintenance plans'),
('pm_plan:delete', 'Delete PM Plan', 'Allow deleting preventive maintenance plans')
ON CONFLICT (id) DO NOTHING;

-- Assign to Super Admin and Tenant Admin
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.name IN ('SUPER_ADMIN', 'TENANT_ADMIN')
  AND p.id IN ('pm_plan:read', 'pm_plan:create', 'pm_plan:update', 'pm_plan:delete');
