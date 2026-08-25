ALTER TABLE pm_plans ADD COLUMN assignee_id UUID REFERENCES users(id);
