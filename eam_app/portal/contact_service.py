"""
Service helpers for public landing page contact requests sent to the System Super Admin.

No database model or migration is created for contact submissions; requests are
validated, rate-limited, and delivered directly via Django's configured SMTP backend.
"""

import logging
import os
import threading
import time
from email.utils import make_msgid, parseaddr
from typing import Any, Dict, Tuple

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email

from users.models import User

logger = logging.getLogger(__name__)

SYSTEM_TENANT_ID = '00000000-0000-0000-0000-000000000000'
SYSTEM_SUPER_ADMIN_ID = '00000000-0000-0000-0000-000000000000'
CONTACT_EMAIL_SUBJECT = '[EAM System] Yêu cầu liên hệ mới'

# Input length limits
MAX_FULL_NAME_LEN = 120
MAX_EMAIL_LEN = 254
MAX_COMPANY_LEN = 150
MAX_SUBJECT_LEN = 160
MAX_MESSAGE_LEN = 3000
MIN_FULL_NAME_LEN = 2
MIN_SUBJECT_LEN = 3
MIN_MESSAGE_LEN = 10

# Anti-spam rate limit: max 5 contact requests per IP within 10 minutes
RATE_LIMIT_MAX_REQUESTS = 5
RATE_LIMIT_WINDOW_SECONDS = 600
_LOCAL_RATE_LOCK = threading.Lock()
_LOCAL_RATE_STORE: Dict[str, Tuple[int, float]] = {}


