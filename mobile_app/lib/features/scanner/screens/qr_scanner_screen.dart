import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:go_router/go_router.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../../core/theme/app_theme.dart';
import '../../work_orders/services/work_order_service.dart';

class QRScannerScreen extends StatefulWidget {
  const QRScannerScreen({super.key});

  @override
  State<QRScannerScreen> createState() => _QRScannerScreenState();
}

class _QRScannerScreenState extends State<QRScannerScreen> {
  final MobileScannerController controller = MobileScannerController(
    detectionSpeed: DetectionSpeed.noDuplicates,
    facing: CameraFacing.back,
  );

  bool _isScanning = true;
  bool _isLoading = false;
  final WorkOrderService _workOrderService = WorkOrderService();

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) async {
    if (!_isScanning || _isLoading) return;

    final List<Barcode> barcodes = capture.barcodes;
    if (barcodes.isNotEmpty) {
      final String? code = barcodes.first.rawValue;
      if (code != null) {
        setState(() {
          _isScanning = false;
          _isLoading = true;
        });

        HapticFeedback.vibrate();

        Map<String, dynamic>? asset;
        try {
          asset = await _workOrderService.getAssetByQrCode(code);
        } catch (e) {
          if (!mounted) return;
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Lỗi kết nối mạng, vui lòng thử lại'),
              backgroundColor: AppTheme.dangerColor,
            ),
          );
          setState(() {
            _isScanning = true;
            _isLoading = false;
          });
          return;
        }
        
        if (!mounted) return;

        if (asset == null) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Không tìm thấy thiết bị'),
              backgroundColor: AppTheme.dangerColor,
            ),
          );
          setState(() {
            _isScanning = true;
            _isLoading = false;
          });
          return;
        }

        final myWorkOrders = await _workOrderService.getMobileHomeWorkOrders();
        final assignedWos = myWorkOrders.where((wo) => wo.assetId == asset!['id']).toList();

        if (!mounted) return;
        setState(() {
          _isLoading = false;
        });

        if (assignedWos.isNotEmpty) {
          context.pushReplacement('/work-order-detail/${assignedWos.first.id}');
        } else {
          context.pushReplacement('/equipment-detail', extra: asset);
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // Camera feed
          MobileScanner(controller: controller, onDetect: _onDetect),

          // Custom Overlay
          QRScannerOverlay(overlayColour: Colors.black.withValues(alpha: 0.6)),

          // Header / Back Button
          Positioned(
            top: MediaQuery.of(context).padding.top + 16,
            left: 16,
            child: IconButton(
              icon: Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.5),
                  ),
                ),
                child: Icon(PhosphorIcons.x(), color: Colors.white, size: 24),
              ),
              onPressed: () => context.pop(),
            ),
          ),

          // Title
          Positioned(
            top: MediaQuery.of(context).padding.top + 24,
            left: 0,
            right: 0,
            child: const Center(
              child: Text(
                'Quét mã thiết bị',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 0.5,
                ),
              ),
            ),
          ),

          // Bottom Controls (Flashlight)
          Positioned(
            bottom: 48,
            left: 0,
            right: 0,
            child: Center(
              child: ValueListenableBuilder(
                valueListenable: controller,
                builder: (context, state, child) {
                  switch (state.torchState) {
                    case TorchState.off:
                      return _buildFlashButton(
                        icon: PhosphorIcons.flashlight(),
                        onPressed: () => controller.toggleTorch(),
                      );
                    case TorchState.on:
                      return _buildFlashButton(
                        icon: PhosphorIcons.flashlight(PhosphorIconsStyle.fill),
                        isActive: true,
                        onPressed: () => controller.toggleTorch(),
                      );
                    case TorchState.unavailable:
                    case TorchState.auto:
                      return const SizedBox.shrink();
                  }
                },
              ),
            ),
          ),

          // Instructional Text
          const Positioned(
            bottom: 120,
            left: 0,
            right: 0,
            child: Center(
              child: Text(
                'Di chuyển camera để quét mã QR\ntrên thiết bị',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  height: 1.5,
                ),
              ),
            ),
          ),

          // Loading Overlay
          if (_isLoading)
            Container(
              color: Colors.black.withValues(alpha: 0.5),
              child: const Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    CircularProgressIndicator(
                      color: AppTheme.primaryColor,
                    ),
                    SizedBox(height: 16),
                    Text(
                      'Đang tra cứu dữ liệu...',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildFlashButton({
    required IconData icon,
    bool isActive = false,
    required VoidCallback onPressed,
  }) {
    return InkWell(
      onTap: onPressed,
      borderRadius: BorderRadius.circular(32),
      child: Container(
        width: 64,
        height: 64,
        decoration: BoxDecoration(
          color: isActive
              ? AppTheme.primaryColor
              : Colors.white.withValues(alpha: 0.2),
          shape: BoxShape.circle,
          border: Border.all(
            color: isActive
                ? AppTheme.primaryColor
                : Colors.white.withValues(alpha: 0.5),
            width: 2,
          ),
        ),
        child: Icon(icon, color: Colors.white, size: 28),
      ),
    );
  }
}

class QRScannerOverlay extends StatelessWidget {
  final Color overlayColour;

  const QRScannerOverlay({super.key, required this.overlayColour});

  @override
  Widget build(BuildContext context) {
    double scanArea =
        (MediaQuery.of(context).size.width < 400 ||
            MediaQuery.of(context).size.height < 400)
        ? 250.0
        : 300.0;

    return Stack(
      children: [
        ColorFiltered(
          colorFilter: ColorFilter.mode(overlayColour, BlendMode.srcOut),
          child: Stack(
            children: [
              Container(
                decoration: const BoxDecoration(color: Colors.transparent),
                child: Align(
                  alignment: Alignment.center,
                  child: Container(
                    width: scanArea,
                    height: scanArea,
                    decoration: BoxDecoration(
                      color: Colors.black,
                      borderRadius: BorderRadius.circular(24),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
        Align(
          alignment: Alignment.center,
          child: CustomPaint(
            foregroundPainter: BorderPainter(scanArea: scanArea),
            child: SizedBox(width: scanArea + 4, height: scanArea + 4),
          ),
        ),
      ],
    );
  }
}

class BorderPainter extends CustomPainter {
  final double scanArea;

  BorderPainter({required this.scanArea});

  @override
  void paint(Canvas canvas, Size size) {
    final width = size.width;
    final height = size.height;
    final borderLength = scanArea * 0.2;
    const strokeWidth = 4.0;
    const radius = 24.0;

    final paint = Paint()
      ..color = AppTheme.primaryColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;

    // Top Left
    canvas.drawArc(
      Rect.fromCircle(center: const Offset(radius, radius), radius: radius),
      -3.14,
      1.57,
      false,
      paint,
    );
    canvas.drawLine(const Offset(0, radius), Offset(0, borderLength), paint);
    canvas.drawLine(const Offset(radius, 0), Offset(borderLength, 0), paint);

    // Top Right
    canvas.drawArc(
      Rect.fromCircle(center: Offset(width - radius, radius), radius: radius),
      -1.57,
      1.57,
      false,
      paint,
    );
    canvas.drawLine(
      Offset(width - borderLength, 0),
      Offset(width - radius, 0),
      paint,
    );
    canvas.drawLine(Offset(width, radius), Offset(width, borderLength), paint);

    // Bottom Left
    canvas.drawArc(
      Rect.fromCircle(center: Offset(radius, height - radius), radius: radius),
      1.57,
      1.57,
      false,
      paint,
    );
    canvas.drawLine(
      Offset(0, height - borderLength),
      Offset(0, height - radius),
      paint,
    );
    canvas.drawLine(
      Offset(radius, height),
      Offset(borderLength, height),
      paint,
    );

    // Bottom Right
    canvas.drawArc(
      Rect.fromCircle(
        center: Offset(width - radius, height - radius),
        radius: radius,
      ),
      0,
      1.57,
      false,
      paint,
    );
    canvas.drawLine(
      Offset(width - borderLength, height),
      Offset(width - radius, height),
      paint,
    );
    canvas.drawLine(
      Offset(width, height - borderLength),
      Offset(width, height - radius),
      paint,
    );
  }

  @override
  bool shouldRepaint(CustomPainter oldDelegate) => false;
}
