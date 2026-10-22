import 'dart:convert';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
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

class _FloorplanViewerScreenState extends State<FloorplanViewerScreen>
    with TickerProviderStateMixin {
  bool _isLoading = true;
  String? _errorMessage;
  bool _isOfflineMode = false;
  Map<String, dynamic>? _floorplanData;
  int _selectedFloor = 1;
  final TransformationController _transformController = TransformationController();

  late AnimationController _dashAnimController;
  late AnimationController _pulseAnimController;

  static const double canvasWidth = 1100.0;
  static const double canvasHeight = 750.0;
  Size? _viewportSize;
  bool _hasAutoFitted = false;

  @override
  void initState() {
    super.initState();

    _dashAnimController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    )..repeat();

    _pulseAnimController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);

    _fetchFloorplanData();
  }

  @override
  void dispose() {
    _dashAnimController.dispose();
    _pulseAnimController.dispose();
    _transformController.dispose();
    super.dispose();
  }

  /// Ánh xạ tọa độ mét (0-220m, 0-130m) sang tọa độ pixel 1100x750 đồng bộ với RouteMapPainter
  static Offset mapMetersToCanvas(double rawX, double rawY) {
    if (rawX <= 250 && rawY <= 150) {
      final double px = 90.0 + (rawX / 220.0) * 920.0;
      final double py = 105.0 + (rawY / 130.0) * 520.0;
      return Offset(px.clamp(80.0, 1020.0), py.clamp(90.0, 650.0));
    }
    return Offset(rawX.clamp(80.0, 1020.0), rawY.clamp(90.0, 650.0));
  }

  Future<void> _fetchFloorplanData() async {
    final cacheKey = 'floorplan_cache_${widget.locationId}';
    try {
      final dio = DioClient().dio;
      final response = await dio.get('/api/v1/locations/${widget.locationId}/floorplan/');
      if (response.statusCode == 200 && response.data['success'] == true) {
        final data = response.data['data'] as Map<String, dynamic>;
        // Lưu bộ đệm ngoại tuyến
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(cacheKey, jsonEncode(data));

        if (mounted) {
          setState(() {
            _floorplanData = data;
            _selectedFloor = _floorplanData?['floorLevel'] ?? 1;
            _isOfflineMode = false;
            _errorMessage = null;
            _isLoading = false;
          });
        }
      } else {
        await _tryLoadFromCache(cacheKey, fallbackMsg: response.data['message']);
      }
    } catch (e) {
      await _tryLoadFromCache(cacheKey, fallbackMsg: 'Lỗi kết nối máy chủ: $e');
    }
  }

  Future<void> _tryLoadFromCache(String cacheKey, {String? fallbackMsg}) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cachedJson = prefs.getString(cacheKey);
      if (cachedJson != null && cachedJson.isNotEmpty && mounted) {
        final data = jsonDecode(cachedJson) as Map<String, dynamic>;
        setState(() {
          _floorplanData = data;
          _selectedFloor = _floorplanData?['floorLevel'] ?? 1;
          _isOfflineMode = true;
          _errorMessage = null;
          _isLoading = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('⚡ Đang xem sơ đồ mặt bằng ngoại tuyến đã lưu trên thiết bị.'),
            backgroundColor: Color(0xFF0284c7),
            duration: Duration(seconds: 3),
          ),
        );
        return;
      }
    } catch (_) {}

    if (mounted) {
      setState(() {
        _errorMessage = fallbackMsg ?? 'Không tải được sơ đồ mặt bằng';
        _isLoading = false;
      });
    }
  }

  void _resetZoom() {
    if (_viewportSize != null) {
      _fitMapToScreen(_viewportSize!.width, _viewportSize!.height);
    } else {
      _transformController.value = Matrix4.identity();
    }
  }

  void _fitMapToScreen(double vw, double vh) {
    if (vw <= 0 || vh <= 0) return;
    final scaleX = (vw - 32) / canvasWidth;
    final scaleY = (vh - 140) / canvasHeight;
    final fitScale = math.min(scaleX, scaleY).clamp(0.2, 1.0);

    final dx = (vw - canvasWidth * fitScale) / 2;
    final dy = (vh - canvasHeight * fitScale) / 2;

    _transformController.value = Matrix4.diagonal3Values(fitScale, fitScale, 1.0)
      ..setTranslationRaw(dx, dy, 0.0);
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
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppTheme.neutral900),
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                              decoration: BoxDecoration(
                                color: statusColor.withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(
                                statusLabel,
                                style: TextStyle(color: statusColor, fontSize: 11, fontWeight: FontWeight.bold),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text(
                              eq['qrCode'] ?? '',
                              style: const TextStyle(color: AppTheme.neutral500, fontSize: 12, fontFamily: 'monospace'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppTheme.neutral50,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppTheme.neutral200),
                ),
                child: Column(
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: _buildInfoItem('Phân xưởng', eq['zoneName'] ?? eq['zoneCode'] ?? 'Chung', PhosphorIcons.factory(PhosphorIconsStyle.regular)),
                        ),
                        Expanded(
                          child: _buildInfoItem('Tọa độ xưởng', 'X=${eq['coordsX'] ?? 0}m, Y=${eq['coordsY'] ?? 0}m', PhosphorIcons.navigationArrow(PhosphorIconsStyle.regular)),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              if (hasWo) ...[
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.dangerColor.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.dangerColor.withValues(alpha: 0.2)),
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
    final String title = widget.locationName ?? _floorplanData?['name'] ?? 'Sơ đồ Vị trí Máy';
    final String code = _floorplanData?['code'] ?? '';
    final bool hasFloorplan = _floorplanData?['hasFloorplan'] ?? false;
    final String floorplanImage = _floorplanData?['floorplanImage'] ?? '';
    final List<dynamic> equipmentList = _floorplanData?['equipmentList'] ?? [];

    // Tìm máy mục tiêu của Work Order nếu có
    Map<String, dynamic>? targetEquipment;
    if (widget.focusAssetId != null) {
      targetEquipment = equipmentList.firstWhere(
        (e) => e['id'] == widget.focusAssetId,
        orElse: () => null,
      );
    }

    // Tọa độ máy mục tiêu (ưu tiên widget -> sau đó equipment trong list)
    double? tx = widget.targetCoordsX ?? (targetEquipment?['coordsX'] as num?)?.toDouble();
    double? ty = widget.targetCoordsY ?? (targetEquipment?['coordsY'] as num?)?.toDouble();

    // Tọa độ trạm xuất phát (Chốt trực KTV hoặc mặc định Tổng Kho CKD)
    double sx = widget.dutyZoneCoordsX ?? 126.6;
    double sy = widget.dutyZoneCoordsY ?? 105.0;

    // Máy mục tiêu an toàn có fallback
    final safeTargetEq = targetEquipment ?? {
      'id': widget.focusAssetId ?? '',
      'name': 'Buồng Sơn Nhúng Tĩnh Điện Đối Lưu Fanuc',
      'qrCode': 'EQ-VF-PAINT-001',
      'zoneName': widget.locationName ?? 'Xưởng Sơn',
      'coordsX': widget.targetCoordsX ?? 180.3,
      'coordsY': widget.targetCoordsY ?? 25.0,
      'status': 'MAINTENANCE',
      'hasActiveWorkOrder': true,
    };

    Offset? startOffset;
    Offset? targetOffset;
    double routeDistanceMeters = 0.0;
    double walkTimeMinutes = 0.0;

    if (tx != null && ty != null && tx > 0 && ty > 0) {
      startOffset = mapMetersToCanvas(sx, sy);
      targetOffset = mapMetersToCanvas(tx, ty);
      final double dx = (tx - sx).abs();
      final double dy = (ty - sy).abs();
      routeDistanceMeters = (dx + dy).clamp(20.0, 500.0);
      walkTimeMinutes = (routeDistanceMeters / 50.0).clamp(0.5, 15.0);
    }

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
            tooltip: 'Căn giữa',
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
                            setState(() {
                              _isLoading = true;
                              _errorMessage = null;
                            });
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
                    // 1. Bản đồ CAD tương tác Fullscreen
                    Positioned.fill(
                      child: LayoutBuilder(
                        builder: (context, constraints) {
                          _viewportSize = Size(constraints.maxWidth, constraints.maxHeight);
                          if (!_hasAutoFitted && constraints.maxWidth > 0) {
                            _hasAutoFitted = true;
                            WidgetsBinding.instance.addPostFrameCallback((_) {
                              _resetZoom();
                            });
                          }

                          return InteractiveViewer(
                            transformationController: _transformController,
                            minScale: 0.2,
                            maxScale: 4.0,
                            constrained: false,
                            boundaryMargin: const EdgeInsets.symmetric(horizontal: 1600, vertical: 1200),
                            child: SizedBox(
                              width: canvasWidth,
                              height: canvasHeight,
                              child: Container(
                                decoration: BoxDecoration(
                                  color: const Color(0xFF0f172a),
                                  borderRadius: BorderRadius.circular(16),
                                  border: Border.all(color: const Color(0xFF334155), width: 2),
                                  boxShadow: const [
                                    BoxShadow(color: Colors.black54, blurRadius: 40, spreadRadius: 6),
                                  ],
                                ),
                                child: AnimatedBuilder(
                                  animation: Listenable.merge([_dashAnimController, _pulseAnimController]),
                                  builder: (context, _) {
                                    return Stack(
                                      clipBehavior: Clip.none,
                                      children: [
                                        // Lớp nền ảnh hoặc CAD Layout đồng bộ
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
                                                      painter: _FactoryFloorplanPainter(
                                                        startOffset: startOffset,
                                                        targetOffset: targetOffset,
                                                        animProgress: _dashAnimController.value,
                                                        pulseProgress: _pulseAnimController.value,
                                                        floorplanTitle: title,
                                                        floorLevel: _selectedFloor,
                                                      ),
                                                    ),
                                                  ),
                                                )
                                              : CustomPaint(
                                                  painter: _FactoryFloorplanPainter(
                                                    startOffset: startOffset,
                                                    targetOffset: targetOffset,
                                                    animProgress: _dashAnimController.value,
                                                    pulseProgress: _pulseAnimController.value,
                                                    floorplanTitle: title,
                                                    floorLevel: _selectedFloor,
                                                  ),
                                                ),
                                        ),

                                        // Điểm xuất phát (Kho tiếp vận hoặc Chốt trực KTV)
                                        if (startOffset != null)
                                          _buildStartDepotPin(startOffset),

                                        // Danh sách các Pin thiết bị trong phân xưởng - chỉ vẽ khi duyệt tự do
                                        if (targetOffset == null)
                                          for (final eq in equipmentList)
                                            _buildEquipmentPin(eq),

                                        // Pin nổi bật máy cần sửa chữa (Target Work Order Machine)
                                        if (targetOffset != null)
                                          _buildTargetMachineMarker(targetOffset, safeTargetEq),
                                      ],
                                    );
                                  },
                                ),
                              ),
                            ),
                          );
                    },
                  ),
                ),

                    // 2. Banner chế độ ngoại tuyến (nếu mất wifi)
                    if (_isOfflineMode)
                      Positioned(
                        top: 12,
                        left: 16,
                        right: 16,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                          decoration: BoxDecoration(
                            color: const Color(0xFF0284c7).withValues(alpha: 0.94),
                            borderRadius: BorderRadius.circular(10),
                            boxShadow: const [
                              BoxShadow(color: Colors.black45, blurRadius: 8, offset: Offset(0, 2)),
                            ],
                          ),
                          child: Row(
                            children: [
                              Icon(PhosphorIcons.wifiSlash(PhosphorIconsStyle.bold), color: Colors.white, size: 18),
                              const SizedBox(width: 8),
                              const Expanded(
                                child: Text(
                                  'Chế độ ngoại tuyến: Đang xem dữ liệu sơ đồ đã lưu đệm.',
                                  style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),

                    // 3. Card tóm tắt đường đi nổi bật tới máy (Highlight Path Info Card)
                    if (targetOffset != null)
                      Positioned(
                        top: _isOfflineMode ? 56 : 16,
                        left: 16,
                        right: 16,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                          decoration: BoxDecoration(
                            color: const Color(0xFF1e293b).withValues(alpha: 0.94),
                            borderRadius: BorderRadius.circular(14),
                            border: Border.all(color: const Color(0xFF0284c7), width: 1.2),
                            boxShadow: const [
                              BoxShadow(color: Colors.black54, blurRadius: 12, offset: Offset(0, 3)),
                            ],
                          ),
                          child: Row(
                            children: [
                              Container(
                                padding: const EdgeInsets.all(8),
                                decoration: const BoxDecoration(
                                  color: Color(0xFF0284c7),
                                  shape: BoxShape.circle,
                                ),
                                child: const Icon(Icons.alt_route, color: Colors.white, size: 18),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    const Text(
                                      'ĐƯỜNG ĐI ĐẾN MÁY CẦN XỬ LÝ',
                                      style: TextStyle(
                                        color: Color(0xFF38bdf8),
                                        fontSize: 10.5,
                                        fontWeight: FontWeight.w900,
                                        letterSpacing: 0.5,
                                      ),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      'Kho CKD ➔ ${targetEquipment?['name'] ?? "Vị trí máy"}',
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 12.5,
                                        fontWeight: FontWeight.bold,
                                      ),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ],
                                ),
                              ),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: const Color(0xFF0369a1).withValues(alpha: 0.6),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Column(
                                  children: [
                                    Text(
                                      '${routeDistanceMeters.toStringAsFixed(0)}m',
                                      style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
                                    ),
                                    Text(
                                      '~${walkTimeMinutes.toStringAsFixed(1)} ph',
                                      style: const TextStyle(color: Color(0xFFbae6fd), fontSize: 9.5),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),

                    // 4. Floating Legend ở dưới màn hình
                    Positioned(
                      left: 16,
                      bottom: 24,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                        decoration: BoxDecoration(
                          color: const Color(0xFF0f172a).withValues(alpha: 0.92),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: const Color(0xFF334155)),
                          boxShadow: const [BoxShadow(color: Colors.black45, blurRadius: 10)],
                        ),
                        child: Row(
                          children: [
                            _buildLegendDot(AppTheme.successColor, 'Bình thường'),
                            const SizedBox(width: 12),
                            _buildLegendDot(const Color(0xFFf59e0b), 'Bảo dưỡng'),
                            const SizedBox(width: 12),
                            _buildLegendDot(AppTheme.dangerColor, 'Sự cố / Phiếu'),
                            const SizedBox(width: 12),
                            _buildLegendDot(const Color(0xFF0284c7), 'Kho xuất phát'),
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

  /// Pin điểm xuất phát (Kho CKD hoặc trạm của KTV) - Căn giữa tinh gọn
  Widget _buildStartDepotPin(Offset offset) {
    return Positioned(
      left: offset.dx - 35,
      top: offset.dy - 34,
      child: SizedBox(
        width: 70,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(4.5),
              decoration: BoxDecoration(
                color: const Color(0xFF10b981),
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: 1.2),
                boxShadow: [
                  BoxShadow(color: const Color(0xFF10b981).withValues(alpha: 0.4), blurRadius: 8, spreadRadius: 1.5),
                ],
              ),
              child: const Icon(Icons.warehouse, color: Colors.white, size: 14),
            ),
            Container(
              margin: const EdgeInsets.only(top: 2),
              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
              decoration: BoxDecoration(
                color: const Color(0xFF047857),
                borderRadius: BorderRadius.circular(4),
              ),
              child: const Text('Kho xuất phát', style: TextStyle(color: Colors.white, fontSize: 8, fontWeight: FontWeight.bold)),
            ),
          ],
        ),
      ),
    );
  }

  /// Marker nổi bật đặc biệt cho máy cần xử lý của Work Order (Kích thước nhỏ gọn, chính xác)
  Widget _buildTargetMachineMarker(Offset offset, Map<String, dynamic>? eq) {
    return Positioned(
      left: offset.dx - 45,
      top: offset.dy - 36,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () {
          if (eq != null) _showEquipmentDetails(eq);
        },
        child: SizedBox(
          width: 90,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.all(5),
                decoration: BoxDecoration(
                  color: const Color(0xFFef4444),
                  shape: BoxShape.circle,
                  border: Border.all(color: Colors.white, width: 1.5),
                  boxShadow: [
                    BoxShadow(
                      color: const Color(0xFFef4444).withValues(alpha: 0.45 + 0.25 * _pulseAnimController.value),
                      blurRadius: 8 + 4 * _pulseAnimController.value,
                      spreadRadius: 1.5 + 1.5 * _pulseAnimController.value,
                    ),
                  ],
                ),
                child: const Icon(Icons.build_circle, color: Colors.white, size: 16),
              ),
              Container(
                margin: const EdgeInsets.only(top: 2),
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
                decoration: BoxDecoration(
                  color: const Color(0xFF991b1b),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: const Color(0xFFfca5a5), width: 0.8),
                ),
                child: const Text(
                  '📍 Máy cần xử lý',
                  style: TextStyle(color: Colors.white, fontSize: 8.5, fontWeight: FontWeight.bold),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEquipmentPin(Map<String, dynamic> eq) {
    final double rawX = (eq['coordsX'] as num?)?.toDouble() ?? 0.0;
    final double rawY = (eq['coordsY'] as num?)?.toDouble() ?? 0.0;
    final bool hasWo = eq['hasActiveWorkOrder'] ?? false;
    final String status = eq['status'] ?? 'OPERATIONAL';
    final bool isFocused = widget.focusAssetId != null && eq['id'] == widget.focusAssetId;

    // Tránh vẽ đè nếu đã vẽ marker nổi bật riêng
    if (isFocused) return const SizedBox();

    final offset = mapMetersToCanvas(rawX, rawY);

    Color pinColor = AppTheme.successColor;
    if (status == 'MAINTENANCE') {
      pinColor = const Color(0xFFf59e0b);
    } else if (status == 'DOWN' || hasWo) {
      pinColor = AppTheme.dangerColor;
    }

    return Positioned(
      left: offset.dx - 22,
      top: offset.dy - 34,
      child: GestureDetector(
        onTap: () => _showEquipmentDetails(eq),
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: pinColor,
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: 1.5),
                boxShadow: [
                  BoxShadow(
                    color: pinColor.withValues(alpha: 0.5),
                    blurRadius: 10,
                    spreadRadius: 2,
                  ),
                ],
              ),
              child: Icon(
                hasWo ? Icons.build_circle : Icons.precision_manufacturing,
                color: Colors.white,
                size: 16,
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
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 9,
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

/// Painter vẽ sơ đồ nhà xưởng 2D CAD đồng bộ hoàn toàn với hệ thống định tuyến RouteMapPainter
class _FactoryFloorplanPainter extends CustomPainter {
  final Offset? startOffset;
  final Offset? targetOffset;
  final double animProgress;
  final double pulseProgress;
  final String floorplanTitle;
  final int floorLevel;

  static const double midHallY = 345.0;

  _FactoryFloorplanPainter({
    this.startOffset,
    this.targetOffset,
    this.animProgress = 0.0,
    this.pulseProgress = 0.0,
    this.floorplanTitle = 'TỔ HỢP NHÀ MÁY SẢN XUẤT VINFAST',
    this.floorLevel = 1,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // 1. Lưới CAD tối màu
    _drawCadGrid(canvas, size);

    // 2. Viền tòa nhà nhà xưởng
    _drawBuildingEnvelope(canvas, size);

    // 3. Các phân xưởng (Zones)
    _drawZones(canvas, size);

    // 4. Trục hành lang vận chuyển chính (Aisle tại Y = 345)
    _drawCentralAisle(canvas, size);

    // 5. Cụm cầu thang chuyển tầng
    _drawStaircaseNode(canvas, size);

    // 6. Vẽ đường đi trực giao Manhattan nổi bật tới máy (nếu có điểm đích)
    if (startOffset != null && targetOffset != null) {
      _drawHighlightedRoute(canvas, startOffset!, targetOffset!);
    }
  }

  void _drawCadGrid(Canvas canvas, Size size) {
    final bgPaint = Paint()..color = const Color(0xFF0f172a);
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), bgPaint);

    final gridPaint = Paint()
      ..color = const Color(0xFF1e293b).withValues(alpha: 0.8)
      ..strokeWidth = 0.8;

    for (double x = 60; x <= 1040; x += 40) {
      canvas.drawLine(Offset(x, 65), Offset(x, 685), gridPaint);
    }
    for (double y = 65; y <= 685; y += 40) {
      canvas.drawLine(Offset(60, y), Offset(1040, y), gridPaint);
    }

    // Vạch thước đo mét
    final rulerStyle = const TextStyle(
      color: Color(0xFF64748b),
      fontSize: 8.5,
      fontWeight: FontWeight.bold,
      fontFamily: 'monospace',
    );

    for (int m = 0; m <= 220; m += 20) {
      double px = 90.0 + (m / 220.0) * 920.0;
      final tickPaint = Paint()..color = const Color(0xFF475569)..strokeWidth = 1.0;
      canvas.drawLine(Offset(px, 59), Offset(px, 65), tickPaint);
      final textSpan = TextSpan(text: '${m}m', style: rulerStyle);
      final tp = TextPainter(text: textSpan, textDirection: TextDirection.ltr)..layout();
      tp.paint(canvas, Offset(px - tp.width / 2, 47));
    }

    for (int m = 0; m <= 130; m += 20) {
      double py = 105.0 + (m / 130.0) * 520.0;
      final tickPaint = Paint()..color = const Color(0xFF475569)..strokeWidth = 1.0;
      canvas.drawLine(Offset(54, py), Offset(60, py), tickPaint);
      final textSpan = TextSpan(text: '${m}m', style: rulerStyle);
      final tp = TextPainter(text: textSpan, textDirection: TextDirection.ltr)..layout();
      tp.paint(canvas, Offset(32, py - tp.height / 2));
    }
  }

  void _drawBuildingEnvelope(Canvas canvas, Size size) {
    final rect = RRect.fromRectAndRadius(
      const Rect.fromLTWH(60, 65, 980, 620),
      const Radius.circular(8),
    );
    final fillPaint = Paint()..color = const Color(0xFF080e1a).withValues(alpha: 0.95);
    final strokePaint = Paint()
      ..color = const Color(0xFF0284c7).withValues(alpha: 0.6)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0;

    canvas.drawRRect(rect, fillPaint);
    canvas.drawRRect(rect, strokePaint);

    // Huy hiệu tên mặt bằng & tầng ở góc trên - tự động co giãn bao trọn tiêu đề
    final cleanTitle = floorplanTitle.trim().isNotEmpty
        ? floorplanTitle.toUpperCase()
        : 'TỔ HỢP NHÀ MÁY SẢN XUẤT VINFAST';
    final titleSpan = TextSpan(
      text: '🏢 $cleanTitle - TẦNG $floorLevel',
      style: const TextStyle(
        color: Color(0xFF38bdf8),
        fontSize: 10.5,
        fontWeight: FontWeight.w900,
        fontFamily: 'monospace',
        letterSpacing: 0.8,
      ),
    );
    final titlePainter = TextPainter(
      text: titleSpan,
      textDirection: TextDirection.ltr,
    )..layout();

    final double badgeWidth = titlePainter.width + 36.0;
    final double badgeLeft = 550.0 - badgeWidth / 2.0;
    final badgeRect = RRect.fromRectAndRadius(
      Rect.fromLTWH(badgeLeft, 22, badgeWidth, 26),
      const Radius.circular(6),
    );
    canvas.drawRRect(badgeRect, Paint()..color = const Color(0xFF0f172a));
    canvas.drawRRect(badgeRect, Paint()
      ..color = const Color(0xFF0284c7)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2);

    titlePainter.paint(canvas, Offset(550 - titlePainter.width / 2, 35 - titlePainter.height / 2));
  }

  void _drawZones(Canvas canvas, Size size) {
    final zones = [
      {'name': 'PHÂN XƯỞNG DẬP (STAMPING)', 'rect': const Rect.fromLTWH(80, 85, 280, 240), 'color': const Color(0xFF38bdf8)},
      {'name': 'PHÂN XƯỞNG HÀN THÂN VỎ', 'rect': const Rect.fromLTWH(375, 85, 320, 240), 'color': const Color(0xFF2dd4bf)},
      {'name': 'XƯỞNG SƠN NHÚNG & PHỦ BÓNG', 'rect': const Rect.fromLTWH(710, 85, 310, 240), 'color': const Color(0xFF818cf8)},
      {'name': 'DÂY CHUYỀN LẮP RÁP HOÀN THIỆN', 'rect': const Rect.fromLTWH(80, 365, 360, 290), 'color': const Color(0xFF10b981)},
      {'name': 'TỔNG KHO VẬT TƯ & TIẾP VẬN CKD', 'rect': const Rect.fromLTWH(455, 365, 315, 290), 'color': const Color(0xFFfb923c)},
      {'name': 'TRUNG TÂM KIỂM ĐỊNH CL (QA/QC)', 'rect': const Rect.fromLTWH(785, 365, 235, 290), 'color': const Color(0xFFa78bfa)},
    ];

    for (final z in zones) {
      final rect = z['rect'] as Rect;
      final color = z['color'] as Color;
      final name = z['name'] as String;

      final fill = Paint()
        ..color = color.withValues(alpha: 0.05)
        ..style = PaintingStyle.fill;
      final stroke = Paint()
        ..color = color.withValues(alpha: 0.4)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2;

      canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(6)), fill);
      canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(6)), stroke);

      final tp = TextPainter(
        text: TextSpan(
          text: name,
          style: TextStyle(color: color.withValues(alpha: 0.85), fontSize: 9.0, fontWeight: FontWeight.bold),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(rect.left + 10, rect.top + 8));
    }
  }

  void _drawCentralAisle(Canvas canvas, Size size) {
    const aisleRect = Rect.fromLTWH(75, midHallY - 10, 950, 20);
    final fill = Paint()
      ..color = const Color(0xFF0284c7).withValues(alpha: 0.12)
      ..style = PaintingStyle.fill;
    final stroke = Paint()
      ..color = const Color(0xFF38bdf8).withValues(alpha: 0.4)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;

    canvas.drawRRect(RRect.fromRectAndRadius(aisleRect, const Radius.circular(4)), fill);
    canvas.drawRRect(RRect.fromRectAndRadius(aisleRect, const Radius.circular(4)), stroke);

    final dashPaint = Paint()
      ..color = const Color(0xFF38bdf8).withValues(alpha: 0.6)
      ..strokeWidth = 1.0;
    for (double x = 75; x < 1025; x += 16) {
      canvas.drawLine(Offset(x, midHallY), Offset(x + 8, midHallY), dashPaint);
    }

    final tp = TextPainter(
      text: const TextSpan(
        text: 'HÀNH LANG VẬN CHUYỂN (AISLE)',
        style: TextStyle(color: Color(0xFF38bdf8), fontSize: 8, fontWeight: FontWeight.bold, letterSpacing: 1.0),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, Offset(550 - tp.width / 2, midHallY - tp.height / 2));
  }

  void _drawStaircaseNode(Canvas canvas, Size size) {
    const stair = Offset(530.0, midHallY);
    final bgPaint = Paint()..color = const Color(0xFF7c3aed)..style = PaintingStyle.fill;
    canvas.drawCircle(stair, 7, bgPaint);
  }

  /// 6. Vẽ đường đi trực giao Manhattan nổi bật tới máy (Orthogonal Manhattan Path)
  void _drawHighlightedRoute(Canvas canvas, Offset start, Offset target) {
    final path = Path();
    path.moveTo(start.dx, start.dy);

    // Điểm rẽ vào hành lang trung tâm
    final corner1 = Offset(start.dx, midHallY);
    final corner2 = Offset(target.dx, midHallY);

    path.lineTo(corner1.dx, corner1.dy);
    path.lineTo(corner2.dx, corner2.dy);
    path.lineTo(target.dx, target.dy);

    // Đường hào quang phát sáng (Outer Glow)
    final glowPaint = Paint()
      ..color = const Color(0xFFf97316).withValues(alpha: 0.35 + 0.15 * pulseProgress)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 8.0
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    canvas.drawPath(path, glowPaint);

    // Đường nét đứt chính màu cam neon (Neon Orange Line)
    final mainPaint = Paint()
      ..color = const Color(0xFFf97316)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.5
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    // Vẽ nét đứt di động (Animated Dash)
    final metrics = path.computeMetrics().toList();
    for (final metric in metrics) {
      double distance = 0.0;
      final double dashLength = 12.0;
      final double gapLength = 6.0;
      final double phase = (animProgress * (dashLength + gapLength));

      distance += phase;
      while (distance < metric.length) {
        final double end = (distance + dashLength).clamp(0.0, metric.length);
        final segment = metric.extractPath(distance, end);
        canvas.drawPath(segment, mainPaint);
        distance += dashLength + gapLength;
      }
    }

    // Mũi tên chỉ hướng tới máy (Direction Arrow)
    final targetDirection = (target.dy >= midHallY) ? 1.0 : -1.0;
    final arrowTip = Offset(target.dx, target.dy - targetDirection * 20);
    final arrowPaint = Paint()
      ..color = const Color(0xFFfbbf24)
      ..style = PaintingStyle.fill;

    final arrowPath = Path();
    arrowPath.moveTo(arrowTip.dx, arrowTip.dy);
    arrowPath.lineTo(arrowTip.dx - 6, arrowTip.dy - targetDirection * 10);
    arrowPath.lineTo(arrowTip.dx + 6, arrowTip.dy - targetDirection * 10);
    arrowPath.close();
    canvas.drawPath(arrowPath, arrowPaint);
  }

  @override
  bool shouldRepaint(covariant _FactoryFloorplanPainter oldDelegate) {
    return oldDelegate.animProgress != animProgress ||
        oldDelegate.pulseProgress != pulseProgress ||
        oldDelegate.startOffset != startOffset ||
        oldDelegate.targetOffset != targetOffset ||
        oldDelegate.floorplanTitle != floorplanTitle ||
        oldDelegate.floorLevel != floorLevel;
  }
}
