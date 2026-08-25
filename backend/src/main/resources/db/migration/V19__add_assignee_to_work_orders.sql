ALTER TABLE work_orders
ADD COLUMN assigned_to UUID,
ADD COLUMN assigned_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN actual_start_time TIMESTAMP WITH TIME ZONE;

ALTER TABLE work_orders
ADD CONSTRAINT fk_work_orders_assignee
FOREIGN KEY (assigned_to) REFERENCES users(id);

CREATE INDEX IF NOT EXISTS idx_work_orders_assigned_to ON work_orders(assigned_to);
