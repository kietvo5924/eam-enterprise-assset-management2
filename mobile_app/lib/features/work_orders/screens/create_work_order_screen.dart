import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../services/work_order_service.dart';

class CreateWorkOrderScreen extends StatefulWidget {
  const CreateWorkOrderScreen({super.key});

  @override
  State<CreateWorkOrderScreen> createState() => _CreateWorkOrderScreenState();
}

class _CreateWorkOrderScreenState extends State<CreateWorkOrderScreen> {
  final _formKey = GlobalKey<FormState>();
  final _service = WorkOrderService();

  bool _isLoading = false;

  String _title = '';
  String _description = '';
  String _priority = 'MEDIUM';
  DateTime _deadline = DateTime.now().add(const Duration(days: 1));
  
  String? _selectedAssetId;
  List<Map<String, dynamic>> _assets = [];

  final List<String> _priorities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
  final List<Map<String, dynamic>> _checklists = [];

  void _addChecklistPreset(String name, String type, String expected, bool mandatory) {
    setState(() {
      _checklists.add({
        'itemName': name,
        'inputType': type,
        'expectedValue': expected,
        'isMandatory': mandatory,
      });
    });
  }

  void _showAddChecklistModal() {
    String name = '';
    String type = 'PASS_FAIL';
    String expected = '';
    bool mandatory = false;

    showDialog(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              title: const Text('Thêm Bước / Chỉ Số Đo', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
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
                        hintText: 'VD: <= 4.5 mm/s, Đạt chuẩn',
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
                  child: const Text('Hủy'),
                ),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryColor,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: () {
                    if (name.trim().isEmpty) return;
                    _addChecklistPreset(name.trim(), type, expected.trim(), mandatory);
                    Navigator.pop(context);
                  },
                  child: const Text('Thêm vào danh sách', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                ),
              ],
            );
          },
        );
      },
    );
  }

  @override
  void initState() {
    super.initState();
    _fetchAssets();
  }

  Future<void> _fetchAssets() async {
    final assets = await _service.getAssets();
    if (mounted) {
      setState(() {
        _assets = assets;
        if (_assets.isNotEmpty) {
          _selectedAssetId = _assets.first['id'];
        }
      });
    }
  }

  Future<void> _submitForm() async {
    if (!_formKey.currentState!.validate()) return;
    _formKey.currentState!.save();

    setState(() {
      _isLoading = true;
    });

    final data = {
      'title': _title,
      'description': _description,
      'priority': _priority,
      'deadline': _deadline.toUtc().toIso8601String(),
      'assetId': _selectedAssetId,
      'checklists': _checklists,
    };

    final success = await _service.createWorkOrder(data);

    if (mounted) {
      setState(() {
        _isLoading = false;
      });

      if (success) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Tạo Phiếu Bảo Trì thành công!'),
            backgroundColor: AppTheme.successColor,
          ),
        );
        context.pop(true);
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Lỗi khi tạo Phiếu Bảo Trì'),
            backgroundColor: AppTheme.dangerColor,
          ),
        );
      }
    }
  }

  Future<void> _pickDeadline() async {
    final pickedDate = await showDatePicker(
      context: context,
      initialDate: _deadline,
      firstDate: DateTime.now(),
      lastDate: DateTime.now().add(const Duration(days: 365)),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: const ColorScheme.light(
              primary: AppTheme.primaryColor,
              onPrimary: Colors.white,
              onSurface: AppTheme.neutral900,
            ),
          ),
          child: child!,
        );
      },
    );

    if (pickedDate != null) {
      if (mounted) {
        final pickedTime = await showTimePicker(
          context: context,
          initialTime: TimeOfDay.fromDateTime(_deadline),
          builder: (context, child) {
            return Theme(
              data: Theme.of(context).copyWith(
                colorScheme: const ColorScheme.light(
                  primary: AppTheme.primaryColor,
                  onPrimary: Colors.white,
                  onSurface: AppTheme.neutral900,
                ),
              ),
              child: child!,
            );
          },
        );
        if (pickedTime != null) {
          setState(() {
            _deadline = DateTime(
              pickedDate.year,
              pickedDate.month,
              pickedDate.day,
              pickedTime.hour,
              pickedTime.minute,
            );
          });
        }
      }
    }
  }

  Future<void> _showAssetPicker() async {
    String searchQuery = '';
    
    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (BuildContext context) {
        return StatefulBuilder(
          builder: (BuildContext context, StateSetter setModalState) {
            final filteredAssets = _assets.where((asset) {
              final name = asset['name'].toString().toLowerCase();
              return name.contains(searchQuery.toLowerCase());
            }).toList();

            return Container(
              height: MediaQuery.of(context).size.height * 0.7,
              decoration: const BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
              ),
              child: Column(
                children: [
                  const SizedBox(height: 12),
                  Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: AppTheme.neutral300,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'Chọn Tài sản',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppTheme.neutral900,
                    ),
                  ),
                  const SizedBox(height: 16),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    child: Container(
                      decoration: BoxDecoration(
                        color: AppTheme.neutral100,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: TextField(
                        onChanged: (value) {
                          setModalState(() {
                            searchQuery = value;
                          });
                        },
                        decoration: InputDecoration(
                          hintText: 'Tìm kiếm tài sản...',
                          hintStyle: const TextStyle(color: AppTheme.neutral400),
                          prefixIcon: Icon(PhosphorIcons.magnifyingGlass(), color: AppTheme.neutral500),
                          border: InputBorder.none,
                          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Expanded(
                    child: ListView.builder(
                      itemCount: filteredAssets.length,
                      itemBuilder: (context, index) {
                        final asset = filteredAssets[index];
                        final isSelected = _selectedAssetId == asset['id'];
                        
                        return ListTile(
                          contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                          leading: Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: isSelected ? AppTheme.primaryColor.withValues(alpha: 0.1) : AppTheme.neutral100,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Icon(
                              PhosphorIcons.cube(PhosphorIconsStyle.fill), 
                              color: isSelected ? AppTheme.primaryColor : AppTheme.neutral500,
                            ),
                          ),
                          title: Text(
                            asset['name'],
                            style: TextStyle(
                              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                              color: isSelected ? AppTheme.primaryColor : AppTheme.neutral900,
                            ),
                          ),
                          trailing: isSelected 
                            ? const Icon(Icons.check_circle, color: AppTheme.primaryColor)
                            : null,
                          onTap: () {
                            setState(() {
                              _selectedAssetId = asset['id'];
                            });
                            Navigator.pop(context);
                          },
                        );
                      },
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.neutral50,
      appBar: AppBar(
        title: const Text('Tạo Phiếu Bảo Trì', style: TextStyle(color: AppTheme.neutral900, fontWeight: FontWeight.bold, fontSize: 18)),
        backgroundColor: Colors.white,
        elevation: 0,
        iconTheme: const IconThemeData(color: AppTheme.neutral900),
      ),
      body: Form(
        key: _formKey,
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _buildSectionTitle('THÔNG TIN CHUNG'),
              const SizedBox(height: 12),
              
              _buildTextField(
                label: 'Tên công việc (*)',
                hint: 'VD: Bảo trì định kỳ máy bơm',
                icon: PhosphorIcons.textT(PhosphorIconsStyle.fill),
                validator: (val) => val == null || val.isEmpty ? 'Vui lòng nhập tên công việc' : null,
                onSaved: (val) => _title = val ?? '',
              ),
              const SizedBox(height: 16),
              
              _buildTextField(
                label: 'Mô tả chi tiết',
                hint: 'Nhập mô tả các việc cần làm...',
                icon: PhosphorIcons.textAlignLeft(PhosphorIconsStyle.fill),
                maxLines: 4,
                onSaved: (val) => _description = val ?? '',
              ),
              const SizedBox(height: 24),
              
              _buildSectionTitle('THIẾT LẬP'),
              const SizedBox(height: 12),
              
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.neutral900.withValues(alpha: 0.03),
                      blurRadius: 10,
                      offset: const Offset(0, 2),
                    )
                  ],
                ),
                child: DropdownButtonHideUnderline(
                  child: DropdownButtonFormField<String>(
                    isExpanded: true,
                    initialValue: _priority,
                    decoration: InputDecoration(
                      icon: Icon(PhosphorIcons.flag(PhosphorIconsStyle.fill), color: AppTheme.primaryColor),
                      border: InputBorder.none,
                      labelText: 'Mức độ ưu tiên',
                      labelStyle: const TextStyle(color: AppTheme.neutral500),
                    ),
                    items: _priorities.map((String value) {
                      return DropdownMenuItem<String>(
                        value: value,
                        child: Text(value, style: const TextStyle(fontWeight: FontWeight.bold)),
                      );
                    }).toList(),
                    onChanged: (newValue) {
                      setState(() {
                        _priority = newValue!;
                      });
                    },
                  ),
                ),
              ),
              const SizedBox(height: 16),
              
              InkWell(
                onTap: _pickDeadline,
                borderRadius: BorderRadius.circular(16),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: [
                      BoxShadow(
                        color: AppTheme.neutral900.withValues(alpha: 0.03),
                        blurRadius: 10,
                        offset: const Offset(0, 2),
                      )
                    ],
                  ),
                  child: Row(
                    children: [
                      Icon(PhosphorIcons.calendar(PhosphorIconsStyle.fill), color: AppTheme.primaryColor),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Thời hạn hoàn thành (Deadline)', style: TextStyle(color: AppTheme.neutral500, fontSize: 12)),
                            const SizedBox(height: 4),
                            Text(
                              '${_deadline.day.toString().padLeft(2, '0')}/${_deadline.month.toString().padLeft(2, '0')}/${_deadline.year} ${_deadline.hour.toString().padLeft(2, '0')}:${_deadline.minute.toString().padLeft(2, '0')}',
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                            ),
                          ],
                        ),
                      ),
                      const Icon(Icons.arrow_drop_down, color: AppTheme.neutral500),
                    ],
                  ),
                ),
              ),
              
              const SizedBox(height: 16),
              
              _buildSectionTitle('TÀI SẢN / THIẾT BỊ'),
              const SizedBox(height: 12),
              
              InkWell(
                onTap: _showAssetPicker,
                borderRadius: BorderRadius.circular(16),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    border: _selectedAssetId == null 
                        ? Border.all(color: AppTheme.dangerColor)
                        : null,
                    boxShadow: [
                      BoxShadow(
                        color: AppTheme.neutral900.withValues(alpha: 0.03),
                        blurRadius: 10,
                        offset: const Offset(0, 2),
                      )
                    ],
                  ),
                  child: Row(
                    children: [
                      Icon(PhosphorIcons.cube(PhosphorIconsStyle.fill), color: AppTheme.primaryColor),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Chọn thiết bị', style: TextStyle(color: AppTheme.neutral500, fontSize: 12)),
                            const SizedBox(height: 4),
                            Text(
                              _selectedAssetId != null 
                                ? _assets.firstWhere((a) => a['id'] == _selectedAssetId, orElse: () => {'name': 'Không xác định'})['name']
                                : 'Chưa chọn thiết bị',
                              style: TextStyle(
                                fontWeight: FontWeight.bold, 
                                fontSize: 16,
                                color: _selectedAssetId != null ? AppTheme.neutral900 : AppTheme.neutral400,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ],
                        ),
                      ),
                      const Icon(Icons.arrow_drop_down, color: AppTheme.neutral500),
                    ],
                  ),
                ),
              ),
              if (_selectedAssetId == null)
                const Padding(
                  padding: EdgeInsets.only(top: 8, left: 16),
                  child: Text(
                    'Vui lòng chọn thiết bị',
                    style: TextStyle(color: AppTheme.dangerColor, fontSize: 12),
                  ),
                ),
              
              const SizedBox(height: 24),
              _buildSectionTitle('QUY TRÌNH & ĐO KIỂM (CHECKLISTS)'),
              const SizedBox(height: 8),

              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    ActionChip(
                      avatar: const Icon(Icons.speed, size: 14, color: Color(0xFF0369a1)),
                      label: const Text('+ Độ rung RMS', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Color(0xFF0369a1))),
                      backgroundColor: const Color(0xFFe0f2fe),
                      side: const BorderSide(color: Color(0xFFbae6fd)),
                      onPressed: () => _addChecklistPreset('Đo kiểm độ rung RMS', 'NUMBER', '<= 4.5 mm/s (ISO 10816-3)', true),
                    ),
                    const SizedBox(width: 8),
                    ActionChip(
                      avatar: const Icon(Icons.thermostat, size: 14, color: Color(0xFFb45309)),
                      label: const Text('+ Nhiệt độ ổ bi', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Color(0xFFb45309))),
                      backgroundColor: const Color(0xFFfef3c7),
                      side: const BorderSide(color: Color(0xFFfde68a)),
                      onPressed: () => _addChecklistPreset('Đo nhiệt độ ổ trục động cơ', 'NUMBER', '< 70°C', true),
                    ),
                    const SizedBox(width: 8),
                    ActionChip(
                      avatar: const Icon(Icons.compress, size: 14, color: Color(0xFF047857)),
                      label: const Text('+ Áp suất dầu', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Color(0xFF047857))),
                      backgroundColor: const Color(0xFFd1fae5),
                      side: const BorderSide(color: Color(0xFFa7f3d0)),
                      onPressed: () => _addChecklistPreset('Kiểm tra áp suất dầu bôi trơn', 'NUMBER', '2.5 - 4.0 bar', false),
                    ),
                    const SizedBox(width: 8),
                    ActionChip(
                      avatar: const Icon(Icons.add, size: 14, color: AppTheme.primaryColor),
                      label: const Text('+ Tự nhập bước', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.primaryColor)),
                      backgroundColor: Colors.white,
                      side: const BorderSide(color: AppTheme.primaryColor),
                      onPressed: _showAddChecklistModal,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),

              if (_checklists.isEmpty)
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.neutral200),
                  ),
                  child: const Center(
                    child: Text(
                      'Chưa có bước thực hiện nào. Nhấn các nút trên để thêm nhanh.',
                      style: TextStyle(color: AppTheme.neutral400, fontSize: 13),
                    ),
                  ),
                )
              else
                ..._checklists.asMap().entries.map((entry) {
                  final idx = entry.key;
                  final item = entry.value;
                  final isMandatory = item['isMandatory'] == true;
                  final isNumber = item['inputType'] == 'NUMBER';

                  return Container(
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppTheme.neutral200),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          isNumber ? Icons.speed : Icons.check_circle_outline,
                          size: 18,
                          color: isNumber ? const Color(0xFF0284c7) : AppTheme.neutral500,
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Wrap(
                                spacing: 6,
                                crossAxisAlignment: WrapCrossAlignment.center,
                                children: [
                                  Text(
                                    item['itemName'],
                                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                                  ),
                                  if (isMandatory)
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                                      decoration: BoxDecoration(
                                        color: const Color(0xFFffe4e6),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: const Text('* BẮT BUỘC', style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: Color(0xFFbe123c))),
                                    ),
                                  if (isNumber)
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                                      decoration: BoxDecoration(
                                        color: const Color(0xFFe0f2fe),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: const Text('ĐO SỐ LIỆU', style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: Color(0xFF0369a1))),
                                    ),
                                ],
                              ),
                              if (item['expectedValue'] != null && (item['expectedValue'] as String).isNotEmpty)
                                Padding(
                                  padding: const EdgeInsets.only(top: 2),
                                  child: Text(
                                    '🎯 Tiêu chuẩn: ${item['expectedValue']}',
                                    style: const TextStyle(fontSize: 11, color: AppTheme.neutral500),
                                  ),
                                ),
                            ],
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.delete_outline, color: AppTheme.dangerColor, size: 18),
                          onPressed: () {
                            setState(() {
                              _checklists.removeAt(idx);
                            });
                          },
                        ),
                      ],
                    ),
                  );
                }),

              const SizedBox(height: 32),
              
              Container(
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [AppTheme.primaryColor, Color(0xFF0080b5)],
                    begin: Alignment.centerLeft,
                    end: Alignment.centerRight,
                  ),
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.primaryColor.withValues(alpha: 0.3),
                      blurRadius: 12,
                      offset: const Offset(0, 6),
                    ),
                  ],
                ),
                child: ElevatedButton(
                  onPressed: _isLoading ? null : _submitForm,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.transparent,
                    shadowColor: Colors.transparent,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    elevation: 0,
                  ),
                  child: _isLoading 
                    ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                    : const Text('TẠO PHIẾU BẢO TRÌ', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16, letterSpacing: 1.0)),
                ),
              ),
              const SizedBox(height: 32), // Add padding so it's not hidden by system nav bar
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Text(
      title,
      style: const TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w900,
        color: AppTheme.neutral400,
        letterSpacing: 1.5,
      ),
    );
  }

  Widget _buildTextField({
    required String label,
    required String hint,
    required IconData icon,
    int maxLines = 1,
    String? initialValue,
    String? Function(String?)? validator,
    void Function(String?)? onSaved,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: AppTheme.neutral900.withValues(alpha: 0.03),
            blurRadius: 10,
            offset: const Offset(0, 2),
          )
        ],
      ),
      child: TextFormField(
        initialValue: initialValue,
        maxLines: maxLines,
        validator: validator,
        onSaved: onSaved,
        decoration: InputDecoration(
          labelText: label,
          labelStyle: const TextStyle(color: AppTheme.neutral500),
          hintText: hint,
          hintStyle: const TextStyle(color: AppTheme.neutral400),
          prefixIcon: maxLines == 1 ? Icon(icon, color: AppTheme.primaryColor) : null,
          border: InputBorder.none,
          contentPadding: EdgeInsets.all(maxLines == 1 ? 16 : 20),
        ),
      ),
    );
  }
}
