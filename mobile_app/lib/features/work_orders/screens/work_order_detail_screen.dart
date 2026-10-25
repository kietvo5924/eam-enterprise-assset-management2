import 'dart:io';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:image_picker/image_picker.dart';
import 'package:go_router/go_router.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../../core/theme/app_theme.dart';
import '../models/work_order.dart';
import '../services/work_order_service.dart';
import '../widgets/swipeable_checklist_tile.dart';
import '../../../core/constants/api_constants.dart';

class WorkOrderDetailScreen extends StatefulWidget {
  final String workOrderId;
  final String workOrderCode;

  const WorkOrderDetailScreen({
    super.key,
    required this.workOrderId,
    required this.workOrderCode,
  });

  @override
  State<WorkOrderDetailScreen> createState() => _WorkOrderDetailScreenState();
}

class _WorkOrderDetailScreenState extends State<WorkOrderDetailScreen> {
  bool _isLoading = true;
  WorkOrder? _workOrder;
  final WorkOrderService _service = WorkOrderService();
  bool _isUploading = false;
  final Map<String, Timer> _debounceTimers = {};

  @override
  void dispose() {
    for (var timer in _debounceTimers.values) {
      timer.cancel();
    }
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    _fetchWorkOrderDetails();
  }

  Future<void> _fetchWorkOrderDetails() async {
    final wo = await _service.getWorkOrderById(widget.workOrderId);
    if (mounted) {
      setState(() {
        _workOrder = wo;
        _isLoading = false;
      });
    }
  }

