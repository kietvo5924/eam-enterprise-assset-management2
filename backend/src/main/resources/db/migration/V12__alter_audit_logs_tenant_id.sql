ALTER TABLE audit_logs ALTER COLUMN tenant_id TYPE UUID USING tenant_id::uuid;
