import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/network/dio_client.dart';

class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key});

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  final DateTime _today = DateTime.now();
  late DateTime _selectedDate;
  bool _isLoading = true;
  List<dynamic> _schedules = [];
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _selectedDate = DateTime(_today.year, _today.month, _today.day);
    _fetchSchedules();
  }

  Future<void> _fetchSchedules() async {
    try {
      final dio = DioClient().dio;
      final startDate = _today.subtract(const Duration(days: 7));
      final endDate = _today.add(const Duration(days: 21));
      final response = await dio.get(
        '/api/v1/users/me/schedule/',
        queryParameters: {
          'start_date': DateFormat('yyyy-MM-dd').format(startDate),
          'end_date': DateFormat('yyyy-MM-dd').format(endDate),
        },
      );

      if (response.statusCode == 200 && response.data['success'] == true) {
        if (mounted) {
          setState(() {
            _schedules = response.data['data'] ?? [];
            _isLoading = false;
            _errorMessage = null;
          });
        }
      } else {
        if (mounted) {
          setState(() {
            _errorMessage = response.data['message'] ?? 'Không lấy được lịch ca trực';
            _isLoading = false;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Lỗi kết nối: $e';
          _isLoading = false;
        });
      }
    }
  }

  Map<String, dynamic>? _getScheduleForDate(DateTime date) {
    final dateStr = DateFormat('yyyy-MM-dd').format(date);
    for (final s in _schedules) {
      if (s['date'] == dateStr) {
        return s;
      }
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final scheduleForDay = _getScheduleForDate(_selectedDate);

    return Scaffold(
      backgroundColor: AppTheme.neutral50,
      appBar: AppBar(
        title: const Text(
          'Lịch ca trực & Chốt phân xưởng',
          style: TextStyle(
            color: AppTheme.neutral900,
            fontWeight: FontWeight.bold,
            fontSize: 18,
          ),
        ),
        backgroundColor: Colors.white,
        elevation: 0,
        actions: [
          IconButton(
            icon: Icon(PhosphorIcons.arrowsClockwise(), color: AppTheme.neutral700),
            tooltip: 'Làm mới',
            onPressed: () {
              setState(() => _isLoading = true);
              _fetchSchedules();
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _fetchSchedules,
        child: Column(
          children: [
            // Custom Horizontal Date Picker
            Container(
              padding: const EdgeInsets.symmetric(vertical: 16),
              decoration: const BoxDecoration(
                color: Colors.white,
                border: Border(bottom: BorderSide(color: AppTheme.neutral200)),
              ),
              child: Column(
                children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Tháng ${_selectedDate.month}, ${_selectedDate.year}',
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w900,
                            color: AppTheme.neutral900,
                          ),
                        ),
                        Row(
                          children: [
                            GestureDetector(
                              onTap: () {
                                setState(() {
                                  _selectedDate = _selectedDate.subtract(const Duration(days: 7));
                                });
                              },
                              child: Icon(PhosphorIcons.caretLeft(PhosphorIconsStyle.bold), size: 16, color: AppTheme.neutral400),
                            ),
                            const SizedBox(width: 16),
                            GestureDetector(
                              onTap: () {
                                setState(() {
                                  _selectedDate = _selectedDate.add(const Duration(days: 7));
                                });
                              },
                              child: Icon(PhosphorIcons.caretRight(PhosphorIconsStyle.bold), size: 16, color: AppTheme.neutral400),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    height: 74,
                    child: ListView.builder(
                      scrollDirection: Axis.horizontal,
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      itemCount: 21, // 3 weeks
                      itemBuilder: (context, index) {
                        final date = _today.subtract(Duration(days: _today.weekday - 1 + 7)).add(Duration(days: index));
                        final isSelected = date.day == _selectedDate.day && date.month == _selectedDate.month && date.year == _selectedDate.year;
                        final isToday = date.day == _today.day && date.month == _today.month && date.year == _today.year;
                        final hasShift = _getScheduleForDate(date) != null;

                        final weekdays = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];

                        return GestureDetector(
                          onTap: () {
                            setState(() {
                              _selectedDate = date;
                            });
                          },
                          child: Container(
                            width: 52,
                            margin: const EdgeInsets.symmetric(horizontal: 4),
                            decoration: BoxDecoration(
                              color: isSelected ? AppTheme.primaryColor : Colors.transparent,
                              borderRadius: BorderRadius.circular(16),
                              border: isSelected
                                  ? null
                                  : Border.all(color: isToday ? AppTheme.primaryColor.withValues(alpha: 0.5) : Colors.transparent),
                            ),
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Text(
                                  weekdays[date.weekday - 1],
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.bold,
                                    color: isSelected ? Colors.white70 : AppTheme.neutral500,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  '${date.day}',
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w900,
                                    color: isSelected ? Colors.white : AppTheme.neutral900,
                                  ),
                                ),
                                if (hasShift)
                                  Container(
                                    margin: const EdgeInsets.only(top: 4),
                                    width: 5,
                                    height: 5,
                                    decoration: BoxDecoration(
                                      color: isSelected ? Colors.white : const Color(0xFF0284c7),
                                      shape: BoxShape.circle,
                                    ),
                                  ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),

            // Content Area
            Expanded(
              child: _isLoading
                  ? const Center(child: CircularProgressIndicator(color: AppTheme.primaryColor))
                  : _errorMessage != null
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.error_outline, color: AppTheme.dangerColor, size: 40),
                              const SizedBox(height: 12),
                              Text(_errorMessage!, style: const TextStyle(color: AppTheme.neutral700)),
                              const SizedBox(height: 12),
                              ElevatedButton(
                                onPressed: () {
                                  setState(() => _isLoading = true);
                                  _fetchSchedules();
                                },
                                child: const Text('Thử lại'),
                              ),
                            ],
                          ),
                        )
                      : scheduleForDay == null
                          ? Center(
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Container(
                                    padding: const EdgeInsets.all(20),
                                    decoration: BoxDecoration(
                                      color: AppTheme.neutral200.withValues(alpha: 0.4),
                                      shape: BoxShape.circle,
                                    ),
                                    child: Icon(
                                      PhosphorIcons.calendarX(PhosphorIconsStyle.fill),
                                      size: 48,
                                      color: AppTheme.neutral400,
                                    ),
                                  ),
                                  const SizedBox(height: 16),
                                  Text(
                                    'Không có lịch ca trực ngày ${DateFormat('dd/MM/yyyy').format(_selectedDate)}',
                                    style: const TextStyle(
                                      fontSize: 15,
                                      fontWeight: FontWeight.bold,
                                      color: AppTheme.neutral700,
                                    ),
                                  ),
                                  const SizedBox(height: 6),
                                  const Text(
                                    'Bạn không được phân ca hoặc đang trong ngày nghỉ',
                                    style: TextStyle(fontSize: 13, color: AppTheme.neutral500),
                                  ),
                                ],
                              ),
                            )
                          : _buildScheduleDetailCard(scheduleForDay),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildScheduleDetailCard(Map<String, dynamic> sched) {
    final shift = sched['shift'];
    final dutyZone = sched['dutyZone'];
    final String status = sched['status'] ?? 'ON_DUTY';
    final String notes = sched['notes'] ?? '';

    Color statusColor = AppTheme.successColor;
    String statusText = 'Đi ca làm việc';
    if (status == 'OFF') {
      statusColor = AppTheme.neutral500;
      statusText = 'Nghỉ ca (OFF)';
    } else if (status == 'LEAVE') {
      statusColor = const Color(0xFFf59e0b);
      statusText = 'Nghỉ phép (LEAVE)';
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Shift Card
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: AppTheme.neutral200),
              boxShadow: const [
                BoxShadow(color: Color(0x06000000), blurRadius: 16, offset: Offset(0, 6)),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: statusColor.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        statusText,
                        style: TextStyle(color: statusColor, fontSize: 12, fontWeight: FontWeight.bold),
                      ),
                    ),
                    if (sched['isToday'] == true)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppTheme.primaryColor,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: const Text('HÔM NAY', style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)),
                      ),
                  ],
                ),
                const SizedBox(height: 16),
                Text(
                  shift?['name'] ?? 'Ca làm việc',
                  style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                    color: AppTheme.neutral900,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Icon(PhosphorIcons.clock(PhosphorIconsStyle.bold), size: 16, color: AppTheme.neutral500),
                    const SizedBox(width: 6),
                    Text(
                      '${shift?['startTime'] ?? '--:--'} — ${shift?['endTime'] ?? '--:--'}',
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: AppTheme.neutral700),
                    ),
                  ],
                ),
                if (notes.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Text(
                    notes,
                    style: const TextStyle(fontSize: 13, color: AppTheme.neutral600, fontStyle: FontStyle.italic),
                  ),
                ],
              ],
            ),
          ),

          const SizedBox(height: 20),

          // Duty Zone & Floorplan Card
          if (dutyZone != null)
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF0f172a), Color(0xFF1e293b)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(24),
                boxShadow: const [
                  BoxShadow(color: Colors.black26, blurRadius: 18, offset: Offset(0, 8)),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: const Color(0xFF0284c7).withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: const Icon(Icons.location_on, color: Color(0xFF38bdf8), size: 24),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'CHỐT TRỰC PHÂN XƯỞNG',
                              style: TextStyle(color: Color(0xFF38bdf8), fontSize: 11, fontWeight: FontWeight.bold, letterSpacing: 1.0),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              dutyZone['name'] ?? 'Phân Xưởng',
                              style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  const Divider(color: Color(0xFF334155)),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Mã chốt', style: TextStyle(color: Colors.white54, fontSize: 11)),
                            const SizedBox(height: 2),
                            Text(
                              dutyZone['code'] ?? '--',
                              style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold, fontFamily: 'monospace'),
                            ),
                          ],
                        ),
                      ),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Tầng lầu', style: TextStyle(color: Colors.white54, fontSize: 11)),
                            const SizedBox(height: 2),
                            Text(
                              'Tầng ${dutyZone['floorLevel'] ?? 1}',
                              style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                      ),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Tọa độ chốt', style: TextStyle(color: Colors.white54, fontSize: 11)),
                            const SizedBox(height: 2),
                            Text(
                              '(${dutyZone['centerX'] ?? 0}m, ${dutyZone['centerY'] ?? 0}m)',
                              style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: () {
                        context.push('/floorplan-viewer', extra: {
                          'locationId': dutyZone['id'] ?? dutyZone['code'],
                          'locationName': dutyZone['name'],
                          'dutyZoneCoordsX': dutyZone['centerX'],
                          'dutyZoneCoordsY': dutyZone['centerY'],
                        });
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF0284c7),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                        elevation: 0,
                      ),
                      icon: const Icon(Icons.map, size: 20),
                      label: const Text(
                        '🗺 Xem Sơ đồ Mặt bằng Chi tiết',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                      ),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
