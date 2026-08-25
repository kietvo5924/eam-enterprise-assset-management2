-- Create Spare Parts table
CREATE TABLE spare_parts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    part_number VARCHAR(100),
    description TEXT,
    quantity_in_stock NUMERIC DEFAULT 0,
    unit_cost NUMERIC(19, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID
);
CREATE INDEX idx_spare_parts_tenant_id ON spare_parts(tenant_id);

-- Create PM Plan Materials (Estimated Parts)
CREATE TABLE pm_plan_materials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    pm_plan_id UUID NOT NULL REFERENCES pm_plans(id) ON DELETE CASCADE,
    spare_part_id UUID NOT NULL REFERENCES spare_parts(id),
    quantity NUMERIC NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID
);
CREATE INDEX idx_pm_plan_materials_pm_plan_id ON pm_plan_materials(pm_plan_id);

-- Create Work Order Materials (Actual Parts used)
CREATE TABLE work_order_materials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    work_order_id UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    spare_part_id UUID NOT NULL REFERENCES spare_parts(id),
    quantity NUMERIC NOT NULL,
    actual_cost NUMERIC(19, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID
);
CREATE INDEX idx_work_order_materials_wo_id ON work_order_materials(work_order_id);

-- Create PM Plan Checklists (SOP tasks)
CREATE TABLE pm_plan_checklists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    pm_plan_id UUID NOT NULL REFERENCES pm_plans(id) ON DELETE CASCADE,
    item_name VARCHAR(255) NOT NULL,
    input_type VARCHAR(50) DEFAULT 'PASS_FAIL',
    expected_value VARCHAR(255),
    is_mandatory BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID
);
CREATE INDEX idx_pm_plan_checklists_pm_plan_id ON pm_plan_checklists(pm_plan_id);

-- Alter PM Plans table to add estimated duration
ALTER TABLE pm_plans ADD COLUMN estimated_duration_minutes INT;

-- Alter Work Orders table to add duration fields
ALTER TABLE work_orders ADD COLUMN estimated_duration_minutes INT;
ALTER TABLE work_orders ADD COLUMN actual_duration_minutes INT;

-- Alter Work Order Checklists to support new input types (currently only has item_name, is_completed)
ALTER TABLE work_order_checklists ADD COLUMN input_type VARCHAR(50) DEFAULT 'PASS_FAIL';
ALTER TABLE work_order_checklists ADD COLUMN expected_value VARCHAR(255);
ALTER TABLE work_order_checklists ADD COLUMN actual_value VARCHAR(255);
ALTER TABLE work_order_checklists ADD COLUMN is_mandatory BOOLEAN DEFAULT FALSE;
