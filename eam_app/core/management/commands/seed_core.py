import os
from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Permission, Role, User
from core.models import Tenant

class Command(BaseCommand):
    help = 'Seed core database with System Tenant, Super Admin, and Permissions'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting seed process...')
        
        with transaction.atomic():
            # 1. Seed Permissions
            permissions_data = [
                ('tenant:read', 'Read Tenant Settings', 'View tenant configuration'),
                ('tenant:update', 'Update Tenant Settings', 'Cấu hình thiết lập tổ chức và danh mục dùng chung (kỹ năng, chứng chỉ, mẫu ca trực)'),
                ('role:read', 'Read Roles', 'View roles and permissions'),
                ('role:create', 'Create Role', 'Create new custom roles'),
                ('role:update', 'Update Role', 'Update existing roles'),
                ('role:delete', 'Delete Role', 'Delete custom roles'),
                ('asset:read', 'Read Assets', 'View assets'),
                ('asset:create', 'Create Asset', 'Create new assets'),
                ('asset:update', 'Update Asset', 'Update existing assets'),
                ('asset:delete', 'Delete Asset', 'Soft delete assets'),
                ('work_order:read', 'Read Work Orders', 'Xem phiếu bảo trì và tra cứu tài nguyên phân công (kỹ năng, chứng chỉ, công cụ đo kiểm, ca trực)'),
                ('work_order:create', 'Create Work Order', 'Tạo phiếu bảo trì, thiết lập yêu cầu kỹ năng, chứng chỉ an toàn và đăng ký giữ chỗ công cụ đo kiểm'),
                ('work_order:update', 'Update Work Order', 'Cập nhật phiếu bảo trì, điều chỉnh yêu cầu thợ và quản lý danh mục/cấp phát/giữ chỗ công cụ đo kiểm'),
                ('work_order:reassign', 'Reassign Work Order', 'Reassign work orders'),
                ('work_order:delete', 'Delete Work Order', 'Delete work orders'),
                ('work_order:execute', 'Receive & Execute Work Order', 'Allows user to be assigned to and execute work orders'),
                ('workforce:read', 'Read Workforce & Tools', 'Tra cứu tài nguyên nhân lực: kỹ năng, chứng chỉ, công cụ đo kiểm và bảng xếp ca trực KTV'),
                ('user:read', 'Read Users', 'Xem danh sách người dùng, hồ sơ năng lực thợ (kỹ năng, bằng cấp chứng chỉ) và xem bảng xếp ca trực KTV'),
                ('user:update', 'Update User', 'Cập nhật tài khoản, hồ sơ thợ (gán kỹ năng, bằng cấp kèm hạn dùng) và xếp ca trực ngày cho KTV'),
                ('audit_logs:read', 'Read Audit Logs', 'View audit logs'),
                ('system:admin', 'System Administration', 'Manage tenants and system settings'),
                ('asset_category:read', 'Read Asset Categories', 'View asset categories'),
                ('asset_category:create', 'Create Asset Category', 'Create new asset categories'),
                ('asset_category:update', 'Update Asset Category', 'Update existing asset categories'),
                ('asset_category:delete', 'Delete Asset Category', 'Soft delete asset categories'),
                ('location:read', 'Read Locations', 'Read locations'),
                ('location:create', 'Create Location', 'Create locations'),
                ('location:update', 'Update Location', 'Update locations'),
                ('location:delete', 'Delete Location', 'Delete locations'),
                ('pm_plan:read', 'Read PM Plans', 'View pm plans'),
                ('pm_plan:create', 'Create PM Plan', 'Create new pm plans'),
                ('pm_plan:update', 'Update PM Plan', 'Update existing pm plans'),
                ('pm_plan:delete', 'Delete PM Plan', 'Soft delete pm plans'),
                ('inventory:read', 'View Inventory', 'Xem kho phụ tùng thay thế và vật tư tiêu hao trong kho'),
                ('inventory:create', 'Create Inventory', 'Can add new spare parts to inventory'),
                ('inventory:update', 'Update Inventory', 'Nhập xuất và điều chỉnh tồn kho phụ tùng, vật tư tiêu hao'),
                ('inventory:delete', 'Delete Inventory', 'Can delete spare parts'),
                ('reports:read', 'Read Enterprise Reports', 'Can view enterprise analytics and valuation reports'),
                ('reports:export', 'Export Enterprise Reports', 'Can export enterprise reports to Excel, PDF, CSV'),
            ]

            for p_id, name, desc in permissions_data:
                Permission.objects.update_or_create(
                    id=p_id,
                    defaults={'name': name, 'description': desc}
                )
            
            self.stdout.write('Permissions seeded.')

            # 2. Seed System Tenant
            system_tenant_id = '00000000-0000-0000-0000-000000000000'
            tenant, created = Tenant.objects.get_or_create(
                id=system_tenant_id,
                defaults={
                    'name': 'System Administration',
                    'tenant_code': 'SYSTEM',
                    'service_plan': 'ENTERPRISE',
                    'timezone': 'UTC'
                }
            )
            
            # 3. Seed Super Admin Role
            super_admin_role_id = '00000000-0000-0000-0000-000000000000'
            super_admin_role, created = Role.all_objects.get_or_create(
                id=super_admin_role_id,
                defaults={
                    'tenant_id': system_tenant_id,
                    'name': 'SUPER_ADMIN',
                    'description': 'Super Administrator for System',
                    'is_system': True
                }
            )

            # Assign all permissions to SUPER_ADMIN
            all_perms = Permission.objects.all()
            super_admin_role.permissions.set(all_perms)
            
            # 4. Seed Super Admin User
            super_admin_user_id = '00000000-0000-0000-0000-000000000000'
            try:
                user = User.all_objects.get(id=super_admin_user_id)
            except User.DoesNotExist:
                user = User.all_objects.create_user(
                    id=super_admin_user_id,
                    tenant_id=system_tenant_id,
                    username='superadmin@eam.local',
                    password='admin123',
                    status='ACTIVE'
                )
                self.stdout.write('Super Admin user created.')
            
            # Use add to avoid error if it already exists, Django handles duplicate relations natively in many-to-many.
            user.roles.add(super_admin_role)

            # 5. Seed Tenant Admin Role for System Tenant
            tenant_admin_role_id = '00000000-0000-0000-0000-000000000001'
            tenant_admin_role, created = Role.all_objects.get_or_create(
                id=tenant_admin_role_id,
                defaults={
                    'tenant_id': system_tenant_id,
                    'name': 'TENANT_ADMIN',
                    'description': 'Administrator for System Tenant',
                    'is_system': True
                }
            )

            # Assign all permissions EXCEPT system:admin to TENANT_ADMIN
            tenant_admin_perms = Permission.objects.exclude(id='system:admin')
            tenant_admin_role.permissions.set(tenant_admin_perms)

            self.stdout.write(self.style.SUCCESS('Successfully seeded core data!'))
