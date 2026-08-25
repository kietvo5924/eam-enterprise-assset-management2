CREATE TABLE meter_readings (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    reading_value DECIMAL(19, 2) NOT NULL,
    reading_date TIMESTAMP WITH TIME ZONE NOT NULL,
    unit VARCHAR(50),
    remarks TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_by UUID,
    CONSTRAINT meter_readings_tenant_id_fk FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_meter_readings_asset_id ON meter_readings(asset_id);
CREATE INDEX idx_meter_readings_tenant_id ON meter_readings(tenant_id);
