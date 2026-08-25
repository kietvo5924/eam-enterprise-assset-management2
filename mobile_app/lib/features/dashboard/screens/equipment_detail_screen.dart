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
    final unitController = TextEditingController();
    final notesController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Cập nhật chỉ số (Meter)'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: valueController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Chỉ số mới (bắt buộc)',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: unitController,
                  decoration: const InputDecoration(
                    labelText: 'Đơn vị tính (VD: km, giờ)',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),
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
                final val = double.tryParse(valueController.text);
                if (val == null) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text(
                        'Vui lòng nhập chỉ số hợp lệ',
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
                      'readingValue': val,
                      'unit': unitController.text,
                      'remarks': notesController.text,
                      'readingDate': DateTime.now().toIso8601String(),
                    });

                if (success) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text(
                        'Cập nhật chỉ số thành công',
                        style: TextStyle(color: Colors.white),
                      ),
                      backgroundColor: AppTheme.successColor,
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
