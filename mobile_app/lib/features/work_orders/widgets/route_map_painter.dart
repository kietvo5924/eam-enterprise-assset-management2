import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../models/technician_route_model.dart';

class RouteMapPainter extends CustomPainter {
  final TechnicianRouteData routeData;
  final int currentFloor;
  final int selectedStopIndex;
  final bool showMachines;
  final double animationProgress; // 0.0 -> 1.0 for dash animation & pulsing
  final double pulseValue; // 0.0 -> 1.0 for active stop pulsing ring

  static const double canvasWidth = 1000.0;
  static const double canvasHeight = 700.0;
  static const double midHallY = 320.0;
  static const Offset stairPoint = Offset(507.0, midHallY);

  RouteMapPainter({
    required this.routeData,
    required this.currentFloor,
    required this.selectedStopIndex,
    required this.showMachines,
    this.animationProgress = 0.0,
    this.pulseValue = 0.0,
  });

  /// Chuyển đổi tọa độ trạm dừng sang tọa độ pixel trên canvas 1000x700
  static Offset getStopCanvasOffset(RouteStop stop, int index) {
    if (stop.coords != null && stop.coords!.x > 0 && stop.coords!.y > 0) {
      double rawX = stop.coords!.x;
      double rawY = stop.coords!.y;

      // Nếu tọa độ tính theo mét (0 - 220m, 0 - 130m)
      if (rawX <= 250 && rawY <= 150) {
        double px = 60.0 + (rawX / 220.0) * 880.0;
        double py = 60.0 + (rawY / 130.0) * 580.0;
        return Offset(px.clamp(70.0, 930.0), py.clamp(70.0, 630.0));
      }
      return Offset(rawX.clamp(70.0, 930.0), rawY.clamp(70.0, 630.0));
    }

    // Tọa độ mặc định phân bổ đẹp theo lưới phân xưởng nếu không có tọa độ cụ thể
    final defaultPositions = [
      const Offset(140.0, 510.0), // 0: Depot / Kho
      const Offset(200.0, 190.0), // 1: Xưởng Dập
      const Offset(480.0, 190.0), // 2: Xưởng Hàn
      const Offset(310.0, 510.0), // 3: Kho Vật tư
      const Offset(780.0, 190.0), // 4: Xưởng Lắp ráp
      const Offset(720.0, 510.0), // 5: Khu QC
      const Offset(140.0, 510.0), // 6: Quay về Depot
    ];
    int posIndex = index % defaultPositions.length;
    return defaultPositions[posIndex];
  }

  @override
  void paint(Canvas canvas, Size size) {
    // 1. Nền CAD Grid tối màu (#0f172a)
    _drawCadGrid(canvas, size);

    // 2. Viền tòa nhà (Outer Building Envelope)
    _drawBuildingEnvelope(canvas, size);

    // 3. Các phân khu (Child Zones) trên tầng hiện tại
    _drawZones(canvas, size);

    // 4. Trục hành lang chính vận chuyển (Central Aisle line tại midHallY = 320)
    _drawCentralAisle(canvas, size);

    // 5. Lớp thiết bị / máy móc (nếu showMachines == true)
    if (showMachines) {
      _drawMachines(canvas, size);
    }

    // 6. Đường đi trực giao Manhattan (Orthogonal Routing)
    _drawManhattanRoutes(canvas, size);

    // 7. Cụm cầu thang chuyển tầng (Staircase node)
    _drawStaircaseNode(canvas, size);

    // 8. Các Pin trạm dừng (Stop Pins) trên tầng hiện tại
    _drawStopPins(canvas, size);
  }

