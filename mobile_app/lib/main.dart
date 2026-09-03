import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:mobile_app/services/api_service.dart';
import 'package:mobile_app/screens/login_screen.dart';
import 'package:mobile_app/screens/home_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  await ApiService().init();

  runApp(const QRAttendanceApp());
}

class QRAttendanceApp extends StatefulWidget {
  const QRAttendanceApp({super.key});

  @override
  State<QRAttendanceApp> createState() => _QRAttendanceAppState();
}

class _QRAttendanceAppState extends State<QRAttendanceApp> {
  ThemeMode _themeMode = ThemeMode.system;

  void toggleTheme() {
    setState(() {
      _themeMode =
          _themeMode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    });
  }

  @override
  Widget build(BuildContext context) {
    const primaryColor = Color(0xFF1E3A8A); // Deep Navy
    const accentColor = Color(0xFF2563EB); // Modern Cobalt Blue
    const surfaceDark = Color(0xFF0B1120);

    return MaterialApp(
      title: 'Dr. Virendra Swarup Memorial Trust GOI - Attendance ERP',
      debugShowCheckedModeBanner: false,
      themeMode: _themeMode,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.light,
        colorScheme: ColorScheme.fromSeed(
          seedColor: primaryColor,
          primary: primaryColor,
          secondary: accentColor,
          surface: const Color(0xFFF8FAFC),
        ),
        scaffoldBackgroundColor: const Color(0xFFF1F5F9),
        appBarTheme: const AppBarTheme(
          backgroundColor: primaryColor,
          foregroundColor: Colors.white,
          elevation: 0,
          centerTitle: true,
        ),
        cardTheme: CardThemeData(
          elevation: 2,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          color: Colors.white,
        ),
      ),
      darkTheme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        colorScheme: ColorScheme.fromSeed(
          seedColor: primaryColor,
          brightness: Brightness.dark,
          primary: const Color(0xFF3B82F6),
          secondary: const Color(0xFF60A5FA),
          surface: const Color(0xFF1E293B),
        ),
        scaffoldBackgroundColor: surfaceDark,
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF0F172A),
          foregroundColor: Colors.white,
          elevation: 0,
          centerTitle: true,
        ),
        cardTheme: CardThemeData(
          elevation: 3,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          color: const Color(0xFF1E293B),
        ),
      ),
      home: ApiService().isAuthenticated
          ? HomeScreen(onToggleTheme: toggleTheme)
          : LoginScreen(onToggleTheme: toggleTheme),
    );
  }
}
