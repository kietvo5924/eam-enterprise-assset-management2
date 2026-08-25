import 'package:flutter/material.dart';
import 'package:flutter_slidable/flutter_slidable.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../../core/theme/app_theme.dart';

class SwipeableChecklistTile extends StatefulWidget {
  final String title;
  final String? subtitle;
  final bool initialCompleted;
  final bool showSwipeHint;
  final String inputType;
  final String? expectedValue;
  final String? actualValue;
  final bool isMandatory;
  final ValueChanged<bool>? onChanged;
  final ValueChanged<String>? onValueChanged;
  final VoidCallback? onDelete;

  const SwipeableChecklistTile({
    super.key,
    required this.title,
    this.subtitle,
    this.initialCompleted = false,
    this.showSwipeHint = false,
    this.inputType = 'PASS_FAIL',
    this.expectedValue,
    this.actualValue,
    this.isMandatory = false,
    this.onChanged,
    this.onValueChanged,
    this.onDelete,
  });

  @override
  State<SwipeableChecklistTile> createState() => _SwipeableChecklistTileState();
}

class _SwipeableChecklistTileState extends State<SwipeableChecklistTile> {
  late bool _isCompleted;

  @override
  void initState() {
    super.initState();
    _isCompleted = widget.initialCompleted;
  }

  void _toggleComplete() {
    setState(() {
      _isCompleted = !_isCompleted;
    });
    if (widget.onChanged != null) {
      widget.onChanged!(_isCompleted);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Slidable(
          key: ValueKey(widget.title),
          endActionPane: widget.onDelete == null ? null : ActionPane(
            motion: const ScrollMotion(),
            extentRatio: 0.25,
            children: [
              SlidableAction(
                onPressed: (context) {
                  if (widget.onDelete != null) widget.onDelete!();
                },
                backgroundColor: AppTheme.dangerColor,
                foregroundColor: Colors.white,
                icon: PhosphorIcons.trash(PhosphorIconsStyle.fill),
                label: 'Xóa',
                borderRadius: const BorderRadius.horizontal(right: Radius.circular(16)),
              ),
            ],
          ),
          child: GestureDetector(
            onTap: widget.onChanged == null ? null : _toggleComplete,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 300),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.transparent),
                // Left border effect
                boxShadow: [
                  BoxShadow(
                    color: _isCompleted ? AppTheme.successColor : AppTheme.primaryColor,
                    offset: const Offset(-4, 0),
                  ),
                  const BoxShadow(
                    color: Color(0x08000000),
                    blurRadius: 12,
                    offset: Offset(0, 4),
                  ),
                ],
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Checkbox
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    width: 24,
                    height: 24,
                    margin: const EdgeInsets.only(right: 12, top: 2),
                    decoration: BoxDecoration(
                      color: _isCompleted ? AppTheme.successColor : Colors.white,
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(
                        color: _isCompleted ? AppTheme.successColor : AppTheme.neutral300,
                        width: 2,
                      ),
                    ),
                    child: _isCompleted
                        ? Icon(PhosphorIcons.check(PhosphorIconsStyle.bold), color: Colors.white, size: 14)
                        : null,
                  ),
                  // Content
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.title,
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.neutral900,
                            height: 1.3,
                            decoration: _isCompleted ? TextDecoration.lineThrough : null,
                            decorationColor: AppTheme.neutral400,
                          ),
                        ),
                        if (widget.subtitle != null && !_isCompleted) ...[
                          const SizedBox(height: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: AppTheme.neutral50,
                              borderRadius: BorderRadius.circular(4),
                              border: Border.all(color: AppTheme.neutral100),
                            ),
                            child: Text(
                              widget.subtitle!,
                              style: const TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w500,
                                color: AppTheme.neutral500,
                              ),
                            ),
                          ),
                        ],
                        if (widget.expectedValue != null && widget.expectedValue!.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Text(
                            'Yêu cầu: ${widget.expectedValue}',
                            style: const TextStyle(fontSize: 12, color: AppTheme.neutral500),
                          ),
                        ],
                        if (widget.inputType == 'NUMBER' || widget.inputType == 'TEXT') ...[
                          const SizedBox(height: 8),
                          TextFormField(
                            initialValue: widget.actualValue,
                            keyboardType: widget.inputType == 'NUMBER' ? TextInputType.number : TextInputType.text,
                            enabled: widget.onChanged != null,
                            decoration: InputDecoration(
                              hintText: widget.inputType == 'NUMBER' ? 'Nhập số liệu...' : 'Nhập ghi chú...',
                              isDense: true,
                              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(8),
                                borderSide: const BorderSide(color: AppTheme.neutral200),
                              ),
                            ),
                            onChanged: (val) {
                              if (widget.onValueChanged != null) {
                                widget.onValueChanged!(val);
                              }
                            },
                          ),
                        ],
                      ],
                    ),
                  ),
                  // Badge
                  if (_isCompleted)
                    Row(
                      children: [
                        Icon(PhosphorIcons.checkCircle(PhosphorIconsStyle.fill), color: AppTheme.successColor, size: 16),
                        const SizedBox(width: 4),
                        const Text(
                          'ĐÃ XONG',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.successColor,
                          ),
                        ),
                      ],
                    ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}
