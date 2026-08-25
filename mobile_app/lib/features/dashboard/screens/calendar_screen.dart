import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../../core/theme/app_theme.dart';

class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key});

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  final DateTime _today = DateTime.now();
  late DateTime _selectedDate;
  
  final List<Map<String, dynamic>> _mockTasks = [
    {
      'time': '08:00',
      'title': 'Bảo trì máy bơm số 1',
      'location': 'Khu vực Xử lý nước',
      'status': 'IN_PROGRESS',
      'duration': '2 giờ'
    },
    {
      'time': '10:30',
      'title': 'Kiểm tra hệ thống điện',
      'location': 'Tòa nhà A',
      'status': 'ASSIGNED',
      'duration': '1.5 giờ'
    },
    {
      'time': '14:00',
      'title': 'Thay thế van áp suất',
      'location': 'Lò hơi số 3',
      'status': 'CREATED',
      'duration': '3 giờ'
    },
  ];

  @override
  void initState() {
    super.initState();
    _selectedDate = _today;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.neutral50,
      appBar: AppBar(
        title: const Text(
          'Lịch bảo trì',
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
            icon: Icon(PhosphorIcons.funnel(), color: AppTheme.neutral700),
            onPressed: () {},
          ),
        ],
      ),
      body: Column(
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
                        'Tháng ${_today.month}, ${_today.year}',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w900,
                          color: AppTheme.neutral900,
                        ),
                      ),
                      Row(
                        children: [
                          Icon(PhosphorIcons.caretLeft(PhosphorIconsStyle.bold), size: 16, color: AppTheme.neutral400),
                          const SizedBox(width: 16),
                          Icon(PhosphorIcons.caretRight(PhosphorIconsStyle.bold), size: 16, color: AppTheme.neutral400),
                        ],
                      )
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  height: 72,
                  child: ListView.builder(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemCount: 14, // 2 weeks
                    itemBuilder: (context, index) {
                      final date = _today.subtract(Duration(days: _today.weekday - 1)).add(Duration(days: index));
                      final isSelected = date.day == _selectedDate.day && date.month == _selectedDate.month;
                      final isToday = date.day == _today.day && date.month == _today.month;
                      
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
                              if (index % 3 == 0) // Mock some dot indicators
                                Container(
                                  margin: const EdgeInsets.only(top: 4),
                                  width: 4,
                                  height: 4,
                                  decoration: BoxDecoration(
                                    color: isSelected ? Colors.white : AppTheme.dangerColor,
                                    shape: BoxShape.circle,
                                  ),
                                )
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

          // Timeline List
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.only(
                left: 20,
                right: 20,
                top: 20,
                bottom: 140, // Padding to avoid overlapping with FAB & Bottom Nav
              ),
              itemCount: _mockTasks.length,
              itemBuilder: (context, index) {
                final task = _mockTasks[index];
                final isLast = index == _mockTasks.length - 1;
                
                Color statusColor;
                switch (task['status']) {
                  case 'IN_PROGRESS':
                    statusColor = const Color(0xFFea580c);
                    break;
                  case 'ASSIGNED':
                    statusColor = AppTheme.infoColor;
                    break;
                  default:
                    statusColor = AppTheme.neutral400;
                }

                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Timeline
                    Column(
                      children: [
                        Text(
                          task['time'],
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w900,
                            color: AppTheme.neutral900,
                          ),
                        ),
                        const SizedBox(height: 8),
                        if (!isLast)
                          Container(
                            width: 2,
                            height: 80,
                            decoration: BoxDecoration(
                              color: AppTheme.neutral200,
                              borderRadius: BorderRadius.circular(1),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(width: 16),
                    // Card
                    Expanded(
                      child: Container(
                        margin: const EdgeInsets.only(bottom: 24),
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(20),
                          boxShadow: [
                            BoxShadow(
                              color: AppTheme.neutral900.withValues(alpha: 0.04),
                              blurRadius: 12,
                              offset: const Offset(0, 4),
                            )
                          ],
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: statusColor.withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Text(
                                    task['status'],
                                    style: TextStyle(
                                      fontSize: 10,
                                      fontWeight: FontWeight.bold,
                                      color: statusColor,
                                      letterSpacing: 0.5,
                                    ),
                                  ),
                                ),
                                Row(
                                  children: [
                                    Icon(PhosphorIcons.clock(), size: 12, color: AppTheme.neutral500),
                                    const SizedBox(width: 4),
                                    Text(
                                      task['duration'],
                                      style: const TextStyle(
                                        fontSize: 12,
                                        color: AppTheme.neutral500,
                                        fontWeight: FontWeight.w500,
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),
                            Text(
                              task['title'],
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.neutral900,
                              ),
                            ),
                            const SizedBox(height: 8),
                            Row(
                              children: [
                                Icon(PhosphorIcons.mapPin(), size: 14, color: AppTheme.neutral500),
                                const SizedBox(width: 4),
                                Text(
                                  task['location'],
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: AppTheme.neutral500,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