  /// 1. Vẽ lưới CAD và thước đo mét
  void _drawCadGrid(Canvas canvas, Size size) {
    final bgPaint = Paint()..color = const Color(0xFF0f172a);
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), bgPaint);

    final gridPaint = Paint()
      ..color = const Color(0xFF1e293b).withValues(alpha: 0.8)
      ..strokeWidth = 0.8;

    // Lưới dọc mỗi 40px
    for (double x = 50; x <= 950; x += 40) {
      canvas.drawLine(Offset(x, 50), Offset(x, 650), gridPaint);
    }
    // Lưới ngang mỗi 40px
    for (double y = 50; y <= 650; y += 40) {
      canvas.drawLine(Offset(50, y), Offset(950, y), gridPaint);
    }

    // Vạch chia thước đo mét phía trên và bên trái
    final rulerTextPaint = const TextStyle(
      color: Color(0xFF64748b),
      fontSize: 8.5,
      fontWeight: FontWeight.bold,
      fontFamily: 'monospace',
    );

    for (int m = 0; m <= 220; m += 20) {
      double px = 50.0 + (m / 220.0) * 900.0;
      final tickPaint = Paint()
        ..color = const Color(0xFF475569)
        ..strokeWidth = 1.0;
      canvas.drawLine(Offset(px, 44), Offset(px, 50), tickPaint);

      final textSpan = TextSpan(text: '${m}m', style: rulerTextPaint);
      final textPainter = TextPainter(
        text: textSpan,
        textDirection: TextDirection.ltr,
      )..layout();
      textPainter.paint(canvas, Offset(px - textPainter.width / 2, 32));
    }

    for (int m = 0; m <= 130; m += 20) {
      double py = 50.0 + (m / 130.0) * 600.0;
      final tickPaint = Paint()
        ..color = const Color(0xFF475569)
        ..strokeWidth = 1.0;
      canvas.drawLine(Offset(44, py), Offset(50, py), tickPaint);

      final textSpan = TextSpan(text: '${m}m', style: rulerTextPaint);
      final textPainter = TextPainter(
        text: textSpan,
        textDirection: TextDirection.ltr,
      )..layout();
      textPainter.paint(canvas, Offset(24, py - textPainter.height / 2));
    }
  }

  /// 2. Vẽ viền bao tòa nhà phân xưởng
  void _drawBuildingEnvelope(Canvas canvas, Size size) {
    final buildingRect = RRect.fromRectAndRadius(
      const Rect.fromLTWH(50, 50, 900, 600),
      const Radius.circular(8),
    );

    final fillPaint = Paint()
      ..color = const Color(0xFF080e1a).withValues(alpha: 0.95)
      ..style = PaintingStyle.fill;
    canvas.drawRRect(buildingRect, fillPaint);

    final borderPaint = Paint()
      ..color = const Color(0xFF0284c7)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5;
    canvas.drawRRect(buildingRect, borderPaint);

    // Huy hiệu tên phân xưởng & tầng ở góc trên
    final badgeRect = RRect.fromRectAndRadius(
      const Rect.fromLTWH(310, 14, 380, 24),
      const Radius.circular(6),
    );
    canvas.drawRRect(badgeRect, Paint()..color = const Color(0xFF0f172a));
    canvas.drawRRect(badgeRect, Paint()
      ..color = const Color(0xFF0284c7)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2);

    final facilityTitle = (routeData.detectedFloorplanName != null && routeData.detectedFloorplanName!.isNotEmpty)
        ? routeData.detectedFloorplanName!.toUpperCase()
        : 'PHÂN XƯỞNG SẢN XUẤT THIẾT BỊ';
    final titleSpan = TextSpan(
      text: '🏢 $facilityTitle - TẦNG $currentFloor',
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
    titlePainter.paint(canvas, Offset(500 - titlePainter.width / 2, 26 - titlePainter.height / 2));
  }

  /// 3. Vẽ các phân khu chức năng (Child Zones) theo tầng
  void _drawZones(Canvas canvas, Size size) {
    if (currentFloor == 1) {
      _drawZoneRect(canvas, const Rect.fromLTWH(70, 70, 260, 225), 'PHÂN XƯỞNG DẬP (STAMPING)', const Color(0xFF0284c7), const Color(0x240ea5e9));
      _drawZoneRect(canvas, const Rect.fromLTWH(360, 70, 270, 225), 'PHÂN XƯỞNG HÀN & SƠN', const Color(0xFF0d9488), const Color(0x2414b8a6));
      _drawZoneRect(canvas, const Rect.fromLTWH(660, 70, 270, 225), 'PHÂN XƯỞNG LẮP RÁP', const Color(0xFF6366f1), const Color(0x246366f1));
      _drawZoneRect(canvas, const Rect.fromLTWH(70, 400, 380, 230), 'KHO VẬT TƯ & TIẾP VẬN CKD', const Color(0xFFd97706), const Color(0x24f59e0b));
      _drawZoneRect(canvas, const Rect.fromLTWH(480, 400, 450, 230), 'KHU VỰC KIỂM TRA CHẤT LƯỢNG QC', const Color(0xFF0891b2), const Color(0x2406b6d4));
    } else {
      _drawZoneRect(canvas, const Rect.fromLTWH(70, 70, 400, 225), 'PHÒNG ĐIỀU HÀNH SCADA & SERVER', const Color(0xFF9333ea), const Color(0x24a855f7));
      _drawZoneRect(canvas, const Rect.fromLTWH(500, 70, 430, 225), 'PHÒNG THỬ NGHIỆM CHẤT LƯỢNG R&D', const Color(0xFF10b981), const Color(0x2410b981));
      _drawZoneRect(canvas, const Rect.fromLTWH(70, 400, 430, 230), 'TRUNG TÂM BẢO TRÌ CƠ ĐIỆN TẦNG 2', const Color(0xFFd97706), const Color(0x24f59e0b));
      _drawZoneRect(canvas, const Rect.fromLTWH(530, 400, 400, 230), 'PHÒNG NGHỈ & DỤNG CỤ KTV', const Color(0xFF0284c7), const Color(0x240ea5e9));
    }
  }

  void _drawZoneRect(Canvas canvas, Rect rect, String title, Color strokeColor, Color fillColor) {
    final rrect = RRect.fromRectAndRadius(rect, const Radius.circular(6));
    canvas.drawRRect(rrect, Paint()..color = fillColor);
    canvas.drawRRect(rrect, Paint()
      ..color = strokeColor.withValues(alpha: 0.8)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4);

    // Tag nhãn phân khu góc trên trái
    final tagW = (title.length * 6.5 + 16).clamp(110.0, 240.0);
    final tagRect = RRect.fromRectAndRadius(
      Rect.fromLTWH(rect.left + 8, rect.top + 8, tagW, 18),
      const Radius.circular(3),
    );
    canvas.drawRRect(tagRect, Paint()..color = const Color(0xFF0f172a).withValues(alpha: 0.9));
    canvas.drawRRect(tagRect, Paint()
      ..color = strokeColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.8);

    final span = TextSpan(
      text: title,
      style: TextStyle(
        color: strokeColor,
        fontSize: 8.5,
        fontWeight: FontWeight.bold,
        fontFamily: 'sans-serif',
      ),
    );
    final tp = TextPainter(
      text: span,
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, Offset(rect.left + 16, rect.top + 17 - tp.height / 2));
  }

  /// 4. Vẽ trục hành lang chính vận chuyển (Central Aisle line tại midHallY = 320)
  void _drawCentralAisle(Canvas canvas, Size size) {
    const startX = 65.0;
    const endX = 935.0;

    // Đường nét đứt hành lang
    final aislePaint = Paint()
      ..color = const Color(0xFF38bdf8).withValues(alpha: 0.35)
      ..strokeWidth = 1.6;

    double x = startX;
    while (x < endX) {
      canvas.drawLine(Offset(x, midHallY), Offset(math.min(x + 10, endX), midHallY), aislePaint);
      x += 16;
    }

    // Nhãn "HÀNH LANG VẬN CHUYỂN (AISLE)"
    const badgeW = 200.0;
    const badgeH = 18.0;
    final aisleBadgeRect = RRect.fromRectAndRadius(
      Rect.fromLTWH(180.0, midHallY - (badgeH / 2), badgeW, badgeH),
      const Radius.circular(4),
    );
    canvas.drawRRect(aisleBadgeRect, Paint()..color = const Color(0xFF0f172a).withValues(alpha: 0.9));
    canvas.drawRRect(aisleBadgeRect, Paint()
      ..color = const Color(0xFF38bdf8).withValues(alpha: 0.6)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.8);

    final span = const TextSpan(
      text: 'HÀNH LANG VẬN CHUYỂN (AISLE)',
      style: TextStyle(
        color: Color(0xFF38bdf8),
        fontSize: 8.5,
        fontWeight: FontWeight.bold,
        fontFamily: 'monospace',
        letterSpacing: 0.6,
      ),
    );
    final tp = TextPainter(
      text: span,
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, Offset(280.0 - tp.width / 2, midHallY - tp.height / 2));
  }

  /// 5. Vẽ footprint các máy móc thiết bị trong xưởng
  void _drawMachines(Canvas canvas, Size size) {
    final machinePositions = currentFloor == 1
        ? [
            const Offset(180, 170),
            const Offset(240, 220),
            const Offset(430, 160),
            const Offset(510, 210),
            const Offset(720, 170),
            const Offset(820, 220),
            const Offset(560, 480),
            const Offset(740, 500),
          ]
        : [
            const Offset(220, 160),
            const Offset(340, 210),
            const Offset(620, 170),
            const Offset(750, 210),
            const Offset(280, 490),
            const Offset(700, 490),
          ];

    final machineBoxPaint = Paint()..color = const Color(0xFF1e293b);
    final machineBorderPaint = Paint()
      ..color = const Color(0xFF38bdf8).withValues(alpha: 0.6)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;
    final dotPaint = Paint()..color = const Color(0xFF38bdf8);

    for (final pt in machinePositions) {
      final rect = Rect.fromCenter(center: pt, width: 22, height: 16);
      canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(2)), machineBoxPaint);
      canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(2)), machineBorderPaint);
      canvas.drawCircle(pt, 2.5, dotPaint);
    }
  }

  /// 6. Vẽ đường đi trực giao Manhattan (Orthogonal Routing)
  void _drawManhattanRoutes(Canvas canvas, Size size) {
    final stops = routeData.orderedStops;
    if (stops.length < 2) return;

    for (int i = 0; i < stops.length - 1; i++) {
      final s1 = stops[i];
      final s2 = stops[i + 1];
      final pt1 = getStopCanvasOffset(s1, i);
      final pt2 = getStopCanvasOffset(s2, i + 1);

      final isUrgentEdge = s2.isUrgent;
      final edgeColor = isUrgentEdge ? const Color(0xFFef4444) : const Color(0xFFf59e0b);

      if (s1.floorNumber == currentFloor && s2.floorNumber == currentFloor) {
        // Cả 2 điểm cùng trên tầng hiện tại -> Nối qua hành lang giữa
        _drawOrthogonalSegment(canvas, pt1, pt2, edgeColor, isUrgentEdge);
      } else if (s1.floorNumber == currentFloor && s2.floorNumber != currentFloor) {
        // Điểm xuất phát ở tầng hiện tại, điểm đến ở tầng khác -> Nối từ điểm 1 tới Cầu thang
        _drawOrthogonalSegment(canvas, pt1, stairPoint, edgeColor, isUrgentEdge);
      } else if (s1.floorNumber != currentFloor && s2.floorNumber == currentFloor) {
        // Điểm xuất phát ở tầng khác, điểm đến ở tầng hiện tại -> Nối từ Cầu thang tới điểm 2
        _drawOrthogonalSegment(canvas, stairPoint, pt2, edgeColor, isUrgentEdge);
      }
    }
  }

  /// Vẽ đoạn đường trực giao P1 -> (P1.x, midHallY) -> (P2.x, midHallY) -> P2
  void _drawOrthogonalSegment(Canvas canvas, Offset p1, Offset p2, Color color, bool isUrgent) {
    final path = Path();
    path.moveTo(p1.dx, p1.dy);

    if ((p1.dy - p2.dy).abs() > 25) {
      path.lineTo(p1.dx, midHallY);
      path.lineTo(p2.dx, midHallY);
      path.lineTo(p2.dx, p2.dy);
    } else {
      path.lineTo(p2.dx, p2.dy);
    }

    // A. Glow Underlay
    final glowPaint = Paint()
      ..color = color.withValues(alpha: isUrgent ? 0.35 : 0.22)
      ..strokeWidth = isUrgent ? 5.5 : 4.0
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    canvas.drawPath(path, glowPaint);

    // B. Đường nét chính
    final mainPaint = Paint()
      ..color = color
      ..strokeWidth = isUrgent ? 2.8 : 2.0
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    canvas.drawPath(path, mainPaint);

    // C. Animated Dash Flow
    _drawAnimatedPathDash(canvas, path);

    // D. Mũi tên chỉ hướng di chuyển
    _drawDirectionArrow(canvas, p1, p2);
  }

  /// Vẽ nét đứt chuyển động nhấp nháy mô phỏng luồng di chuyển
  void _drawAnimatedPathDash(Canvas canvas, Path path) {
    final metrics = path.computeMetrics();
    final dashPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.8)
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;

    const dashLength = 6.0;
    const dashSpace = 8.0;
    final totalDash = dashLength + dashSpace;
    final offset = animationProgress * totalDash;

    for (final metric in metrics) {
      double distance = offset;
      while (distance < metric.length) {
        final start = distance;
        final end = math.min(distance + dashLength, metric.length);
        if (end > start) {
          final extract = metric.extractPath(start, end);
          canvas.drawPath(extract, dashPaint);
        }
        distance += totalDash;
      }
    }
  }

  /// Vẽ mũi tên chỉ hướng dọc theo đoạn đường Manhattan
  void _drawDirectionArrow(Canvas canvas, Offset p1, Offset p2) {
    // Đặt mũi tên tại đoạn hành lang giữa (midHallY)
    if ((p1.dx - p2.dx).abs() > 30) {
      final midX = (p1.dx + p2.dx) / 2;
      final isRight = p2.dx > p1.dx;
      _drawArrowHead(canvas, Offset(midX, midHallY), isRight ? 0.0 : math.pi, const Color(0xFFffffff));
    }
  }

  void _drawArrowHead(Canvas canvas, Offset point, double angle, Color color) {
    canvas.save();
    canvas.translate(point.dx, point.dy);
    canvas.rotate(angle);

    final arrowPath = Path()
      ..moveTo(5, 0)
      ..lineTo(-5, -4)
      ..lineTo(-3, 0)
      ..lineTo(-5, 4)
      ..close();

    final paint = Paint()..color = color;
    canvas.drawPath(arrowPath, paint);
    canvas.restore();
  }

  /// 7. Vẽ biểu tượng Cầu thang bộ và nhãn chặng chuyển tầng
  void _drawStaircaseNode(Canvas canvas, Size size) {
    final stops = routeData.orderedStops;
    final transitions = <Map<String, dynamic>>[];

    for (int i = 0; i < stops.length - 1; i++) {
      final s1 = stops[i];
      final s2 = stops[i + 1];
      if (s1.floorNumber == currentFloor && s2.floorNumber != currentFloor) {
        transitions.add({
          'fromStop': s1.step,
          'toStop': s2.step,
          'text': '🪜 [CHẶNG ${s1.step}➔${s2.step}] Sang Tầng ${s2.floorNumber}',
        });
      } else if (s1.floorNumber != currentFloor && s2.floorNumber == currentFloor) {
        transitions.add({
          'fromStop': s1.step,
          'toStop': s2.step,
          'text': '🪜 [CHẶNG ${s1.step}➔${s2.step}] Đến từ Tầng ${s1.floorNumber}',
        });
      }
    }

    final stairCenter = stairPoint;

    // Khung biểu tượng cầu thang kiến trúc CAD
    final stairRect = Rect.fromCenter(center: stairCenter, width: 56, height: 38);
    canvas.drawRRect(RRect.fromRectAndRadius(stairRect, const Radius.circular(4)), Paint()..color = const Color(0xFF0f172a));
    canvas.drawRRect(RRect.fromRectAndRadius(stairRect, const Radius.circular(4)), Paint()
      ..color = const Color(0xFF94a3b8)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.6);

    // Bậc thang bên trong
    final rungPaint = Paint()
      ..color = const Color(0xFFcbd5e1)
      ..strokeWidth = 1.2;
    for (double rx = stairRect.left + 8; rx <= stairRect.right - 8; rx += 7) {
      canvas.drawLine(Offset(rx, stairRect.top + 5), Offset(rx, stairRect.bottom - 5), rungPaint);
    }
    // Thanh dọc chia 2 vế thang
    canvas.drawLine(
      Offset(stairRect.left, stairCenter.dy),
      Offset(stairRect.right, stairCenter.dy),
      Paint()..color = const Color(0xFF64748b)..strokeWidth = 1.2,
    );

    // Chữ "CẦU THANG BỘ" phía dưới
    final textSpan = const TextSpan(
      text: 'CẦU THANG BỘ',
      style: TextStyle(
        color: Color(0xFF94a3b8),
        fontSize: 7.5,
        fontWeight: FontWeight.bold,
        fontFamily: 'monospace',
      ),
    );
    final tp = TextPainter(
      text: textSpan,
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, Offset(stairCenter.dx - tp.width / 2, stairRect.bottom + 4));

    // Huy hiệu thông báo chuyển tầng nếu có chặng liên quan
    for (int tIdx = 0; tIdx < transitions.length; tIdx++) {
      final t = transitions[tIdx];
      final String text = t['text'];
      final pillW = (text.length * 6.5 + 24).clamp(160.0, 260.0);
      final pillY = stairRect.top - 24 - (tIdx * 20);

      final pillRect = RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset(stairCenter.dx, pillY), width: pillW, height: 18),
        const Radius.circular(4),
      );
      canvas.drawRRect(pillRect, Paint()..color = const Color(0xFF0f172a));
      canvas.drawRRect(pillRect, Paint()
        ..color = const Color(0xFF38bdf8)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.0);

      final pillSpan = TextSpan(
        text: text,
        style: const TextStyle(
          color: Color(0xFFf1f5f9),
          fontSize: 8.5,
          fontWeight: FontWeight.bold,
          fontFamily: 'monospace',
        ),
      );
      final pillTp = TextPainter(
        text: pillSpan,
        textDirection: TextDirection.ltr,
      )..layout();
      pillTp.paint(canvas, Offset(stairCenter.dx - pillTp.width / 2, pillY - pillTp.height / 2));
    }
  }

  /// 8. Vẽ các Pin trạm dừng (Stop Pins) thuộc tầng hiện tại
  void _drawStopPins(Canvas canvas, Size size) {
    final stops = routeData.orderedStops;
    final activeFloorStops = <Map<String, dynamic>>[];

    for (int i = 0; i < stops.length; i++) {
      final s = stops[i];
      if (s.floorNumber == currentFloor) {
        activeFloorStops.add({
          'stop': s,
          'index': i,
          'offset': getStopCanvasOffset(s, i),
        });
      }
    }

    // Nếu không có trạm nào trên tầng này -> Vẽ bảng thông báo giữa màn hình
    if (activeFloorStops.isEmpty) {
      final noticeRect = RRect.fromRectAndRadius(
        const Rect.fromLTWH(320, 280, 360, 80),
        const Radius.circular(12),
      );
      canvas.drawRRect(noticeRect, Paint()..color = const Color(0xFF0b1329).withValues(alpha: 0.95));
      canvas.drawRRect(noticeRect, Paint()
        ..color = const Color(0xFF0284c7)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.6);

      final titleSpan = TextSpan(
        text: '🏢 Không có trạm bảo trì trên Tầng $currentFloor',
        style: const TextStyle(
          color: Color(0xFF38bdf8),
          fontSize: 12.0,
          fontWeight: FontWeight.bold,
        ),
      );
      final tp = TextPainter(text: titleSpan, textDirection: TextDirection.ltr)..layout();
      tp.paint(canvas, Offset(500 - tp.width / 2, 305));

      final subSpan = const TextSpan(
        text: 'Các trạm trong lộ trình thuộc các tầng làm việc khác.',
        style: TextStyle(
          color: Color(0xFF94a3b8),
          fontSize: 10.0,
        ),
      );
      final subTp = TextPainter(text: subSpan, textDirection: TextDirection.ltr)..layout();
      subTp.paint(canvas, Offset(500 - subTp.width / 2, 328));
      return;
    }

    // Vẽ từng Pin trạm dừng
    for (final item in activeFloorStops) {
      final RouteStop stop = item['stop'];
      final int stepIndex = item['index'];
      final Offset pt = item['offset'];
      final bool isSelected = (selectedStopIndex == stepIndex);

      final Color pinColor = stop.pinColor;
      const double baseRadius = 14.0;

      // Halo viền mờ bên ngoài
      canvas.drawCircle(pt, baseRadius + 5, Paint()..color = pinColor.withValues(alpha: 0.22));

      // Hiệu ứng vòng tròn phát sáng Pulsing Ring khi trạm đang được chọn
      if (isSelected) {
        final double pulseRadius = baseRadius + 7 + (pulseValue * 8);
        final pulsePaint = Paint()
          ..color = const Color(0xFF38bdf8).withValues(alpha: 1.0 - pulseValue)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.5;
        canvas.drawCircle(pt, pulseRadius, pulsePaint);

        // Vòng viền cyan cố định
        final activeRing = Paint()
          ..color = const Color(0xFF38bdf8)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.2;
        canvas.drawCircle(pt, baseRadius + 5, activeRing);
      }

      // Hình tròn lõi chính của Pin
      final pinPaint = Paint()..color = pinColor;
      canvas.drawCircle(pt, baseRadius, pinPaint);

      // Viền trắng của Pin
      final borderPaint = Paint()
        ..color = Colors.white
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.0;
      canvas.drawCircle(pt, baseRadius, borderPaint);

      // Số thứ tự trạm dừng ở tâm Pin
      final numberSpan = TextSpan(
        text: '$stepIndex',
        style: TextStyle(
          color: (stop.isDepot || stop.isUrgent || stop.isWarehouse || stop.isToolPickup)
              ? Colors.white
              : const Color(0xFF0f172a),
          fontSize: 11.5,
          fontWeight: FontWeight.w900,
          fontFamily: 'sans-serif',
        ),
      );
      final numTp = TextPainter(
        text: numberSpan,
        textDirection: TextDirection.ltr,
      )..layout();
      numTp.paint(canvas, Offset(pt.dx - numTp.width / 2, pt.dy - numTp.height / 2));
    }
  }

  @override
  bool shouldRepaint(covariant RouteMapPainter oldDelegate) {
    return oldDelegate.currentFloor != currentFloor ||
        oldDelegate.selectedStopIndex != selectedStopIndex ||
        oldDelegate.showMachines != showMachines ||
        oldDelegate.animationProgress != animationProgress ||
        oldDelegate.pulseValue != pulseValue ||
        oldDelegate.routeData != routeData;
  }
}