class ContactValidationError(Exception):
    """Raised when visitor contact form data fails validation or anti-spam checks."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ContactConfigurationError(Exception):
    """Raised when SMTP or Super Admin recipient email is not configured."""


class ContactDeliveryError(Exception):
    """Raised when SMTP delivery fails."""


def _contains_header_injection(value: str) -> bool:
    """Return True if value contains CR, LF, or NUL bytes used in header injection."""
    return any(ch in value for ch in ('\r', '\n', '\x00'))


def _is_valid_deliverable_email(email: str) -> bool:
    """Validate email syntax and reject internal .local placeholder addresses."""
    if not email or _contains_header_injection(email) or len(email) > MAX_EMAIL_LEN:
        return False
    cleaned = email.strip()
    if cleaned.lower().endswith('.local'):
        return False
    try:
        validate_email(cleaned)
    except DjangoValidationError:
        return False
    return True


def resolve_system_super_admin_email() -> str:
    """
    Resolve the deliverable email of the System Tenant Super Admin.

    Strictly queries User.all_objects scoped to System Tenant
    (00000000-0000-0000-0000-000000000000), SUPER_ADMIN role, and ACTIVE status.
    Falls back to SYSTEM_ADMIN_CONTACT_EMAIL only if no valid Super Admin email exists.
    """
    super_admins = list(
        User.all_objects.filter(
            tenant_id=SYSTEM_TENANT_ID,
            roles__name='SUPER_ADMIN',
            status='ACTIVE',
        )
        .distinct()
    )

    # Prioritize the canonical System Super Admin record first
    super_admins.sort(
        key=lambda u: 0 if str(u.id) == SYSTEM_SUPER_ADMIN_ID else (1 if u.username == 'superadmin@eam.local' else 2)
    )

    for admin_user in super_admins:
        candidate = (admin_user.email or '').strip()
        if _is_valid_deliverable_email(candidate):
            return candidate

    fallback_email = (
        getattr(settings, 'SYSTEM_ADMIN_CONTACT_EMAIL', '')
        or os.environ.get('SYSTEM_ADMIN_CONTACT_EMAIL', '')
        or ''
    ).strip()
    if _is_valid_deliverable_email(fallback_email):
        return fallback_email

    raise ContactConfigurationError(
        'Chưa tìm thấy email hợp lệ của System Super Admin để tiếp nhận liên hệ.'
    )


def ensure_smtp_configured() -> str:
    """
    Verify email backend and sender address are configured before sending.

    Returns the configured DEFAULT_FROM_EMAIL.
    """
    backend = (getattr(settings, 'EMAIL_BACKEND', '') or '').strip()
    from_email = (getattr(settings, 'DEFAULT_FROM_EMAIL', '') or '').strip()

    if not backend or not from_email or _contains_header_injection(from_email):
        raise ContactConfigurationError(
            'Hệ thống gửi email (SMTP) chưa được cấu hình đầy đủ. Vui lòng thử lại sau.'
        )

    if backend == 'django.core.mail.backends.smtp.EmailBackend':
        host = (getattr(settings, 'EMAIL_HOST', '') or '').strip()
        host_user = (getattr(settings, 'EMAIL_HOST_USER', '') or '').strip()
        host_password = getattr(settings, 'EMAIL_HOST_PASSWORD', '') or ''
        if not host or (host == 'smtp.gmail.com' and (not host_user or not host_password)):
            raise ContactConfigurationError(
                'Hệ thống gửi email (SMTP) chưa được cấu hình đầy đủ. Vui lòng thử lại sau.'
            )
        if not _is_valid_deliverable_email(from_email):
            raise ContactConfigurationError(
                'Địa chỉ email người gửi (DEFAULT_FROM_EMAIL) chưa hợp lệ.'
            )

    return from_email


def _clean_single_line(raw_value: Any, field_label: str, min_len: int, max_len: int, required: bool = True) -> str:
    """Strip and validate a single-line input field against header injection and length bounds."""
    if raw_value is None:
        raw_value = ''
    if not isinstance(raw_value, str):
        raise ContactValidationError(f'{field_label} không hợp lệ.')
    if _contains_header_injection(raw_value):
        raise ContactValidationError(f'{field_label} chứa ký tự điều khiển không hợp lệ.')

    cleaned = raw_value.strip()
    if not cleaned:
        if required:
            raise ContactValidationError(f'Vui lòng nhập {field_label.lower()}.')
        return ''

    if len(cleaned) < min_len:
        raise ContactValidationError(f'{field_label} phải có ít nhất {min_len} ký tự.')
    if len(cleaned) > max_len:
        raise ContactValidationError(f'{field_label} không được vượt quá {max_len} ký tự.')
    return cleaned


def validate_contact_payload(data: Dict[str, Any]) -> Dict[str, str]:
    """
    Validate and sanitize contact form fields submitted from the landing page.

    Any client-supplied recipient/sender overrides are ignored by design.
    """
    if not isinstance(data, dict):
        raise ContactValidationError('Dữ liệu gửi lên không hợp lệ.')

    # Honeypot anti-spam trap: bots often populate hidden website/url fields
    honeypot = str(data.get('website') or data.get('hp_field') or '').strip()
    if honeypot:
        raise ContactValidationError('Yêu cầu không hợp lệ.', status_code=400)

    full_name = _clean_single_line(
        data.get('full_name') or data.get('fullName') or data.get('name'),
        'Họ và tên',
        MIN_FULL_NAME_LEN,
        MAX_FULL_NAME_LEN,
        required=True,
    )

    raw_email = data.get('email')
    if not isinstance(raw_email, str) or _contains_header_injection(raw_email):
        raise ContactValidationError('Địa chỉ email không hợp lệ.')
    email = raw_email.strip()
    if not email:
        raise ContactValidationError('Vui lòng nhập địa chỉ email.')
    if len(email) > MAX_EMAIL_LEN:
        raise ContactValidationError(f'Email không được vượt quá {MAX_EMAIL_LEN} ký tự.')
    try:
        validate_email(email)
    except DjangoValidationError as exc:
        raise ContactValidationError('Địa chỉ email không đúng định dạng.') from exc

    company = _clean_single_line(
        data.get('company') or data.get('organization'),
        'Công ty / Tổ chức',
        0,
        MAX_COMPANY_LEN,
        required=False,
    )

    subject = _clean_single_line(
        data.get('subject') or data.get('topic'),
        'Chủ đề',
        MIN_SUBJECT_LEN,
        MAX_SUBJECT_LEN,
        required=True,
    )

    raw_message = data.get('message') or data.get('content') or data.get('body')
    if not isinstance(raw_message, str):
        raise ContactValidationError('Nội dung liên hệ không hợp lệ.')
    if '\x00' in raw_message:
        raise ContactValidationError('Nội dung liên hệ chứa ký tự không hợp lệ.')
    message = raw_message.strip()
    if not message:
        raise ContactValidationError('Vui lòng nhập nội dung liên hệ.')
    if len(message) < MIN_MESSAGE_LEN:
        raise ContactValidationError(f'Nội dung liên hệ phải có ít nhất {MIN_MESSAGE_LEN} ký tự.')
    if len(message) > MAX_MESSAGE_LEN:
        raise ContactValidationError(f'Nội dung liên hệ không được vượt quá {MAX_MESSAGE_LEN} ký tự.')

    return {
        'full_name': full_name,
        'email': email,
        'company': company or 'Không cung cấp',
        'subject': subject,
        'message': message,
    }


def get_client_ip(request) -> str:
    """Extract client IP address for rate limiting."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip() or 'unknown'
    return request.META.get('REMOTE_ADDR', 'unknown') or 'unknown'


