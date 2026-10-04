import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:go_router/go_router.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/network/dio_client.dart';
import '../../../core/constants/api_constants.dart';

class FloorplanViewerScreen extends StatefulWidget {
  final String locationId;
  final String? locationName;
  final String? focusAssetId;
  final double? targetCoordsX;
  final double? targetCoordsY;
  final double? dutyZoneCoordsX;
  final double? dutyZoneCoordsY;

  const FloorplanViewerScreen({
    super.key,
    required this.locationId,
    this.locationName,
    this.focusAssetId,
    this.targetCoordsX,
    this.targetCoordsY,
    this.dutyZoneCoordsX,
    this.dutyZoneCoordsY,
  });

  @override
  State<FloorplanViewerScreen> createState() => _FloorplanViewerScreenState();
}

class _FloorplanViewerScreenState extends State<FloorplanViewerScreen> {
  bool _isLoading = true;
  String? _errorMessage;
  Map<String, dynamic>? _floorplanData;
  int _selectedFloor = 1;
  final TransformationController _transformController = TransformationController();

  @override
  void initState() {
    super.initState();
    _fetchFloorplanData();
  }

  @override
  void dispose() {
    _transformController.dispose();
    super.dispose();
  }

  Future<void> _fetchFloorplanData() async {
    try {
      final dio = DioClient().dio;
      final response = await dio.get('/api/v1/locations/${widget.locationId}/floorplan/');
      if (response.statusCode == 200 && response.data['success'] == true) {
        if (mounted) {
          setState(() {
            _floorplanData = response.data['data'];
            _selectedFloor = _floorplanData?['floorLevel'] ?? 1;
            _isLoading = false;
          });
        }
      } else {
        if (mounted) {
          setState(() {
            _errorMessage = response.data['message'] ?? 'Không tải được sơ đồ mặt bằng';
            _isLoading = false;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Lỗi kết nối máy chủ: $e';
          _isLoading = false;
        });
      }
    }
  }

  void _resetZoom() {
    _transformController.value = Matrix4.identity();
  }

  void _adjustZoom(double factor) {
    final current = _transformController.value.clone();
    current.scaleByDouble(factor, factor, 1.0, 1.0);
    _transformController.value = current;
  }

  void _showEquipmentDetails(Map<String, dynamic> eq) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        final bool hasWo = eq['hasActiveWorkOrder'] ?? false;
        final String status = eq['status'] ?? 'OPERATIONAL';
        final String? woId = eq['activeWorkOrderId'];
        final String? woCode = eq['activeWorkOrderCode'];

        Color statusColor = AppTheme.successColor;
        String statusLabel = 'Đang hoạt động';
        if (status == 'MAINTENANCE') {
          statusColor = const Color(0xFFf59e0b);
          statusLabel = 'Đang bảo dưỡng';
        } else if (status == 'DOWN' || hasWo) {
          statusColor = AppTheme.dangerColor;
          statusLabel = hasWo ? 'Có phiếu sửa chữa' : 'Sự cố dừng máy';
        }

        return Container(
          padding: const EdgeInsets.all(24),
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppTheme.neutral300,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 52,
                    height: 52,
                    decoration: BoxDecoration(
                      color: statusColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: statusColor.withValues(alpha: 0.2)),
                    ),
                    child: Center(
                      child: Icon(
                        PhosphorIcons.cube(PhosphorIconsStyle.fill),
                        color: statusColor,
                        size: 28,
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          eq['name'] ?? 'Thiết bị',
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w900,
                            color: AppTheme.neutral900,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: statusColor.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(
                                statusLabel,
                                style: TextStyle(
                                  color: statusColor,
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text(
                              eq['qrCode'] ?? '',
                              style: const TextStyle(
                                fontSize: 12,
                                color: AppTheme.neutral500,
                                fontFamily: 'monospace',
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              const Divider(color: AppTheme.neutral200),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: _buildInfoItem(
                      'Tọa độ mặt bằng',
                      'X=${(eq['coordsX'] as num?)?.toDouble() ?? 0}m, Y=${(eq['coordsY'] as num?)?.toDouble() ?? 0}m',
                      PhosphorIcons.mapPin(PhosphorIconsStyle.bold),
                    ),
                  ),
                  Expanded(
                    child: _buildInfoItem(
                      'Tầng vị trí',
                      'Tầng ${eq['floorLevel'] ?? 1}',
                      PhosphorIcons.stairs(PhosphorIconsStyle.bold),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: _buildInfoItem(
                      'Model / Serial',
                      '${eq['model'] ?? '-'} / ${eq['serialNumber'] ?? '-'}',
                      PhosphorIcons.tag(PhosphorIconsStyle.bold),
                    ),
                  ),
                  Expanded(
                    child: _buildInfoItem(
                      'Nhóm thiết bị',
                      eq['categoryName'] ?? 'Cơ điện',
                      PhosphorIcons.folder(PhosphorIconsStyle.bold),
                    ),
                  ),
                ],
              ),
              if (hasWo && woId != null) ...[
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFfef2f2),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFfecaca)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.warning_amber_rounded, color: AppTheme.dangerColor),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Đang có phiếu sửa chữa: ${woCode ?? 'WO'}',
                          style: const TextStyle(
                            color: AppTheme.dangerColor,
                            fontWeight: FontWeight.bold,
                            fontSize: 13,
                          ),
                        ),
                      ),
                      TextButton(
                        onPressed: () {
                          Navigator.pop(ctx);
                          context.push('/work-order-detail/$woId', extra: woCode);
                        },
                        child: const Text('Xem phiếu', style: TextStyle(fontWeight: FontWeight.bold)),
                      )
                    ],
                  ),
                ),
              ],
              const SizedBox(height: 24),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.pop(ctx),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      ),
                      child: const Text('Đóng', style: TextStyle(fontWeight: FontWeight.bold)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: () {
                        Navigator.pop(ctx);
                        context.push('/create-work-order');
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primaryColor,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      ),
                      icon: const Icon(Icons.add, color: Colors.white, size: 18),
                      label: const Text(
                        'Tạo Phiếu Việc',
                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildInfoItem(String label, String value, IconData icon) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, size: 14, color: AppTheme.neutral400),
            const SizedBox(width: 4),
            Text(label, style: const TextStyle(fontSize: 11, color: AppTheme.neutral500)),
          ],
        ),
        const SizedBox(height: 3),
        Text(
          value,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppTheme.neutral900),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final String title = widget.locationName ?? _floorplanData?['name'] ?? 'Sơ đồ Mặt bằng Phân xưởng';
    final String code = _floorplanData?['code'] ?? '';
    final bool hasFloorplan = _floorplanData?['hasFloorplan'] ?? false;
    final String floorplanImage = _floorplanData?['floorplanImage'] ?? '';
    final String vectorPreset = _floorplanData?['vectorPreset'] ?? 'STANDARD';
    final List<dynamic> equipmentList = _floorplanData?['equipmentList'] ?? [];

    return Scaffold(
      backgroundColor: const Color(0xFF090d16),
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
            ),
            if (code.isNotEmpty)
              Text(
                'Mã: $code • Tầng $_selectedFloor',
                style: const TextStyle(color: Colors.white60, fontSize: 11),
              ),
          ],
        ),
        backgroundColor: const Color(0xFF0f172a),
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
        actions: [
          IconButton(
            icon: const Icon(Icons.zoom_in, color: Colors.white),
            tooltip: 'Phóng to',
            onPressed: () => _adjustZoom(1.2),
          ),
          IconButton(
            icon: const Icon(Icons.zoom_out, color: Colors.white),
            tooltip: 'Thu nhỏ',
            onPressed: () => _adjustZoom(0.8),
          ),
          IconButton(
            icon: const Icon(Icons.restart_alt, color: Colors.white),
            tooltip: 'Góc nhìn gốc',
            onPressed: _resetZoom,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: AppTheme.primaryColor))
          : _errorMessage != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.error_outline, color: AppTheme.dangerColor, size: 48),
                        const SizedBox(height: 16),
                        Text(_errorMessage!, style: const TextStyle(color: Colors.white, fontSize: 14), textAlign: TextAlign.center),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: () {
                            setState(() => _isLoading = true);
                            _fetchFloorplanData();
                          },
                          child: const Text('Thử lại'),
                        ),
                      ],
                    ),
                  ),
                )
              : Stack(
                  children: [
                    // Interactive Canvas
                    Positioned.fill(
                      child: InteractiveViewer(
                        transformationController: _transformController,
                        minScale: 0.5,
                        maxScale: 4.0,
                        boundaryMargin: const EdgeInsets.all(300),
                        child: Center(
                          child: Container(
                            width: 1000,
                            height: 700,
                            decoration: BoxDecoration(
                              color: const Color(0xFF0f172a),
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(color: const Color(0xFF334155), width: 2),
                              boxShadow: const [
                                BoxShadow(color: Colors.black54, blurRadius: 30, spreadRadius: 5),
                              ],
                            ),
                            child: Stack(
                              clipBehavior: Clip.none,
                              children: [
                                // Background Layer: Floorplan Image or Vector Preset
                                Positioned.fill(
                                  child: hasFloorplan && floorplanImage.isNotEmpty
                                      ? ClipRRect(
                                          borderRadius: BorderRadius.circular(14),
                                          child: CachedNetworkImage(
                                            imageUrl: floorplanImage.startsWith('http')
                                                ? floorplanImage
                                                : '${ApiConstants.baseUrl}$floorplanImage',
                                            fit: BoxFit.contain,
                                            errorWidget: (ctx, url, err) => CustomPaint(
                                              painter: _FactoryFloorplanPainter(preset: vectorPreset),
                                            ),
                                          ),
                                        )
                                      : CustomPaint(
                                          painter: _FactoryFloorplanPainter(preset: vectorPreset),
                                        ),
                                ),

                                // Technician Duty Station Pin
                                if (widget.dutyZoneCoordsX != null && widget.dutyZoneCoordsY != null)
                                  _buildTechnicianPin(widget.dutyZoneCoordsX!, widget.dutyZoneCoordsY!),

                                // Equipment Pins
                                for (final eq in equipmentList)
                                  _buildEquipmentPin(eq),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),

                    // Floating Legend & Floor Switcher
                    Positioned(
                      left: 16,
                      bottom: 24,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                        decoration: BoxDecoration(
                          color: const Color(0xFF0f172a).withValues(alpha: 0.9),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: const Color(0xFF334155)),
                          boxShadow: const [BoxShadow(color: Colors.black38, blurRadius: 10)],
                        ),
                        child: Row(
                          children: [
                            _buildLegendDot(AppTheme.successColor, 'Bình thường'),
                            const SizedBox(width: 12),
                            _buildLegendDot(const Color(0xFFf59e0b), 'Bảo dưỡng'),
                            const SizedBox(width: 12),
                            _buildLegendDot(AppTheme.dangerColor, 'Sự cố / Phiếu'),
                            const SizedBox(width: 12),
                            _buildLegendDot(const Color(0xFF0284c7), 'Chốt trực KTV'),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
    );
  }

  Widget _buildLegendDot(Color color, String label) {
    return Row(
      children: [
        Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 5),
        Text(label, style: const TextStyle(color: Colors.white70, fontSize: 11, fontWeight: FontWeight.bold)),
      ],
    );
  }

  Widget _buildTechnicianPin(double x, double y) {
    // Normalization: width 100m -> 1000px, height 70m -> 700px
    final double left = (x / 100.0) * 1000.0;
    final double top = (y / 70.0) * 700.0;

    return Positioned(
      left: left - 20,
      top: top - 44,
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: const Color(0xFF0284c7),
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(color: const Color(0xFF0284c7).withValues(alpha: 0.6), blurRadius: 14, spreadRadius: 4),
              ],
            ),
            child: const Icon(Icons.person_pin, color: Colors.white, size: 24),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: const Color(0xFF0369a1),
              borderRadius: BorderRadius.circular(6),
            ),
            child: const Text('Chốt trực', style: TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Widget _buildEquipmentPin(Map<String, dynamic> eq) {
    final double x = (eq['coordsX'] as num?)?.toDouble() ?? 0.0;
    final double y = (eq['coordsY'] as num?)?.toDouble() ?? 0.0;
    final bool hasWo = eq['hasActiveWorkOrder'] ?? false;
    final String status = eq['status'] ?? 'OPERATIONAL';
    final bool isFocused = widget.focusAssetId != null && eq['id'] == widget.focusAssetId;

    final double left = (x / 100.0) * 1000.0;
    final double top = (y / 70.0) * 700.0;

    Color pinColor = AppTheme.successColor;
    if (status == 'MAINTENANCE') {
      pinColor = const Color(0xFFf59e0b);
    } else if (status == 'DOWN' || hasWo) {
      pinColor = AppTheme.dangerColor;
    }

    return Positioned(
      left: left - 18,
      top: top - 38,
      child: GestureDetector(
        onTap: () => _showEquipmentDetails(eq),
        child: Column(
          children: [
            Container(
              padding: EdgeInsets.all(isFocused ? 8 : 6),
              decoration: BoxDecoration(
                color: pinColor,
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: isFocused ? 3 : 1.5),
                boxShadow: [
                  BoxShadow(
                    color: pinColor.withValues(alpha: 0.6),
                    blurRadius: isFocused ? 20 : 10,
                    spreadRadius: isFocused ? 6 : 2,
                  ),
                ],
              ),
              child: Icon(
                hasWo ? Icons.build_circle : Icons.precision_manufacturing,
                color: Colors.white,
                size: isFocused ? 22 : 16,
              ),
            ),
            Container(
              margin: const EdgeInsets.only(top: 2),
              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
              decoration: BoxDecoration(
                color: Colors.black87,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                eq['qrCode'] ?? eq['name'] ?? '',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: isFocused ? 11 : 9,
                  fontWeight: FontWeight.bold,
                  fontFamily: 'monospace',
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FactoryFloorplanPainter extends CustomPainter {
  final String preset;
  _FactoryFloorplanPainter({required this.preset});

  @override
  void paint(Canvas canvas, Size size) {
    final paintGrid = Paint()
      ..color = const Color(0xFF1e293b)
      ..strokeWidth = 1.0;

    // Grid lines every 50px (5 meters)
    for (double x = 0; x <= size.width; x += 50) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paintGrid);
    }
    for (double y = 0; y <= size.height; y += 50) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paintGrid);
    }

    final paintAisle = Paint()
      ..color = const Color(0xFF0284c7).withValues(alpha: 0.1)
      ..style = PaintingStyle.fill;
    final paintBorder = Paint()
      ..color = const Color(0xFF38bdf8).withValues(alpha: 0.4)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;

    // Main Aisle 4.0m
    canvas.drawRect(Rect.fromLTWH(70, 310, 860, 60), paintAisle);
    canvas.drawRect(Rect.fromLTWH(70, 310, 860, 60), paintBorder);

    // Workshop Bay Blocks
    final paintBay = Paint()
      ..color = const Color(0xFF0f172a).withValues(alpha: 0.8)
      ..style = PaintingStyle.fill;

    // Top BAYS
    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(90, 80, 240, 190), const Radius.circular(8)), paintBay);
    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(90, 80, 240, 190), const Radius.circular(8)), paintBorder);

    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(380, 80, 240, 190), const Radius.circular(8)), paintBay);
    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(380, 80, 240, 190), const Radius.circular(8)), paintBorder);

    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(670, 80, 240, 190), const Radius.circular(8)), paintBay);
    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(670, 80, 240, 190), const Radius.circular(8)), paintBorder);

    // Bottom BAYS
    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(90, 420, 390, 210), const Radius.circular(8)), paintBay);
    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(90, 420, 390, 210), const Radius.circular(8)), paintBorder);

    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(520, 420, 390, 210), const Radius.circular(8)), paintBay);
    canvas.drawRRect(RRect.fromRectAndRadius(const Rect.fromLTWH(520, 420, 390, 210), const Radius.circular(8)), paintBorder);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