  Future<void> _handleChecklistToggle(
    WorkOrderChecklist item,
    bool isCompleted,
    [String? actualValue]
  ) async {
    final finalVal = actualValue ?? item.actualValue;
    setState(() {
      item.isCompleted = isCompleted;
      item.actualValue = finalVal;
    });

    final success = await _service.updateChecklist(
      widget.workOrderId,
      item.itemName,
      isCompleted,
      finalVal,
    );
    if (success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            "Đã ${isCompleted ? 'hoàn thành' : 'bỏ hoàn thành'} \"${item.itemName}\"",
          ),
          backgroundColor: AppTheme.successColor,
          duration: const Duration(seconds: 1),
        ),
      );
    } else {
      // Revert if failed?
    }
  }

  Future<void> _showLogMeterReadingModal() async {
    if (_workOrder?.assetId == null) return;
    
    final vibController = TextEditingController();
    final tempController = TextEditingController();
    final extraCustomCodeController = TextEditingController();
    final extraValController = TextEditingController();
    final extraUnitController = TextEditingController();
    String extraMetricType = 'NONE';
    String machineState = 'RUNNING';
    bool isSubmitting = false;

    await showDialog(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return AlertDialog(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              title: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: const Color(0xFFe0f2fe),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.speed, color: Color(0xFF0369a1), size: 20),
                  ),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Text(
                      'Đo kiểm & Phân tích hiện trường',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Nhập chỉ số cảm biến để hệ thống AI phân tích tình trạng bất thường ngay lập tức.',
                      style: TextStyle(fontSize: 12, color: AppTheme.neutral500),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: vibController,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(
                        labelText: 'Độ rung RMS (mm/s)',
                        hintText: 'VD: 1.2 hoặc 7.8',
                        prefixIcon: Icon(Icons.speed, color: Color(0xFF0369a1)),
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: tempController,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(
                        labelText: 'Nhiệt độ ổ trục (°C)',
                        hintText: 'VD: 45.0',
                        prefixIcon: Icon(Icons.thermostat, color: Color(0xFFb45309)),
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      initialValue: extraMetricType,
                      decoration: const InputDecoration(
                        labelText: 'Chỉ số đo bổ sung / tùy chỉnh',
                        border: OutlineInputBorder(),
                      ),
                      items: const [
                        DropdownMenuItem(value: 'NONE', child: Text('-- Không thêm chỉ số khác --')),
                        DropdownMenuItem(value: 'PRESSURE', child: Text('Áp suất (PRESSURE - bar)')),
                        DropdownMenuItem(value: 'CURRENT', child: Text('Dòng điện (CURRENT - A)')),
                        DropdownMenuItem(value: 'VOLTAGE', child: Text('Điện áp (VOLTAGE - V)')),
                        DropdownMenuItem(value: 'RPM', child: Text('Tốc độ vòng quay (RPM - v/p)')),
                        DropdownMenuItem(value: 'FLOW_RATE', child: Text('Lưu lượng (FLOW_RATE - m³/h)')),
                        DropdownMenuItem(value: 'OIL_LEVEL', child: Text('Mức dầu (OIL_LEVEL - %)')),
                        DropdownMenuItem(value: 'RUN_HOURS', child: Text('Giờ vận hành (RUN_HOURS - h)')),
                        DropdownMenuItem(value: 'NOISE', child: Text('Độ ồn (NOISE - dB)')),
                        DropdownMenuItem(value: 'CUSTOM', child: Text('Khác... (Chỉ số tùy chỉnh)')),
                      ],
                      onChanged: (val) {
                        setModalState(() {
                          extraMetricType = val ?? 'NONE';
                          if (extraMetricType == 'PRESSURE') {
                            extraUnitController.text = 'bar';
                          } else if (extraMetricType == 'CURRENT') {
                            extraUnitController.text = 'A';
                          } else if (extraMetricType == 'VOLTAGE') {
                            extraUnitController.text = 'V';
                          } else if (extraMetricType == 'RPM') {
                            extraUnitController.text = 'v/p';
                          } else if (extraMetricType == 'FLOW_RATE') {
                            extraUnitController.text = 'm³/h';
                          } else if (extraMetricType == 'OIL_LEVEL') {
                            extraUnitController.text = '%';
                          } else if (extraMetricType == 'RUN_HOURS') {
                            extraUnitController.text = 'h';
                          } else if (extraMetricType == 'NOISE') {
                            extraUnitController.text = 'dB';
                          } else if (extraMetricType == 'CUSTOM') {
                            extraUnitController.text = '';
                          }
                        });
                      },
                    ),
                    if (extraMetricType == 'CUSTOM') ...[
                      const SizedBox(height: 12),
                      TextField(
                        controller: extraCustomCodeController,
                        textCapitalization: TextCapitalization.characters,
                        decoration: const InputDecoration(
                          labelText: 'Mã chỉ số tùy chỉnh (*)',
                          hintText: 'VD: RPM, NOISE, FLOW_RATE',
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ],
                    if (extraMetricType != 'NONE') ...[
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            flex: 2,
                            child: TextField(
                              controller: extraValController,
                              keyboardType: const TextInputType.numberWithOptions(decimal: true),
                              decoration: const InputDecoration(
                                labelText: 'Giá trị bổ sung (*)',
                                hintText: 'Nhập số đo...',
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            flex: 1,
                            child: TextField(
                              controller: extraUnitController,
                              decoration: const InputDecoration(
                                labelText: 'Đơn vị',
                                border: OutlineInputBorder(),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
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
                        setModalState(() {
                          machineState = val ?? 'RUNNING';
                        });
                      },
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: isSubmitting ? null : () => Navigator.pop(context),
                  child: const Text('Đóng'),
                ),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryColor,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: isSubmitting
                      ? null
                      : () async {
                          final readings = <Map<String, dynamic>>[];

                          // 1. Kiểm tra độ rung
                          final vibText = vibController.text.trim().replaceFirst(',', '.');
                          double? vib;
                          if (vibText.isNotEmpty) {
                            vib = double.tryParse(vibText);
                            if (vib == null || vib.isNaN || vib.isInfinite || vib < 0) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Vui lòng nhập giá trị độ rung hợp lệ (>= 0)!'),
                                  backgroundColor: AppTheme.dangerColor,
                                ),
                              );
                              return;
                            }
                            readings.add({
                              'metricCode': 'VIBRATION',
                              'value': vib,
                              'unit': 'mm/s',
                              'remarks': 'Đo kiểm độ rung tại hiện trường',
                            });
                          }

                          // 2. Kiểm tra nhiệt độ
                          final tempText = tempController.text.trim().replaceFirst(',', '.');
                          if (tempText.isNotEmpty) {
                            final temp = double.tryParse(tempText);
                            if (temp == null || temp.isNaN || temp.isInfinite) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Vui lòng nhập nhiệt độ hợp lệ!'),
                                  backgroundColor: AppTheme.dangerColor,
                                ),
                              );
                              return;
                            }
                            readings.add({
                              'metricCode': 'TEMPERATURE',
                              'value': temp,
                              'unit': '°C',
                              'remarks': 'Nhiệt độ ổ trục đo kiểm di động',
                            });
                          }

                          // 3. Kiểm tra chỉ số bổ sung / tùy chỉnh
                          if (extraMetricType != 'NONE') {
                            String code = extraMetricType;
                            if (extraMetricType == 'CUSTOM') {
                              final customCode = extraCustomCodeController.text.trim().toUpperCase();
                              if (customCode.isEmpty) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('Vui lòng nhập mã chỉ số tùy chỉnh!'),
                                    backgroundColor: AppTheme.dangerColor,
                                  ),
                                );
                                return;
                              }
                              if (!RegExp(r'^[A-Z0-9_\-]+$').hasMatch(customCode)) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('Mã chỉ số tùy chỉnh chỉ gồm chữ cái, số, gạch dưới hoặc gạch nối.'),
                                    backgroundColor: AppTheme.dangerColor,
                                  ),
                                );
                                return;
                              }
                              code = customCode;
                            }

                            final extraValText = extraValController.text.trim().replaceFirst(',', '.');
                            if (extraValText.isEmpty) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text('Vui lòng nhập giá trị đo cho chỉ số $code!'),
                                  backgroundColor: AppTheme.dangerColor,
                                ),
                              );
                              return;
                            }
                            final extraVal = double.tryParse(extraValText);
                            if (extraVal == null || extraVal.isNaN || extraVal.isInfinite) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text('Giá trị đo của chỉ số $code không hợp lệ!'),
                                  backgroundColor: AppTheme.dangerColor,
                                ),
                              );
                              return;
                            }

                            readings.add({
                              'metricCode': code,
                              'value': extraVal,
                              'unit': extraUnitController.text.trim(),
                              'remarks': 'Chỉ số đo bổ sung tại hiện trường',
                            });
                          }

                          // Ràng buộc: phải có ít nhất 1 chỉ số đo
                          if (readings.isEmpty) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text('Vui lòng nhập ít nhất một chỉ số đo (Độ rung, Nhiệt độ hoặc Chỉ số khác)!'),
                                backgroundColor: AppTheme.dangerColor,
                              ),
                            );
                            return;
                          }

                          setModalState(() {
                            isSubmitting = true;
                          });

                          final payload = {
                            'workOrderId': widget.workOrderId,
                            'machineState': machineState,
                            'readings': readings,
                            'readingValue': readings.first['value'],
                            'metricCode': readings.first['metricCode'],
                            'readingDate': DateTime.now().toIso8601String(),
                          };

                          final success = await _service.logMeterReading(
                            _workOrder!.assetId!,
                            payload,
                          );

                          if (mounted) {
                            Navigator.pop(context);
                            if (success) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(
                                    vib != null && vib > 4.5
                                        ? '⚠️ CẢNH BÁO: Độ rung $vib mm/s vượt ngưỡng Zone D! Đã kích hoạt cảnh báo bất thường.'
                                        : '✅ Đã ghi nhận ${readings.length} chỉ số đo kiểm thành công.',
                                  ),
                                  backgroundColor: (vib != null && vib > 4.5) ? AppTheme.dangerColor : AppTheme.successColor,
                                  duration: const Duration(seconds: 4),
                                ),
                              );
                              _fetchWorkOrderDetails();
                            } else {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Lỗi khi lưu số đo cảm biến. Vui lòng thử lại.'),
                                  backgroundColor: AppTheme.dangerColor,
                                ),
                              );
                            }
                          }
                        },
                  child: isSubmitting
                      ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                      : const Text('Lưu & Phân Tích', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _addChecklistItem() async {
    String name = '';
    String type = 'PASS_FAIL';
    String expected = '';
    bool mandatory = false;

    final result = await showDialog<bool>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              title: const Text('Thêm bước thực hiện / Chỉ số đo', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      autofocus: true,
                      decoration: const InputDecoration(
                        labelText: 'Tên bước hoặc chỉ số đo (*)',
                        hintText: 'VD: Đo độ rung RMS, Kiểm tra bu-lông',
                        border: OutlineInputBorder(),
                      ),
                      onChanged: (val) => name = val,
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      initialValue: type,
                      decoration: const InputDecoration(
                        labelText: 'Loại dữ liệu',
                        border: OutlineInputBorder(),
                      ),
                      items: const [
                        DropdownMenuItem(value: 'PASS_FAIL', child: Text('Đạt / Không đạt (Checklist)')),
                        DropdownMenuItem(value: 'NUMBER', child: Text('Đo số liệu (Cảm biến/Thước đo)')),
                        DropdownMenuItem(value: 'TEXT', child: Text('Ghi chú văn bản')),
                      ],
                      onChanged: (val) {
                        setDialogState(() {
                          type = val ?? 'PASS_FAIL';
                        });
                      },
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      decoration: const InputDecoration(
                        labelText: 'Tiêu chuẩn / Giá trị kỳ vọng',
                        hintText: 'VD: <= 4.5 mm/s',
                        border: OutlineInputBorder(),
                      ),
                      onChanged: (val) => expected = val,
                    ),
                    const SizedBox(height: 8),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Bắt buộc đo kiểm / hoàn thành', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                      value: mandatory,
                      activeThumbColor: AppTheme.dangerColor,
                      onChanged: (val) {
                        setDialogState(() {
                          mandatory = val;
                        });
                      },
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Hủy', style: TextStyle(color: AppTheme.neutral500)),
                ),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryColor,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: () {
                    if (name.trim().isEmpty) return;
                    Navigator.pop(context, true);
                  },
                  child: const Text('Thêm', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                ),
              ],
            );
          },
        );
      },
    );

    if (result == true && name.trim().isNotEmpty) {
      final success = await _service.updateChecklist(
        widget.workOrderId,
        name.trim(),
        false,
        null,
        type,
        expected.trim().isNotEmpty ? expected.trim() : null,
        mandatory,
      );
      if (success && mounted) {
        _fetchWorkOrderDetails();
      }
    }
  }

  Future<void> _deleteChecklistItem(WorkOrderChecklist item) async {
    final success = await _service.deleteChecklist(widget.workOrderId, item.id);
    if (success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Đã xóa bước thực hiện'),
          backgroundColor: AppTheme.successColor,
        ),
      );
      _fetchWorkOrderDetails();
    }
  }

  Future<void> _pickAndUploadImage() async {
    final picker = ImagePicker();
    final XFile? image = await picker.pickImage(
      source: ImageSource.camera,
      imageQuality:
          50, // Compress image to 50% quality to avoid backend size limits
      maxWidth: 1920, // Resize image to reasonable size
    );

    if (image != null) {
      setState(() {
        _isUploading = true;
      });

      final success = await _service.uploadAttachment(
        widget.workOrderId,
        image.path,
      );

      if (mounted) {
        setState(() {
          _isUploading = false;
        });

        if (success) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Tải ảnh lên thành công!'),
              backgroundColor: AppTheme.successColor,
            ),
          );
          if (_workOrder != null) {
            setState(() {
              _workOrder!.attachments.add(
                WorkOrderAttachment(
                  id: DateTime.now().millisecondsSinceEpoch.toString(),
                  fileUrl: image.path,
                  fileName: image.name,
                  isLocal: true,
                ),
              );
            });
          }
          _fetchWorkOrderDetails(); // Refresh to show new image
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Lỗi tải ảnh lên.'),
              backgroundColor: AppTheme.dangerColor,
            ),
          );
        }
      }
    }
  }

  Future<void> _editResolutionNotes() async {
    String? newNotes = _workOrder!.resolutionNotes;
    final result = await showDialog<bool>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text(
            'Ghi chú kết quả',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          content: TextField(
            autofocus: true,
            maxLines: 4,
            controller: TextEditingController(text: newNotes),
            decoration: const InputDecoration(
              hintText: 'Nhập ghi chú hoặc kết quả thực hiện...',
              border: OutlineInputBorder(),
              contentPadding: EdgeInsets.symmetric(
                horizontal: 12,
                vertical: 12,
              ),
            ),
            onChanged: (val) => newNotes = val,
          ),
          actions: [
            TextButton(
              onPressed: () => context.pop(),
              child: const Text(
                'Hủy',
                style: TextStyle(color: AppTheme.neutral500),
              ),
            ),
            TextButton(
              onPressed: () => context.pop(true),
              child: const Text(
                'Lưu',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primaryColor,
                ),
              ),
            ),
          ],
        );
      },
    );

    if (result == true && newNotes != null) {
      final success = await _service.updateNotes(widget.workOrderId, newNotes!);
      if (success && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Đã cập nhật ghi chú'),
            backgroundColor: AppTheme.successColor,
          ),
        );
        _fetchWorkOrderDetails();
      }
    }
  }

  void _showBottomSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) => Container(
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
          boxShadow: [
            BoxShadow(
              color: Color(0x33000000),
              blurRadius: 40,
              offset: Offset(0, -10),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                margin: const EdgeInsets.only(top: 12, bottom: 16),
                width: 48,
                height: 6,
                decoration: BoxDecoration(
                  color: AppTheme.neutral300,
                  borderRadius: BorderRadius.circular(3),
                ),
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: AppTheme.neutral100)),
              ),
              child: const Text(
                'Thao tác Phiếu Bảo Trì',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.neutral900,
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Column(
                children: [
                  if (_workOrder!.status != 'COMPLETED') ...[
                    _buildBottomSheetAction(
                      icon: PhosphorIcons.pause(PhosphorIconsStyle.fill),
                      iconColor: AppTheme.primaryColor,
                      iconBgColor: const Color(0xFFe0f2fe),
                      title: 'Tạm dừng',
                      subtitle: 'Lưu tiến độ và quay lại sau',
                      onTap: () => context.pop(),
                    ),
                  ],
                  _buildBottomSheetAction(
                    icon: PhosphorIcons.flag(PhosphorIconsStyle.fill),
                    iconColor: AppTheme.warningColor,
                    iconBgColor: const Color(0xFFffedd5),
                    title: 'Báo cáo sự cố',
                    subtitle: 'Tạo follow-up WO khẩn cấp',
                    onTap: () => context.pop(),
                  ),
                  if (_workOrder!.status != 'COMPLETED') ...[
                    _buildBottomSheetAction(
                      icon: PhosphorIcons.arrowsClockwise(
                        PhosphorIconsStyle.fill,
                      ),
                      iconColor: AppTheme.neutral600,
                      iconBgColor: AppTheme.neutral100,
                      title: 'Yêu cầu phân công lại',
                      subtitle: 'Gửi yêu cầu đến Supervisor',
                      onTap: () => context.pop(),
                    ),
                  ],
                  if (_workOrder!.status != 'COMPLETED') ...[
                    _buildBottomSheetAction(
                      icon: PhosphorIcons.x(PhosphorIconsStyle.fill),
                      iconColor: AppTheme.dangerColor,
                      iconBgColor: const Color(0xFFfee2e2),
                      title: 'Hủy thao tác',
                      textColor: AppTheme.dangerColor,
                      onTap: () => context.pop(),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  Widget _buildBottomSheetAction({
    required IconData icon,
    required Color iconColor,
    required Color iconBgColor,
    required String title,
    String? subtitle,
    Color textColor = AppTheme.neutral900,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: iconBgColor,
                shape: BoxShape.circle,
              ),
              child: Icon(icon, color: iconColor, size: 18),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                      color: textColor,
                    ),
                  ),
                  if (subtitle != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppTheme.neutral500,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(IconData icon, String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 24,
          height: 24,
          decoration: BoxDecoration(
            color: AppTheme.neutral100,
            borderRadius: BorderRadius.circular(4),
          ),
          child: Icon(icon, color: AppTheme.neutral500, size: 14),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.neutral400,
                  letterSpacing: 0.5,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                value,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.neutral800,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  void _showReportIncidentBottomSheet(BuildContext context) {
    String notes = '';
    String proposedAction = 'CORE_REPLACEMENT';
    String priority = 'URGENT';
    bool isSubmitting = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (modalCtx, setModalState) {
            return Container(
              padding: EdgeInsets.only(
                left: 20,
                right: 20,
                top: 20,
                bottom: MediaQuery.of(modalCtx).viewInsets.bottom + 20,
              ),
              decoration: const BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
              ),
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: const Color(0xFFfef3c7),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Icon(PhosphorIcons.warningOctagon(PhosphorIconsStyle.bold), color: const Color(0xFFd97706), size: 22),
                        ),
                        const SizedBox(width: 12),
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Báo Cáo Sự Cố Phát Sinh',
                                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                              ),
                              Text(
                                'Đề xuất Đại tu / Thay thế phụ tùng cốt lõi',
                                style: TextStyle(color: AppTheme.neutral500, fontSize: 12),
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          onPressed: () => Navigator.of(modalCtx).pop(),
                          icon: const Icon(Icons.close, color: AppTheme.neutral400),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFFfffbeb),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xFFfde68a)),
                      ),
                      child: const Text(
                        'Thông báo khẩn sẽ gửi đến Quản đốc/Quản lý để phê duyệt xuất vật tư và tạo Work Order Đại tu tiếp theo (Follow-up). Bạn vẫn hoàn tất phiếu kiểm tra hiện tại như bình thường.',
                        style: TextStyle(color: Color(0xFF92400e), fontSize: 12),
                      ),
                    ),
                    const SizedBox(height: 16),
                    const Text('Mức can thiệp đề xuất *', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                    const SizedBox(height: 6),
                    DropdownButtonFormField<String>(
                      isExpanded: true,
                      initialValue: proposedAction,
                      decoration: InputDecoration(
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                      ),
                      items: const [
                        DropdownMenuItem(
                          value: 'CORE_REPLACEMENT',
                          child: Text('Đại tu cốt lõi (Thay vòng bi/rô-to)', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                        ),
                        DropdownMenuItem(
                          value: 'MICRO_MAINTENANCE',
                          child: Text('Bảo trì vi mô bổ sung', style: TextStyle(fontSize: 13)),
                        ),
                        DropdownMenuItem(
                          value: 'GENERAL',
                          child: Text('Bảo dưỡng mở rộng', style: TextStyle(fontSize: 13)),
                        ),
                      ],
                      onChanged: (val) {
                        setModalState(() {
                          proposedAction = val ?? 'CORE_REPLACEMENT';
                        });
                      },
                    ),
                    const SizedBox(height: 14),
                    const Text('Mức độ ưu tiên đề xuất', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                    const SizedBox(height: 6),
                    DropdownButtonFormField<String>(
                      isExpanded: true,
                      initialValue: priority,
                      decoration: InputDecoration(
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                      ),
                      items: const [
                        DropdownMenuItem(
                          value: 'URGENT',
                          child: Text('Khẩn cấp (URGENT) - Nguy cơ dừng máy', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.red)),
                        ),
                        DropdownMenuItem(
                          value: 'HIGH',
                          child: Text('Cao (HIGH) - Cần xử lý trong ca', style: TextStyle(fontSize: 13)),
                        ),
                        DropdownMenuItem(
                          value: 'MEDIUM',
                          child: Text('Trung bình (MEDIUM)', style: TextStyle(fontSize: 13)),
                        ),
                      ],
                      onChanged: (val) {
                        setModalState(() {
                          priority = val ?? 'URGENT';
                        });
                      },
                    ),
                    const SizedBox(height: 14),
                    const Text('Mô tả chi tiết sự cố phát sinh *', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                    const SizedBox(height: 6),
                    TextField(
                      maxLines: 3,
                      decoration: InputDecoration(
                        hintText: 'Mô tả hiện trạng hư hỏng tại chỗ (nứt vỡ vòng bi, quá nhiệt, rò rỉ dầu...)...',
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                        contentPadding: const EdgeInsets.all(12),
                      ),
                      onChanged: (val) => notes = val,
                    ),
                    const SizedBox(height: 20),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: isSubmitting
                            ? null
                            : () async {
                                if (notes.trim().isEmpty) {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(
                                      content: Text('Vui lòng nhập mô tả sự cố phát sinh.'),
                                      backgroundColor: AppTheme.dangerColor,
                                    ),
                                  );
                                  return;
                                }
                                setModalState(() => isSubmitting = true);
                                final ok = await _service.reportIncident(
                                  widget.workOrderId,
                                  description: notes.trim(),
                                  proposedAction: proposedAction,
                                  priority: priority,
                                );
                                if (modalCtx.mounted) {
                                  Navigator.of(modalCtx).pop();
                                }
                                if (context.mounted) {
                                  if (ok) {
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(
                                        content: Text('Đã gửi báo cáo sự cố thành công đến Quản đốc/Quản lý!'),
                                        backgroundColor: AppTheme.successColor,
                                      ),
                                    );
                                  } else {
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(
                                        content: Text('Không thể gửi báo cáo sự cố. Vui lòng thử lại.'),
                                        backgroundColor: AppTheme.dangerColor,
                                      ),
                                    );
                                  }
                                }
                              },
                        icon: isSubmitting
                            ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                            : Icon(PhosphorIcons.paperPlaneTilt(PhosphorIconsStyle.bold), color: Colors.white, size: 18),
                        label: Text(
                          isSubmitting ? 'ĐANG GỬI BÁO CÁO...' : 'GỬI BÁO CÁO LÊN QUẢN ĐỐC',
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14),
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFFd97706),
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    if (_workOrder == null) {
      return Scaffold(
        appBar: AppBar(),
        body: const Center(child: Text('Không tải được Phiếu Bảo Trì')),
      );
    }

    final statusUI = _workOrder!.getStatusUI();

    return Scaffold(
      backgroundColor: AppTheme.neutral100,
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: Colors.white,
          border: Border(top: BorderSide(color: AppTheme.neutral200)),
        ),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (_workOrder!.status == 'IN_PROGRESS' || _workOrder!.status == 'ASSIGNED') ...[
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      onPressed: () => _showReportIncidentBottomSheet(context),
                      icon: Icon(PhosphorIcons.warningOctagon(PhosphorIconsStyle.bold), color: const Color(0xFFd97706), size: 18),
                      label: const Text(
                        'Báo cáo phát sinh sự cố tại hiện trường',
                        style: TextStyle(color: Color(0xFFb45309), fontWeight: FontWeight.bold, fontSize: 13),
                      ),
                      style: OutlinedButton.styleFrom(
                        side: const BorderSide(color: Color(0xFFfde68a)),
                        backgroundColor: const Color(0xFFfffbeb),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                ],
                _SlideToComplete(
                  key: ValueKey('${_workOrder!.status}_${_workOrder!.id}'),
                  isAlreadyCompleted: _workOrder!.status == 'COMPLETED',
                  actionType: (_workOrder!.status == 'IN_PROGRESS' || _workOrder!.status == 'COMPLETED') ? 'COMPLETE' : 'START',
                  onCompleted: () async {
                if (_workOrder!.status != 'IN_PROGRESS' && _workOrder!.status != 'COMPLETED') {
                  final success = await _service.updateStatus(
                    widget.workOrderId,
                    'IN_PROGRESS',
                  );
                  if (mounted) {
                    if (success) {
                      _fetchWorkOrderDetails();
                      return true;
                    } else {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Lỗi khi bắt đầu công việc. Vui lòng thử lại.'),
                          backgroundColor: AppTheme.dangerColor,
                        ),
                      );
                      return false;
                    }
                  }
                  return success;
                } else {
                  final missingMandatory = _workOrder?.checklists.any((c) {
                    if (!c.isMandatory) return false;
                    if (!c.isCompleted) return true;
                    if (c.inputType == 'NUMBER') {
                      final val = (c.actualValue ?? '').trim().replaceAll(',', '.');
                      if (val.isEmpty || double.tryParse(val) == null) {
                        return true;
                      }
                    }
                    return false;
                  }) ?? false;

                  if (missingMandatory) {
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Chưa hoàn thành hoặc thiếu số liệu đo kiểm bắt buộc (*) trước khi đóng phiếu!'),
                          backgroundColor: AppTheme.dangerColor,
                        ),
                      );
                    }
                    return false;
                  }

                  final hasAttachments = _workOrder?.attachments.isNotEmpty ?? false;
                  if (!hasAttachments) {
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Bắt buộc phải chụp ít nhất 1 ảnh minh chứng trực tiếp từ camera trước khi hoàn thành!'),
                          backgroundColor: AppTheme.dangerColor,
                        ),
                      );
                    }
                    return false;
                  }

                  final success = await _service.updateStatus(
                    widget.workOrderId,
                    'COMPLETED',
                  );
                  if (mounted) {
                    if (success) {
                      context.pop(); // Go back to Home
                      return true;
                    } else {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Lỗi khi hoàn thành công việc. Vui lòng kiểm tra lại kết nối hoặc dữ liệu.'),
                          backgroundColor: AppTheme.dangerColor,
                        ),
                      );
                      return false;
                    }
                  }
                  return success;
                }
              },
            ),
          ],
        ),
      ),
    ),
  ),
  appBar: AppBar(
        backgroundColor: AppTheme.neutral100,
        elevation: 0,
        leading: IconButton(
          icon: Icon(PhosphorIcons.arrowLeft(), color: AppTheme.neutral900),
          onPressed: () => context.pop(true),
        ),
        actions: [
          if (_isUploading)
            Padding(
              padding: const EdgeInsets.only(right: 20),
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppTheme.neutral200),
                  ),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: AppTheme.primaryColor,
                        ),
                      ),
                      const SizedBox(width: 6),
                      const Text(
                        'ĐANG TẢI LÊN...',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.neutral600,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header Info
              Container(
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
                  children: [
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: statusUI['bgColor'],
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            statusUI['label'].toString().toUpperCase(),
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w900,
                              color: statusUI['textColor'],
                              letterSpacing: 1.5,
                            ),
                          ),
                        ),
                        if (_workOrder!.priority != null) ...[
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: AppTheme.dangerColor.withValues(
                                alpha: 0.1,
                              ),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              _workOrder!.priority!.toUpperCase(),
                              style: const TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w900,
                                color: AppTheme.dangerColor,
                                letterSpacing: 1.5,
                              ),
                            ),
                          ),
                        ],
                        Text(
                          widget.workOrderCode,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.primaryColor,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      _workOrder!.title,
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.w900,
                        color: AppTheme.neutral900,
                        height: 1.2,
                      ),
                    ),
                    if (_workOrder!.description.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Text(
                        _workOrder!.description,
                        style: const TextStyle(
                          fontSize: 14,
                          color: AppTheme.neutral600,
                        ),
                      ),
                    ],
                    const SizedBox(height: 16),
                    const Divider(color: AppTheme.neutral200),
                    const SizedBox(height: 12),
                    _buildInfoRow(
                      PhosphorIcons.mapPin(PhosphorIconsStyle.fill),
                      'Thiết bị',
                      '${_workOrder!.assetName ?? 'Không có thiết bị'} - ${_workOrder!.assetLocation ?? 'Không rõ vị trí'}',
                    ),
                    const SizedBox(height: 12),
                    _buildInfoRow(
                      PhosphorIcons.wrench(PhosphorIconsStyle.fill),
                      'Cấp độ can thiệp',
                      _workOrder!.getMaintenanceActionLabel(),
                    ),
                    if (_workOrder!.coordsX != null || _workOrder!.zoneId != null || _workOrder!.assetLocation != null) ...[
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: const Color(0xFF0f172a),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: const Color(0xFF334155)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                const Icon(Icons.location_on, color: Color(0xFF38bdf8), size: 18),
                                const SizedBox(width: 6),
                                Expanded(
                                  child: Text(
                                    'Vị trí: ${_workOrder!.zoneId ?? _workOrder!.assetLocation ?? 'Phân xưởng'} (Tầng ${_workOrder!.floorLevel ?? 1})',
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 12,
                                    ),
                                  ),
                                ),
                                if (_workOrder!.coordsX != null && _workOrder!.coordsY != null)
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: const Color(0xFF0284c7).withValues(alpha: 0.3),
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: Text(
                                      'X=${_workOrder!.coordsX}m, Y=${_workOrder!.coordsY}m',
                                      style: const TextStyle(color: Color(0xFF38bdf8), fontSize: 10, fontFamily: 'monospace', fontWeight: FontWeight.bold),
                                    ),
                                  ),
                              ],
                            ),
                            const SizedBox(height: 10),
                            SizedBox(
                              width: double.infinity,
                              child: ElevatedButton.icon(
                                onPressed: () {
                                  context.push('/floorplan-viewer', extra: {
                                    'locationId': _workOrder!.zoneId ?? '',
                                    'locationName': _workOrder!.assetLocation ?? _workOrder!.zoneId ?? 'Phân xưởng',
                                    'focusAssetId': _workOrder!.assetId,
                                    'targetCoordsX': _workOrder!.coordsX,
                                    'targetCoordsY': _workOrder!.coordsY,
                                  });
                                },
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: const Color(0xFF0284c7),
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(vertical: 10),
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                                  elevation: 0,
                                ),
                                icon: const Icon(Icons.map, size: 16),
                                label: const Text('🗺 Xem Ghim Máy Trên Sơ Đồ', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    const SizedBox(height: 8),
                    _buildInfoRow(
                      PhosphorIcons.calendar(PhosphorIconsStyle.fill),
                      'Hạn chót',
                      _workOrder!.getFormattedTime(),
                    ),
                    const SizedBox(height: 8),
                    _buildInfoRow(
                      PhosphorIcons.user(PhosphorIconsStyle.fill),
                      'Người phụ trách',
                      _workOrder!.assigneeUsername ?? 'Chưa phân công',
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 24),

              // Checklist Section
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Row(
                      children: [
                        Container(
                          width: 24,
                          height: 24,
                          decoration: BoxDecoration(
                            // ignore: deprecated_member_use
                            color: AppTheme.primaryColor.withOpacity(0.1),
                            shape: BoxShape.circle,
                          ),
                          child: Icon(
                            PhosphorIcons.checkSquareOffset(
                              PhosphorIconsStyle.fill,
                            ),
                            color: AppTheme.primaryColor,
                            size: 14,
                          ),
                        ),
                        const SizedBox(width: 8),
                        const Flexible(
                          child: Text(
                            'Các bước thực hiện',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                              color: AppTheme.neutral800,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (_workOrder!.status != 'COMPLETED')
                    Row(
                      children: [
                        if (_workOrder!.assetId != null) ...[
                          TextButton.icon(
                            onPressed: _showLogMeterReadingModal,
                            icon: const Icon(Icons.speed, size: 16, color: Color(0xFF0284c7)),
                            label: const Text(
                              'Đo Rung/Nhiệt',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                                color: Color(0xFF0284c7),
                              ),
                            ),
                            style: TextButton.styleFrom(
                              backgroundColor: const Color(0xFFe0f2fe),
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                            ),
                          ),
                          const SizedBox(width: 8),
                        ],
                        IconButton(
                          onPressed: _addChecklistItem,
                          icon: Icon(
                            PhosphorIcons.plusCircle(PhosphorIconsStyle.fill),
                            color: AppTheme.primaryColor,
                          ),
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(),
                        ),
                      ],
                    ),
                ],
              ),
              const SizedBox(height: 12),

              if (_workOrder!.checklists.isEmpty)
                const Padding(
                  padding: EdgeInsets.only(bottom: 12.0),
                  child: Text(
                    'Không có checklist nào',
                    style: TextStyle(color: AppTheme.neutral400),
                  ),
                ),

              ..._workOrder!.checklists.map((chk) {
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12.0),
                  child: SwipeableChecklistTile(
                    title: chk.itemName,
                    initialCompleted: chk.isCompleted,
                    inputType: chk.inputType,
                    expectedValue: chk.expectedValue,
                    actualValue: chk.actualValue,
                    isMandatory: chk.isMandatory,
                    onChanged: _workOrder!.status == 'COMPLETED'
                        ? null
                        : (val) => _handleChecklistToggle(chk, val, chk.actualValue),
                    onValueChanged: _workOrder!.status == 'COMPLETED'
                        ? null
                        : (val) {
                            chk.actualValue = val;
                            final trimmed = val.trim().replaceAll(',', '.');
                            final isValid = chk.inputType == 'NUMBER'
                                ? double.tryParse(trimmed) != null
                                : trimmed.isNotEmpty;
                            if (isValid) {
                              chk.isCompleted = true;
                            }
                            if (_debounceTimers.containsKey(chk.id)) {
                              _debounceTimers[chk.id]!.cancel();
                            }
                            _debounceTimers[chk.id] = Timer(const Duration(milliseconds: 500), () {
                              _handleChecklistToggle(chk, isValid || chk.isCompleted, val);
                            });
                          },
                    onDelete: _workOrder!.status == 'COMPLETED'
                        ? null
                        : () => _deleteChecklistItem(chk),
                  ),
                );
              }),

              const SizedBox(height: 20),

              // Attachment Section
              Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Container(
                    width: 24,
                    height: 24,
                    decoration: const BoxDecoration(
                      color: Color(0xFFdbeafe),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      PhosphorIcons.camera(PhosphorIconsStyle.fill),
                      color: AppTheme.primaryColor,
                      size: 14,
                    ),
                  ),
                  const SizedBox(width: 8),
                  const Text(
                    'Minh chứng',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.neutral800,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '(${_workOrder!.attachments.length} ảnh)',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                      color: AppTheme.neutral400,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  ..._workOrder!.attachments.map((att) {
                    final bool isLocalFile = att.isLocal;
                    final apiUri = Uri.parse(ApiConstants.baseUrl);
                    String imageUrl = att.fileUrl.startsWith('http')
                        ? att.fileUrl
                        : 'http://${apiUri.host}:9000${att.fileUrl}';

                    if (imageUrl.contains('localhost')) {
                      imageUrl = imageUrl.replaceAll('localhost', apiUri.host);
                    }

                    return ClipRRect(
                      borderRadius: BorderRadius.circular(16),
                      child: Container(
                        width: 80,
                        height: 80,
                        color: AppTheme.neutral200,
                        child: isLocalFile
                            ? Image.file(
                                File(att.fileUrl),
                                fit: BoxFit.cover,
                                errorBuilder: (context, error, stackTrace) => Center(
                                  child: Icon(
                                    PhosphorIcons.imageBroken(),
                                    color: AppTheme.neutral400,
                                  ),
                                ),
                              )
                            : CachedNetworkImage(
                                imageUrl: imageUrl,
                                fit: BoxFit.cover,
                                placeholder: (context, url) => const Center(
                                  child: SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  ),
                                ),
                                errorWidget: (context, url, error) => Center(
                                  child: Icon(
                                    PhosphorIcons.imageBroken(),
                                    color: AppTheme.neutral400,
                                  ),
                                ),
                              ),
                      ),
                    );
                  }),
                  if (_workOrder!.status != 'COMPLETED')
                    GestureDetector(
                      onTap: _pickAndUploadImage,
                      child: Container(
                        width: 80,
                        height: 80,
                        decoration: BoxDecoration(
                          color: const Color(0xFFeff6ff),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                            color: AppTheme.primaryColor,
                            width: 2,
                          ),
                        ),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              PhosphorIcons.plus(PhosphorIconsStyle.bold),
                              color: AppTheme.primaryColor,
                              size: 20,
                            ),
                            const SizedBox(height: 4),
                            const Text(
                              'THÊM',
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.primaryColor,
                                letterSpacing: 0.5,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
              ),

              const SizedBox(height: 32),

              // Resolution Notes Section
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 24,
                        height: 24,
                        decoration: const BoxDecoration(
                          color: Color(0xFFfef3c7),
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          PhosphorIcons.note(PhosphorIconsStyle.fill),
                          color: AppTheme.warningColor,
                          size: 14,
                        ),
                      ),
                      const SizedBox(width: 8),
                      const Text(
                        'Kết quả / Ghi chú',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.neutral800,
                        ),
                      ),
                    ],
                  ),
                  if (_workOrder!.status != 'COMPLETED')
                    IconButton(
                      onPressed: _editResolutionNotes,
                      icon: Icon(
                        PhosphorIcons.pencilSimple(PhosphorIconsStyle.fill),
                        color: AppTheme.primaryColor,
                      ),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                ],
              ),
              const SizedBox(height: 12),

              InkWell(
                onTap: _workOrder!.status == 'COMPLETED'
                    ? null
                    : _editResolutionNotes,
                borderRadius: BorderRadius.circular(16),
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: const [
                      BoxShadow(
                        color: Color(0x08000000),
                        blurRadius: 16,
                        offset: Offset(0, 8),
                      ),
                    ],
                  ),
                  child: Text(
                    _workOrder!.resolutionNotes?.isNotEmpty == true
                        ? _workOrder!.resolutionNotes!
                        : 'Chưa có ghi chú kết quả. Nhấn để thêm...',
                    style: TextStyle(
                      fontSize: 14,
                      color: _workOrder!.resolutionNotes?.isNotEmpty == true
                          ? AppTheme.neutral800
                          : AppTheme.neutral400,
                      fontStyle: _workOrder!.resolutionNotes?.isNotEmpty == true
                          ? FontStyle.normal
                          : FontStyle.italic,
                    ),
                  ),
                ),
              ),

              const SizedBox(height: 32),

              // Bottom Action Menu
              Row(
                children: [
                  Container(
                    width: 24,
                    height: 24,
                    decoration: BoxDecoration(
                      // ignore: deprecated_member_use
                      color: AppTheme.primaryColor.withOpacity(0.1),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      PhosphorIcons.dotsThreeVertical(PhosphorIconsStyle.fill),
                      color: AppTheme.primaryColor,
                      size: 14,
                    ),
                  ),
                  const SizedBox(width: 8),
                  const Text(
                    'Hành động khác',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.neutral800,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              InkWell(
                onTap: () => _showBottomSheet(context),
                borderRadius: BorderRadius.circular(16),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: const [
                      BoxShadow(
                        color: Color(0x08000000),
                        blurRadius: 16,
                        offset: Offset(0, 8),
                      ),
                    ],
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          Icon(
                            PhosphorIcons.listDashes(PhosphorIconsStyle.fill),
                            color: AppTheme.primaryColor,
                            size: 20,
                          ),
                          const SizedBox(width: 12),
                          const Text(
                            'Mở menu thao tác',
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                              color: AppTheme.neutral800,
                            ),
                          ),
                        ],
                      ),
                      Icon(
                        PhosphorIcons.caretUp(),
                        color: AppTheme.neutral400,
                        size: 16,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 100),
            ],
          ),
        ),
      ),
    );
  }
}

