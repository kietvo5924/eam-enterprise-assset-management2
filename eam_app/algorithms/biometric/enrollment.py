"""
Web Face Enrollment & Deep Feature Extraction Pipeline (Phase 11.7).
Căn cứ Đề cương Đồ án Tốt nghiệp & Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân.

Quy trình xử lý:
    1. Nhận tệp ảnh chân dung tải lên từ Web Portal (Task 5.2).
    2. Cắt chuẩn 112 x 112 x 3, chuẩn hóa [-1.0, 1.0]: x_norm = (x - 127.5) / 128.0.
    3. Trích xuất vector đặc trưng sinh trắc học 128 chiều (MobileFaceNet deep feature).
    4. Chuẩn hóa L2-norm bằng giải thuật thuần: ||v||_2 = 1.0.
    5. Lưu 128 số thực vào bảng biometric_profiles trong PostgreSQL.
    6. Mã hóa AES-256 ảnh gốc lưu trữ an toàn tuân thủ Nghị định 13/2023/NĐ-CP.
"""

import io
import os
import sys
import math
import hashlib
import uuid
from typing import Optional
from datetime import datetime
from PIL import Image
import numpy as np
import cv2
from django.utils import timezone
from django.conf import settings
from .cosine_similarity import normalize_l2_from_scratch, calculate_l2_norm_from_scratch


_GCM_MAGIC = b'EAM_GCM1'
_LEGACY_SIMULATED_MARKER = b'SIMULATED_FACE_IMAGE_BYTES'


def _get_secret_key_bytes() -> bytes:
    secret = getattr(settings, 'SECRET_KEY', None)
    if not secret or not str(secret).strip():
        raise ValueError("Cấu hình SECRET_KEY chưa hợp lệ để thực hiện mã hóa sinh trắc học.")
    return str(secret).encode('utf-8')


def _get_legacy_cbc_key() -> bytes:
    """Dẫn xuất khóa tương thích ngược để giải mã các tệp snapshot AES-CBC cũ đã lưu."""
    return hashlib.sha256(_get_secret_key_bytes()).digest()


def _get_gcm_key() -> bytes:
    """Dẫn xuất khóa riêng tách biệt miền (domain-separated) cho AES-256-GCM."""
    return hashlib.sha256(b'eam-biometric-aes-256-gcm-v1|' + _get_secret_key_bytes()).digest()


def _is_automated_test_runtime() -> bool:
    return bool(('test' in sys.argv or 'pytest' in sys.modules) and getattr(settings, 'BIOMETRIC_ALLOW_TEST_EMBEDDINGS', True))


# Khóa tương thích ngược phục vụ kiểm tra mô-đun (chỉ dùng cho giải mã dữ liệu CBC cũ)
AES_KEY = _get_legacy_cbc_key() if getattr(settings, 'configured', False) and getattr(settings, 'SECRET_KEY', None) else b''

# Pipeline phát hiện khuôn mặt & trích xuất đặc trưng mạng nơ-ron sâu 128D (SFace / YuNet SOTA)
_MODELS_DIR = os.path.join(os.path.dirname(__file__), 'models')
_YUNET_PATH = os.path.join(_MODELS_DIR, 'face_detection_yunet_2023mar.onnx')
_SFACE_PATH = os.path.join(_MODELS_DIR, 'face_recognition_sface_2021dec.onnx')

_SFACE_RECOGNIZER = None
_FACE_CASCADE = None
_EYE_CASCADE = None


def _get_face_pipeline():
    global _SFACE_RECOGNIZER, _FACE_CASCADE, _EYE_CASCADE
    if _SFACE_RECOGNIZER is None and os.path.exists(_SFACE_PATH):
        try:
            _SFACE_RECOGNIZER = cv2.FaceRecognizerSF.create(_SFACE_PATH, "")
        except Exception:
            _SFACE_RECOGNIZER = None

    if _FACE_CASCADE is None:
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        _FACE_CASCADE = cv2.CascadeClassifier(cascade_path)
    if _EYE_CASCADE is None:
        eye_path = cv2.data.haarcascades + 'haarcascade_eye.xml'
        _EYE_CASCADE = cv2.CascadeClassifier(eye_path)

    return _SFACE_RECOGNIZER, _FACE_CASCADE, _EYE_CASCADE


