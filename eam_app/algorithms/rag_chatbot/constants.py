"""
Constants and configurations for Task 11.9: Intelligent AI Assistant / Chatbot (RAG).
Includes:
- Industrial slang and onomatopoeia dictionary
- Context-aware life-safety hazard classifications and instructions
- Similarity tiers and thresholds
- System prompt templates
"""

# 1. Từ điển tiếng lóng & từ tượng thanh bảo trì công nghiệp phong phú
SLANG_TECHNICAL_DICTIONARY = {
    # Hiện tượng cơ học & Vòng bi / Trục
    'lạch cạch': 'mechanical looseness cavitation bearing vibration',
    'kêu lạch cạch': 'mechanical looseness cavitation bearing vibration',
    'cọc cọc': 'bearing clearance excessive radial play mechanical looseness',
    'kêu cọc cọc': 'bearing clearance excessive radial play mechanical looseness',
    'kêu rột rột': 'bearing race spalling mechanical abrasion friction',
    'rột rột': 'bearing race spalling mechanical abrasion friction',
    'kêu è è': 'electromagnetic hum motor stator unbalance magnetostriction',
    'kêu o o': 'high frequency resonance motor electrical hum',
    'rít rít': 'belt slip dry friction lack of lubrication',
    'kêu rít rít': 'belt slip dry friction lack of lubrication',
    'kêu két két': 'metal to metal contact dry friction unlubricated journal',
    'két két': 'metal to metal contact dry friction unlubricated journal',
    'kêu lục cục': 'gear tooth chipping misalignment backlash abnormality',
    'lục cục': 'gear tooth chipping misalignment backlash abnormality',
    'rơ bạc đạn': 'bearing clearance excessive radial play mechanical looseness',
    'rơ lắc': 'shaft runout excessive clearance spindle looseness',
    'đảo đầu trục': 'shaft eccentricity bent shaft dynamic unbalance',
    'cháy bạc': 'bearing burn out seizure thermal expansion failure',
    'dơ bạc': 'bearing contamination particulate ingress lubrication degradation',
    'bó bạc': 'bearing seizure thermal lock journal freeze',
    'lỏng bu lông': 'loosened bolt fastener fatigue insufficient torque',
    'tuôn gai': 'thread stripped fastener failure thread shear',
    'tuôn ren': 'thread stripped fastener failure thread shear',

    # Thủy lực & Khí nén
    'xì xèo': 'gas leakage pressure relief valve discharging',
    'chết heo': 'brake caliper seizure hydraulic cylinder failure',
    'kẹt ty': 'valve spindle seizure hydraulic piston jamming',
    'xì phốt': 'mechanical seal leakage oil gasket blow out',
    'xì phớt': 'mechanical seal leakage oil gasket blow out',
    'rỉ phốt': 'slow hydraulic seal seepage gasket weep',
    'rò phớt': 'mechanical seal leakage oil gasket blow out',
    'hụt hơi': 'suction loss flow rate drop insufficient pressure',
    'xì hơi': 'pneumatic leak compressed air pressure loss fitting leak',
    'tuột áp': 'pressure drop hydraulic pump failure internal bypass',
    'tụt áp': 'pressure drop hydraulic pump failure internal bypass',
    'tụt ben': 'hydraulic cylinder drift check valve internal leak',
    'bơm giật': 'hydraulic pump pulsation line hammer pressure surge',
    'rung ống': 'hydraulic line cavitation fluid pulsation pipe vibration',
    'sủi bọt dầu': 'oil aeration foam formation cavitation pump suction leak',
    'dầu nhũ hóa': 'hydraulic oil water contamination emulsification',
    'dầu bị nhũ hóa': 'hydraulic oil water contamination emulsification',
    'nghẹt van': 'hydraulic proportional valve spool blockage contamination',
    'ngẹt van': 'hydraulic valve spool blockage particulate entrapment',
    'nghẹt lược': 'oil suction filter strainer clogging high differential pressure',

    # Điện & Tự động hóa
    'phù tụ': 'capacitor bulging dielectric breakdown overvoltage',
    'tụ phù': 'capacitor bulging dielectric breakdown overvoltage',
    'tụ bị phù': 'capacitor bulging dielectric breakdown overvoltage',
    'nổ tụ': 'capacitor catastrophic dielectric breakdown burst',
    'chập điện': 'electrical short circuit insulation failure flashover',
    'cháy cuộn': 'stator winding insulation burn out interturn short circuit',
    'nhảy cb': 'circuit breaker trip overload fault short circuit',
    'nhảy aptomat': 'circuit breaker trip overcurrent protective release',
    'rò điện': 'insulation leakage grounding fault residual current',
    'giật tê tê': 'chassis ground leakage floating voltage grounding defect',
    'mất pha': 'phase loss single phasing unbalanced motor supply',
    'lệch pha': 'three phase voltage unbalance neutral drift',
    'sụt áp': 'line voltage drop feeder impedance transient dip',
    'treo biến tần': 'inverter drive fault freeze overvoltage trip err code',
    'báo lỗi f': 'vfd inverter error code fault trip parameter latch',
    'loạn cảm ứng': 'inductive sensor noise false trigger emi interference',
    'chết rơ le': 'relay coil failure burnt contacts stuck armature',
    'dính tiếp điểm': 'contactor contact welding arc erosion stuck closed',

    # Truyền động cơ cấu & Ly hợp / Phanh
    'cháy bố': 'clutch friction lining burn overheating slippage',
    'mòn bố': 'brake lining wear friction pad degradation',
    'trượt bố': 'clutch slippage torque transfer loss lining glazing',
    'trượt đai': 'v-belt slippage pulley groove wear low belt tension',
    'chùng xích': 'drive chain elongation pitch wear loose tensioner',
    'nhảy xích': 'chain sprocket tooth skip excessive sag worn teeth',
    'mòn nhông': 'sprocket gear tooth wear profile degradation',
    'mẻ răng': 'gear tooth breakage spalling shock load defect',
    'kẹt ray': 'linear guide rail binding recirculating ball jam',
    'trật khớp': 'coupling misalignment flexible element shear offset',
    'bó thắng': 'brake caliper seizure thermal drag lockup',
    'kẹt phanh': 'brake mechanical freeze solenoid coil burn out',
}