class _SlideToComplete extends StatefulWidget {
  final Future<bool> Function() onCompleted;
  final bool isAlreadyCompleted;
  final String actionType;

  const _SlideToComplete({
    super.key,
    required this.onCompleted,
    this.isAlreadyCompleted = false,
    this.actionType = 'COMPLETE',
  });

  @override
  State<_SlideToComplete> createState() => _SlideToCompleteState();
}

class _SlideToCompleteState extends State<_SlideToComplete> {
  double _dragPosition = 0.0;
  bool _isCompleted = false;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _isCompleted = widget.isAlreadyCompleted;
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final maxDrag = constraints.maxWidth - 56.0 - 8.0;
        return Container(
          height: 56,
          decoration: BoxDecoration(
            color: _isCompleted
                ? AppTheme.successColor.withValues(alpha: 0.1)
                : AppTheme.neutral100,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Stack(
            children: [
              Container(
                width: _isCompleted
                    ? constraints.maxWidth
                    : _dragPosition + 56 + 8,
                decoration: BoxDecoration(
                  color: _isCompleted
                      ? AppTheme.successColor.withValues(alpha: 0.2)
                      : AppTheme.primaryColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
              Center(
                child: _isLoading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : AnimatedSwitcher(
                        duration: const Duration(milliseconds: 300),
                        child: Row(
                          key: ValueKey(_isCompleted),
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              _isCompleted
                                  ? (widget.actionType == 'START' ? 'ĐANG LÀM' : 'ĐÃ HOÀN THÀNH')
                                  : (widget.actionType == 'START' ? 'VUỐT ĐỂ BẮT ĐẦU' : 'VUỐT ĐỂ HOÀN THÀNH'),
                              style: TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.bold,
                                color: _isCompleted
                                    ? AppTheme.successColor
                                    : AppTheme.neutral500,
                                letterSpacing: 1.2,
                              ),
                            ),
                            if (!_isCompleted) ...[
                              const SizedBox(width: 8),
                              Icon(
                                PhosphorIcons.arrowRight(
                                  PhosphorIconsStyle.bold,
                                ),
                                size: 16,
                                color: AppTheme.neutral500,
                              ),
                            ],
                          ],
                        ),
                      ),
              ),
              Positioned(
                right: _isCompleted ? 4 : null,
                left: _isCompleted ? null : _dragPosition + 4,
                top: 4,
                bottom: 4,
                width: 48,
                child: GestureDetector(
                  onHorizontalDragUpdate: (details) {
                    if (_isCompleted || _isLoading) return;
                    setState(() {
                      _dragPosition += details.delta.dx;
                      if (_dragPosition < 0) _dragPosition = 0;
                      if (_dragPosition > maxDrag) _dragPosition = maxDrag;
                    });
                  },
                  onHorizontalDragEnd: (details) async {
                    if (_isCompleted || _isLoading) return;
                    if (_dragPosition > maxDrag * 0.8) {
                      setState(() {
                        _dragPosition = maxDrag;
                        _isLoading = true;
                      });
                      final success = await widget.onCompleted();
                      if (mounted) {
                        setState(() {
                          _isLoading = false;
                          if (success) {
                            _isCompleted = true;
                          } else {
                            _dragPosition = 0.0;
                            _isCompleted = false;
                          }
                        });
                      }
                    } else {
                      setState(() {
                        _dragPosition = 0;
                      });
                    }
                  },
                  child: Container(
                    decoration: BoxDecoration(
                      color: _isCompleted
                          ? AppTheme.successColor
                          : AppTheme.primaryColor,
                      borderRadius: BorderRadius.circular(12),
                      boxShadow: [
                        BoxShadow(
                          color:
                              (_isCompleted
                                      ? AppTheme.successColor
                                      : AppTheme.primaryColor)
                                  .withValues(alpha: 0.3),
                          blurRadius: 8,
                          offset: const Offset(0, 2),
                        ),
                      ],
                    ),
                    child: Icon(
                      _isCompleted
                          ? PhosphorIcons.check(PhosphorIconsStyle.bold)
                          : PhosphorIcons.arrowRight(PhosphorIconsStyle.bold),
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