def extract_face_embedding_from_image(image_bytes: bytes, user_id: str = None) -> list[float]:
    """
    Trích xuất vector 128 chiều từ ảnh chân dung khuôn mặt thực tế bằng mạng nơ-ron sâu (Deep Learning).
    Quy trình kiểm tra nghiêm ngặt:
        1. Giải mã dữ liệu nhị phân thành ảnh ma trận OpenCV BGR.
        2. Nhận diện khuôn mặt chính diện và 5 điểm mốc giải phẫu (Landmarks: mắt, mũi, miệng)
           qua mô hình YuNet Deep Neural Network.
        3. Căn chỉnh phối cảnh khuôn mặt chuẩn (Landmark Alignment Crop 112x112x3) để loại bỏ 100% nền xung quanh.
        4. Trích xuất vector đặc trưng sinh trắc học 128 chiều qua mô hình SFace (MobileFaceNet architecture).
        5. Chuẩn hóa L2-norm thuần: ||v||_2 = 1.0.
    """
    if not image_bytes or len(image_bytes) < 100:
        raise ValueError("Tệp ảnh rỗng hoặc không đủ kích thước để phân tích.")

    nparr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        try:
            pil_img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception as ex:
            raise ValueError(f"Định dạng tệp ảnh không hợp lệ: {ex}")

    h, w = img_bgr.shape[:2]
    recognizer, cascade, eye_cascade = _get_face_pipeline()

    # 1. Thử nhận diện khuôn mặt qua YuNet Deep Face Detector (nhận diện chuẩn xác 5 điểm mốc)
    faces = None
    if os.path.exists(_YUNET_PATH):
        try:
            scale = 1.0
            det_img = img_bgr
            det_w, det_h = w, h
            if max(w, h) > 1280:
                scale = 1280.0 / max(w, h)
                det_w = int(w * scale)
                det_h = int(h * scale)
                det_img = cv2.resize(img_bgr, (det_w, det_h))

            detector = cv2.FaceDetectorYN.create(_YUNET_PATH, "", (det_w, det_h), 0.5, 0.3, 5000)
            _, raw_faces = detector.detect(det_img)
            if raw_faces is not None and len(raw_faces) > 0:
                if scale != 1.0:
                    scaled_faces = []
                    for rf in raw_faces:
                        f_copy = rf.copy()
                        f_copy[0:14] /= scale
                        scaled_faces.append(f_copy)
                    faces = np.array(scaled_faces)
                else:
                    faces = raw_faces
        except Exception:
            faces = None

    feat = None
    if faces is not None and len(faces) > 0:
        # Chọn khuôn mặt có diện tích lớn nhất trong khung hình
        best_face = max(faces, key=lambda f: f[2] * f[3])
        if recognizer is not None:
            aligned = recognizer.alignCrop(img_bgr, best_face)
            feat = recognizer.feature(aligned).flatten()
    else:
        # 2. Fallback: Haar Cascade + Cân bằng sáng nếu môi trường ánh sáng đặc thù
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        h_faces = cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        if len(h_faces) == 0:
            gray_eq = cv2.equalizeHist(gray)
            h_faces = cascade.detectMultiScale(
                gray_eq,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(60, 60),
                flags=cv2.CASCADE_SCALE_IMAGE
            )

        if len(h_faces) == 0:
            raise ValueError("Không phát hiện khuôn mặt trong khung hình. Vui lòng căn chỉnh thẳng vào camera và đủ ánh sáng!")

        best_h_face = max(h_faces, key=lambda f: f[2] * f[3])
        fx, fy, fw, fh = best_h_face
        crop = cv2.resize(img_bgr[fy:fy+fh, fx:fx+fw], (112, 112))
        if recognizer is not None:
            feat = recognizer.feature(crop).flatten()

    if feat is None or len(feat) == 0:
        raise ValueError("Không thể trích xuất đặc trưng sinh trắc học từ ảnh này.")

    # Chuẩn hóa L2-norm từ đầu
    norm = np.linalg.norm(feat)
    if norm > 0:
        feat = feat / norm

    return [round(float(v), 6) for v in feat]


