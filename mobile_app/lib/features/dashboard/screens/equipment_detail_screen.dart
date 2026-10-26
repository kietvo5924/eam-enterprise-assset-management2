import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../core/theme/app_theme.dart';
import '../../work_orders/services/work_order_service.dart';

class EquipmentDetailScreen extends StatefulWidget {
  final Map<String, dynamic> equipment;

  const EquipmentDetailScreen({super.key, required this.equipment});

  @override
  State<EquipmentDetailScreen> createState() => _EquipmentDetailScreenState();
}

class _EquipmentDetailScreenState extends State<EquipmentDetailScreen> {
  final WorkOrderService _workOrderService = WorkOrderService();

  String _formatCurrency(dynamic value) {
    if (value == null) return 'N/A';
    try {
      final num = double.parse(value.toString());
      final format = NumberFormat.currency(locale: 'vi_VN', symbol: 'VNĐ');
      return format.format(num);
    } catch (e) {
      return value.toString();
    }
  }

  String _formatDate(dynamic dateString) {
    if (dateString == null) return 'N/A';
    try {
      final date = DateTime.parse(dateString.toString());
      return DateFormat('dd/MM/yyyy').format(date);
    } catch (e) {
      return dateString.toString();
    }
  }

  String _formatDutyCycle(dynamic ratio) {
    if (ratio == null) return 'Chạy liên tục 24/7 (3 ca) — Hệ số 1.0';
    final num = double.tryParse(ratio.toString()) ?? 1.0;
    if (num >= 0.95) return 'Chạy liên tục 24/7 (3 ca) — Hệ số 1.0';
    if (num >= 0.70) return 'Chạy 2 ca / 16h mỗi ngày — Hệ số 0.75';
    if (num >= 0.45) return 'Chạy 1 ca 12h / Luân phiên — Hệ số 0.5';
    if (num >= 0.30) return 'Giờ hành chính (8h/ngày, 6 ngày/tuần) — Hệ số 0.33';
    if (num >= 0.20) return 'Giờ hành chính (8h/ngày, 5 ngày/tuần) — Hệ số 0.25';
    return 'Máy dự phòng / Chạy không thường xuyên — Hệ số 0.1';
  }

