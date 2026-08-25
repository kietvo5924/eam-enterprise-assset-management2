CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    username VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uk_users_username_tenant UNIQUE (username, tenant_id)
);

CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uk_roles_name_tenant UNIQUE (name, tenant_id)
);

CREATE TABLE IF NOT EXISTS permissions (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id VARCHAR(100) NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

-- Seed basic permissions
INSERT INTO permissions (id, name, description) VALUES
('tenant:read', 'Read Tenant Settings', 'View tenant configuration'),
('tenant:update', 'Update Tenant Settings', 'Modify tenant configuration'),
('role:read', 'Read Roles', 'View roles and permissions'),
('role:create', 'Create Role', 'Create new custom roles'),
('role:update', 'Update Role', 'Update existing roles'),
('role:delete', 'Delete Role', 'Delete custom roles'),
('asset:read', 'Read Assets', 'View assets'),
('asset:create', 'Create Asset', 'Create new assets'),
('asset:update', 'Update Asset', 'Update existing assets'),
('asset:delete', 'Delete Asset', 'Soft delete assets'),
('work_order:read', 'Read Work Orders', 'View work orders'),
('work_order:create', 'Create Work Order', 'Create new work orders'),
('work_order:update', 'Update Work Order', 'Update existing work orders'),
('work_order:reassign', 'Reassign Work Order', 'Reassign work orders'),
('user:read', 'Read Users', 'View users'),
('user:create', 'Create User', 'Create users'),
('user:update', 'Update User', 'Update users')
ON CONFLICT (id) DO NOTHING;
