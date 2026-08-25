ALTER TABLE work_orders
ADD COLUMN parent_id UUID,
ADD CONSTRAINT fk_work_orders_parent_id
    FOREIGN KEY (parent_id)
    REFERENCES work_orders (id)
    ON DELETE SET NULL;
