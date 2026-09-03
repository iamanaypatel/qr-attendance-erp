import 'package:flutter/material.dart';
import 'package:mobile_app/services/api_service.dart';
import 'package:mobile_app/screens/home_screen.dart';

class LoginScreen extends StatefulWidget {
  final VoidCallback onToggleTheme;
  const LoginScreen({super.key, required this.onToggleTheme});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isLoading = false;
  bool _obscurePassword = true;
  String? _errorMessage;
  bool _isServerOnline = false;

  @override
  void initState() {
    super.initState();
    _checkServer();
  }

  Future<void> _checkServer() async {
    final online = await ApiService().checkHealth();
    if (mounted) {
      setState(() {
        _isServerOnline = online;
      });
    }
  }

  Future<void> _handleLogin() async {
    final user = _usernameController.text.trim();
    final pass = _passwordController.text.trim();

    if (user.isEmpty || pass.isEmpty) {
      setState(() {
        _errorMessage = "Please enter both identity/username and password.";
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final res = await ApiService().login(user, pass);

    if (!mounted) return;

    setState(() {
      _isLoading = false;
    });

    if (res['success'] == true) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => HomeScreen(onToggleTheme: widget.onToggleTheme),
        ),
      );
    } else {
      setState(() {
        _errorMessage = res['message'] ?? "Invalid credentials. Please verify your login details.";
      });
    }
  }

  Future<void> _quickSwitchAccount(String username) async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final ok = await ApiService().switchAccount(username);
    if (!mounted) return;

    setState(() {
      _isLoading = false;
    });

