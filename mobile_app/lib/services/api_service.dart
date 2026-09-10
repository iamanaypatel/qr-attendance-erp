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

    // Clean up any legacy multi-account cache to enforce single-user session isolation
    if (prefs.containsKey('saved_accounts_v2')) {
      await prefs.remove('saved_accounts_v2');
    }
    if (prefs.containsKey('saved_accounts')) {
      await prefs.remove('saved_accounts');
    }
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
    // Enforce strictly ONE active user session at a time in APK
    if (_currentUser != null) {
      return {
        'success': false,
        'message': 'Another user is already logged in. Please logout from the current account before signing in with another account.',
      };
    }

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

  Future<void> logout() async {
    try {
      await http
          .get(Uri.parse('$_baseUrl/auth/logout'), headers: _headers(isJson: false))
          .timeout(const Duration(seconds: 4));
    } catch (_) {}

    _sessionCookie = null;
    _currentUser = null;

    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('session_cookie');
    await prefs.remove('current_user');
    await prefs.remove('saved_accounts_v2');
    await prefs.remove('saved_accounts');
  }

  Future<Map<String, dynamic>> scanAttendance(String token, {int? subjectId, String? semester}) async {
    try {
      final bodyMap = <String, dynamic>{'token': token.trim()};
      if (subjectId != null) {
        bodyMap['subject_id'] = subjectId;
      }
      if (semester != null && semester.isNotEmpty) {
        bodyMap['semester'] = semester;
      }

      final response = await http
          .post(
            Uri.parse('$_baseUrl/api/attendance/scan'),
            headers: _headers(),
            body: jsonEncode(bodyMap),
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

  Future<List<dynamic>> getSubjects({int? deptId, String? semester}) async {
    try {
      final queryParams = <String, String>{};
      if (deptId != null) queryParams['department_id'] = deptId.toString();
      if (semester != null && semester.isNotEmpty) queryParams['semester'] = semester;

      final uri = Uri.parse('$_baseUrl/api/subjects').replace(queryParameters: queryParams);
      final response = await http.get(uri, headers: _headers()).timeout(const Duration(seconds: 6));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['subjects'] as List<dynamic>? ?? [];
      }
      return [];
    } catch (e) {
      debugPrint("getSubjects error: $e");
      return [];
    }
  }

  Future<List<dynamic>> getTeacherSubjects() async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/api/teacher/subjects'), headers: _headers())
          .timeout(const Duration(seconds: 6));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['subjects'] as List<dynamic>? ?? [];
      }
      return [];
    } catch (e) {
      debugPrint("getTeacherSubjects error: $e");
      return [];
    }
  }

  Future<Map<String, dynamic>?> getStudentAttendanceSummary() async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/api/student/attendance'), headers: _headers())
          .timeout(const Duration(seconds: 6));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          return Map<String, dynamic>.from(data);
        }
      }
      return null;
    } catch (e) {
      debugPrint("getStudentAttendanceSummary error: $e");
      return null;
    }
  }

  Future<Map<String, dynamic>?> getStudentSubjectAttendanceDetail(int subjectId) async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/api/student/attendance/$subjectId'), headers: _headers())
          .timeout(const Duration(seconds: 6));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          return Map<String, dynamic>.from(data);
        }
      }
      return null;
    } catch (e) {
      debugPrint("getStudentSubjectAttendanceDetail error: $e");
      return null;
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

  Future<void> _cacheStudentProfile(Map<String, dynamic> student) async {
    if (_currentUser != null) {
      _currentUser!['student'] = student;
      try {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('current_user', jsonEncode(_currentUser));
      } catch (_) {}
    }
  }

  Future<Map<String, dynamic>?> getStudentDetails(int id) async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/api/students/$id'), headers: _headers())
          .timeout(const Duration(seconds: 6));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true && data['student'] != null) {
          return Map<String, dynamic>.from(data['student']);
        }
      }
      return null;
    } catch (_) {
      return null;
    }
  }

  Future<Map<String, dynamic>?> getCurrentStudent() async {
    bool hasNetworkError = false;
    bool isExplicitlyUnlinked = false;
    String unlinkedMsg = "Student profile is not linked to this account. Please contact the administrator.";

    // 1. Check if valid student is already cached in current session
    if (_currentUser != null &&
        _currentUser!['student'] is Map &&
        (_currentUser!['student'] as Map)['student_id'] != null) {
      final s = Map<String, dynamic>.from(_currentUser!['student']);
      if (s['student_id'].toString().isNotEmpty) {
        return s;
      }
    }

    // 2. Try primary route: GET /api/student/me
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/api/student/me'), headers: _headers())
          .timeout(const Duration(seconds: 6));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true && data['student'] != null) {
          final student = Map<String, dynamic>.from(data['student']);
          await _cacheStudentProfile(student);
          return student;
        }
      } else if (response.statusCode == 404) {
        try {
          final data = jsonDecode(response.body);
          if (data['error_code'] == 'PROFILE_NOT_LINKED') {
            isExplicitlyUnlinked = true;
            if (data['message'] != null) unlinkedMsg = data['message'];
          }
        } catch (_) {}
      }
    } catch (e) {
      debugPrint("api/student/me error: $e");
      hasNetworkError = true;
    }

    // 3. Try alternative route: GET /api/student/profile
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/api/student/profile'), headers: _headers())
          .timeout(const Duration(seconds: 6));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true && data['student'] != null) {
          final student = Map<String, dynamic>.from(data['student']);
          await _cacheStudentProfile(student);
          return student;
        }
      }
    } catch (e) {
      debugPrint("api/student/profile error: $e");
    }

    // 4. Fallback: Search students by username / roll number / display name
    if (_currentUser != null) {
      final username = (_currentUser!['username'] ?? '').toString().trim();
      final displayName = (_currentUser!['display_name'] ?? '').toString().trim();
      final email = (_currentUser!['email'] ?? '').toString().trim();

      if (username.isNotEmpty) {
        final matches = await searchStudents(username);
        for (final raw in matches) {
          if (raw is Map) {
            final s = Map<String, dynamic>.from(raw);
            final sid = (s['student_id'] ?? '').toString().toLowerCase();
            final roll = (s['roll_number'] ?? '').toString().toLowerCase();
            if (sid == username.toLowerCase() || roll == username.toLowerCase()) {
              await _cacheStudentProfile(s);
              return s;
            }
          }
        }
        if (matches.length == 1 && matches.first is Map) {
          final s = Map<String, dynamic>.from(matches.first);
          await _cacheStudentProfile(s);
          return s;
        }
      }

      if (displayName.isNotEmpty && displayName.toLowerCase() != username.toLowerCase()) {
        final matches = await searchStudents(displayName);
        for (final raw in matches) {
          if (raw is Map) {
            final s = Map<String, dynamic>.from(raw);
            final sname = (s['full_name'] ?? '').toString().toLowerCase();
            if (sname == displayName.toLowerCase()) {
              await _cacheStudentProfile(s);
              return s;
            }
          }
        }
      }

      if (email.isNotEmpty) {
        final matches = await searchStudents(email);
        for (final raw in matches) {
          if (raw is Map) {
            final s = Map<String, dynamic>.from(raw);
            final semail = (s['email'] ?? '').toString().toLowerCase();
            if (semail == email.toLowerCase()) {
              await _cacheStudentProfile(s);
              return s;
            }
          }
        }
      }
    }

    // 5. Fallback: Reuse identity from working Attendance scans
    try {
      final scans = await getTodayAttendance();
      if (_currentUser != null && scans.isNotEmpty) {
        final username = (_currentUser!['username'] ?? '').toString().trim().toLowerCase();
        final displayName = (_currentUser!['display_name'] ?? '').toString().trim().toLowerCase();

        for (final rec in scans) {
          if (rec is Map) {
            final sid = (rec['student_id'] ?? '').toString().toLowerCase();
            final roll = (rec['roll_number'] ?? '').toString().toLowerCase();
            final sname = (rec['student_name'] ?? '').toString().toLowerCase();
            final sObj = rec['student'] is Map ? Map<String, dynamic>.from(rec['student']) : null;

            if ((sid.isNotEmpty && sid == username) ||
                (roll.isNotEmpty && roll == username) ||
                (sname.isNotEmpty && sname == displayName)) {
              if (sObj != null && sObj['student_id'] != null) {
                await _cacheStudentProfile(sObj);
                return sObj;
              }
              if (sObj != null && sObj['id'] is int) {
                final fullStudent = await getStudentDetails(sObj['id']);
                if (fullStudent != null) {
                  await _cacheStudentProfile(fullStudent);
                  return fullStudent;
                }
              }
              final synth = {
                'student_id': rec['student_id'] ?? username,
                'full_name': rec['student_name'] ?? _currentUser!['display_name'] ?? 'Student',
                'roll_number': rec['roll_number'] ?? '-',
                'qr_token': rec['student_id'] ?? username,
              };
              await _cacheStudentProfile(synth);
              return synth;
            }
          }
        }
      }
    } catch (e) {
      debugPrint("Attendance identity reuse fallback error: $e");
    }

    // 6. Return specific error structure to distinguish Network Error vs Unlinked
    if (isExplicitlyUnlinked) {
      return {'error': 'PROFILE_NOT_LINKED', 'message': unlinkedMsg};
    }
    if (hasNetworkError) {
      return {'error': 'NETWORK_ERROR', 'message': 'Unable to connect to server. Please check your network and retry.'};
    }

    return {'error': 'PROFILE_NOT_LINKED', 'message': unlinkedMsg};
  }
}

