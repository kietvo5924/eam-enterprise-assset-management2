INSERT INTO permissions (id, name, description) 
VALUES ('work_order:execute', 'Receive & Execute Work Order', 'Allows user to be assigned to and execute work orders') 
ON CONFLICT (id) DO NOTHING;