    if (ok) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => HomeScreen(onToggleTheme: widget.onToggleTheme),
        ),
      );
    } else {
      setState(() {
        _errorMessage = "Session expired for this account. Please enter password to log in.";
      });
    }
  }

  void _showServerConfigDialog() {
    final controller = TextEditingController(text: ApiService().baseUrl);
    bool testing = false;
    String testStatus = "";

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          title: const Row(
            children: [
              Icon(Icons.cloud_sync_rounded, color: Color(0xFF2563EB)),
              SizedBox(width: 10),
              Text("ERP Server Endpoint", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                "Enter production or local server endpoint:",
                style: TextStyle(fontSize: 13),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: controller,
                decoration: InputDecoration(
                  labelText: "Server URL",
                  hintText: "https://qr-attendance-erp.onrender.com",
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                  prefixIcon: const Icon(Icons.link_rounded),
                ),
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                children: [
                  ActionChip(
                    avatar: const Icon(Icons.cloud_done, size: 14, color: Colors.green),
                    label: const Text("Render Cloud", style: TextStyle(fontSize: 11)),
                    onPressed: () {
                      controller.text = "https://qr-attendance-erp.onrender.com";
                    },
                  ),
                  ActionChip(
                    avatar: const Icon(Icons.wifi, size: 14, color: Colors.blue),
                    label: const Text("Local Wi-Fi", style: TextStyle(fontSize: 11)),
                    onPressed: () {
                      controller.text = "http://10.162.3.118:5001";
                    },
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  ElevatedButton.icon(
                    icon: testing
                        ? const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Icon(Icons.network_ping, size: 16),
                    label: const Text("Ping"),
                    onPressed: testing
                        ? null
                        : () async {
                            setDialogState(() {
                              testing = true;
                              testStatus = "Pinging...";
                            });
                            await ApiService().setServerUrl(controller.text);
                            final ok = await ApiService().checkHealth();
                            setDialogState(() {
                              testing = false;
                              testStatus = ok ? "✓ 200 OK" : "✗ Offline";
                            });
                            _checkServer();
                          },
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      testStatus,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: testStatus.startsWith("✓") ? Colors.green : Colors.red,
                      ),
                    ),
                  ),
                ],
              )
            ],
          ),
          actions: [
            TextButton(
              onPressed: () async {
                await ApiService().setServerUrl(controller.text);
                if (ctx.mounted) Navigator.pop(ctx);
                _checkServer();
              },
              child: const Text("Save & Apply"),
            ),
          ],
        ),
      ),
    );
  }

  Color _getRoleColor(String? role) {
    switch (role?.toLowerCase()) {
      case 'admin':
        return Colors.amber.shade700;
      case 'teacher':
        return Colors.blue.shade600;
      case 'student':
        return const Color(0xFF10B981);
      default:
        return Colors.indigo;
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

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final saved = ApiService().savedAccounts;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.circle,
                    size: 9,
                    color: _isServerOnline ? Colors.greenAccent : Colors.orangeAccent,
                  ),
                  const SizedBox(width: 6),
                  Text(
                    _isServerOnline ? "LIVE CLOUD" : "CONNECTING",
                    style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, letterSpacing: 0.5),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_ethernet_rounded),
            tooltip: "Server Config",
            onPressed: _showServerConfigDialog,
          ),
          IconButton(
            icon: Icon(isDark ? Icons.light_mode_rounded : Icons.dark_mode_rounded),
            tooltip: "Toggle Theme",
            onPressed: widget.onToggleTheme,
          ),
        ],
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 440),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                // Modern Hero Card with Gradient
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(22),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF1E3A8A), Color(0xFF2563EB), Color(0xFF4F46E5)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(24),
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0xFF2563EB).withValues(alpha: 0.35),
                        blurRadius: 20,
                        offset: const Offset(0, 10),
                      )
                    ],
                  ),
                  child: Column(
                    children: [
                      Container(
                        width: 84,
                        height: 84,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(22),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withValues(alpha: 0.35),
                              blurRadius: 18,
                              offset: const Offset(0, 8),
                            ),
                          ],
                        ),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(22),
                          child: Image.asset(
                            'assets/images/app_logo.png',
                            fit: BoxFit.cover,
                            errorBuilder: (ctx, err, stack) => const Icon(
                              Icons.qr_code_scanner_rounded,
                              size: 48,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        "VSGOI",
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 26,
                          fontWeight: FontWeight.w900,
                          color: Colors.white,
                          letterSpacing: 1.5,
                        ),
                      ),
                      const SizedBox(height: 2),
                      const Text(
                        "Dr. Virendra Swarup Memorial Trust GOI",
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 12.5,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                          letterSpacing: 0.2,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        "Smart Attendance ERP & Academic Portal",
                        style: TextStyle(
                          fontSize: 11,
                          color: Colors.white.withValues(alpha: 0.85),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 20),

                // Multi-Account Switcher Section (if user has previously logged in accounts)
                if (saved.isNotEmpty) ...[
                  Card(
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              const Row(
                                children: [
                                  Icon(Icons.switch_account_rounded, size: 18, color: Color(0xFF2563EB)),
                                  SizedBox(width: 8),
                                  Text(
                                    "SWITCH SAVED ACCOUNT",
                                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, letterSpacing: 0.5),
                                  ),
                                ],
                              ),
                              Text(
                                "${saved.length} Available",
                                style: const TextStyle(fontSize: 11, color: Colors.grey),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          ...saved.map((acc) {
                            final username = acc['username'] ?? '';
                            final role = acc['role'] ?? 'user';
                            final name = acc['display_name'] ?? username;
                            final roleColor = _getRoleColor(role);

                            return Container(
                              margin: const EdgeInsets.only(bottom: 8),
                              decoration: BoxDecoration(
                                color: Theme.of(context).colorScheme.surface,
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(color: Colors.grey.withValues(alpha: 0.2)),
                              ),
                              child: ListTile(
                                dense: true,
                                leading: CircleAvatar(
                                  backgroundColor: roleColor.withValues(alpha: 0.2),
                                  child: Icon(_getRoleIcon(role), color: roleColor, size: 18),
                                ),
                                title: Text(name, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                                subtitle: Text("@$username • ${role.toUpperCase()}", style: TextStyle(fontSize: 11, color: roleColor)),
                                trailing: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    IconButton(
                                      icon: const Icon(Icons.close, size: 16, color: Colors.grey),
                                      tooltip: "Remove",
                                      onPressed: () async {
                                        await ApiService().removeAccount(username);
                                        setState(() {});
                                      },
                                    ),
                                    ElevatedButton(
                                      style: ElevatedButton.styleFrom(
                                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                                        visualDensity: VisualDensity.compact,
                                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                                      ),
                                      onPressed: _isLoading ? null : () => _quickSwitchAccount(username),
                                      child: const Text("Enter", style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                                    ),
                                  ],
                                ),
                              ),
                            );
                          }),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  const Row(
                    children: [
                      Expanded(child: Divider()),
                      Padding(
                        padding: EdgeInsets.symmetric(horizontal: 12),
                        child: Text("OR SIGN IN WITH NEW ACCOUNT", style: TextStyle(fontSize: 11, color: Colors.grey, fontWeight: FontWeight.bold)),
                      ),
                      Expanded(child: Divider()),
                    ],
                  ),
                  const SizedBox(height: 16),
                ],

                // New Login Card
                Card(
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                  child: Padding(
                    padding: const EdgeInsets.all(22),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Text(
                          "Account Sign In",
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          "Access Admin, Faculty Scanner, or Student Portal",
                          style: TextStyle(fontSize: 12, color: Colors.grey),
                        ),
                        const SizedBox(height: 18),

                        if (_errorMessage != null) ...[
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.red.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(color: Colors.redAccent.withValues(alpha: 0.4)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.error_outline_rounded, color: Colors.red, size: 20),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    _errorMessage!,
                                    style: const TextStyle(color: Colors.red, fontSize: 13),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 16),
                        ],

                        // Identity Input
                        TextField(
                          controller: _usernameController,
                          decoration: InputDecoration(
                            labelText: "Username / Student ID / Email",
                            hintText: "e.g. admin, teacher, or student",
                            prefixIcon: const Icon(Icons.person_outline_rounded),
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
                          ),
                        ),
                        const SizedBox(height: 16),

                        // Password Input
                        TextField(
                          controller: _passwordController,
                          obscureText: _obscurePassword,
                          decoration: InputDecoration(
                            labelText: "Password",
                            hintText: "Enter password",
                            prefixIcon: const Icon(Icons.lock_outline_rounded),
                            suffixIcon: IconButton(
                              icon: Icon(_obscurePassword ? Icons.visibility_off_rounded : Icons.visibility_rounded),
                              onPressed: () {
                                setState(() {
                                  _obscurePassword = !_obscurePassword;
                                });
                              },
                            ),
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
                          ),
                        ),
                        const SizedBox(height: 22),

                        // Login Button
                        Container(
                          height: 50,
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(
                              colors: [Color(0xFF1E3A8A), Color(0xFF2563EB)],
                            ),
                            borderRadius: BorderRadius.circular(14),
                            boxShadow: [
                              BoxShadow(
                                color: const Color(0xFF2563EB).withValues(alpha: 0.3),
                                blurRadius: 10,
                                offset: const Offset(0, 4),
                              ),
                            ],
                          ),
                          child: ElevatedButton(
                            onPressed: _isLoading ? null : _handleLogin,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.transparent,
                              shadowColor: Colors.transparent,
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                            ),
                            child: _isLoading
                                ? const SizedBox(
                                    width: 22,
                                    height: 22,
                                    child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5),
                                  )
                                : const Row(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Icon(Icons.login_rounded, size: 20),
                                      SizedBox(width: 8),
                                      Text(
                                        "Sign In to ERP",
                                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                                      ),
                                    ],
                                  ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

                const SizedBox(height: 20),

                // Server status indicator pill
                InkWell(
                  onTap: _showServerConfigDialog,
                  borderRadius: BorderRadius.circular(20),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    decoration: BoxDecoration(
                      color: isDark ? Colors.white.withValues(alpha: 0.05) : Colors.black.withValues(alpha: 0.04),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: Colors.grey.withValues(alpha: 0.2)),
                    ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.cloud_done_rounded, size: 16, color: Color(0xFF2563EB)),
                          const SizedBox(width: 8),
                          Flexible(
                            child: Text(
                              "Server: ${ApiService().baseUrl.replaceAll('https://', '')}",
                              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const SizedBox(width: 6),
                          const Icon(Icons.edit_rounded, size: 14, color: Colors.grey),
                        ],
                      ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
