import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../models/technician_route_model.dart';
import '../services/tsp_routing_service.dart';
import '../widgets/route_map_painter.dart';

class TechnicianRouteScreen extends StatefulWidget {
  final List<String>? initialWorkOrderIds;

  const TechnicianRouteScreen({
    super.key,
    this.initialWorkOrderIds,
  });

  @override
  State<TechnicianRouteScreen> createState() => _TechnicianRouteScreenState();
}

class _TechnicianRouteScreenState extends State<TechnicianRouteScreen>
    with TickerProviderStateMixin {
  final TSPRoutingService _routingService = TSPRoutingService();
  final TransformationController _transformController = TransformationController();
  final ScrollController _timelineScrollController = ScrollController();

  TechnicianRouteData? _routeData;
  bool _isLoading = true;
  bool _isActionLoading = false;
  String? _errorMessage;
  bool _isOfflineMode = false;

  int _currentFloor = 1;
  int _selectedStopIndex = 0;
  bool _showMachines = true;

  Size? _viewportSize;
  bool _hasAutoFitted = false;

  // Cấu hình tham số lộ trình
  TimeOfDay _startTime = const TimeOfDay(hour: 8, minute: 0);
  bool _returnToDepot = true;
  List<Map<String, dynamic>> _warehousesList = [];
  String? _selectedWarehouseId;

  // Điều khiển phát lại hành trình (Playback Stepper)
  bool _isPlaying = false;
  Timer? _playbackTimer;

  // Animation controllers
  late AnimationController _dashAnimController;
  late AnimationController _pulseAnimController;

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

    _loadInitialData();
  }

  @override
  void dispose() {
    _playbackTimer?.cancel();
    _dashAnimController.dispose();
    _pulseAnimController.dispose();
    _transformController.dispose();
    _timelineScrollController.dispose();
    super.dispose();
  }

  String _formatTimeOfDay(TimeOfDay tod) {
    final h = tod.hour.toString().padLeft(2, '0');
    final m = tod.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }

  Future<void> _loadInitialData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      // 1. Tải danh sách kho vật tư
      _warehousesList = await _routingService.getAvailableWarehouses();
      if (_warehousesList.isNotEmpty) {
        _selectedWarehouseId = _warehousesList.first['id'];
      }

      // 2. Gọi API tối ưu lộ trình
      final route = await _routingService.optimizeRoute(
        workOrderIds: widget.initialWorkOrderIds,
        startTime: _formatTimeOfDay(_startTime),
        returnToDepot: _returnToDepot,
      );

      _applyRouteData(route, isOffline: false);
    } catch (e) {
      debugPrint('[TechnicianRouteScreen] API error: $e, falling back to cache');
      // Thử đọc từ bộ đệm ngoại tuyến
      final cachedRoute = await _routingService.getCachedRoute();
      if (cachedRoute != null && mounted) {
        _applyRouteData(cachedRoute, isOffline: true);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('⚡ Đang hiển thị lộ trình ngoại tuyến đã lưu.'),
            backgroundColor: Color(0xFF0284c7),
            duration: Duration(seconds: 3),
          ),
        );
      } else if (mounted) {
        // Nếu không có cache, nạp dữ liệu mẫu để KTV trải nghiệm
        final demoRoute = _routingService.getFallbackDemoRoute();
        _applyRouteData(demoRoute, isOffline: true);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Chưa kết nối máy chủ. Đang hiển thị dữ liệu mô phỏng phân xưởng.'),
            backgroundColor: Color(0xFFf59e0b),
          ),
        );
      }
    }
  }

  void _applyRouteData(TechnicianRouteData route, {required bool isOffline}) {
    if (!mounted) return;

    // Tìm các tầng có mặt trong danh sách trạm
    final floors = route.orderedStops.map((s) => s.floorNumber).toSet().toList()..sort();
    final defaultFloor = route.detectedFloorLevel ?? (floors.isNotEmpty ? floors.first : 1);

    setState(() {
      _routeData = route;
      _isOfflineMode = isOffline;
      _currentFloor = defaultFloor;
      _selectedStopIndex = 0;
      _isLoading = false;
      _isActionLoading = false;
    });

    WidgetsBinding.instance.addPostFrameCallback((_) {
      _resetZoom();
    });
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
    final availableH = vh * 0.58;
    final scaleX = (vw - 24) / RouteMapPainter.canvasWidth;
    final scaleY = (availableH - 24) / RouteMapPainter.canvasHeight;
    final fitScale = math.min(scaleX, scaleY).clamp(0.2, 1.0);

    final dx = (vw - RouteMapPainter.canvasWidth * fitScale) / 2;
    final dy = math.max(16.0, (availableH - RouteMapPainter.canvasHeight * fitScale) / 2);

    _transformController.value = Matrix4.diagonal3Values(fitScale, fitScale, 1.0)
      ..setTranslationRaw(dx, dy, 0.0);
  }

  void _adjustZoom(double factor) {
    final current = _transformController.value.clone();
    current.scaleByDouble(factor, factor, 1.0, 1.0);
    _transformController.value = current;
  }

  void _focusOnStop(int stopIndex) {
    if (_routeData == null || stopIndex < 0 || stopIndex >= _routeData!.orderedStops.length) return;
    final stop = _routeData!.orderedStops[stopIndex];

    // Tự động chuyển tầng nếu trạm dừng ở tầng khác
    if (stop.floorNumber != _currentFloor) {
      setState(() {
        _currentFloor = stop.floorNumber;
      });
    }

    setState(() {
      _selectedStopIndex = stopIndex;
    });

    final targetOffset = RouteMapPainter.getStopCanvasOffset(stop, stopIndex);
    _centerCameraOnOffset(targetOffset);
    _scrollTimelineToStop(stopIndex);
  }

  void _centerCameraOnOffset(Offset point) {
    final vw = _viewportSize?.width ?? 390.0;
    final vh = (_viewportSize?.height ?? 600.0) * 0.60;
    const currentScale = 0.75;

    final dx = (vw / 2) - point.dx * currentScale;
    final dy = (vh / 2) - point.dy * currentScale;

    _transformController.value = Matrix4.identity()
      ..translateByDouble(dx, dy, 0.0, 1.0)
      ..scaleByDouble(currentScale, currentScale, 1.0, 1.0);
  }

  void _scrollTimelineToStop(int index) {
    if (!_timelineScrollController.hasClients) return;
    final target = (index * 140.0).clamp(0.0, _timelineScrollController.position.maxScrollExtent);
    _timelineScrollController.animateTo(
      target,
      duration: const Duration(milliseconds: 350),
      curve: Curves.easeInOut,
    );
  }

  void _togglePlayback() {
    if (_isPlaying) {
      _playbackTimer?.cancel();
      setState(() => _isPlaying = false);
    } else {
      if (_routeData == null || _routeData!.orderedStops.isEmpty) return;
      setState(() => _isPlaying = true);

      _playbackTimer = Timer.periodic(const Duration(milliseconds: 1400), (timer) {
        if (!mounted || !_isPlaying || _routeData == null) {
          timer.cancel();
          return;
        }

        final nextIndex = (_selectedStopIndex + 1) % _routeData!.orderedStops.length;
        _focusOnStop(nextIndex);

        // Khi chạy hết chu trình và về trạm đầu
        if (nextIndex == 0) {
          timer.cancel();
          setState(() => _isPlaying = false);
        }
      });
    }
  }

  // Lưu đệm ngoại tuyến thủ công
  Future<void> _saveOfflineCache() async {
    if (_routeData == null) return;
    final success = await _routingService.saveRouteToCache(_routeData!);
    if (!mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            Icon(
              success ? PhosphorIcons.checkCircle(PhosphorIconsStyle.fill) : PhosphorIcons.warningCircle(PhosphorIconsStyle.fill),
              color: Colors.white,
              size: 20,
            ),
            const SizedBox(width: 8),
            Text(
              success
                  ? 'Đã lưu đệm lộ trình ngoại tuyến thành công!'
                  : 'Lỗi khi lưu bộ đệm ngoại tuyến.',
            ),
          ],
        ),
        backgroundColor: success ? AppTheme.successColor : AppTheme.dangerColor,
      ),
    );
  }

  // Chọn giờ xuất phát
  Future<void> _selectStartTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _startTime,
      builder: (context, child) {
        return MediaQuery(
          data: MediaQuery.of(context).copyWith(alwaysUse24HourFormat: true),
          child: child ?? const SizedBox(),
        );
      },
    );

    if (picked != null && picked != _startTime) {
      setState(() => _startTime = picked);
      _recalculateRoute();
    }
  }

  // Hành động: Tính lại lộ trình (Optimize)
  Future<void> _recalculateRoute() async {
    setState(() => _isActionLoading = true);
    try {
      final route = await _routingService.optimizeRoute(
        workOrderIds: widget.initialWorkOrderIds,
        startTime: _formatTimeOfDay(_startTime),
        returnToDepot: _returnToDepot,
      );
      _applyRouteData(route, isOffline: false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Đã cập nhật lộ trình di chuyển tối ưu!'),
            backgroundColor: AppTheme.successColor,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isActionLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Lỗi tính toán: $e'),
            backgroundColor: AppTheme.dangerColor,
          ),
        );
      }
    }
  }

  // Hành động: Ghé kho lấy vật tư (Pitstop)
  Future<void> _triggerPitstop() async {
    if (_routeData == null) return;
    setState(() => _isActionLoading = true);

    try {
      final currentStop = _routeData!.orderedStops[_selectedStopIndex];
      List<String> remainingIds = _routeData!.orderedStops
          .skip(_selectedStopIndex + 1)
          .where((s) => s.workOrderId != null)
          .map((s) => s.workOrderId!)
          .toList();
      if (remainingIds.isEmpty) {
        remainingIds = _routeData!.orderedStops
            .where((s) => s.workOrderId != null)
            .map((s) => s.workOrderId!)
            .toList();
      }

      final route = await _routingService.reRouteMidShift(
        currentLocationId: currentStop.locationId,
        currentCoords: currentStop.coords != null
            ? {'x': currentStop.coords!.x, 'y': currentStop.coords!.y}
            : null,
        actionTrigger: 'PIT_STOP',
        includeWarehousePitstop: true,
        pitstopLocationId: _selectedWarehouseId,
        remainingWorkOrderIds: remainingIds,
        returnToDepot: _returnToDepot,
        startTime: _formatTimeOfDay(_startTime),
      );

      _applyRouteData(route, isOffline: false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Đã chèn trạm tiếp vận kho vật tư vào lộ trình!'),
            backgroundColor: Color(0xFFf97316),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isActionLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Lỗi tái định tuyến: $e'),
            backgroundColor: AppTheme.dangerColor,
          ),
        );
      }
    }
  }

  // Hành động: Tái định tuyến động từ vị trí hiện tại
  Future<void> _triggerDynamicReRoute() async {
    if (_routeData == null) return;
    setState(() => _isActionLoading = true);

    try {
      final currentStop = _routeData!.orderedStops[_selectedStopIndex];
      List<String> remainingIds = _routeData!.orderedStops
          .skip(_selectedStopIndex + 1)
          .where((s) => s.workOrderId != null)
          .map((s) => s.workOrderId!)
          .toList();
      if (remainingIds.isEmpty) {
        remainingIds = _routeData!.orderedStops
            .where((s) => s.workOrderId != null)
            .map((s) => s.workOrderId!)
            .toList();
      }

      final route = await _routingService.reRouteMidShift(
        currentLocationId: currentStop.locationId,
        currentCoords: currentStop.coords != null
            ? {'x': currentStop.coords!.x, 'y': currentStop.coords!.y}
            : null,
        actionTrigger: 'DYNAMIC_RE_ROUTE',
        includeWarehousePitstop: false,
        remainingWorkOrderIds: remainingIds,
        returnToDepot: _returnToDepot,
        startTime: _formatTimeOfDay(_startTime),
      );

      _applyRouteData(route, isOffline: false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Đã tái định tuyến động thành công từ vị trí hiện tại!'),
            backgroundColor: Color(0xFF0284c7),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isActionLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Lỗi tái định tuyến: $e'),
            backgroundColor: AppTheme.dangerColor,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final availableFloors = _routeData?.orderedStops
            .map((s) => s.floorNumber)
            .toSet()
            .toList() ??
        [1];
    availableFloors.sort();

    return Scaffold(
      backgroundColor: const Color(0xFF0f172a),
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Sơ Đồ Lộ Trình Di Chuyển',
              style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
            ),
            if (_routeData != null)
              Text(
                '${_routeData!.technicianName ?? "Kỹ thuật viên"} • Tầng $_currentFloor',
                style: const TextStyle(color: Colors.white70, fontSize: 11),
              ),
          ],
        ),
        backgroundColor: const Color(0xFF0f172a),
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
        actions: [
          // Nút Lưu đệm ngoại tuyến
          IconButton(
            icon: Icon(PhosphorIcons.cloudArrowDown(PhosphorIconsStyle.bold), color: Colors.white),
            tooltip: 'Lưu đệm ngoại tuyến',
            onPressed: _saveOfflineCache,
          ),
          // Nút Reset Zoom
          IconButton(
            icon: Icon(PhosphorIcons.arrowsCounterClockwise(PhosphorIconsStyle.bold), color: Colors.white),
            tooltip: 'Căn giữa bản đồ',
            onPressed: _resetZoom,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(color: Color(0xFF38bdf8)),
                  SizedBox(height: 16),
                  Text(
                    'Đang tính toán ma trận khoảng cách & lộ trình tối ưu...',
                    style: TextStyle(color: Colors.white70, fontSize: 13),
                  ),
                ],
              ),
            )
          : _routeData == null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.error_outline, color: AppTheme.dangerColor, size: 48),
                        const SizedBox(height: 16),
                        Text(
                          _errorMessage ?? 'Không tìm thấy dữ liệu lộ trình.',
                          style: const TextStyle(color: Colors.white, fontSize: 14),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _loadInitialData,
                          child: const Text('Thử lại'),
                        ),
                      ],
                    ),
                  ),
                )
              : Stack(
              children: [
                // 1. Bản đồ 2D tương tác Fullscreen CAD Map
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
                          width: RouteMapPainter.canvasWidth,
                          height: RouteMapPainter.canvasHeight,
                          child: Container(
                            decoration: BoxDecoration(
                              color: const Color(0xFF0f172a),
                              borderRadius: BorderRadius.circular(16),
                              boxShadow: const [
                                BoxShadow(color: Colors.black87, blurRadius: 40, spreadRadius: 8),
                              ],
                            ),
                            child: AnimatedBuilder(
                              animation: Listenable.merge([_dashAnimController, _pulseAnimController]),
                              builder: (context, _) {
                                return Stack(
                                  clipBehavior: Clip.none,
                                  children: [
                                    // Nền CustomPaint CAD Map
                                    CustomPaint(
                                      size: const Size(
                                        RouteMapPainter.canvasWidth,
                                        RouteMapPainter.canvasHeight,
                                      ),
                                      painter: RouteMapPainter(
                                        routeData: _routeData!,
                                        currentFloor: _currentFloor,
                                        selectedStopIndex: _selectedStopIndex,
                                        showMachines: _showMachines,
                                        animationProgress: _dashAnimController.value,
                                        pulseValue: _pulseAnimController.value,
                                      ),
                                    ),

                                    // Các Pin bấm tương tác trực tiếp trên bản đồ
                                    for (int i = 0; i < _routeData!.orderedStops.length; i++)
                                      if (_routeData!.orderedStops[i].floorNumber == _currentFloor)
                                        _buildInteractivePinOverlay(i),
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

                // 2. Banner chế độ ngoại tuyến (nếu có)
                if (_isOfflineMode)
                  Positioned(
                    top: 12,
                    left: 16,
                    right: 16,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      decoration: BoxDecoration(
                        color: const Color(0xFF0284c7).withValues(alpha: 0.92),
                        borderRadius: BorderRadius.circular(10),
                        boxShadow: const [
                          BoxShadow(color: Colors.black38, blurRadius: 8, offset: Offset(0, 2)),
                        ],
                      ),
                      child: Row(
                        children: [
                          Icon(PhosphorIcons.wifiSlash(PhosphorIconsStyle.bold), color: Colors.white, size: 18),
                          const SizedBox(width: 8),
                          const Expanded(
                            child: Text(
                              'Chế độ ngoại tuyến: Xem dữ liệu đã lưu đệm trên thiết bị.',
                              style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),

                // 3. Floating Overlay Top Right (Chuyển tầng, Bật/tắt máy móc, Zoom)
                Positioned(
                  top: _isOfflineMode ? 56 : 16,
                  right: 16,
                  child: _buildFloatingControls(availableFloors),
                ),

                // 4. Floating Stepper Playback Control (Thanh điều khiển tiến trình nổi)
                Positioned(
                  top: _isOfflineMode ? 56 : 16,
                  left: 16,
                  child: _buildPlaybackStepperControl(),
                ),

                // 5. Thanh trượt Bottom Sheet chi tiết lộ trình (DraggableScrollableSheet - nằm trên hết các nút điều khiển nổi)
                _buildDraggableBottomSheet(),

                // 6. Loading overlay khi đang gọi API tái định tuyến
                if (_isActionLoading)
                  Positioned.fill(
                    child: Container(
                      color: Colors.black45,
                      child: const Center(
                        child: CircularProgressIndicator(color: Color(0xFF38bdf8)),
                      ),
                    ),
                  ),
              ],
            ),
    );
  }

  /// Pin tương tác trong Stack để bấm chọn trạm mượt mà
  Widget _buildInteractivePinOverlay(int index) {
    final stop = _routeData!.orderedStops[index];
    final offset = RouteMapPainter.getStopCanvasOffset(stop, index);

    return Positioned(
      left: offset.dx - 22,
      top: offset.dy - 22,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => _focusOnStop(index),
        child: Container(
          width: 44,
          height: 44,
          color: Colors.transparent,
        ),
      ),
    );
  }

  /// Floating Controls ở góc trên bên phải
  Widget _buildFloatingControls(List<int> availableFloors) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        // Chuyển tầng
        if (availableFloors.length > 1)
          Container(
            padding: const EdgeInsets.all(3),
            decoration: BoxDecoration(
              color: const Color(0xFF1e293b).withValues(alpha: 0.9),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFF334155)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: availableFloors.map((floor) {
                final isSelected = floor == _currentFloor;
                return InkWell(
                  onTap: () {
                    setState(() => _currentFloor = floor);
                  },
                  borderRadius: BorderRadius.circular(8),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: isSelected ? const Color(0xFF0284c7) : Colors.transparent,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      'Tầng $floor',
                      style: TextStyle(
                        color: isSelected ? Colors.white : Colors.white60,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
        const SizedBox(height: 8),

        // Nút toggle máy móc
        InkWell(
          onTap: () {
            setState(() => _showMachines = !_showMachines);
          },
          borderRadius: BorderRadius.circular(8),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: _showMachines ? const Color(0xFF0284c7).withValues(alpha: 0.25) : const Color(0xFF1e293b).withValues(alpha: 0.9),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: _showMachines ? const Color(0xFF38bdf8) : const Color(0xFF334155),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  PhosphorIcons.cpu(PhosphorIconsStyle.bold),
                  color: _showMachines ? const Color(0xFF38bdf8) : Colors.white60,
                  size: 14,
                ),
                const SizedBox(width: 5),
                Text(
                  'Máy móc',
                  style: TextStyle(
                    color: _showMachines ? const Color(0xFF38bdf8) : Colors.white60,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 8),

        // Zoom controls
        Container(
          decoration: BoxDecoration(
            color: const Color(0xFF1e293b).withValues(alpha: 0.9),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: const Color(0xFF334155)),
          ),
          child: Column(
            children: [
              IconButton(
                icon: Icon(PhosphorIcons.plus(PhosphorIconsStyle.bold), color: Colors.white, size: 16),
                tooltip: 'Phóng to',
                onPressed: () => _adjustZoom(1.2),
                constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                padding: EdgeInsets.zero,
              ),
              const Divider(color: Color(0xFF334155), height: 1),
              IconButton(
                icon: Icon(PhosphorIcons.minus(PhosphorIconsStyle.bold), color: Colors.white, size: 16),
                tooltip: 'Thu nhỏ',
                onPressed: () => _adjustZoom(0.8),
                constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                padding: EdgeInsets.zero,
              ),
            ],
          ),
        ),
      ],
    );
  }

  /// Floating Playback Stepper Control (Tiến / Lùi / Play / Pause)
  Widget _buildPlaybackStepperControl() {
    if (_routeData == null || _routeData!.orderedStops.isEmpty) return const SizedBox();
    final totalStops = _routeData!.orderedStops.length;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      decoration: BoxDecoration(
        color: const Color(0xFF1e293b).withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFF38bdf8).withValues(alpha: 0.4)),
        boxShadow: const [
          BoxShadow(color: Colors.black45, blurRadius: 10, offset: Offset(0, 4)),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Nút Lùi
          IconButton(
            icon: Icon(PhosphorIcons.caretLeft(PhosphorIconsStyle.bold), color: Colors.white, size: 16),
            tooltip: 'Trạm trước',
            onPressed: () {
              final prev = (_selectedStopIndex - 1 + totalStops) % totalStops;
              _focusOnStop(prev);
            },
            constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
            padding: EdgeInsets.zero,
          ),

          // Nhãn Chặng X/N
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 6),
            child: Text(
              'Chặng $_selectedStopIndex/${totalStops - 1}',
              style: const TextStyle(
                color: Color(0xFF38bdf8),
                fontSize: 11.5,
                fontWeight: FontWeight.bold,
                fontFamily: 'monospace',
              ),
            ),
          ),

          // Nút Tiến
          IconButton(
            icon: Icon(PhosphorIcons.caretRight(PhosphorIconsStyle.bold), color: Colors.white, size: 16),
            tooltip: 'Trạm kế tiếp',
            onPressed: () {
              final next = (_selectedStopIndex + 1) % totalStops;
              _focusOnStop(next);
            },
            constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
            padding: EdgeInsets.zero,
          ),

          // Nút Play / Pause
          InkWell(
            onTap: _togglePlayback,
            borderRadius: BorderRadius.circular(16),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: _isPlaying ? const Color(0xFFef4444) : const Color(0xFF0284c7),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Row(
                children: [
                  Icon(
                    _isPlaying ? PhosphorIcons.pause(PhosphorIconsStyle.fill) : PhosphorIcons.play(PhosphorIconsStyle.fill),
                    color: Colors.white,
                    size: 13,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    _isPlaying ? 'Dừng' : 'Chạy',
                    style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Draggable Scrollable Bottom Sheet chứa KPI Cards & Timeline Chặng
  Widget _buildDraggableBottomSheet() {
    return DraggableScrollableSheet(
      initialChildSize: 0.38,
      minChildSize: 0.12,
      maxChildSize: 0.90,
      snap: true,
      snapSizes: const [0.12, 0.38, 0.90],
      builder: (context, scrollController) {
        return Container(
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
            boxShadow: [
              BoxShadow(color: Colors.black26, blurRadius: 20, spreadRadius: 4),
            ],
          ),
          child: ListView(
            controller: scrollController,
            padding: EdgeInsets.zero,
            children: [
              // Thanh gạt kéo Handle
              Center(
                child: Container(
                  margin: const EdgeInsets.only(top: 10, bottom: 8),
                  width: 40,
                  height: 4.5,
                  decoration: BoxDecoration(
                    color: AppTheme.neutral300,
                    borderRadius: BorderRadius.circular(3),
                  ),
                ),
              ),

              // Banner lộ trình linh động thích ứng theo vị trí thao tác gần nhất của KTV
              if (_routeData != null && (_routeData!.isAdaptiveStart || (_routeData!.orderedStops.isNotEmpty && _routeData!.orderedStops.first.isCurrentLocation)))
                _buildAdaptiveStartBanner(),

              // 4 Thẻ KPI cuộn ngang
              _buildKpiCardsHorizontal(),

              const Divider(color: AppTheme.neutral200, height: 16),

              // Thanh công cụ thao tác nhanh (Giờ xuất phát, Pitstop, Tái định tuyến)
              _buildQuickActionBar(),

              const Divider(color: AppTheme.neutral200, height: 16),

              // Danh sách Timeline các chặng làm việc
              _buildTimelineList(),
            ],
          ),
        );
      },
    );
  }

  Widget _buildAdaptiveStartBanner() {
    final stop0 = _routeData!.orderedStops.first;
    final machineName = _routeData!.lastKnownMachine ?? stop0.assetName ?? stop0.name;
    final timeStr = _routeData!.lastKnownTime ?? 'gần đây';
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFecfdf5),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF6ee7b7), width: 1.2),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF10b981).withValues(alpha: 0.1),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: const BoxDecoration(
              color: Color(0xFF10b981),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.navigation, color: Colors.white, size: 16),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Text(
                      'LỘ TRÌNH LINH ĐỘNG THÍCH ỨNG',
                      style: TextStyle(
                        color: Color(0xFF047857),
                        fontSize: 11,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 0.5,
                      ),
                    ),
                    SizedBox(width: 6),
                    Text('⚡', style: TextStyle(fontSize: 11)),
                  ],
                ),
                const SizedBox(height: 3),
                Text(
                  'KTV vừa thao tác tại: $machineName (lúc $timeStr). Hệ thống đã tự động định tuyến xuất phát từ máy này tới công việc tiếp theo!',
                  style: const TextStyle(
                    color: Color(0xFF065f46),
                    fontSize: 11.5,
                    height: 1.35,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// 4 Thẻ KPI cuộn ngang
  Widget _buildKpiCardsHorizontal() {
    if (_routeData == null) return const SizedBox();
    final data = _routeData!;

    final hours = (data.totalEstimatedMinutes / 60).toStringAsFixed(1);
    final distanceMeters = data.totalDistanceMeters.toStringAsFixed(0);
    final stopsCount = data.totalStops.toString();
    final modeLabel = data.routingMode.contains('MANHATTAN') ? 'Manhattan 2D' : 'Tô-pô Phân cấp';

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        children: [
          _buildKpiCard(
            title: 'Tổng thời gian',
            value: '${data.totalEstimatedMinutes} ph',
            subValue: '~$hours giờ làm việc',
            icon: PhosphorIcons.clock(PhosphorIconsStyle.bold),
            color: const Color(0xFF0284c7),
            bgColor: const Color(0xFFe0f2fe),
          ),
          const SizedBox(width: 10),
          _buildKpiCard(
            title: 'Tổng quãng đường',
            value: '$distanceMeters m',
            subValue: 'Đi bộ trong xưởng',
            icon: PhosphorIcons.path(PhosphorIconsStyle.bold),
            color: const Color(0xFF10b981),
            bgColor: const Color(0xFFd1fae5),
          ),
          const SizedBox(width: 10),
          _buildKpiCard(
            title: 'Số trạm dừng',
            value: '$stopsCount trạm',
            subValue: 'Bao gồm trạm kho',
            icon: PhosphorIcons.mapPin(PhosphorIconsStyle.bold),
            color: const Color(0xFFf59e0b),
            bgColor: const Color(0xFFfef3c7),
          ),
          const SizedBox(width: 10),
          _buildKpiCard(
            title: 'Mô hình định tuyến',
            value: modeLabel,
            subValue: 'Trực giao hành lang',
            icon: PhosphorIcons.gitBranch(PhosphorIconsStyle.bold),
            color: const Color(0xFF8b5cf6),
            bgColor: const Color(0xFFede9fe),
          ),
        ],
      ),
    );
  }

  Widget _buildKpiCard({
    required String title,
    required String value,
    required String subValue,
    required IconData icon,
    required Color color,
    required Color bgColor,
  }) {
    return Container(
      width: 140,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 16),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: const TextStyle(color: AppTheme.neutral900, fontSize: 16, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 2),
          Text(
            subValue,
            style: const TextStyle(color: AppTheme.neutral500, fontSize: 10),
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  /// Thanh thao tác nhanh (Giờ xuất phát, Về kho, Pitstop)
  Widget _buildQuickActionBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Hàng tùy chọn: Giờ xuất phát + Checkbox Quay về kho
          Row(
            children: [
              // Chọn giờ xuất phát
              InkWell(
                onTap: _selectStartTime,
                borderRadius: BorderRadius.circular(8),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppTheme.neutral100,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppTheme.neutral300),
                  ),
                  child: Row(
                    children: [
                      Icon(PhosphorIcons.clock(PhosphorIconsStyle.bold), color: AppTheme.neutral700, size: 14),
                      const SizedBox(width: 6),
                      Text(
                        'Xuất phát: ${_formatTimeOfDay(_startTime)}',
                        style: const TextStyle(color: AppTheme.neutral900, fontSize: 12, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                ),
              ),
              const Spacer(),

              // Checkbox quay về kho cuối ca
              InkWell(
                onTap: () {
                  setState(() => _returnToDepot = !_returnToDepot);
                  _recalculateRoute();
                },
                child: Row(
                  children: [
                    Checkbox(
                      value: _returnToDepot,
                      activeColor: const Color(0xFF0284c7),
                      onChanged: (val) {
                        setState(() => _returnToDepot = val ?? true);
                        _recalculateRoute();
                      },
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      visualDensity: VisualDensity.compact,
                    ),
                    const Text(
                      'Về kho cuối ca',
                      style: TextStyle(color: AppTheme.neutral800, fontSize: 12, fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // Dropdown chọn kho tiếp vận (nếu có danh sách kho)
          if (_warehousesList.isNotEmpty)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              margin: const EdgeInsets.only(bottom: 10),
              decoration: BoxDecoration(
                color: AppTheme.neutral50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppTheme.neutral300),
              ),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<String>(
                  value: _selectedWarehouseId,
                  isExpanded: true,
                  hint: const Text('Chọn kho tiếp vận vật tư', style: TextStyle(fontSize: 12)),
                  items: _warehousesList.map((wh) {
                    return DropdownMenuItem<String>(
                      value: wh['id'],
                      child: Text(
                        '🏢 ${wh['name']} (Tầng ${wh['floorLevel']})',
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                      ),
                    );
                  }).toList(),
                  onChanged: (val) {
                    setState(() => _selectedWarehouseId = val);
                  },
                ),
              ),
            ),

          // 3 Nút hành động tiện ích
          Row(
            children: [
              // Về lấy vật tư
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: _triggerPitstop,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFf97316),
                    foregroundColor: Colors.white,
                    elevation: 0,
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  icon: Icon(PhosphorIcons.package(PhosphorIconsStyle.bold), size: 14),
                  label: const Text('Về lấy vật tư', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold)),
                ),
              ),
              const SizedBox(width: 8),

              // Tái định tuyến
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: _triggerDynamicReRoute,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF0284c7),
                    foregroundColor: Colors.white,
                    elevation: 0,
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  icon: Icon(PhosphorIcons.arrowsClockwise(PhosphorIconsStyle.bold), size: 14),
                  label: const Text('Tái định tuyến', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold)),
                ),
              ),
              const SizedBox(width: 8),

              // Tính lại
              ElevatedButton(
                onPressed: _recalculateRoute,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF10b981),
                  foregroundColor: Colors.white,
                  elevation: 0,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                child: Icon(PhosphorIcons.lightning(PhosphorIconsStyle.bold), size: 16),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// Danh sách Timeline các Chặng làm việc
  Widget _buildTimelineList() {
    if (_routeData == null || _routeData!.orderedStops.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(32),
        child: Center(child: Text('Không có trạm dừng nào trong ca trực hôm nay.')),
      );
    }

    final stops = _routeData!.orderedStops;

    return ListView.builder(
      controller: _timelineScrollController,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: stops.length,
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 40),
      itemBuilder: (context, index) {
        final stop = stops[index];
        final isSelected = (_selectedStopIndex == index);

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Thông tin di chuyển từ trạm trước tới trạm này
            if (index > 0)
              Padding(
                padding: const EdgeInsets.only(left: 20, top: 4, bottom: 4),
                child: Row(
                  children: [
                    Container(
                      width: 2,
                      height: 24,
                      color: AppTheme.neutral300,
                    ),
                    const SizedBox(width: 14),
                    Icon(PhosphorIcons.arrowDown(PhosphorIconsStyle.bold), size: 12, color: AppTheme.neutral500),
                    const SizedBox(width: 6),
                    Text(
                      'Di chuyển ${stop.travelDistanceMeters.toStringAsFixed(0)}m (~${stop.travelTimeMinutes.toStringAsFixed(1)} ph)',
                      style: const TextStyle(color: AppTheme.neutral500, fontSize: 11, fontStyle: FontStyle.italic),
                    ),
                  ],
                ),
              ),

            // Banner cảnh báo chuyển tầng
            if (stop.floorTransition != null)
              Container(
                margin: const EdgeInsets.only(left: 8, bottom: 6, top: 2),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: const Color(0xFFede9fe),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFFc4b5fd)),
                ),
                child: Row(
                  children: [
                    const Text('🪜', style: TextStyle(fontSize: 14)),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        'Chuyển tầng: Tầng ${stop.floorTransition!.fromFloor} ➔ Tầng ${stop.floorTransition!.toFloor} qua Cầu thang bộ',
                        style: const TextStyle(
                          color: Color(0xFF6d28d9),
                          fontSize: 11.5,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

            // Thẻ công việc của trạm
            InkWell(
              onTap: () => _focusOnStop(index),
              borderRadius: BorderRadius.circular(12),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: isSelected ? const Color(0xFFf0f9ff) : Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: isSelected ? const Color(0xFF0284c7) : AppTheme.neutral200,
                    width: isSelected ? 2 : 1,
                  ),
                  boxShadow: [
                    if (isSelected)
                      BoxShadow(
                        color: const Color(0xFF0284c7).withValues(alpha: 0.15),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      )
                    else
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.03),
                        blurRadius: 4,
                        offset: const Offset(0, 1),
                      ),
                  ],
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Badge số thứ tự trạm
                    Container(
                      width: 32,
                      height: 32,
                      decoration: BoxDecoration(
                        color: stop.pinColor,
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: stop.pinColor.withValues(alpha: 0.35),
                            blurRadius: 6,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        '${stop.step}',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 13,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),

                    // Nội dung công việc
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Hàng Header: Tên trạm / Mã WO + Nhãn mức độ
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  stop.name,
                                  style: const TextStyle(
                                    color: AppTheme.neutral900,
                                    fontSize: 13,
                                    fontWeight: FontWeight.bold,
                                  ),
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              const SizedBox(width: 6),
                              _buildPriorityChip(stop),
                            ],
                          ),
                          const SizedBox(height: 4),

                          // Mã WO & Tên máy móc
                          if (stop.workOrderCode != null || stop.assetName != null)
                            Padding(
                              padding: const EdgeInsets.only(bottom: 4),
                              child: Text(
                                '${stop.workOrderCode ?? ""} • ${stop.assetName ?? ""}',
                                style: const TextStyle(
                                  color: Color(0xFF0284c7),
                                  fontSize: 11.5,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),

                          // Vị trí & Tầng
                          Row(
                            children: [
                              Icon(PhosphorIcons.mapPin(PhosphorIconsStyle.bold), size: 12, color: AppTheme.neutral500),
                              const SizedBox(width: 4),
                              Expanded(
                                child: Text(
                                  '${stop.locationName ?? "Hiện trường"} (Tầng ${stop.floorNumber})',
                                  style: const TextStyle(color: AppTheme.neutral600, fontSize: 11),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),

                          // Giờ đến dự kiến & Khung giờ máy
                          Row(
                            children: [
                              Icon(PhosphorIcons.clock(PhosphorIconsStyle.bold), size: 12, color: const Color(0xFF10b981)),
                              const SizedBox(width: 4),
                              Text(
                                'Dự kiến: ${stop.estimatedArrival}',
                                style: const TextStyle(
                                  color: Color(0xFF047857),
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              if (stop.timeWindow != null && stop.timeWindow!.displayString.isNotEmpty) ...[
                                const SizedBox(width: 10),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFFfef3c7),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    '⏰ Khung giờ: ${stop.timeWindow!.displayString}',
                                    style: const TextStyle(
                                      color: Color(0xFFb45309),
                                      fontSize: 10,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),
                              ],
                            ],
                          ),
                          if (stop.workOrderId != null) ...[
                            const SizedBox(height: 8),
                            InkWell(
                              onTap: () {
                                context.push('/work-order-detail/${stop.workOrderId}', extra: stop.workOrderCode);
                              },
                              borderRadius: BorderRadius.circular(8),
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                                decoration: BoxDecoration(
                                  color: const Color(0xFF0284c7).withValues(alpha: 0.1),
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(color: const Color(0xFF0284c7).withValues(alpha: 0.3)),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(PhosphorIcons.arrowSquareOut(PhosphorIconsStyle.bold), size: 13, color: const Color(0xFF0284c7)),
                                    const SizedBox(width: 5),
                                    const Text(
                                      'Mở chi tiết phiếu việc',
                                      style: TextStyle(color: Color(0xFF0284c7), fontSize: 11, fontWeight: FontWeight.bold),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildPriorityChip(RouteStop stop) {
    if (stop.isUrgent) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: BoxDecoration(
          color: const Color(0xFFfee2e2),
          borderRadius: BorderRadius.circular(4),
        ),
        child: const Text(
          'KHẨN CẤP',
          style: TextStyle(color: Color(0xFFb91c1c), fontSize: 9.5, fontWeight: FontWeight.w900),
        ),
      );
    }
    if (stop.priority == 'HIGH') {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: BoxDecoration(
          color: const Color(0xFFffedd5),
          borderRadius: BorderRadius.circular(4),
        ),
        child: const Text(
          'ƯU TIÊN CAO',
          style: TextStyle(color: Color(0xFFc2410c), fontSize: 9.5, fontWeight: FontWeight.bold),
        ),
      );
    }
    if (stop.isWarehouse) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: BoxDecoration(
          color: const Color(0xFFfef3c7),
          borderRadius: BorderRadius.circular(4),
        ),
        child: const Text(
          'TIẾP VẬN',
          style: TextStyle(color: Color(0xFFb45309), fontSize: 9.5, fontWeight: FontWeight.bold),
        ),
      );
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppTheme.neutral100,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        stop.typeLabel.toUpperCase(),
        style: const TextStyle(color: AppTheme.neutral600, fontSize: 9.5, fontWeight: FontWeight.bold),
      ),
    );
  }
}
