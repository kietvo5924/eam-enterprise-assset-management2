import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../database/app_database.dart';

class UserProvider extends ChangeNotifier {
  String _username = '';
  String _roles = '';
  String _tenantId = '';

  String get username => _username;
  String get roles => _roles;
  String get tenantId => _tenantId;

  String get shortName {
    if (_username.isEmpty) return 'Kỹ thuật viên';
    final parts = _username.split('@');
    return parts[0];
  }

  bool get canCreateWorkOrder {
    final r = _roles.toLowerCase();
    return r.contains('admin') || r.contains('manager') || r.contains('supervisor');
  }

  Future<void> loadUser() async {
    final prefs = await SharedPreferences.getInstance();
    _username = prefs.getString('username') ?? '';
    _roles = prefs.getString('roles') ?? '';
    _tenantId = prefs.getString('tenantId') ?? '';
    notifyListeners();

    // Trigger local DB cleanup in background
    if (_tenantId.isNotEmpty) {
      try {
        AppDatabase.instance.workOrderDao.deleteOldCompletedWorkOrders();
        AppDatabase.instance.assetDao.deleteOrphanedAssets();
      } catch (e) {
        // Ignore DB init/cleanup errors
      }
    }
  }
}
