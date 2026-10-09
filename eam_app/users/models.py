import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from core.models import BaseTenantModel, TenantManager

class Permission(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'permissions'

    def __str__(self):
        return self.name

class Role(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    is_system = models.BooleanField(default=False)
    permissions = models.ManyToManyField(Permission, related_name='roles', db_table='role_permissions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'roles'
        unique_together = (('name', 'tenant'),)

    def __str__(self):
        return self.name

class UserManagerMixin:
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username field must be set')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, email, password, **extra_fields)

class UserManager(UserManagerMixin, BaseUserManager, TenantManager):
    pass

class AllUserManager(UserManagerMixin, BaseUserManager):
    pass

class User(AbstractBaseUser, BaseTenantModel):
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('PENDING', 'Pending'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    
    roles = models.ManyToManyField(Role, related_name='users', db_table='user_roles')
    
    reset_token = models.CharField(max_length=255, null=True, blank=True)
    reset_token_expiry = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # For Django Admin compatibility if needed
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = UserManager()
    all_objects = AllUserManager() # Bypassing tenant filter if needed

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        db_table = 'users'
        unique_together = (('username', 'tenant'), ('email', 'tenant'))

    def __str__(self):
        return self.username

    def get_full_name(self):
        return self.username

    def get_short_name(self):
        return self.username

class InviteToken(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=255)
    token = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'invite_tokens'


class TechnicianProfile(BaseTenantModel):
    AVAILABILITY_CHOICES = (
        ('AVAILABLE', 'Available'),
        ('BUSY', 'Busy'),
        ('ON_LEAVE', 'On Leave'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        'users.User',
        on_delete=models.CASCADE,
        related_name='technician_profile'
    )
    skills = models.JSONField(default=list, blank=True)
    skill_level = models.SmallIntegerField(default=1)
    certifications = models.JSONField(default=list, blank=True)
    coords_x = models.FloatField(default=0.0)
    coords_y = models.FloatField(default=0.0)
    floor_level = models.SmallIntegerField(default=1)
    floorplan = models.ForeignKey(
        'assets.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='technician_profiles',
        help_text='Mặt bằng làm việc chính được gán cho nhân viên'
    )
    zone_id = models.CharField(max_length=64, blank=True, default='')
    shift_end_time = models.DateTimeField(null=True, blank=True)
    max_shift_minutes = models.IntegerField(default=480, help_text="Thời gian làm việc tối đa trong ca (phút)")
    monthly_accumulated_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    is_on_duty = models.BooleanField(default=True)
    availability_status = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default='AVAILABLE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'technician_profiles'
        indexes = [
            models.Index(fields=['tenant', 'availability_status', 'is_on_duty']),
            models.Index(fields=['tenant', 'user']),
        ]

    def __str__(self):
        return f"Profile of {self.user.username} (Level {self.skill_level})"


class WorkforceSkill(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True, default='GENERAL')
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'workforce_skills'
        unique_together = (('code', 'tenant'),)
        indexes = [
            models.Index(fields=['tenant', 'code']),
            models.Index(fields=['tenant', 'category', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class CertificationType(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    issuing_body = models.CharField(max_length=255, blank=True, default='')
    validity_months = models.IntegerField(default=12, help_text='Thời hạn hiệu lực theo tháng (0 = vô thời hạn)')
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'certification_types'
        unique_together = (('code', 'tenant'),)
        indexes = [
            models.Index(fields=['tenant', 'code']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class UserCertification(BaseTenantModel):
    STATUS_CHOICES = (
        ('ACTIVE', 'Active / Còn hiệu lực'),
        ('EXPIRED', 'Expired / Hết hạn'),
        ('REVOKED', 'Revoked / Bị thu hồi'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='held_certifications')
    certification_type = models.ForeignKey(CertificationType, on_delete=models.CASCADE, related_name='user_certifications')
    certificate_number = models.CharField(max_length=100, blank=True, default='')
    issued_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_certifications'
        indexes = [
            models.Index(fields=['tenant', 'user', 'status']),
            models.Index(fields=['tenant', 'expiry_date']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.certification_type.code} ({self.status})"

    @property
    def is_valid(self):
        from django.utils import timezone
        if self.status != 'ACTIVE':
            return False
        if self.expiry_date and self.expiry_date < timezone.now().date():
            return False
        return True


class ShiftTemplate(BaseTenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_overnight = models.BooleanField(default=False, help_text='Ca trực kéo dài qua ngày hôm sau (ví dụ 22:00 - 06:00)')
    color_code = models.CharField(max_length=32, default='#3b82f6')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'shift_templates'
        unique_together = (('code', 'tenant'),)
        indexes = [
            models.Index(fields=['tenant', 'code']),
        ]

    def __str__(self):
        return f"{self.name} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"


class TechnicianSchedule(BaseTenantModel):
    STATUS_CHOICES = (
        ('ON_DUTY', 'On Duty / Đi ca'),
        ('OFF', 'Off / Nghỉ ca'),
        ('LEAVE', 'On Leave / Nghỉ phép'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='schedules')
    work_date = models.DateField()
    shift_template = models.ForeignKey(ShiftTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name='schedules')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ON_DUTY')
    duty_zone_id = models.CharField(max_length=64, blank=True, default='', help_text='Khu vực hoặc phân xưởng trực trong ca hôm nay')
    notes = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'technician_schedules'
        unique_together = (('tenant', 'user', 'work_date'),)
        indexes = [
            models.Index(fields=['tenant', 'work_date', 'status']),
            models.Index(fields=['tenant', 'user', 'work_date']),
        ]

    def __str__(self):
        shift_name = self.shift_template.name if self.shift_template else self.status
        return f"{self.user.username} - {self.work_date}: {shift_name}"

