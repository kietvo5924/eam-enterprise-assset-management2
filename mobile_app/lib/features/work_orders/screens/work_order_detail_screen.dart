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
    final success = await _service.updateChecklist(
      widget.workOrderId,
      item.itemName,
      isCompleted,
      actualValue ?? item.actualValue,
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

  Future<void> _addChecklistItem() async {
    String? newItemName;
    final result = await showDialog<bool>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text(
            'Thêm bước thực hiện',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          content: TextField(
            autofocus: true,
            decoration: const InputDecoration(
              hintText: 'Nhập tên bước...',
              border: OutlineInputBorder(),
              contentPadding: EdgeInsets.symmetric(
                horizontal: 12,
                vertical: 12,
              ),
            ),
            onChanged: (val) => newItemName = val,
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
                'Thêm',
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

    if (result == true &&
        newItemName != null &&
        newItemName!.trim().isNotEmpty) {
      final success = await _service.updateChecklist(
        widget.workOrderId,
        newItemName!.trim(),
        false,
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
                'Thao tác Work Order',
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

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    if (_workOrder == null) {
      return Scaffold(
        appBar: AppBar(),
        body: const Center(child: Text('Không tải được Work Order')),
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
            child: _SlideToComplete(
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
                    } else {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Lỗi khi bắt đầu công việc. Vui lòng thử lại.'),
                          backgroundColor: AppTheme.dangerColor,
                        ),
                      );
                    }
                  }
                } else {
                  final success = await _service.updateStatus(
                    widget.workOrderId,
                    'COMPLETED',
                  );
                  if (mounted) {
                    if (success) {
                      context.pop(); // Go back to Home
                    } else {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Vui lòng hoàn thành tất cả các bước và ghi chú trước khi hoàn thành!'),
                          backgroundColor: AppTheme.dangerColor,
                        ),
                      );
                    }
                  }
                }
              },
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
                          PhosphorIcons.checkSquareOffset(
                            PhosphorIconsStyle.fill,
                          ),
                          color: AppTheme.primaryColor,
                          size: 14,
                        ),
                      ),
                      const SizedBox(width: 8),
                      const Text(
                        'Các bước thực hiện',
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
                            if (_debounceTimers.containsKey(chk.id)) {
                              _debounceTimers[chk.id]!.cancel();
                            }
                            _debounceTimers[chk.id] = Timer(const Duration(milliseconds: 500), () {
                              _handleChecklistToggle(chk, val.isNotEmpty || chk.isCompleted, val);
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
  final Future<void> Function() onCompleted;
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
                      await widget.onCompleted();
                      if (mounted) {
                        setState(() {
                          _isCompleted = true;
                          _isLoading = false;
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
