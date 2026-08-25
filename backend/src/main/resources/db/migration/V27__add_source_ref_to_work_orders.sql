ALTER TABLE work_orders
ADD COLUMN source_reference VARCHAR(255);

CREATE INDEX idx_work_orders_source_ref ON work_orders(source_reference);