  @override
  Widget build(BuildContext context) {
    final status =
        widget.equipment['status']?.toString().toUpperCase() ?? 'UNKNOWN';
    Color statusColor = AppTheme.neutral400;
    String statusText = status;

    if (status == 'ACTIVE' || status == 'OPERATIONAL') {
      statusColor = AppTheme.successColor;
      statusText = 'Hoạt động';
    } else if (status == 'MAINTENANCE') {
      statusColor = AppTheme.warningColor;
      statusText = 'Bảo trì';
    } else if (status == 'BROKEN') {
      statusColor = AppTheme.dangerColor;
      statusText = 'Hỏng hóc';
    } else if (status == 'DECOMMISSIONED') {
      statusColor = AppTheme.neutral500;
      statusText = 'Thanh lý';
    } else if (status == 'RESERVED') {
      statusColor = AppTheme.infoColor;
      statusText = 'Đang dự trữ';
    }

    return Scaffold(
      backgroundColor: AppTheme.neutral50,
      appBar: AppBar(
        title: const Text(
          'Chi tiết Tài sản',
          style: TextStyle(
            color: AppTheme.neutral900,
            fontWeight: FontWeight.bold,
            fontSize: 18,
          ),
        ),
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: Icon(PhosphorIcons.arrowLeft(), color: AppTheme.neutral900),
          onPressed: () => context.pop(),
        ),
      ),
      body: SingleChildScrollView(
        child: Column(
          children: [
            // Header Card
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(24),
              decoration: const BoxDecoration(
                color: Colors.white,
                border: Border(bottom: BorderSide(color: AppTheme.neutral200)),
              ),
              child: Column(
                children: [
                  Container(
                    width: 96,
                    height: 96,
                    decoration: BoxDecoration(
                      color: AppTheme.primaryColor.withValues(alpha: 0.1),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      PhosphorIcons.engine(PhosphorIconsStyle.fill),
                      size: 48,
                      color: AppTheme.primaryColor,
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    widget.equipment['name'] ?? 'Chưa có tên',
                    style: const TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w900,
                      color: AppTheme.neutral900,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    widget.equipment['serialNumber'] ?? 'N/A',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.primaryColor,
                      letterSpacing: 1.0,
                    ),
                  ),
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      color: statusColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      statusText.toUpperCase(),
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: statusColor,
                        letterSpacing: 1.5,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Thông tin chung',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.neutral900,
                    ),
                  ),
                  const SizedBox(height: 16),
                  _buildInfoCard([
                    _buildInfoRow(
                      PhosphorIcons.mapPin(),
                      'Vị trí',
                      widget.equipment['locationName'] ?? 'Chưa cấu hình',
                    ),
                    _buildInfoRow(
                      PhosphorIcons.tag(),
                      'Phân loại',
                      widget.equipment['categoryName'] ?? 'Chưa cấu hình',
                    ),
                    _buildInfoRow(
                      PhosphorIcons.barcode(),
                      'Model',
                      widget.equipment['model'] ?? 'N/A',
                    ),
                    _buildInfoRow(
                      PhosphorIcons.factory(),
                      'Nhà sản xuất',
                      widget.equipment['manufacturer'] ?? 'N/A',
                    ),
                    _buildInfoRow(
                      PhosphorIcons.clock(),
                      'Chu kỳ vận hành / Ca kíp',
                      _formatDutyCycle(widget.equipment['dutyCycleRatio']),
                    ),
                  ]),

                  const SizedBox(height: 24),
                  const Text(
                    'Thông tin Mua sắm & Giá trị',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.neutral900,
                    ),
                  ),
                  const SizedBox(height: 16),
                  _buildInfoCard([
                    _buildInfoRow(
                      PhosphorIcons.calendar(),
                      'Ngày mua',
                      _formatDate(widget.equipment['purchaseDate']),
                    ),
                    _buildInfoRow(
                      PhosphorIcons.currencyCircleDollar(),
                      'Giá trị hiện tại',
                      _formatCurrency(widget.equipment['value']),
                    ),
                  ]),

                  const SizedBox(height: 24),
                  const Text(
                    'Tài sản Hệ thống',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.neutral900,
                    ),
                  ),
                  const SizedBox(height: 16),
                  _buildInfoCard([
                    _buildInfoRow(
                      PhosphorIcons.treeStructure(),
                      'Thuộc cụm tài sản',
                      widget.equipment['parentId'] != null
                          ? 'Có (ID: ${widget.equipment['parentId']})'
                          : 'Tài sản độc lập',
                    ),
                    _buildInfoRow(
                      PhosphorIcons.qrCode(),
                      'Mã QR Gắn kết',
                      widget.equipment['qrCode'] ?? 'Chưa tạo mã',
                    ),
                    _buildInfoRow(
                      PhosphorIcons.clock(),
                      'Cập nhật lần cuối',
                      _formatDate(widget.equipment['updatedAt']),
                    ),
                  ]),

                  const SizedBox(height: 40),
                ],
              ),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showLogMeterDialog,
        backgroundColor: AppTheme.primaryColor,
        icon: Icon(
          PhosphorIcons.gauge(PhosphorIconsStyle.fill),
          color: Colors.white,
        ),
        label: const Text(
          'Cập nhật chỉ số',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
      ),
    );
  }

  void _showLogMeterDialog() {
    final valueController = TextEditingController();
    final unitController = TextEditingController(text: 'mm/s');
    final customMetricController = TextEditingController();
    final notesController = TextEditingController();
    String metricCode = 'VIBRATION';
    String machineState = 'RUNNING';
    double loadFactor = 1.0;

    showDialog(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              title: const Text('Cập nhật chỉ số đo kiểm tra', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    DropdownButtonFormField<String>(
                      isExpanded: true,
                      initialValue: metricCode,
                      decoration: const InputDecoration(
                        labelText: 'Loại chỉ số đo',
                        border: OutlineInputBorder(),
                      ),
                      items: const [
                        DropdownMenuItem(value: 'VIBRATION', child: Text('Độ rung RMS (VIBRATION)')),
                        DropdownMenuItem(value: 'TEMPERATURE', child: Text('Nhiệt độ (TEMPERATURE)')),
                        DropdownMenuItem(value: 'PRESSURE', child: Text('Áp suất (PRESSURE)')),
                        DropdownMenuItem(value: 'CURRENT', child: Text('Dòng điện (CURRENT)')),
                        DropdownMenuItem(value: 'VOLTAGE', child: Text('Điện áp (VOLTAGE)')),
                        DropdownMenuItem(value: 'RPM', child: Text('Tốc độ vòng quay (RPM)')),
                        DropdownMenuItem(value: 'FLOW_RATE', child: Text('Lưu lượng (FLOW_RATE)')),
                        DropdownMenuItem(value: 'OIL_LEVEL', child: Text('Mức dầu bôi trơn (OIL_LEVEL)')),
                        DropdownMenuItem(value: 'RUN_HOURS', child: Text('Giờ vận hành (RUN_HOURS)')),
                        DropdownMenuItem(value: 'NOISE', child: Text('Độ ồn (NOISE)')),
                        DropdownMenuItem(value: 'CUSTOM', child: Text('Khác... (Chỉ số tùy chỉnh)')),
                      ],
                      onChanged: (val) {
                        setDialogState(() {
                          metricCode = val ?? 'VIBRATION';
                          if (metricCode == 'VIBRATION') {
                            unitController.text = 'mm/s';
                          } else if (metricCode == 'TEMPERATURE') {
                            unitController.text = '°C';
                          } else if (metricCode == 'PRESSURE') {
                            unitController.text = 'bar';
                          } else if (metricCode == 'CURRENT') {
                            unitController.text = 'A';
                          } else if (metricCode == 'VOLTAGE') {
                            unitController.text = 'V';
                          } else if (metricCode == 'RPM') {
                            unitController.text = 'v/p';
                          } else if (metricCode == 'FLOW_RATE') {
                            unitController.text = 'm³/h';
                          } else if (metricCode == 'OIL_LEVEL') {
                            unitController.text = '%';
                          } else if (metricCode == 'RUN_HOURS') {
                            unitController.text = 'h';
                          } else if (metricCode == 'NOISE') {
                            unitController.text = 'dB';
                          } else if (metricCode == 'CUSTOM') {
                            unitController.text = '';
                          }
                        });
                      },
                    ),
                    if (metricCode == 'CUSTOM') ...[
                      const SizedBox(height: 12),
                      TextField(
                        controller: customMetricController,
                        textCapitalization: TextCapitalization.characters,
                        decoration: const InputDecoration(
                          labelText: 'Mã chỉ số tùy chỉnh (*)',
                          hintText: 'VD: RPM, NOISE, FLOW_RATE',
                          border: OutlineInputBorder(),
                          helperText: 'Chữ in hoa, số và dấu gạch dưới',
                        ),
                      ),
                    ],
                    const SizedBox(height: 12),
                    TextField(
                      controller: valueController,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(
                        labelText: 'Chỉ số mới (bắt buộc)',
                        hintText: 'VD: 1.2 hoặc 7.8',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: unitController,
                      decoration: const InputDecoration(
                        labelText: 'Đơn vị tính',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      isExpanded: true,
                      initialValue: machineState,
                      decoration: const InputDecoration(
                        labelText: 'Trạng thái vận hành máy',
                        border: OutlineInputBorder(),
                      ),
                      items: const [
                        DropdownMenuItem(value: 'RUNNING', child: Text('Đang chạy ổn định (RUNNING)')),
                        DropdownMenuItem(value: 'WARM_UP', child: Text('Đang khởi động (WARM-UP)')),
                        DropdownMenuItem(value: 'IDLE', child: Text('Không tải / Nghỉ (IDLE)')),
                      ],
                      onChanged: (val) {
                        setDialogState(() {
                          machineState = val ?? 'RUNNING';
                        });
                      },
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<double>(
                      isExpanded: true,
                      initialValue: loadFactor,
                      decoration: const InputDecoration(
                        labelText: 'Mức tải máy lúc đo (*)',
                        border: OutlineInputBorder(),
                      ),
                      items: const [
                        DropdownMenuItem(value: 0.5, child: Text('0.5 - 50% Không tải / Chạy ấm máy', overflow: TextOverflow.ellipsis)),
                        DropdownMenuItem(value: 0.8, child: Text('0.8 - 80% Vừa phải', overflow: TextOverflow.ellipsis)),
                        DropdownMenuItem(value: 1.0, child: Text('1.0 - 100% Đủ tải định mức', overflow: TextOverflow.ellipsis)),
                        DropdownMenuItem(value: 1.2, child: Text('1.2 - 120% Tải cao', overflow: TextOverflow.ellipsis)),
                        DropdownMenuItem(value: 1.4, child: Text('1.4 - 140% Quá tải đỉnh', overflow: TextOverflow.ellipsis)),
                      ],
                      onChanged: (val) {
                        setDialogState(() {
                          loadFactor = val ?? 1.0;
                        });
                      },
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: notesController,
                      decoration: const InputDecoration(
                        labelText: 'Ghi chú',
                        border: OutlineInputBorder(),
                      ),
                      maxLines: 2,
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Hủy'),
                ),
                ElevatedButton(
                  onPressed: () async {
                    String effectiveMetric = metricCode;
                    if (metricCode == 'CUSTOM') {
                      final customCode = customMetricController.text.trim().toUpperCase();
                      if (customCode.isEmpty) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Vui lòng nhập mã chỉ số đo tùy chỉnh!'),
                            backgroundColor: AppTheme.dangerColor,
                          ),
                        );
                        return;
                      }
                      final regex = RegExp(r'^[A-Z0-9_\-]+$');
                      if (!regex.hasMatch(customCode)) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Mã chỉ số đo chỉ gồm chữ cái, số, gạch dưới hoặc gạch nối.'),
                            backgroundColor: AppTheme.dangerColor,
                          ),
                        );
                        return;
                      }
                      effectiveMetric = customCode;
                    }

                    final val = double.tryParse(valueController.text.trim().replaceFirst(',', '.'));
                    if (val == null || val.isNaN || val.isInfinite) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text(
                            'Vui lòng nhập chỉ số là số hợp lệ',
                            style: TextStyle(color: Colors.white),
                          ),
                          backgroundColor: AppTheme.dangerColor,
                        ),
                      );
                      return;
                    }

                    Navigator.pop(context); // Close dialog

                    final success = await _workOrderService
                        .logMeterReading(widget.equipment['id'], {
                          'metricCode': effectiveMetric,
                          'readingValue': val,
                          'unit': unitController.text.trim(),
                          'machineState': machineState,
                          'loadFactor': loadFactor,
                          'remarks': notesController.text.trim(),
                          'readingDate': DateTime.now().toIso8601String(),
                        });

                    if (mounted) {
                      if (success) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(
                              effectiveMetric == 'VIBRATION' && val > 4.5
                                  ? '⚠️ CẢNH BÁO: Độ rung $val mm/s vượt ngưỡng Zone D! Đã kích hoạt cảnh báo bất thường.'
                                  : 'Cập nhật chỉ số thành công ($effectiveMetric: $val ${unitController.text})',
                              style: const TextStyle(color: Colors.white),
                            ),
                            backgroundColor: (effectiveMetric == 'VIBRATION' && val > 4.5) ? AppTheme.dangerColor : AppTheme.successColor,
                          ),
                        );
                      } else {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text(
                              'Lỗi khi cập nhật chỉ số',
                              style: TextStyle(color: Colors.white),
                            ),
                            backgroundColor: AppTheme.dangerColor,
                          ),
                        );
                      }
                    }
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryColor,
                  ),
                  child: const Text('Lưu', style: TextStyle(color: Colors.white)),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Widget _buildInfoCard(List<Widget> rows) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        boxShadow: const [
          BoxShadow(
            color: Color(0x08000000),
            blurRadius: 16,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        children:
            rows
                .expand(
                  (widget) => [
                    widget,
                    const Divider(color: AppTheme.neutral100, height: 24),
                  ],
                )
                .toList()
              ..removeLast(),
      ),
    );
  }

  Widget _buildInfoRow(IconData icon, String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: AppTheme.neutral100,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, color: AppTheme.neutral500, size: 16),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.neutral400,
                  letterSpacing: 0.5,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                value,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.neutral900,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
