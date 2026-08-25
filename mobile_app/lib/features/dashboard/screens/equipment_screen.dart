import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';

import '../../work_orders/services/work_order_service.dart';

class EquipmentScreen extends StatefulWidget {
  const EquipmentScreen({super.key});

  @override
  State<EquipmentScreen> createState() => _EquipmentScreenState();
}

class _EquipmentScreenState extends State<EquipmentScreen> {
  final WorkOrderService _service = WorkOrderService();
  late Future<List<Map<String, dynamic>>> _assetsFuture;
  String _searchQuery = '';
  String _selectedStatus = 'ALL';

  final List<Map<String, String>> _statusFilters = [
    {'value': 'ALL', 'label': 'Tất cả'},
    {'value': 'OPERATIONAL', 'label': 'Hoạt động'},
    {'value': 'MAINTENANCE', 'label': 'Bảo trì'},
    {'value': 'BROKEN', 'label': 'Hỏng hóc'},
  ];

  @override
  void initState() {
    super.initState();
    _assetsFuture = _service.getAssets();
  }

  @override
  Widget build(BuildContext context) {

    return Scaffold(
      backgroundColor: AppTheme.neutral50,
      appBar: AppBar(
        title: const Text(
          'Thiết bị',
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
            icon: Icon(PhosphorIcons.qrCode(), color: AppTheme.neutral700),
            onPressed: () {},
          ),
        ],
      ),
      body: Column(
        children: [
          // Search Bar & Filters
          Container(
            padding: const EdgeInsets.all(16),
            decoration: const BoxDecoration(
              color: Colors.white,
              border: Border(bottom: BorderSide(color: AppTheme.neutral200)),
            ),
            child: Column(
              children: [
                Container(
                  decoration: BoxDecoration(
                    color: AppTheme.neutral100,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: TextField(
                    onChanged: (val) {
                      setState(() {
                        _searchQuery = val;
                      });
                    },
                    decoration: InputDecoration(
                      hintText: 'Tìm kiếm thiết bị...',
                      hintStyle: const TextStyle(color: AppTheme.neutral400, fontSize: 14),
                      prefixIcon: Icon(PhosphorIcons.magnifyingGlass(), color: AppTheme.neutral400),
                      border: InputBorder.none,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: _statusFilters.map((filter) {
                      final isSelected = _selectedStatus == filter['value'];
                      return Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: FilterChip(
                          label: Text(filter['label']!),
                          labelStyle: TextStyle(
                            color: isSelected ? Colors.white : AppTheme.neutral600,
                            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                            fontSize: 13,
                          ),
                          backgroundColor: AppTheme.neutral100,
                          selectedColor: AppTheme.primaryColor,
                          selected: isSelected,
                          showCheckmark: false,
                          side: BorderSide.none,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                          onSelected: (selected) {
                            setState(() {
                              _selectedStatus = filter['value']!;
                            });
                          },
                        ),
                      );
                    }).toList(),
                  ),
                ),
              ],
            ),
          ),

          // Equipment List
          Expanded(
            child: FutureBuilder<List<Map<String, dynamic>>>(
              future: _assetsFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError || !snapshot.hasData || snapshot.data!.isEmpty) {
                  return const Center(
                    child: Text('Không có thiết bị nào', style: TextStyle(color: AppTheme.neutral500)),
                  );
                }

                final allEquipments = snapshot.data!;
                final equipments = allEquipments.where((eq) {
                  final name = eq['name']?.toString().toLowerCase() ?? '';
                  final code = eq['serialNumber']?.toString().toLowerCase() ?? '';
                  final status = eq['status']?.toString().toUpperCase() ?? 'UNKNOWN';
                  final search = _searchQuery.toLowerCase();
                  
                  final matchesSearch = name.contains(search) || code.contains(search);
                  final matchesStatus = _selectedStatus == 'ALL' || 
                      (_selectedStatus == 'OPERATIONAL' && (status == 'ACTIVE' || status == 'OPERATIONAL')) || 
                      status == _selectedStatus;
                      
                  return matchesSearch && matchesStatus;
                }).toList();

                if (equipments.isEmpty) {
                  return const Center(
                    child: Text('Không tìm thấy thiết bị phù hợp', style: TextStyle(color: AppTheme.neutral500)),
                  );
                }

                final Map<String, List<Map<String, dynamic>>> grouped = {};
                for (var eq in equipments) {
                  final loc = eq['locationName']?.toString() ?? 'Chưa cấu hình vị trí';
                  grouped.putIfAbsent(loc, () => []).add(eq);
                }

                final sortedLocations = grouped.keys.toList()..sort();

                List<Widget> listWidgets = [];
                for (var loc in sortedLocations) {
                  listWidgets.add(
                    Padding(
                      padding: const EdgeInsets.only(top: 24, bottom: 12, left: 4),
                      child: Row(
                        children: [
                          Icon(PhosphorIcons.mapPin(PhosphorIconsStyle.fill), color: AppTheme.primaryColor, size: 20),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              loc,
                              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: AppTheme.neutral900),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(color: AppTheme.neutral200, borderRadius: BorderRadius.circular(12)),
                            child: Text('${grouped[loc]!.length}', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.neutral700)),
                          ),
                        ],
                      ),
                    ),
                  );

                  for (var eq in grouped[loc]!) {
                    final status = eq['status']?.toString().toUpperCase() ?? 'UNKNOWN';
                    Color statusColor = AppTheme.neutral400;
                    String statusText = status;
                    
                    if (status == 'ACTIVE' || status == 'OPERATIONAL') {
                      statusColor = AppTheme.successColor;
                      statusText = 'Hoạt động';
                    } else if (status == 'MAINTENANCE') {
                      statusColor = AppTheme.warningColor;
                      statusText = 'Bảo trì';
                    } else if (status == 'BROKEN') {
                      statusColor = AppTheme.dangerColor;
                      statusText = 'Hỏng hóc';
                    } else if (status == 'DECOMMISSIONED') {
                      statusColor = AppTheme.neutral500;
                      statusText = 'Thanh lý';
                    } else if (status == 'RESERVED') {
                      statusColor = AppTheme.infoColor;
                      statusText = 'Dự trữ';
                    } else {
                      statusColor = AppTheme.neutral500;
                      statusText = status;
                    }

                    listWidgets.add(
                      Container(
                        margin: const EdgeInsets.only(bottom: 12),
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
                        child: InkWell(
                          borderRadius: BorderRadius.circular(20),
                          onTap: () {
                            context.push('/equipment-detail', extra: eq);
                          },
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Container(
                                  width: 64,
                                  height: 64,
                                  decoration: BoxDecoration(
                                    color: AppTheme.neutral100,
                                    borderRadius: BorderRadius.circular(16),
                                  ),
                                  child: Icon(
                                    PhosphorIcons.engine(PhosphorIconsStyle.fill),
                                    size: 32,
                                    color: AppTheme.primaryColor,
                                  ),
                                ),
                                const SizedBox(width: 16),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Expanded(
                                            child: Text(
                                              eq['serialNumber'] ?? 'N/A',
                                              style: const TextStyle(
                                                fontSize: 12,
                                                fontWeight: FontWeight.bold,
                                                color: AppTheme.neutral500,
                                              ),
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                          ),
                                          const SizedBox(width: 8),
                                          Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                            decoration: BoxDecoration(
                                              color: statusColor.withValues(alpha: 0.1),
                                              borderRadius: BorderRadius.circular(6),
                                            ),
                                            child: Text(
                                              statusText,
                                              style: TextStyle(
                                                fontSize: 10,
                                                fontWeight: FontWeight.bold,
                                                color: statusColor,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 6),
                                      Text(
                                        eq['name'] ?? 'Chưa có tên',
                                        style: const TextStyle(
                                          fontSize: 15,
                                          fontWeight: FontWeight.bold,
                                          color: AppTheme.neutral900,
                                          height: 1.2,
                                        ),
                                      ),
                                      const SizedBox(height: 8),
                                      Row(
                                        children: [
                                          Icon(PhosphorIcons.tag(PhosphorIconsStyle.fill), size: 14, color: AppTheme.neutral400),
                                          const SizedBox(width: 4),
                                          Expanded(
                                            child: Text(
                                              "${eq['categoryName'] ?? 'Không phân loại'} • ${eq['model'] ?? 'Không rõ Model'}",
                                              style: const TextStyle(
                                                fontSize: 12,
                                                color: AppTheme.neutral500,
                                              ),
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    );
                  }
                }

                return ListView(
                  padding: const EdgeInsets.only(
                    left: 16,
                    right: 16,
                    bottom: 140, // Padding to avoid overlapping with FAB & Bottom Nav
                  ),
                  children: listWidgets,
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
