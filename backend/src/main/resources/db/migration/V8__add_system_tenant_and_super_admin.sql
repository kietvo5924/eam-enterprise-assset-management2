-- Thêm cột tenant_code và service_plan vào bảng tenants
ALTER TABLE tenants ADD COLUMN tenant_code VARCHAR(50);
ALTER TABLE tenants ADD COLUMN service_plan VARCHAR(50) DEFAULT 'FREE';
ALTER TABLE tenants ADD CONSTRAINT uk_tenants_code UNIQUE (tenant_code);

-- Khởi tạo SYSTEM tenant (sử dụng UUID 0)
INSERT INTO tenants (id, name, tenant_code, service_plan, timezone) 
VALUES ('00000000-0000-0000-0000-000000000000', 'System Administration', 'SYSTEM', 'ENTERPRISE', 'UTC')
ON CONFLICT (id) DO NOTHING;

-- Khởi tạo role SUPER_ADMIN cho SYSTEM tenant
INSERT INTO roles (id, tenant_id, name, description, is_system)
VALUES ('00000000-0000-0000-0000-000000000000', '00000000-0000-0000-0000-000000000000', 'SUPER_ADMIN', 'Super Administrator for System', TRUE)
ON CONFLICT (id) DO NOTHING;

-- Thêm quyền system:admin
INSERT INTO permissions (id, name, description) VALUES
('system:admin', 'System Administration', 'Manage tenants and system settings')
ON CONFLICT (id) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id) 
VALUES ('00000000-0000-0000-0000-000000000000', 'system:admin')
ON CONFLICT DO NOTHING;

-- Khởi tạo tài khoản superadmin mặc định (password: admin123)
-- hash bcrypt của 'admin123': $2a$10$tZ.r/C37qT8eD0F40mKx7.Ootb7Y9T2X/n/b18751Xl/e92Q48rGq
INSERT INTO users (id, tenant_id, username, password_hash, status)
VALUES ('00000000-0000-0000-0000-000000000000', '00000000-0000-0000-0000-000000000000', 'superadmin@eam.local', '$2a$06$RwabscgyqBt.a44Oj.Hm7eUOaBpSIKAz0.Z1P2D5amrq6EHqkuT.W', 'ACTIVE')
ON CONFLICT (id) DO NOTHING;

INSERT INTO user_roles (user_id, role_id)
VALUES ('00000000-0000-0000-0000-000000000000', '00000000-0000-0000-0000-000000000000')
ON CONFLICT DO NOTHING;

-- Khởi tạo role TENANT_ADMIN cho SYSTEM tenant (giống hệt tenant bình thường)
INSERT INTO roles (id, tenant_id, name, description, is_system)
VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'TENANT_ADMIN', 'Administrator for System Tenant', TRUE)
ON CONFLICT (id) DO NOTHING;

-- Cấp tất cả các quyền (ngoại trừ system:admin) cho TENANT_ADMIN của SYSTEM tenant
INSERT INTO role_permissions (role_id, permission_id)
SELECT '00000000-0000-0000-0000-000000000001', id FROM permissions WHERE id != 'system:admin'
ON CONFLICT DO NOTHING;