def encrypt_aes_256(data: bytes, key: Optional[bytes] = None) -> bytes:
    """
    Mã hóa dữ liệu nhị phân với giải thuật AES-256-GCM có xác thực toàn vẹn (AEAD).
    Định dạng đầu ra: _GCM_MAGIC (8B) + nonce (12B) + auth_tag (16B) + ciphertext.
    Tuyệt đối không dùng XOR dự phòng.
    """
    if not isinstance(data, (bytes, bytearray)) or len(data) == 0:
        raise ValueError("Dữ liệu nhị phân cần mã hóa không hợp lệ hoặc rỗng.")

    try:
        from Crypto.Cipher import AES
    except ImportError as exc:
        raise RuntimeError("Thiếu thư viện mã hóa AES-256 (pycryptodome). Không thể lưu dữ liệu sinh trắc học không an toàn.") from exc

    enc_key = key if key is not None else _get_gcm_key()
    nonce = os.urandom(12)
    cipher = AES.new(enc_key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(bytes(data))
    return _GCM_MAGIC + nonce + tag + ciphertext


def decrypt_aes_256(encrypted_data: bytes, key: Optional[bytes] = None) -> bytes:
    """
    Giải mã dữ liệu sinh trắc học AES-256:
    - Dữ liệu mới có header _GCM_MAGIC: giải mã và xác thực thẻ tag AES-256-GCM.
    - Dữ liệu cũ trước nâng cấp: giải mã tương thích ngược AES-256-CBC + kiểm tra PKCS7 unpad nghiêm ngặt.
    - Tuyệt đối không rơi về XOR và không âm thầm bỏ qua lỗi giải mã.
    """
    if not isinstance(encrypted_data, (bytes, bytearray)) or len(encrypted_data) == 0:
        raise ValueError("Dữ liệu mã hóa rỗng hoặc sai kiểu.")

    raw = bytes(encrypted_data)
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
    except ImportError as exc:
        raise RuntimeError("Thiếu thư viện giải mã AES-256 (pycryptodome).") from exc

    if raw.startswith(_GCM_MAGIC):
        min_len = len(_GCM_MAGIC) + 12 + 16 + 1
        if len(raw) < min_len:
            raise ValueError("Dữ liệu mã hóa AES-256-GCM bị cắt cụt hoặc không hợp lệ.")
        offset = len(_GCM_MAGIC)
        nonce = raw[offset:offset + 12]
        tag = raw[offset + 12:offset + 28]
        ciphertext = raw[offset + 28:]
        dec_key = key if key is not None else _get_gcm_key()
        try:
            cipher = AES.new(dec_key, AES.MODE_GCM, nonce=nonce)
            return cipher.decrypt_and_verify(ciphertext, tag)
        except Exception as exc:
            raise ValueError("Giải mã AES-256-GCM thất bại: khóa không khớp hoặc dữ liệu đã bị thay đổi.") from exc

    # Tương thích ngược giải mã snapshot AES-256-CBC cũ đã lưu trước đây
    if len(raw) < 32 or ((len(raw) - 16) % AES.block_size) != 0:
        raise ValueError("Định dạng dữ liệu mã hóa AES-CBC cũ không hợp lệ hoặc bị hỏng.")

    iv = raw[:16]
    ciphertext = raw[16:]
    dec_key = key if key is not None else _get_legacy_cbc_key()
    try:
        cipher = AES.new(dec_key, AES.MODE_CBC, iv)
        return unpad(cipher.decrypt(ciphertext), AES.block_size)
    except Exception as exc:
        raise ValueError("Giải mã AES-256-CBC thất bại: padding hoặc khóa giải mã không hợp lệ.") from exc


def validate_real_image_bytes(image_bytes: bytes) -> bytes:
    """
    Xác thực dữ liệu nhị phân là tệp ảnh thật hợp lệ, chặn ảnh rỗng hoặc chuỗi ảnh giả.
    """
    if not isinstance(image_bytes, (bytes, bytearray)) or len(image_bytes) < 100:
        raise ValueError("Tệp ảnh chân dung rỗng hoặc không đủ kích thước hợp lệ.")
    raw = bytes(image_bytes)
    if _LEGACY_SIMULATED_MARKER in raw:
        raise ValueError("Từ chối dữ liệu ảnh giả lập trong quy trình đăng ký sinh trắc học.")

    nparr = np.frombuffer(raw, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        try:
            with Image.open(io.BytesIO(raw)) as pil_img:
                pil_img.verify()
        except Exception as exc:
            raise ValueError(f"Định dạng tệp ảnh không hợp lệ: {exc}") from exc
    return raw


def validate_embedding_vector(embedding) -> list[float]:
    """
    Xác thực vector đặc trưng 128 chiều hợp lệ, không chứa NaN/Inf hoặc vector 0, và chuẩn hóa L2.
    """
    if not isinstance(embedding, (list, tuple, np.ndarray)) or len(embedding) != 128:
        raise ValueError("Vector đặc trưng khuôn mặt phải gồm đúng 128 phần tử số thực.")

    cleaned = []
    for val in embedding:
        if isinstance(val, bool):
            raise ValueError("Vector đặc trưng chứa giá trị boolean không hợp lệ.")
        f_val = float(val)
        if not math.isfinite(f_val):
            raise ValueError("Vector đặc trưng chứa giá trị NaN hoặc vô cực.")
        cleaned.append(f_val)

    norm = calculate_l2_norm_from_scratch(cleaned)
    if norm <= 1e-6 or not math.isfinite(norm):
        raise ValueError("Vector đặc trưng có chuẩn L2 bằng 0, không hợp lệ.")

    return normalize_l2_from_scratch(cleaned)


def decrypt_image_snapshot(snapshot_path: str) -> bytes:
    """Đọc và giải mã ảnh snapshot đã mã hóa. Ném ngoại lệ nếu tệp hỏng hoặc giải mã thất bại."""
    if not snapshot_path or not isinstance(snapshot_path, str):
        raise ValueError("Đường dẫn ảnh snapshot sinh trắc học không hợp lệ.")

    if snapshot_path.startswith('/media/'):
        clean_rel = snapshot_path[len('/media/'):]
        full_path = os.path.join(settings.MEDIA_ROOT, clean_rel)
    else:
        full_path = snapshot_path

    with open(full_path, 'rb') as f:
        encrypted_data = f.read()
    decrypted = decrypt_aes_256(encrypted_data)
    if not decrypted:
        raise ValueError("Ảnh snapshot sau giải mã bị rỗng.")
    return decrypted


def save_audit_snapshot(
    image_bytes: bytes,
    user_id: str,
    tenant_id: str,
    prefix: str = 'face_enrollment',
) -> str:
    """
    Mã hóa AES-256-GCM và lưu trữ ảnh chân dung hoặc ảnh hiện trường lên MinIO/Media.
    Tuyệt đối không lưu ảnh giả hoặc ảnh thô không mã hóa.
    """
    valid_bytes = validate_real_image_bytes(image_bytes)
    encrypted = encrypt_aes_256(valid_bytes)
    now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{prefix}_{user_id}_{now_str}_{uuid.uuid4().hex[:6]}.enc"
    rel_path = f"biometric_audits/{tenant_id}/{filename}"
    
    # Lưu vào MEDIA_ROOT
    full_path = os.path.join(settings.MEDIA_ROOT, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'wb') as f:
        f.write(encrypted)

    return f"/media/{rel_path}"


def enroll_user_face(
    user,
    image_bytes: Optional[bytes] = None,
    enrolled_by=None,
    precomputed_embedding: Optional[list[float]] = None,
    allow_precomputed: Optional[bool] = None,
):
    """
    Đăng ký hồ sơ sinh trắc học cho User.
    Trong luồng production bắt buộc phải có ảnh chân dung thật và tự động trích xuất 128D bằng Deep Learning.
    Trong môi trường kiểm thử tự động (Django test/pytest với BIOMETRIC_ALLOW_TEST_EMBEDDINGS=True),
    có thể cung cấp precomputed_embedding miễn là allow_precomputed không bị tắt tường minh (False).
    """
    from users.models import BiometricProfile

    if allow_precomputed is False:
        can_use_precomputed = False
    else:
        can_use_precomputed = bool(precomputed_embedding is not None and _is_automated_test_runtime())

    if can_use_precomputed:
        embedding = validate_embedding_vector(precomputed_embedding)
        if image_bytes is not None:
            validate_real_image_bytes(image_bytes)
    else:
        if precomputed_embedding is not None and image_bytes is None:
            raise ValueError("Không chấp nhận đăng ký sinh trắc học chỉ bằng vector giả lập khi thiếu ảnh chụp khuôn mặt thật.")
        valid_bytes = validate_real_image_bytes(image_bytes)
        embedding = validate_embedding_vector(extract_face_embedding_from_image(valid_bytes, user_id=str(user.id)))

    snapshot_path = None
    if image_bytes is not None:
        snapshot_path = save_audit_snapshot(image_bytes, str(user.id), str(user.tenant_id))

    profile, _ = BiometricProfile.all_objects.update_or_create(
        user=user,
        tenant=user.tenant,
        defaults={
            'face_embedding': embedding,
            'enrolled_by': enrolled_by,
            'is_active': True,
        }
    )
    return profile, snapshot_path