# 2. Phân loại tình huống nguy cấp sinh mạng theo nguy cơ mở rộng
EMERGENCY_HAZARDS = {
    'ELECTRICAL_FIRE': {
        'name': 'Chập điện / Cháy máy biến áp / Tủ điện MSB',
        'keywords': [
            'cháy dầu máy biến áp', 'cháy biến áp', 'cháy tủ điện', 
            'chập điện bốc khói', 'chập cháy biến áp', 'cháy nổ máy biến áp', 
            'đang bốc khói khẩn cấp', 'cháy dầu', 'dập lửa dầu biến áp',
            'cháy dầu biến áp', 'dập lửa biến áp', 'chữa cháy biến áp',
            'dập lửa trạm biến áp', 'dập lửa máy biến áp', 'hồ quang điện',
            'nổ tủ điện', 'phóng điện cao thế', 'bốc khói trạm điện'
        ],
        'action_summary': 'CẮT ĐIỆN TỔNG + DÙNG BÌNH KHÍ/BỘT + TUYỆT ĐỐI CẤM DÙNG NƯỚC',
        'instruction': (
            "⚡ **CẢNH BÁO NGUY HIỂM TÍNH MẠNG - SỰ CỐ CHÁY ĐIỆN / BIẾN ÁP!**\n\n"
            "1. **CẮT NGAY CẦU DAO TỔNG** tủ điện phân phối và kích hoạt ngắt nguồn cách ly LOTO.\n"
            "2. **Sử dụng bình chữa cháy khí CO2, khí sạch FM200 hoặc bột khô ABC** để dập lửa.\n"
            "3. **TUYỆT ĐỐI CẤM DÙNG NƯỚC** để xối vào đám cháy thiết bị điện hoặc dầu biến áp (nguy cơ phóng điện cao áp giết người và nổ dầu bắn lan truyền).\n"
            "4. Sơ tán toàn bộ nhân sự khỏi khu vực nhiễm khói độc và gọi ngay Đội PCCC cơ sở / 114."
        )
    },
    'GAS_LEAK': {
        'name': 'Rò rỉ khí gas / Khí độc / Ngạt khí Amoniac',
        'keywords': [
            'rò rỉ khí độc', 'xì khí gas', 'rò rỉ gas', 'mùi gas nồng nặc', 
            'xì khí độc', 'vỡ đường ống gas', 'thoát khí độc', 'rò khí gas',
            'rò rỉ khí gas', 'xì gas', 'rò rỉ amoniac', 'xì khí nh3',
            'mùi clo nồng nặc', 'ngạt khí buồng kín', 'xì khí gas lạnh'
        ],
        'action_summary': 'SƠ TÁN NGƯỢC CHIỀU GIÓ + CẤM BẬT/TẮT ĐIỆN + KHÓA VAN NGOÀI TRỜI',
        'instruction': (
            "☣️ **CẢNH BÁO NGUY HIỂM TÍNH MẠNG - RÒ RỈ KHÍ ĐỘC / KHÍ GAS!**\n\n"
            "1. **SƠ TÁN TOÀN BỘ NHÂN VIÊN** ngay lập tức theo hướng **NGƯỢC CHIỀU GIÓ**.\n"
            "2. **TUYỆT ĐỐI CẤM** bật/tắt thiết bị điện, công tắc đèn hoặc tạo ra bất kỳ tia lửa điện nào.\n"
            "3. Đóng van khóa chặn nguồn cấp khí ngoài trời (chỉ thực hiện nếu đứng ngoài luồng khí độc).\n"
            "4. Báo động toàn phân xưởng và gọi ngay đội cứu nạn khẩn cấp chuyên dụng."
        )
    },
    'MECHANICAL_ENTRANGLEMENT': {
        'name': 'Kẹt cơ cấu truyền động / Nguy cơ nghiền ép / Máy dập',
        'keywords': [
            'kẹt tay', 'kẹt chân', 'nghiền ép', 'kẹt cơ cấu', 
            'cuốn vào trục', 'kẹt người', 'kẹt vào băng tải', 'mắc kẹt trong máy',
            'kẹt vào máy', 'kẹt máy ép', 'ép dập tay', 'bị cuốn vào xích',
            'kẹt robot công nghiệp'
        ],
        'action_summary': 'BẤM NGAY NÚT E-STOP + KHÓA NGUỒN LOTO + GỌI Y TẾ KHẨN CẤP',
        'instruction': (
            "⚙️ **CẢNH BÁO NGUY HIỂM TÍNH MẠNG - KẸT CƠ CẤU TRUYỀN ĐỘNG / NGHIỀN ÉP!**\n\n"
            "1. **BẤM NGAY NÚT DỪNG KHẨN CẤP (E-STOP)** trên máy hoặc giật dây an toàn tuyến chuyền.\n"
            "2. Thực hiện cách ly khóa nguồn động lực (Lockout/Tagout - LOTO) và xả triệt để áp tích cơ/thủy lực trước khi tiếp cận.\n"
            "3. Không đảo chiều động cơ đột ngột tránh gây thêm chấn thương thứ cấp cho nạn nhân.\n"
            "4. Gọi trợ giúp y tế khẩn cấp và đội cứu hộ nhà máy."
        )
    },
    'CHEMICAL_ACID_SPILL': {
        'name': 'Axit / Hóa chất ăn mòn bắn vào người / Bỏng kiềm',
        'keywords': [
            'axit bắn', 'hóa chất văng', 'bỏng axit', 'hóa chất vào mắt', 
            'bắn hóa chất', 'axit văng vào người', 'bỏng hóa chất',
            'dính axit', 'bắn axit', 'bắn xút', 'bỏng kiềm', 'bắn hóa chất tẩy rửa'
        ],
        'action_summary': 'BỒN RỬA MẮT KHẨN CẤP XỐI NƯỚC 15 PHÚT + GỌI CẤP CỨU',
        'instruction': (
            "🧪 **CẢNH BÁO NGUY HIỂM TÍNH MẠNG - HÓA CHẤT / AXIT ĂN MÒN BẮN VÀO NGƯỜI!**\n\n"
            "1. **ĐƯA NẠN NHÂN ĐẾN NGAY BỒN RỬA MẮT / VÒI TẮM KHẨN CẤP** gần nhất.\n"
            "2. **XỐI NƯỚC SẠCH LIÊN TỤC TỐI THIỂU 15 PHÚT** vào vùng mắt/da dính hóa chất.\n"
            "3. Cởi bỏ ngay quần áo dính hóa chất trong khi đang xối nước, không chà xát mạnh.\n"
            "4. Đưa ngay nạn nhân cùng phiếu an toàn hóa chất (MSDS) đến cơ sở y tế gần nhất."
        )
    },
    'PRESSURE_EXPLOSION': {
        'name': 'Nguy cơ nổ bình áp lực / Nồi hơi / Nổ bình tích áp',
        'keywords': [
            'quá áp bình khí', 'nổ bình tích áp', 'bình khí nén rung lắc mạnh',
            'đồng hồ áp vượt vạch đỏ', 'xì van an toàn liên tục', 'nứt bình áp lực'
        ],
        'action_summary': 'CẮT CẤP NGUỒN BƠM ÁP + SƠ TÁN BÁN KÍNH 50M + MỞ VAN XẢ TỰ ĐỘNG TỪ XA',
        'instruction': (
            "💥 **CẢNH BÁO NGUY HIỂM TÍNH MẠNG - NGUY CƠ NỔ BÌNH ÁP LỰC CAO!**\n\n"
            "1. **NGẮT NGUỒN ĐỘNG CƠ BƠM ÁP LỰC** ngay lập tức từ tủ điều khiển trung tâm từ xa.\n"
            "2. **SƠ TÁN TOÀN BỘ KHU VỰC** trong bán kính tối thiểu 50 mét, cảnh báo mảnh văng kim loại.\n"
            "3. Kích hoạt van xả áp phụ khẩn cấp nếu có hệ thống điều khiển ngoài tầm nguy hiểm.\n"
            "4. Tuyệt đối không đứng đối diện trực tiếp nắp bình tích áp hoặc đường hàn ống chịu lực."
        )
    }
}

