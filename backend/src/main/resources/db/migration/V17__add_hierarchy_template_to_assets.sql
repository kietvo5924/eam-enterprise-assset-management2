ALTER TABLE assets ADD COLUMN hierarchy_template_id UUID;
ALTER TABLE assets ADD CONSTRAINT fk_assets_hierarchy_template FOREIGN KEY (hierarchy_template_id) REFERENCES hierarchy_templates(id);
CREATE INDEX idx_assets_hierarchy_template_id ON assets(hierarchy_template_id);
