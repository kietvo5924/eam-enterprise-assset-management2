import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  static const Color primaryColor = Color(0xFF00a0e2);
  static const Color primaryHoverColor = Color(0xFF0080b5);
  static const Color primaryLightColor = Color(0xFFe6f6fc);
  
  static const Color successColor = Color(0xFF52c41a);
  static const Color warningColor = Color(0xFFfaad14);
  static const Color dangerColor = Color(0xFFff4d4f);
  static const Color infoColor = Color(0xFF1677ff);

  static const Color neutral50 = Color(0xFFf8fafc);
  static const Color neutral100 = Color(0xFFf1f5f9);
  static const Color neutral200 = Color(0xFFe2e8f0);
  static const Color neutral300 = Color(0xFFcbd5e1);
  static const Color neutral400 = Color(0xFF94a3b8);
  static const Color neutral500 = Color(0xFF64748b);
  static const Color neutral600 = Color(0xFF475569);
  static const Color neutral700 = Color(0xFF334155);
  static const Color neutral800 = Color(0xFF1e293b);
  static const Color neutral900 = Color(0xFF0f172a);

  static ThemeData get lightTheme {
    return ThemeData(
      primaryColor: primaryColor,
      scaffoldBackgroundColor: neutral50,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primaryColor,
        primary: primaryColor,
        secondary: primaryHoverColor,
        error: dangerColor,
        surface: Colors.white,
      ),
      textTheme: GoogleFonts.beVietnamProTextTheme(),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.white,
        foregroundColor: neutral900,
        elevation: 0,
        centerTitle: false,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryColor,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          elevation: 2,
          padding: const EdgeInsets.symmetric(vertical: 14),
          textStyle: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
        ),
      ),
      snackBarTheme: const SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}
