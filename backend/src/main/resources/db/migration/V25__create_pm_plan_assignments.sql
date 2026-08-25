CREATE TABLE pm_plan_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    pm_plan_id UUID NOT NULL REFERENCES pm_plans(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    baseline_meter_reading NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID,
    UNIQUE(tenant_id, pm_plan_id, asset_id)
);

CREATE INDEX idx_pm_plan_assignments_tenant_id ON pm_plan_assignments(tenant_id);
CREATE INDEX idx_pm_plan_assignments_pm_plan_id ON pm_plan_assignments(pm_plan_id);
CREATE INDEX idx_pm_plan_assignments_asset_id ON pm_plan_assignments(asset_id);
