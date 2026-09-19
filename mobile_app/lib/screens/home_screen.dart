import 'package:flutter/material.dart';
import 'package:mobile_app/services/api_service.dart';
import 'package:mobile_app/screens/take_attendance_screen.dart';
import 'package:mobile_app/screens/dashboard_screen.dart';
import 'package:mobile_app/screens/student_qr_screen.dart';
import 'package:mobile_app/screens/login_screen.dart';
import 'package:mobile_app/screens/reset_data_screen.dart';

class HomeScreen extends StatefulWidget {
  final VoidCallback onToggleTheme;
  const HomeScreen({super.key, required this.onToggleTheme});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    // If student, default to QR pass tab
    final user = ApiService().currentUser;
    if (user != null && user['role'] == 'student') {
      _currentIndex = 0; // First tab for student will be QR Pass
    }
  }

  Color _getRoleColor(String? role) {
    switch (role?.toLowerCase()) {
      case 'admin':
        return Colors.amber.shade700;
      case 'teacher':
        return const Color(0xFF2563EB);
      case 'student':
        return const Color(0xFF10B981);
      default:
        return const Color(0xFF4F46E5);
    }
  }

  IconData _getRoleIcon(String? role) {
    switch (role?.toLowerCase()) {
      case 'admin':
        return Icons.admin_panel_settings_rounded;
      case 'teacher':
        return Icons.school_rounded;
      case 'student':
        return Icons.person_rounded;
      default:
        return Icons.account_circle_rounded;
    }
  }

  void _confirmLogout() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        title: const Row(
          children: [
            Icon(Icons.logout_rounded, color: Colors.redAccent),
            SizedBox(width: 8),
            Text("Confirm Logout"),
          ],
        ),
        content: const Text(
          "Are you sure you want to log out? All session credentials and cached data will be cleared.",
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text("Cancel"),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.redAccent,
              foregroundColor: Colors.white,
            ),
            onPressed: () async {
              Navigator.pop(ctx);
              final nav = Navigator.of(context);
              await ApiService().logout();
              if (!mounted) return;
              nav.pushAndRemoveUntil(
                MaterialPageRoute(
                  builder: (_) => LoginScreen(onToggleTheme: widget.onToggleTheme),
                ),
                (route) => false,
              );
            },
            child: const Text("Log Out"),
          ),
        ],
      ),
    );
  }

  void _showUserSessionSheet() {
    final user = ApiService().currentUser;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: Theme.of(context).scaffoldBackgroundColor,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.2),
              blurRadius: 20,
              offset: const Offset(0, -5),
            )
          ],
        ),
        child: SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 44,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.grey.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Header
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    "Current Session",
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, letterSpacing: -0.5),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close_rounded),
                    onPressed: () => Navigator.pop(ctx),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // Active Account Card
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF1E3A8A), Color(0xFF2563EB)],
                  ),
                  borderRadius: BorderRadius.circular(18),
                  boxShadow: [
                    BoxShadow(
                      color: const Color(0xFF2563EB).withValues(alpha: 0.3),
                      blurRadius: 10,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 24,
                      backgroundColor: Colors.white.withValues(alpha: 0.25),
                      child: Icon(_getRoleIcon(user?['role']), color: Colors.white, size: 26),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Flexible(
                                child: Text(
                                  user?['display_name'] ?? user?['username'] ?? 'Active User',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 16,
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              const SizedBox(width: 6),
                              const Icon(Icons.check_circle_rounded, color: Colors.greenAccent, size: 16),
                            ],
                          ),
                          Text(
                            "@${user?['username'] ?? ''} • ${(user?['role'] ?? 'user').toString().toUpperCase()}",
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.85),
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Text(
                        "ACTIVE",
                        style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 16),

              if (user?['role'] == 'admin') ...[
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.redAccent,
                      side: const BorderSide(color: Colors.redAccent),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                    ),
                    icon: const Icon(Icons.delete_sweep_rounded, color: Colors.redAccent),
                    label: const Text(
                      "Reset Data & Start Fresh",
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                    onPressed: () {
                      Navigator.pop(ctx);
                      Navigator.push(
                        context,
                        MaterialPageRoute(builder: (_) => const ResetDataScreen()),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 12),
              ],

              // Action Buttons
              Row(
                children: [
                  OutlinedButton.icon(
                    onPressed: widget.onToggleTheme,
                    icon: const Icon(Icons.brightness_4_rounded, size: 18),
                    label: const Text("Theme"),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.redAccent,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      icon: const Icon(Icons.logout_rounded, size: 18),
                      label: const Text("Log Out"),
                      onPressed: () {
                        Navigator.pop(ctx);
                        _confirmLogout();
                      },
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = ApiService().currentUser;
    final isStudent = user != null && user['role'] == 'student';
    final roleColor = _getRoleColor(user?['role']);

    // Build role-adaptive screens and navigation items
    final List<Widget> screens = isStudent
        ? [
            const StudentQrScreen(),
            const DashboardScreen(),
          ]
        : [
            const TakeAttendanceScreen(),
            const DashboardScreen(),
            const StudentQrScreen(),
          ];

    final List<NavigationDestination> destinations = isStudent
        ? const [
            NavigationDestination(
              icon: Icon(Icons.badge_outlined),
              selectedIcon: Icon(Icons.badge_rounded),
              label: "My Pass",
            ),
            NavigationDestination(
              icon: Icon(Icons.pie_chart_outline_rounded),
              selectedIcon: Icon(Icons.pie_chart_rounded),
              label: "Attendance",
            ),
          ]
        : const [
            NavigationDestination(
              icon: Icon(Icons.how_to_reg_outlined),
              selectedIcon: Icon(Icons.how_to_reg_rounded),
              label: "Attendance",
            ),
            NavigationDestination(
              icon: Icon(Icons.dashboard_outlined),
              selectedIcon: Icon(Icons.dashboard_rounded),
              label: "Analytics",
            ),
            NavigationDestination(
              icon: Icon(Icons.badge_outlined),
              selectedIcon: Icon(Icons.badge_rounded),
              label: "ID Cards",
            ),
          ];

    // Ensure valid current index on role change
    final safeIndex = _currentIndex >= screens.length ? 0 : _currentIndex;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              width: 28,
              height: 28,
              margin: const EdgeInsets.only(right: 8),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(8),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.2),
                    blurRadius: 4,
                  ),
                ],
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Image.asset(
                  'assets/images/app_logo.png',
                  fit: BoxFit.cover,
                  errorBuilder: (c, e, s) => const Icon(Icons.school_rounded, size: 22),
                ),
              ),
            ),
            Text(
              isStudent ? "Student Portal" : "VSGOI",
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18, letterSpacing: 0.5),
            ),
          ],
        ),
        actions: [
          // Current User Badge
          InkWell(
            onTap: _showUserSessionSheet,
            borderRadius: BorderRadius.circular(20),
            child: Container(
              margin: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.white.withValues(alpha: 0.3)),
              ),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 12,
                    backgroundColor: roleColor,
                    child: Icon(_getRoleIcon(user?['role']), size: 14, color: Colors.white),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    user?['username'] ?? 'User',
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                ],
              ),
            ),
          ),
          // Explicit Logout Button
          IconButton(
            icon: const Icon(Icons.logout_rounded),
            tooltip: "Logout",
            onPressed: _confirmLogout,
          ),
        ],
      ),
      body: IndexedStack(
        index: safeIndex,
        children: screens,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: safeIndex,
        onDestinationSelected: (idx) {
          setState(() {
            _currentIndex = idx;
          });
        },
        destinations: destinations,
      ),
    );
  }
}
