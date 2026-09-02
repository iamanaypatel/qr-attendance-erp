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

  final List<Widget> _screens = [
    const ScannerScreen(),
    const DashboardScreen(),
    const StudentQrScreen(),
  ];

  void _showSettingsDialog() {
    final controller = TextEditingController(text: ApiService().baseUrl);
    final user = ApiService().currentUser;

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text("ERP Settings & Account"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const CircleAvatar(child: Icon(Icons.person)),
              title: Text(user?['username'] ?? 'User', style: const TextStyle(fontWeight: FontWeight.bold)),
              subtitle: Text("Role: ${user?['role']?.toString().toUpperCase() ?? 'GUEST'}"),
            ),
            const Divider(),
            const Text("Server Endpoint:", style: TextStyle(fontSize: 12, color: Colors.grey)),
            Text(ApiService().baseUrl, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              decoration: const InputDecoration(
                labelText: "Update Server URL",
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                ElevatedButton(
                  onPressed: () async {
                    final messenger = ScaffoldMessenger.of(context);
                    await ApiService().setServerUrl(controller.text);
                    if (ctx.mounted) Navigator.pop(ctx);
                    messenger.showSnackBar(
                      SnackBar(content: Text("Updated server URL to: ${ApiService().baseUrl}")),
                    );
                  },
                  child: const Text("Save URL"),
                ),
                const SizedBox(width: 8),
                TextButton(
                  onPressed: widget.onToggleTheme,
                  child: const Text("Toggle Theme"),
                ),
              ],
            ),
            const Divider(),
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.red.shade700,
                foregroundColor: Colors.white,
              ),
              icon: const Icon(Icons.logout),
              label: const Text("Sign Out"),
              onPressed: () async {
                Navigator.pop(ctx);
                await ApiService().logout();
                if (!mounted) return;
                Navigator.of(context).pushReplacement(
                  MaterialPageRoute(
                    builder: (_) => LoginScreen(onToggleTheme: widget.onToggleTheme),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (idx) {
          if (idx == 3) {
            _showSettingsDialog();
          } else {
            setState(() {
              _currentIndex = idx;
            });
          }
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.qr_code_scanner_outlined),
            selectedIcon: Icon(Icons.qr_code_scanner),
            label: "Scanner",
          ),
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard),
            label: "Dashboard",
          ),
          NavigationDestination(
            icon: Icon(Icons.badge_outlined),
            selectedIcon: Icon(Icons.badge),
            label: "Student ID",
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings),
            label: "Settings",
          ),
        ],
      ),
    );
  }
}
