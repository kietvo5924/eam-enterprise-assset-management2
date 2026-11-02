"""
Cosine Similarity & L2-Norm Linear Algebra Matcher (100% From-Scratch).
Căn cứ Đề cương Đồ án Tốt nghiệp & Đặc tả Kỹ thuật Phase 11.7.

YÊU CẦU BẮT BUỘC:
    Tự cài đặt giải thuật đại số tuyến tính 100% từ nguyên bản toán học (From Scratch).
    Tuyệt đối KHÔNG dùng thư viện hộp đen bên thứ ba (như scipy.spatial.distance,
    sklearn.metrics hay face_recognition).

Công thức:
    Dot(u, v) = sum(u_i * v_i)
    ||u||_2 = sqrt(sum(u_i^2))
    ||v||_2 = sqrt(sum(v_i^2))
    Cosine Similarity(u, v) = Dot(u, v) / (||u||_2 * ||v||_2)

Ngưỡng phân định sinh trắc học MobileFaceNet:
    - Sim >= 0.72: Xác thực thành công (Verified)
    - 0.65 <= Sim < 0.72: Chưa rõ nét (Indeterminate)
    - Sim < 0.65: Từ chối khuôn mặt (Rejected)
"""

import math


def calculate_l2_norm_from_scratch(vec: list[float]) -> float:
    """
    Tính chuẩn Euclid (L2-norm) của một vector toán học từ đầu:
        ||v||_2 = sqrt(sum(v_i^2))
    An toàn tuyệt đối trước NaN, Inf và kiểu dữ liệu không hợp lệ.
    """
    if not vec:
        return 0.0
    sum_sq = 0.0
    for val in vec:
        try:
            f_val = float(val)
        except (ValueError, TypeError):
            return 0.0
        if not math.isfinite(f_val):
            return 0.0
        sum_sq += f_val * f_val
    if not math.isfinite(sum_sq) or sum_sq <= 0.0:
        return 0.0
    return math.sqrt(sum_sq)


l2_norm_from_scratch = calculate_l2_norm_from_scratch


def dot_product_from_scratch(vec_u: list[float], vec_v: list[float]) -> float:
    """
    Tích vô hướng hai vector từ đầu:
        Dot(u, v) = sum(u_i * v_i)
    """
    if not vec_u or not vec_v or len(vec_u) != len(vec_v):
        return 0.0
    dot = 0.0
    for i in range(len(vec_u)):
        try:
            u_i = float(vec_u[i])
            v_i = float(vec_v[i])
        except (ValueError, TypeError):
            return 0.0
        if not math.isfinite(u_i) or not math.isfinite(v_i):
            return 0.0
        dot += u_i * v_i
    return dot if math.isfinite(dot) else 0.0


def normalize_l2_from_scratch(vec: list[float]) -> list[float]:
    """
    Chuẩn hóa vector về mặt cầu đơn vị siêu không gian R^N:
        v_norm = v / ||v||_2  sao cho ||v_norm||_2 = 1.0
    """
    if not vec:
        return []
    norm = calculate_l2_norm_from_scratch(vec)
    if norm == 0.0 or math.isclose(norm, 0.0, abs_tol=1e-12) or not math.isfinite(norm):
        return [0.0] * len(vec)
    res = []
    for val in vec:
        try:
            f_val = float(val)
        except (ValueError, TypeError):
            return [0.0] * len(vec)
        if not math.isfinite(f_val):
            return [0.0] * len(vec)
        res.append(round(f_val / norm, 6))
    return res


def calculate_cosine_similarity_from_scratch(
    vec_u: list[float],
    vec_v: list[float],
) -> float:
    """
    Tự cài đặt giải thuật Cosine Similarity 100% từ nguyên bản toán học đại số tuyến tính.

    Công thức:
        Dot(u, v) = sum(u_i * v_i)
        ||u||_2 = sqrt(sum(u_i^2)),  ||v||_2 = sqrt(sum(v_i^2))
        Cosine(u, v) = Dot(u, v) / (||u||_2 * ||v||_2)
    """
    if not vec_u or not vec_v or len(vec_u) != len(vec_v):
        return 0.0

    dot_product = 0.0
    norm_u_sq = 0.0
    norm_v_sq = 0.0

    for i in range(len(vec_u)):
        try:
            u_i = float(vec_u[i])
            v_i = float(vec_v[i])
        except (ValueError, TypeError):
            return 0.0
        if not math.isfinite(u_i) or not math.isfinite(v_i):
            return 0.0
        dot_product += u_i * v_i
        norm_u_sq += u_i * u_i
        norm_v_sq += v_i * v_i

    if norm_u_sq <= 0.0 or norm_v_sq <= 0.0:
        return 0.0

    denom = math.sqrt(norm_u_sq) * math.sqrt(norm_v_sq)
    if not math.isfinite(denom) or denom <= 0.0:
        return 0.0

    similarity = dot_product / denom
    if not math.isfinite(similarity):
        return 0.0

    # Kẹp giá trị trong khoảng [-1.0, 1.0] để tránh sai số số thực dấu phẩy động
    similarity = max(-1.0, min(1.0, similarity))
    return round(float(similarity), 4)


def verify_face_cosine_similarity(
    live_vec: list[float],
    profile_vec: list[float],
    threshold: float = 0.72,
) -> tuple[bool, float]:
    """
    Kiểm tra độ khớp khuôn mặt giữa vector thời gian thực từ camera
    và vector hồ sơ đăng ký trên Web với ngưỡng chuẩn 0.72.

    Returns:
        (is_verified: bool, similarity: float)
    """
    sim = calculate_cosine_similarity_from_scratch(live_vec, profile_vec)
    is_verified = (sim >= threshold)
    return is_verified, sim
