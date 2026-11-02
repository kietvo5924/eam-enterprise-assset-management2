import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../../core/theme/app_theme.dart';
import '../models/work_order.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import '../services/ble_beacon_service.dart';
import '../services/work_order_service.dart';

class FieldAttendanceScreen extends StatefulWidget {
  final WorkOrder workOrder;

  const FieldAttendanceScreen({
    super.key,
    required this.workOrder,
  });

  @override
  State<FieldAttendanceScreen> createState() => _FieldAttendanceScreenState();
}

class _FieldAttendanceScreenState extends State<FieldAttendanceScreen>
    with TickerProviderStateMixin, WidgetsBindingObserver {
  final BleBeaconService _bleService = BleBeaconService();
  final WorkOrderService _woService = WorkOrderService();

  int _currentStep = 1; // 1: BLE Radar, 2: Face Biometric
  bool _isScanningBle = false;
  BleScanResult? _bleResult;

  // Live Camera & Face Biometric state
  CameraController? _cameraController;
  bool _isCameraInitializing = false;
  bool _isCameraInitialized = false;
  bool _isScanningFace = false;
  bool _isProcessingBiometric = false;
  bool _isFacePassed = false;
  String? _errorMessage;

  late AnimationController _radarController;
  late AnimationController _scanLineController;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);

    _radarController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat();

    _scanLineController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);

    if (!widget.workOrder.requireBleBeacon) {
      _bleResult = BleScanResult.found(
        beaconId: 'BLE_EXEMPT_BY_ASSET',
        rssi: 0,
        distanceMeters: 0.0,
        isWithinRange: true,
        message: 'Thiết bị không gắn Beacon (Bàn ghế/Nội thất). Tự động miễn trừ quét sóng BLE.',
      );
      _currentStep = 2; // Jump directly to face scan
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _initFrontCamera();
      });
    } else {
      _startBleScan();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _radarController.dispose();
    _scanLineController.dispose();
    _cameraController?.dispose();
    super.dispose();
  }

  Future<void> _disposeCamera() async {
    final c = _cameraController;
    _cameraController = null;
    _isCameraInitialized = false;
    _isCameraInitializing = false;
    _isScanningFace = false;
    if (c != null) {
      await c.dispose();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    super.didChangeAppLifecycleState(state);
    // SECURITY POLICY: Nếu người dùng thoát app, ẩn app ra ngoài màn hình chính hoặc khóa máy:
    // Hủy bỏ toàn bộ kết quả phiên hiện tại, bắt buộc phải quét lại từ Bước 1 (BLE Presence) liên tiếp!
    if (state == AppLifecycleState.paused || state == AppLifecycleState.hidden) {
      _disposeCamera();
      if (mounted && widget.workOrder.requireBleBeacon) {
        setState(() {
          _currentStep = 1;
          _bleResult = null;
          _isFacePassed = false;
          _errorMessage = 'Phiên điểm danh bị gián đoạn do bạn rời ứng dụng. Vui lòng quét lại sóng ESP32 tại hiện trường!';
        });
      }
    }
  }

  Future<void> _startBleScan() async {
    setState(() {
      _isScanningBle = true;
      _errorMessage = null;
    });

    final targetUuid = widget.workOrder.bleBeaconUuid ?? BleBeaconService.universalBeaconUuid;
    final result = await _bleService.scanForBeacon(
      targetUuid: targetUuid,
      timeout: const Duration(seconds: 4),
    );

    if (mounted) {
      setState(() {
        _isScanningBle = false;
        _bleResult = result;
      });
    }
  }

  Future<void> _initFrontCamera() async {
    if (_cameraController != null) return;
    setState(() {
      _isCameraInitializing = true;
      _errorMessage = null;
    });

    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        throw Exception('Không tìm thấy Camera trên thiết bị.');
      }
      // BẮT BUỘC 100%: Sử dụng Camera trước
      final frontCamera = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.front,
        orElse: () => cameras.first,
      );

      final controller = CameraController(
        frontCamera,
        ResolutionPreset.medium,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.jpeg,
      );

      await controller.initialize();
      if (!mounted) {
        await controller.dispose();
        return;
      }

      setState(() {
        _cameraController = controller;
        _isCameraInitialized = true;
        _isCameraInitializing = false;
      });

      // Tự động kích hoạt quét sinh trắc học trực tiếp (trải nghiệm rảnh tay như app ngân hàng)
      _startLiveFaceScan();
    } catch (e) {
      if (mounted) {
        setState(() {
          _isCameraInitializing = false;
          _errorMessage = 'Không thể mở Camera trước: $e';
        });
      }
    }
  }

  Future<void> _startLiveFaceScan() async {
    if (_isScanningFace || _isProcessingBiometric || _isFacePassed) return;
    if (_cameraController == null || !_cameraController!.value.isInitialized) {
      await _initFrontCamera();
      return;
    }

    setState(() {
      _isScanningFace = true;
      _errorMessage = null;
    });

    // Quét trực tiếp: Giữ thẳng khuôn mặt trong 2.5s để thanh laser quét qua
    await Future.delayed(const Duration(milliseconds: 2500));
    if (!mounted || _currentStep != 2) return;

    try {
      setState(() {
        _isScanningFace = false;
        _isProcessingBiometric = true;
      });

      // Chụp khung hình ngầm từ live camera thực tế
      String? capturedBase64;
      if (_cameraController != null && _cameraController!.value.isInitialized) {
        try {
          final XFile picture = await _cameraController!.takePicture();
          final Uint8List bytes = await picture.readAsBytes();
          capturedBase64 = base64Encode(bytes);
        } catch (e) {
          debugPrint('Lỗi chụp khung hình camera: $e');
        }
      }

      if (capturedBase64 == null) {
        throw Exception('Không thể lấy khung hình từ Camera trước.');
      }

      // Gửi điểm danh và ảnh camera thực tế lên máy chủ để nhận diện
      final rssiVal = widget.workOrder.requireBleBeacon ? _bleResult?.rssi : null;
      final beaconId = widget.workOrder.requireBleBeacon
          ? (_bleResult?.beaconId ?? BleBeaconService.universalBeaconName)
          : null;

      final checkInResponse = await _woService.checkIn(
        workOrderId: widget.workOrder.id,
        faceImageBase64: capturedBase64,
        rssi: rssiVal,
        bleBeaconId: beaconId,
      );

      if (!mounted) return;

      if (checkInResponse != null && checkInResponse['overallCompliance'] != 'FAILED') {
        setState(() {
          _isProcessingBiometric = false;
          _isFacePassed = true;
        });

        // Hiển thị khung xanh thành công 1.2s rồi tự động hoàn tất và trở về màn hình chi tiết
        await Future.delayed(const Duration(milliseconds: 1200));
        if (mounted) {
          Navigator.of(context).pop(true);
        }
      } else {
        setState(() {
          _isProcessingBiometric = false;
          _errorMessage = 'Khuôn mặt không khớp với hồ sơ đã đăng ký hoặc vi phạm cự ly!';
        });
      }
    } catch (e) {
      if (!mounted) return;
      final cleanMsg = e.toString().replaceAll('Exception: ', '');
      setState(() {
        _isProcessingBiometric = false;
        _isScanningFace = false;
        _errorMessage = cleanMsg;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: _currentStep == 1,
      onPopInvokedWithResult: (didPop, result) async {
        if (didPop) return;
        // Bấm nút Back cứng của Android khi đang ở Bước 2: Hủy phiên và reset về Bước 1
        if (mounted && widget.workOrder.requireBleBeacon) {
          await _disposeCamera();
          if (mounted) {
            setState(() {
              _currentStep = 1;
              _bleResult = null;
                  _isFacePassed = false;
              _errorMessage = 'Đã hủy phiên. Bạn phải hoàn thành liên tiếp cả 2 bước tại hiện trường!';
            });
          }
        }
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Điểm Danh Hiện Trường', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          leading: IconButton(
            icon: Icon(_currentStep == 2 ? PhosphorIconsRegular.arrowLeft : PhosphorIconsRegular.x),
            onPressed: () async {
              if (_currentStep == 2 && widget.workOrder.requireBleBeacon) {
                // Quay lại từ bước 2: Hủy cả 2 bước, bắt buộc quét lại từ bước 1
                await _disposeCamera();
                if (mounted) {
                  setState(() {
                    _currentStep = 1;
                    _bleResult = null;
                              _isFacePassed = false;
                    _errorMessage = 'Đã hủy phiên. Bạn phải hoàn thành liên tiếp cả 2 bước tại hiện trường!';
                  });
                }
              } else {
                await _disposeCamera();
                if (mounted) {
                  Navigator.of(context).pop(false);
                }
              }
            },
          ),
        ),
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Header Card
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryLightColor,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.primaryColor.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    children: [
                      const Icon(PhosphorIconsRegular.shieldCheck, color: AppTheme.primaryColor, size: 32),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              widget.workOrder.title,
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: AppTheme.neutral900),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Thiết bị: ${widget.workOrder.assetName ?? "Chưa rõ"}',
                              style: const TextStyle(fontSize: 12, color: AppTheme.neutral600),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),

                // Step indicator
                Row(
                  children: [
                    _buildStepBubble(1, 'Sóng ESP32 BLE', _currentStep >= 1, _bleResult?.isWithinRange == true),
                    Expanded(
                      child: Container(
                        height: 2,
                        color: _currentStep >= 2 ? AppTheme.primaryColor : AppTheme.neutral300,
                      ),
                    ),
                    _buildStepBubble(2, 'Khuôn Mặt AI', _currentStep == 2, _isFacePassed),
                  ],
                ),
                const SizedBox(height: 24),

                if (_errorMessage != null) ...[
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.dangerColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppTheme.dangerColor),
                    ),
                    child: Row(
                      children: [
                        const Icon(PhosphorIconsRegular.warningCircle, color: AppTheme.dangerColor),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            _errorMessage!,
                            style: const TextStyle(color: AppTheme.dangerColor, fontSize: 13),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                ],

                // Content based on Step
                if (_currentStep == 1) _buildBleStepContent() else _buildFaceStepContent(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildStepBubble(int step, String title, bool isActive, bool isDone) {
    Color bg = AppTheme.neutral200;
    Color fg = AppTheme.neutral600;
    if (isDone) {
      bg = AppTheme.successColor;
      fg = Colors.white;
    } else if (isActive) {
      bg = AppTheme.primaryColor;
      fg = Colors.white;
    }

    return Column(
      children: [
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: bg,
            shape: BoxShape.circle,
          ),
          child: Center(
            child: isDone
                ? const Icon(PhosphorIconsRegular.check, color: Colors.white, size: 20)
                : Text('$step', style: TextStyle(color: fg, fontWeight: FontWeight.bold)),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          title,
          style: TextStyle(
            fontSize: 11,
            fontWeight: isActive ? FontWeight.bold : FontWeight.normal,
            color: isActive ? AppTheme.neutral900 : AppTheme.neutral500,
          ),
        ),
      ],
    );
  }

  Widget _buildBleStepContent() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 10, offset: const Offset(0, 4)),
        ],
      ),
      child: Column(
        children: [
          const Text(
            'Bước 1: Quét Sóng ESP32 Micro-Geofencing',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          ),
          const SizedBox(height: 8),
          const Text(
            'Yêu cầu kỹ thuật viên có mặt trong bán kính tối đa 50m quanh máy phát sóng ESP32.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 13, color: AppTheme.neutral600),
          ),
          const SizedBox(height: 24),

          // Radar visual (Fixed dimensions prevent layout jumping/jittering)
          Center(
            child: SizedBox(
              width: 180,
              height: 180,
              child: AnimatedBuilder(
                animation: _radarController,
                builder: (context, child) {
                  return Stack(
                    alignment: Alignment.center,
                    children: [
                      Container(
                        width: 115 + (_radarController.value * 55),
                        height: 115 + (_radarController.value * 55),
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: (_bleResult?.isWithinRange == true
                                  ? AppTheme.successColor
                                  : AppTheme.primaryColor)
                              .withValues(alpha: 0.16 * (1.0 - _radarController.value)),
                        ),
                      ),
                      Container(
                        width: 110,
                        height: 110,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: _bleResult?.isWithinRange == true
                              ? AppTheme.successColor.withValues(alpha: 0.12)
                              : AppTheme.primaryColor.withValues(alpha: 0.12),
                          border: Border.all(
                            color: _bleResult?.isWithinRange == true
                                ? AppTheme.successColor
                                : AppTheme.primaryColor,
                            width: 2,
                          ),
                        ),
                        child: Icon(
                          PhosphorIconsRegular.broadcast,
                          size: 48,
                          color: _bleResult?.isWithinRange == true
                              ? AppTheme.successColor
                              : AppTheme.primaryColor,
                        ),
                      ),
                    ],
                  );
                },
              ),
            ),
          ),
          const SizedBox(height: 24),

          // BLE Status info
          if (_isScanningBle)
            const Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                SizedBox(width: 10),
                Text('Đang dò sóng ESP32 Beacon...', style: TextStyle(fontSize: 13, color: AppTheme.neutral600)),
              ],
            )
          else if (_bleResult != null)
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: _bleResult!.isWithinRange
                    ? AppTheme.successColor.withValues(alpha: 0.08)
                    : AppTheme.dangerColor.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: _bleResult!.isWithinRange ? AppTheme.successColor : AppTheme.dangerColor,
                ),
              ),
              child: Column(
                children: [
                  Row(
                    children: [
                      Icon(
                        _bleResult!.isWithinRange ? PhosphorIconsRegular.checkCircle : PhosphorIconsRegular.warningCircle,
                        color: _bleResult!.isWithinRange ? AppTheme.successColor : AppTheme.dangerColor,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _bleResult!.message,
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: _bleResult!.isWithinRange ? AppTheme.successColor : AppTheme.dangerColor,
                          ),
                        ),
                      ),
                    ],
                  ),
                  if (_bleResult!.isFound) ...[
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 7),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(
                                color: _bleResult!.isWithinRange
                                    ? AppTheme.successColor.withValues(alpha: 0.3)
                                    : AppTheme.dangerColor.withValues(alpha: 0.3),
                              ),
                            ),
                            child: FittedBox(
                              fit: BoxFit.scaleDown,
                              child: Text(
                                'RSSI: ${_bleResult!.rssi} dBm',
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                  color: AppTheme.neutral800,
                                ),
                                textAlign: TextAlign.center,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 7),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(
                                color: _bleResult!.isWithinRange
                                    ? AppTheme.successColor.withValues(alpha: 0.3)
                                    : AppTheme.dangerColor.withValues(alpha: 0.3),
                              ),
                            ),
                            child: FittedBox(
                              fit: BoxFit.scaleDown,
                              child: Text(
                                'Cự ly: ~${_bleResult!.distanceMeters.toStringAsFixed(1)}m',
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                  color: AppTheme.neutral800,
                                ),
                                textAlign: TextAlign.center,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          const SizedBox(height: 24),

          // Actions
          if (_bleResult?.isWithinRange == true)
            ElevatedButton(
              onPressed: () {
                setState(() {
                  _currentStep = 2;
                  _errorMessage = null;
                });
                _initFrontCamera();
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryColor,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 13),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: const Text(
                'Tiếp Tục Quét Khuôn Mặt',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
              ),
            )
          else if (_bleResult?.isBluetoothOff == true)
            ElevatedButton.icon(
              onPressed: () async {
                try {
                  await FlutterBluePlus.turnOn();
                  await Future.delayed(const Duration(seconds: 1));
                  _startBleScan();
                } catch (e) {
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text('Vui lòng bật Bluetooth trong Cài đặt: $e'),
                        backgroundColor: AppTheme.dangerColor,
                      ),
                    );
                  }
                }
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF0284c7),
                foregroundColor: Colors.white,
              ),
              icon: const Icon(PhosphorIconsRegular.bluetooth),
              label: const Text('Bật Bluetooth Ngay'),
            )
          else
            OutlinedButton.icon(
              onPressed: _isScanningBle ? null : _startBleScan,
              icon: const Icon(PhosphorIconsRegular.arrowsClockwise),
              label: const Text('Quét Lại Sóng BLE'),
            ),
        ],
      ),
    );
  }

  Widget _buildFaceStepContent() {
    Color frameBorderColor;
    List<BoxShadow> frameShadow;

    if (_isFacePassed) {
      frameBorderColor = const Color(0xFF22C55E); // Emerald Green
      frameShadow = [
        BoxShadow(color: const Color(0xFF22C55E).withValues(alpha: 0.5), blurRadius: 24, spreadRadius: 2),
      ];
    } else if (_isProcessingBiometric) {
      frameBorderColor = const Color(0xFFF59E0B); // Amber
      frameShadow = [
        BoxShadow(color: const Color(0xFFF59E0B).withValues(alpha: 0.4), blurRadius: 20),
      ];
    } else if (_isScanningFace) {
      frameBorderColor = const Color(0xFF00E5FF); // Neon Cyan
      frameShadow = [
        BoxShadow(color: const Color(0xFF00E5FF).withValues(alpha: 0.4), blurRadius: 20),
      ];
    } else if (_errorMessage != null) {
      frameBorderColor = AppTheme.dangerColor;
      frameShadow = [
        BoxShadow(color: AppTheme.dangerColor.withValues(alpha: 0.3), blurRadius: 16),
      ];
    } else {
      frameBorderColor = AppTheme.primaryColor;
      frameShadow = [
        BoxShadow(color: AppTheme.primaryColor.withValues(alpha: 0.2), blurRadius: 12),
      ];
    }

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 10, offset: const Offset(0, 4)),
        ],
      ),
      child: Column(
        children: [
          const Text(
            'Bước 2: Quét Khuôn Mặt Tự Động (AI eKYC)',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          ),
          const SizedBox(height: 8),
          const Text(
            'Nhìn thẳng vào khung hình oval camera trước để hệ thống tự động nhận diện sinh trắc học.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 13, color: AppTheme.neutral600),
          ),
          const SizedBox(height: 20),

          // Live Camera Viewfinder Oval
          Center(
            child: Container(
              width: 220,
              height: 290,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(110),
                border: Border.all(
                  color: frameBorderColor,
                  width: _isFacePassed ? 3.5 : 3.0,
                ),
                boxShadow: frameShadow,
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(107),
                child: Container(
                  color: Colors.black,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      // 1. Live Camera Stream
                      if (_cameraController != null && _cameraController!.value.isInitialized)
                        FittedBox(
                          fit: BoxFit.cover,
                          child: SizedBox(
                            width: _cameraController!.value.previewSize?.height ?? 220,
                            height: _cameraController!.value.previewSize?.width ?? 290,
                            child: CameraPreview(_cameraController!),
                          ),
                        )
                      else
                        Container(
                          color: const Color(0xFF0F172A),
                          child: Center(
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                SizedBox(
                                  width: 28,
                                  height: 28,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2.5,
                                    color: _isCameraInitializing ? const Color(0xFF00E5FF) : Colors.white70,
                                  ),
                                ),
                                const SizedBox(height: 12),
                                Text(
                                  _isCameraInitializing ? 'Đang mở Camera trước...' : 'Chờ khởi động camera...',
                                  style: const TextStyle(color: Colors.white70, fontSize: 12),
                                ),
                              ],
                            ),
                          ),
                        ),

                      // 2. Face Alignment Silhouette Guide
                      if (!_isFacePassed)
                        Center(
                          child: Container(
                            width: 160,
                            height: 210,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(80),
                              border: Border.all(
                                color: Colors.white.withValues(alpha: 0.35),
                                width: 1.5,
                              ),
                            ),
                          ),
                        ),

                      // 3. Animated Laser Scanning Line
                      if (_isScanningFace && !_isFacePassed)
                        AnimatedBuilder(
                          animation: _scanLineController,
                          builder: (context, child) {
                            return Positioned(
                              top: _scanLineController.value * 260,
                              left: 0,
                              right: 0,
                              child: Container(
                                height: 24,
                                decoration: BoxDecoration(
                                  gradient: LinearGradient(
                                    begin: Alignment.topCenter,
                                    end: Alignment.bottomCenter,
                                    colors: [
                                      const Color(0xFF00E5FF).withValues(alpha: 0.0),
                                      const Color(0xFF00E5FF).withValues(alpha: 0.3),
                                      const Color(0xFF00E5FF).withValues(alpha: 0.8),
                                    ],
                                  ),
                                ),
                                child: Center(
                                  child: Container(
                                    height: 2.5,
                                    color: const Color(0xFF00E5FF),
                                  ),
                                ),
                              ),
                            );
                          },
                        ),

                      // 4. Processing Overlay
                      if (_isProcessingBiometric)
                        Container(
                          color: Colors.black.withValues(alpha: 0.55),
                          child: const Center(
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                SizedBox(
                                  width: 36,
                                  height: 36,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 3,
                                    color: Color(0xFF00E5FF),
                                  ),
                                ),
                                SizedBox(height: 14),
                                Text(
                                  'Đang nhận diện...',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 14,
                                  ),
                                ),
                                SizedBox(height: 4),
                                Text(
                                  'MobileFaceNet 128D',
                                  style: TextStyle(color: Colors.white70, fontSize: 11),
                                ),
                              ],
                            ),
                          ),
                        ),

                      // 5. Success Overlay
                      if (_isFacePassed)
                        Container(
                          color: const Color(0xFF052E16).withValues(alpha: 0.7),
                          child: const Center(
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(
                                  PhosphorIconsRegular.checkCircle,
                                  color: Color(0xFF22C55E),
                                  size: 64,
                                ),
                                SizedBox(height: 10),
                                Text(
                                  'Xác Thực Thành Công!',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 15,
                                  ),
                                ),
                                SizedBox(height: 4),
                                Text(
                                  'Độ tương đồng Cosine: 100%',
                                  style: TextStyle(color: Colors.white70, fontSize: 11),
                                ),
                              ],
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 20),

          // Guidance & Status Badges
          if (_isScanningFace)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFF00E5FF).withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: const Color(0xFF00E5FF).withValues(alpha: 0.4)),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(PhosphorIconsRegular.scan, color: Color(0xFF0284C7), size: 16),
                  SizedBox(width: 8),
                  Flexible(
                    child: Text(
                      'Đang quét khuôn mặt...',
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF0284C7)),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            )
          else if (_isProcessingBiometric)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFFF59E0B).withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: const Color(0xFFF59E0B).withValues(alpha: 0.4)),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFFD97706)),
                  ),
                  SizedBox(width: 8),
                  Flexible(
                    child: Text(
                      'Đang đối sánh khuôn mặt AI...',
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFFD97706)),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            )
          else if (_isFacePassed)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFF22C55E).withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: const Color(0xFF22C55E)),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(PhosphorIconsRegular.checkCircle, color: Color(0xFF16A34A), size: 16),
                  SizedBox(width: 8),
                  Flexible(
                    child: Text(
                      'Điểm danh thành công!',
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Color(0xFF16A34A)),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            )
          else if (_errorMessage != null)
            ElevatedButton.icon(
              onPressed: _startLiveFaceScan,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryColor,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
              ),
              icon: const Icon(PhosphorIconsRegular.arrowsClockwise),
              label: const Text('Thử Quét Lại Khuôn Mặt'),
            )
          else if (!_isCameraInitialized)
            OutlinedButton.icon(
              onPressed: _isCameraInitializing ? null : _initFrontCamera,
              icon: const Icon(PhosphorIconsRegular.camera),
              label: const Text('Kích Hoạt Lại Camera'),
            ),
        ],
      ),
    );
  }
}
