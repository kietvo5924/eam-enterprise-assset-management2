CREATE TABLE IF NOT EXISTS work_order_checklists (
    id UUID PRIMARY KEY,
    work_order_id UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL,
    item_name VARCHAR(255) NOT NULL,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_wo_checklists_wo_id ON work_order_checklists(work_order_id);
CREATE INDEX IF NOT EXISTS idx_wo_checklists_tenant_id ON work_order_checklists(tenant_id);

CREATE TABLE IF NOT EXISTS work_order_attachments (
    id UUID PRIMARY KEY,
    work_order_id UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL,
    file_url VARCHAR(1024) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(100) NOT NULL,
    file_size BIGINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by UUID,
    updated_by UUID
);

CREATE INDEX IF NOT EXISTS idx_wo_attachments_wo_id ON work_order_attachments(work_order_id);
CREATE INDEX IF NOT EXISTS idx_wo_attachments_tenant_id ON work_order_attachments(tenant_id);

ALTER TABLE work_orders
ADD COLUMN IF NOT EXISTS resolution_notes TEXT;
