import os
import sys
import random
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent / 'eam_app'
sys.path.insert(0, str(BASE_DIR))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import Tenant
from workorders.models import WorkOrder
from django.utils import timezone
from analytics.services import DashboardCacheService, TrendAnalyticsService

tenant = Tenant.objects.get(id='c47f0051-58e5-4d74-b2c2-c1f2b556c536')
now = timezone.now()

# 1. Distribute completed work orders evenly across days -28 to -1 (avg 2 per day)
completed_wos = list(WorkOrder.all_objects.filter(tenant=tenant, status='COMPLETED').order_by('id'))
# Generate a realistic daily quota for 28 days that sums to len(completed_wos)
import itertools

# Create a smooth distribution sequence: mostly 2s, some 1s, some 3s
daily_counts = [2, 1, 2, 3, 2, 1, 2, 2, 3, 2, 1, 2, 3, 2, 2, 1, 3, 2, 2, 1, 2, 3, 2, 2, 3, 2, 2, 2]
# Adjust to match exactly len(completed_wos)
diff = len(completed_wos) - sum(daily_counts)
idx = 0
while diff != 0:
    if diff > 0:
        daily_counts[idx % len(daily_counts)] += 1
        diff -= 1
    else:
        daily_counts[idx % len(daily_counts)] -= 1
        diff += 1
    idx += 1

wo_iter = iter(completed_wos)
for day_offset, count in enumerate(daily_counts, start=1):
    target_date = now - timedelta(days=29 - day_offset)
    for _ in range(count):
        try:
            wo = next(wo_iter)
        except StopIteration:
            break
        comp_time = target_date.replace(hour=random.randint(10, 17), minute=random.randint(0, 59))
        lead_hours = random.randint(8, 36)
        create_time = comp_time - timedelta(hours=lead_hours)
        WorkOrder.all_objects.filter(id=wo.id).update(created_at=create_time, completed_at=comp_time)

# 2. Update active work orders: spread over past 4 days
active_wos = list(WorkOrder.all_objects.filter(tenant=tenant, status__in=['CREATED', 'ASSIGNED', 'IN_PROGRESS']))
active_offsets = [0, 0, 1, 1, 2, 3, 4]
for idx, wo in enumerate(active_wos):
    off = active_offsets[idx % len(active_offsets)]
    act_created = (now - timedelta(days=off)).replace(hour=random.randint(8, 16), minute=random.randint(0, 59))
    WorkOrder.all_objects.filter(id=wo.id).update(created_at=act_created)

# Invalidate cache
DashboardCacheService.invalidate_all(tenant.id)

trends = TrendAnalyticsService.get_30_day_trends(tenant)
print("Updated 30-Day Trends (Sampled):")
for s in trends['series'][-15:]:
    print(f"  Date {s['date']}: Created = {s['created']}, Completed = {s['completed']}")
print(f"Total Completed: {sum(s['completed'] for s in trends['series'])}")
print(f"Total Created in 30d: {sum(s['created'] for s in trends['series'])}")
print("Done!")
