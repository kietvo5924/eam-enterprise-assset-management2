from users.models import Permission

perms = [
    {'id': 'users.view', 'name': 'View Users', 'description': 'Can view user lists and details'},
    {'id': 'users.edit', 'name': 'Manage Users', 'description': 'Can create, edit, and delete users'},
    {'id': 'roles.view', 'name': 'View Roles', 'description': 'Can view roles and permissions'},
    {'id': 'roles.edit', 'name': 'Manage Roles', 'description': 'Can create, edit, and delete roles'},
    {'id': 'assets.view', 'name': 'View Assets', 'description': 'Can view asset registry'},
    {'id': 'assets.edit', 'name': 'Manage Assets', 'description': 'Can add and update assets'},
    {'id': 'workorders.view', 'name': 'View Work Orders', 'description': 'Can view work orders'},
    {'id': 'workorders.edit', 'name': 'Manage Work Orders', 'description': 'Can manage work orders'},
    {'id': 'inventory.view', 'name': 'View Inventory', 'description': 'Can view spare parts and stock levels'},
    {'id': 'inventory.edit', 'name': 'Manage Inventory', 'description': 'Can adjust stock levels and add parts'},
    {'id': 'pm.view', 'name': 'View PM Plans', 'description': 'Can view preventive maintenance plans'},
    {'id': 'pm.edit', 'name': 'Manage PM Plans', 'description': 'Can create and modify PM plans'},
]

for p in perms:
    Permission.objects.get_or_create(id=p['id'], defaults={'name': p['name'], 'description': p['description']})

print("Permissions seeded successfully!")
