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
  List<Map<String, dynamic>> _savedAccounts = [];

  String get baseUrl => _baseUrl;
  Map<String, dynamic>? get currentUser => _currentUser;
  bool get isAuthenticated => _currentUser != null;
  List<Map<String, dynamic>> get savedAccounts => List.unmodifiable(_savedAccounts);

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString('server_url');
    if (saved == null ||
        saved.contains("10.0.2.2") ||
        saved.contains("10.162.3.118") ||
        saved.contains("127.0.0.1") ||
        saved.contains("localhost")) {
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

    // Load saved multi-accounts
    final accountsJson = prefs.getString('saved_accounts_v2');
    if (accountsJson != null) {
      try {
        final List list = jsonDecode(accountsJson);
        _savedAccounts = list.map((e) => Map<String, dynamic>.from(e)).toList();
      } catch (_) {
        _savedAccounts = [];
      }
    }
  }

  Future<void> _saveAccountsToPrefs() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('saved_accounts_v2', jsonEncode(_savedAccounts));
  }

  Future<void> setServerUrl(String url) async {
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
      final uri = Uri.parse('$_baseUrl/api/auth/login');
      final response = await http
          .post(
            uri,
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json',
            },
            body: jsonEncode({'identity': identity, 'password': password}),
          )
          .timeout(const Duration(seconds: 12));

      _updateCookie(response);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          _currentUser = data['user'];
          final prefs = await SharedPreferences.getInstance();
          await prefs.setString('current_user', jsonEncode(_currentUser));

          // Save to multi-accounts list
          final username = _currentUser!['username'] ?? identity;
          _savedAccounts.removeWhere((a) => a['username'] == username);
          _savedAccounts.insert(0, {
            'username': username,
            'role': _currentUser!['role'],
            'display_name': _currentUser!['display_name'] ?? username,
            'session_cookie': _sessionCookie ?? '',
            'last_login': DateTime.now().toIso8601String(),
            'full_user': _currentUser,
          });
          await _saveAccountsToPrefs();

          return {
            'success': true,
            'message': data['message'] ?? 'Welcome back, $identity!',
            'user': _currentUser,
          };
        }
      }

      try {
        final err = jsonDecode(response.body);
        return {
          'success': false,
          'message': err['message'] ?? 'Invalid credentials. Please verify your username and password.',
        };
      } catch (_) {
        return {
          'success': false,
          'message': 'Invalid credentials. Please verify your username and password.',
        };
      }
    } catch (e) {
      debugPrint("Login exception: $e");
      return {
        'success': false,
        'message': 'Connection error: $e',
      };
    }
  }

  Future<bool> switchAccount(String username) async {
    try {
      final account = _savedAccounts.firstWhere(
        (a) => a['username'] == username,
        orElse: () => {},
      );
      if (account.isEmpty) return false;

      _currentUser = Map<String, dynamic>.from(account['full_user'] ?? {});
      _sessionCookie = account['session_cookie'];

      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('current_user', jsonEncode(_currentUser));
      if (_sessionCookie != null) {
        await prefs.setString('session_cookie', _sessionCookie!);
      }

      return true;
    } catch (e) {
      debugPrint("Switch account error: $e");
      return false;
    }
  }

  Future<void> removeAccount(String username) async {
    _savedAccounts.removeWhere((a) => a['username'] == username);
    await _saveAccountsToPrefs();
    if (_currentUser != null && _currentUser!['username'] == username) {
      await logout();
    }
  }

  Future<void> logout({bool removeCurrent = false}) async {
    try {
      await http.get(Uri.parse('$_baseUrl/auth/logout'), headers: _headers(isJson: false));
    } catch (_) {}

    if (removeCurrent && _currentUser != null) {
      _savedAccounts.removeWhere((a) => a['username'] == _currentUser!['username']);
      await _saveAccountsToPrefs();
    }

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
        'message': 'Network scan failure: $e',
      };
    }
  }

  Future<Map<String, dynamic>> getDashboardStats() async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/api/dashboard/stats'), headers: _headers())
          .timeout(const Duration(seconds: 6));

      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      return {'success': false, 'message': 'HTTP ${response.statusCode}'};
    } catch (e) {
      return {'success': false, 'message': '$e'};
    }
  }

  Future<List<dynamic>> getTodayActivity() async {
    return getTodayAttendance();
  }

  Future<List<dynamic>> getTodayAttendance() async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/api/attendance/today'), headers: _headers())
          .timeout(const Duration(seconds: 6));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['records'] as List<dynamic>? ?? [];
      }
      return [];
    } catch (_) {
      return [];
    }
  }

  Future<List<dynamic>> searchStudents([String? query, int? dept]) async {
    try {
      final queryParams = <String, String>{};
      if (query != null && query.isNotEmpty) queryParams['q'] = query;
      if (dept != null) queryParams['dept'] = dept.toString();

      final uri = Uri.parse('$_baseUrl/api/students').replace(queryParameters: queryParams);
      final response = await http.get(uri, headers: _headers()).timeout(const Duration(seconds: 6));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['students'] as List<dynamic>? ?? [];
      }
      return [];
    } catch (e) {
      debugPrint("Search students error: $e");
      return [];
    }
  }
}