def check_and_increment_contact_rate_limit(client_ip: str) -> Tuple[bool, int]:
    """
    Enforce IP-based rate limiting for the public contact endpoint.

    Uses Django's configured cache (Redis) with a thread-safe in-memory fallback
    if the cache backend is unreachable.
    Returns (allowed, remaining_count).
    """
    cache_key = f'eam:contact_rl:{client_ip}'
    try:
        current = cache.get(cache_key)
        if current is None:
            cache.set(cache_key, 1, timeout=RATE_LIMIT_WINDOW_SECONDS)
            return True, RATE_LIMIT_MAX_REQUESTS - 1
        current_int = int(current)
        if current_int >= RATE_LIMIT_MAX_REQUESTS:
            return False, 0
        try:
            new_val = cache.incr(cache_key)
        except Exception:
            new_val = current_int + 1
            cache.set(cache_key, new_val, timeout=RATE_LIMIT_WINDOW_SECONDS)
        return True, max(0, RATE_LIMIT_MAX_REQUESTS - int(new_val))
    except Exception:
        now = time.monotonic()
        with _LOCAL_RATE_LOCK:
            count, expires_at = _LOCAL_RATE_STORE.get(cache_key, (0, 0.0))
            if now >= expires_at:
                _LOCAL_RATE_STORE[cache_key] = (1, now + RATE_LIMIT_WINDOW_SECONDS)
                return True, RATE_LIMIT_MAX_REQUESTS - 1
            if count >= RATE_LIMIT_MAX_REQUESTS:
                return False, 0
            new_count = count + 1
            _LOCAL_RATE_STORE[cache_key] = (new_count, expires_at)
            return True, max(0, RATE_LIMIT_MAX_REQUESTS - new_count)


def send_super_admin_contact_email(cleaned_data: Dict[str, str]) -> str:
    """
    Send the validated visitor contact request to the System Super Admin.

    Returns the resolved recipient email address upon successful SMTP acceptance.
    """
    from_email = ensure_smtp_configured()
    recipient_email = resolve_system_super_admin_email()

    body = (
        "Bạn nhận được một yêu cầu liên hệ mới từ trang giới thiệu Hệ thống EAM.\n\n"
        "Thông tin người gửi:\n"
        f"- Họ và tên: {cleaned_data['full_name']}\n"
        f"- Email: {cleaned_data['email']}\n"
        f"- Công ty / Tổ chức: {cleaned_data['company']}\n"
        f"- Chủ đề: {cleaned_data['subject']}\n\n"
        "Nội dung liên hệ:\n"
        f"{cleaned_data['message']}\n"
    )

    _, parsed_from = parseaddr(from_email)
    sender_domain = parsed_from.split('@', 1)[1] if '@' in parsed_from else None
    msg_headers = {}
    if sender_domain and not sender_domain.lower().endswith(('.local', '.internal')):
        msg_headers['Message-ID'] = make_msgid(domain=sender_domain)

    email_msg = EmailMessage(
        subject=CONTACT_EMAIL_SUBJECT,
        body=body,
        from_email=from_email,
        to=[recipient_email],
        reply_to=[cleaned_data['email']],
        headers=msg_headers or None,
    )

    try:
        sent_count = email_msg.send(fail_silently=False)
    except Exception as exc:
        logger.error(
            'Contact email delivery failed (%s)',
            type(exc).__name__,
        )
        raise ContactDeliveryError(
            'Không thể gửi yêu cầu liên hệ qua máy chủ email vào lúc này. Vui lòng thử lại sau.'
        ) from exc

    if sent_count < 1:
        logger.error('Contact email delivery returned sent_count=%s', sent_count)
        raise ContactDeliveryError(
            'Máy chủ email không xác nhận gửi thư. Vui lòng thử lại sau.'
        )

    return recipient_email
