import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  String _baseUrl = "https://qr-attendance-erp.onrender.com";
  String? _sessionCookie;
  Map<String, dynamic>? _currentUser;

  String get baseUrl => _baseUrl;
  Map<String, dynamic>? get currentUser => _currentUser;
  bool get isAuthenticated => _currentUser != null;

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString('server_url');
    if (saved == null || saved.contains("10.0.2.2") || saved.contains("10.162.3.118") || saved.contains("127.0.0.1") || saved.contains("localhost")) {
      _baseUrl = "https://qr-attendance-erp.onrender.com";
      await prefs.setString('server_url', _baseUrl);
    } else {
      _baseUrl = saved;
    }
    _sessionCookie = prefs.getString('session_cookie');
    final userJson = prefs.getString('current_user');
    if (userJson != null) {
      try {
        _currentUser = jsonDecode(userJson);
      } catch (e) {
        _currentUser = null;
      }
    }
  }

  Future<void> setServerUrl(String url) async {
    // Strip trailing slashes
    _baseUrl = url.trim().replaceAll(RegExp(r'/+$'), '');
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('server_url', _baseUrl);
  }

  Map<String, String> _headers({bool isJson = true}) {
    final headers = <String, String>{};
    if (isJson) {
      headers['Content-Type'] = 'application/json';
      headers['Accept'] = 'application/json';
    }
    if (_sessionCookie != null && _sessionCookie!.isNotEmpty) {
      headers['Cookie'] = _sessionCookie!;
    }
    return headers;
  }

  void _updateCookie(http.Response response) async {
    final rawCookie = response.headers['set-cookie'];
    if (rawCookie != null) {
      // Extract session cookie part before ';'
      final parts = rawCookie.split(';');
      _sessionCookie = parts[0];
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('session_cookie', _sessionCookie!);
    }
  }

  Future<bool> checkHealth() async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/api/health'))
          .timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['status'] == 'healthy';
      }
      return false;
    } catch (e) {
      debugPrint("Health check error: $e");
      return false;
    }
  }

  Future<Map<String, dynamic>> login(String identity, String password) async {
    try {
      final uri = Uri.parse('$_baseUrl/auth/login');
      // Use form-encoded data to authenticate with Flask-Login
      final response = await http
          .post(
            uri,
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: {'identity': identity, 'password': password},
          )
          .timeout(const Duration(seconds: 7));

      _updateCookie(response);

      // On successful Flask login, server returns 302 redirect to dashboard
      // Or 200 with dashboard if redirect is followed by HTTP client
      final success = response.statusCode == 200 || response.statusCode == 302;
      if (success) {
        await getDashboardStats();
        _currentUser = {
          'username': identity,
          'role': identity == 'admin' ? 'admin' : (identity == 'teacher' ? 'teacher' : 'student'),
        };

        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('current_user', jsonEncode(_currentUser));

        return {
          'success': true,
          'message': 'Welcome back, $identity!',
          'user': _currentUser,
        };
      } else {
        return {
          'success': false,
          'message': 'Invalid credentials or connection rejected.',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'message': 'Connection error: $e',
      };
    }
  }

  Future<void> logout() async {
    try {
      await http.get(Uri.parse('$_baseUrl/auth/logout'), headers: _headers(isJson: false));
    } catch (_) {}
    _sessionCookie = null;
    _currentUser = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('session_cookie');
    await prefs.remove('current_user');
  }

  Future<Map<String, dynamic>> scanAttendance(String token) async {
    try {
      final response = await http
          .post(
            Uri.parse('$_baseUrl/api/attendance/scan'),
            headers: _headers(),
            body: jsonEncode({'token': token.trim()}),
          )
          .timeout(const Duration(seconds: 8));

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return data;
    } catch (e) {
      return {
        'success': false,
        'message': 'Scanner network error: $e',
      };
    }
  }

  Future<Map<String, dynamic>> getDashboardStats() async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/api/dashboard/stats'), headers: _headers())
          .timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      return {'success': false};
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  Future<List<dynamic>> getTodayAttendance() async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/api/attendance/today'), headers: _headers())
          .timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['records'] as List<dynamic>? ?? [];
      }
      return [];
    } catch (e) {
      return [];
    }
  }

  Future<List<dynamic>> searchStudents(String query) async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/api/students?q=${Uri.encodeComponent(query)}'), headers: _headers())
          .timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['students'] as List<dynamic>? ?? [];
      }
      return [];
    } catch (e) {
      return [];
    }
  }
}