# 3. Từ khóa nhận diện câu hỏi mang tính lý thuyết / phòng ngừa
THEORETICAL_KEYWORDS = [
    'nguyên nhân', 'phòng ngừa', 'tại sao', 'lý thuyết', 
    'biện pháp', 'cơ chế', 'dấu hiệu', 'chu kỳ', 'quy trình định kỳ', 
    'làm thế nào để phòng', 'cách phòng tránh', 'lý do', 'phòng chống',
    'hướng dẫn phòng', 'làm sao để phòng', 'biện pháp phòng'
]

# 4. Từ phủ định an toàn (phủ định trực tiếp hiện tượng nguy cấp)
NEGATION_WORDS = [
    'không bị', 'chưa bị', 'không có rò rỉ', 'không có cháy', 'không có sự cố',
    'chưa thấy', 'chẳng bị', 'không xì', 'chưa xì', 'không cháy', 'chưa bốc khói',
    'chưa nổ', 'không gây', 'không hề cháy', 'chưa hề bốc khói', 'không phải sự cố'
]

# 5. Từ cấm kỵ dùng cho Contradiction Guard
FORBIDDEN_NEGATION_TERMS = [
    'cấm', 'tuyệt đối cấm', 'không được', 'tránh', 'không bao giờ',
    'do not', 'never', 'must not', 'prohibited'
]

# 6. Ngưỡng phân tầng độ tương đồng ngữ nghĩa Cosine (Semantic Match)
SIMILARITY_THRESHOLD_FALLBACK = 0.65
SIMILARITY_THRESHOLD_HIGH = 0.75

SAFE_FALLBACK_MESSAGE = (
    "Hiện chưa có tài liệu kỹ thuật được phê duyệt cho trường hợp này, "
    "vui lòng liên hệ Kỹ sư trưởng."
)

MEDIUM_CONFIDENCE_WARNING = (
    "⚠️ Tài liệu tham khảo có độ tương đồng trung bình (65% - 75%), "
    "kỹ thuật viên cần đối chiếu kỹ thiết bị thực tế trước khi thao tác."
)

DEFAULT_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMENSION = 384
OLLAMA_DEFAULT_MODEL = "llama3:8b"
OLLAMA_BACKUP_MODEL = "qwen2.5:7b"
OLLAMA_TEMPERATURE = 0.1
OLLAMA_TIMEOUT_SECONDS = 10
