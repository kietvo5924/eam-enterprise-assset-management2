ALTER TABLE pm_plan_assignments
ADD COLUMN last_triggered_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN last_triggered_meter NUMERIC;
