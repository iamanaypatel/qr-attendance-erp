import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:mobile_app/services/api_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    final api = ApiService();
    await api.logout();
    await api.init();
  });

  test('Test A — Single user login state & storage isolation', () async {
    final api = ApiService();
    expect(api.isAuthenticated, false);
    expect(api.currentUser, null);

    // Simulate successful login of User A by mocking SharedPreferences storage directly
    final userA = {
      'id': 1,
      'username': 'student_a',
      'role': 'student',
      'display_name': 'Student A',
      'student': {
        'id': 101,
        'student_id': 'VSGOI-001',
        'full_name': 'Student A FullName',
      },
    };

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('current_user', jsonEncode(userA));
    await prefs.setString('session_cookie', 'session_student_a=123');
    await api.init();

    expect(api.isAuthenticated, true);
    expect(api.currentUser?['username'], 'student_a');
    expect(api.currentUser?['student']?['student_id'], 'VSGOI-001');
  });

  test('Test B — Second login attempt is strictly blocked while user is authenticated', () async {
    final api = ApiService();

    // Setup active session for User A
    final userA = {
      'id': 1,
      'username': 'student_a',
      'role': 'student',
      'display_name': 'Student A',
    };
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('current_user', jsonEncode(userA));
    await prefs.setString('session_cookie', 'session_user_a');
    await api.init();

    expect(api.isAuthenticated, true);

    // Attempt login as User B while User A is active
    final result = await api.login('student_b', 'password123');

    // Must be blocked
    expect(result['success'], false);
    expect(
      result['message'],
      contains('Another user is already logged in. Please logout from the current account before signing in with another account.'),
    );

    // User A session must remain unchanged and active
    expect(api.isAuthenticated, true);
    expect(api.currentUser?['username'], 'student_a');

    // Storage must still be User A
    final storedUser = prefs.getString('current_user');
    expect(storedUser, isNotNull);
    expect(jsonDecode(storedUser!)['username'], 'student_a');
    expect(prefs.getString('session_cookie'), 'session_user_a');
  });

  test('Test C & D — Full logout clears all state and permits User B login without data mixing', () async {
    final api = ApiService();
    final prefs = await SharedPreferences.getInstance();

    // User A logged in with cached student profile
    final userA = {
      'id': 1,
      'username': 'student_a',
      'role': 'student',
      'display_name': 'Student A',
      'student': {
        'id': 101,
        'student_id': 'VSGOI-001',
        'full_name': 'Student Alpha',
        'penalty_count': 2,
      },
    };
    await prefs.setString('current_user', jsonEncode(userA));
    await prefs.setString('session_cookie', 'cookie_a');
    await api.init();

    expect(api.isAuthenticated, true);

    // Perform full logout
    await api.logout();

    // Verification of complete purge
    expect(api.isAuthenticated, false);
    expect(api.currentUser, null);
    expect(prefs.containsKey('current_user'), false);
    expect(prefs.containsKey('session_cookie'), false);
    expect(prefs.containsKey('saved_accounts_v2'), false);
    expect(prefs.containsKey('saved_accounts'), false);

    // Now User B can be authenticated without any trace of User A
    final userB = {
      'id': 2,
      'username': 'student_b',
      'role': 'student',
      'display_name': 'Student B',
      'student': {
        'id': 102,
        'student_id': 'VSGOI-002',
        'full_name': 'Student Beta',
        'penalty_count': 0,
      },
    };
    await prefs.setString('current_user', jsonEncode(userB));
    await prefs.setString('session_cookie', 'cookie_b');
    await api.init();

    expect(api.isAuthenticated, true);
    expect(api.currentUser?['username'], 'student_b');
    expect(api.currentUser?['student']?['student_id'], 'VSGOI-002');
    expect(api.currentUser?['student']?['full_name'], 'Student Beta');
    // Ensure no User A data exists
    expect(api.currentUser?['username'], isNot('student_a'));
    expect(api.currentUser?['student']?['student_id'], isNot('VSGOI-001'));
  });

  test('Test E — App restart restores single session or stays logged out after explicit logout', () async {
    final api = ApiService();
    final prefs = await SharedPreferences.getInstance();

    // Scenario 1: Active session exists before app close
    final user = {
      'id': 3,
      'username': 'teacher_smith',
      'role': 'teacher',
      'display_name': 'Prof. Smith',
    };
    await prefs.setString('current_user', jsonEncode(user));
    await prefs.setString('session_cookie', 'cookie_smith');

    // Simulate App Restart by calling init() on fresh instance
    await api.init();
    expect(api.isAuthenticated, true);
    expect(api.currentUser?['username'], 'teacher_smith');

    // Scenario 2: User explicitly logs out, then app restarts
    await api.logout();
    expect(api.isAuthenticated, false);

    // Simulate App Restart after explicit logout
    await api.init();
    expect(api.isAuthenticated, false);
    expect(api.currentUser, null);
  });
}
