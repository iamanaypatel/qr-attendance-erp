import 'package:flutter/material.dart';
import 'package:mobile_app/services/api_service.dart';
import 'package:mobile_app/screens/scanner_screen.dart';
import 'package:mobile_app/screens/dashboard_screen.dart';
import 'package:mobile_app/screens/student_qr_screen.dart';
import 'package:mobile_app/screens/login_screen.dart';

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

  void _showAccountSwitcherSheet() {
    final user = ApiService().currentUser;
    final saved = ApiService().savedAccounts;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setSheetState) {
          final isDark = Theme.of(context).brightness == Brightness.dark;

          return Container(
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
                        "Multi-User Accounts",
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

                  const SizedBox(height: 20),

                  // Other Saved Accounts
                  if (saved.length > 1) ...[
                    const Text(
                      "SWITCH TO ANOTHER ACCOUNT",
                      style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, letterSpacing: 0.6, color: Colors.grey),
                    ),
                    const SizedBox(height: 10),
                    ConstrainedBox(
                      constraints: const BoxConstraints(maxHeight: 180),
                      child: ListView(
                        shrinkWrap: true,
                        children: saved.where((a) => a['username'] != user?['username']).map((acc) {
                          final role = acc['role'] ?? 'user';
                          final username = acc['username'] ?? '';
                          final roleColor = _getRoleColor(role);

                          return Container(
                            margin: const EdgeInsets.only(bottom: 8),
                            decoration: BoxDecoration(
                              color: isDark ? Colors.white.withValues(alpha: 0.05) : Colors.black.withValues(alpha: 0.03),
                              borderRadius: BorderRadius.circular(14),
                              border: Border.all(color: Colors.grey.withValues(alpha: 0.15)),
                            ),
                            child: ListTile(
                              leading: CircleAvatar(
                                backgroundColor: roleColor.withValues(alpha: 0.15),
                                child: Icon(_getRoleIcon(role), color: roleColor, size: 20),
                              ),
                              title: Text(acc['display_name'] ?? username, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                              subtitle: Text("@$username • ${role.toUpperCase()}", style: TextStyle(fontSize: 11, color: roleColor)),
                              trailing: ElevatedButton(
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: const Color(0xFF2563EB),
                                  foregroundColor: Colors.white,
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                                  visualDensity: VisualDensity.compact,
                                ),
                                onPressed: () async {
                                  Navigator.pop(ctx);
                                  await ApiService().switchAccount(username);
                                  if (!mounted) return;
                                  setState(() {});
                                },
                                child: const Text("Switch", style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                              ),
                            ),
                          );
                        }).toList(),
                      ),
                    ),
                    const SizedBox(height: 14),
                  ],

                  // Add Another Account Button
                  OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size(double.infinity, 46),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      side: const BorderSide(color: Color(0xFF2563EB)),
                    ),
                    icon: const Icon(Icons.person_add_alt_1_rounded, size: 18, color: Color(0xFF2563EB)),
                    label: const Text(
                      "+ Add Another Account",
                      style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF2563EB)),
                    ),
                    onPressed: () {
                      Navigator.pop(ctx);
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => LoginScreen(onToggleTheme: widget.onToggleTheme),
                        ),
                      );
                    },
                  ),

                  const SizedBox(height: 12),

                  // Sign Out Row
                  Row(
                    children: [
                      Expanded(
                        child: TextButton.icon(
                          style: TextButton.styleFrom(
                            foregroundColor: Colors.redAccent,
                            padding: const EdgeInsets.symmetric(vertical: 12),
                          ),
                          icon: const Icon(Icons.logout_rounded, size: 18),
                          label: const Text("Sign Out This Account"),
                          onPressed: () async {
                            final nav = Navigator.of(context);
                            Navigator.pop(ctx);
                            await ApiService().logout(removeCurrent: true);
                            if (!mounted) return;
                            nav.pushReplacement(
                              MaterialPageRoute(
                                builder: (_) => LoginScreen(onToggleTheme: widget.onToggleTheme),
                              ),
                            );
                          },
                        ),
                      ),
                      TextButton(
                        onPressed: widget.onToggleTheme,
                        child: const Icon(Icons.brightness_4_rounded, size: 20),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
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
            const ScannerScreen(),
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
              icon: Icon(Icons.qr_code_scanner_outlined),
              selectedIcon: Icon(Icons.qr_code_scanner_rounded),
              label: "Scanner",
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
              isStudent ? "Student Portal" : "Apex QR ERP",
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
            ),
          ],
        ),
        actions: [
          // Account Switcher Avatar Pill
          InkWell(
            onTap: _showAccountSwitcherSheet,
            borderRadius: BorderRadius.circular(20),
            child: Container(
              margin: const EdgeInsets.symmetric(vertical: 8, horizontal: 8),
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
                  const SizedBox(width: 4),
                  const Icon(Icons.keyboard_arrow_down_rounded, size: 16, color: Colors.white),
                ],
              ),
            ),
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
