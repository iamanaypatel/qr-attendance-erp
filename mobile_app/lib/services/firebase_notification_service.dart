import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:mobile_app/firebase_options.dart';

@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  if (kDebugMode) {
    print("FCM Background Message: ${message.messageId} - ${message.notification?.title}");
  }
}

class FirebaseNotificationService {
  static final FirebaseNotificationService _instance = FirebaseNotificationService._internal();
  factory FirebaseNotificationService() => _instance;
  FirebaseNotificationService._internal();

  bool _isInitialized = false;
  String? _fcmToken;

  String? get fcmToken => _fcmToken;
  bool get isInitialized => _isInitialized;

  Future<void> initialize() async {
    if (_isInitialized) return;

    try {
      await Firebase.initializeApp(
        options: DefaultFirebaseOptions.currentPlatform,
      );

      FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

      final messaging = FirebaseMessaging.instance;

      // Request notification permissions
      final settings = await messaging.requestPermission(
        alert: true,
        announcement: false,
        badge: true,
        carPlay: false,
        criticalAlert: false,
        provisional: false,
        sound: true,
      );

      if (kDebugMode) {
        print('User notification permission status: ${settings.authorizationStatus}');
      }

      // Fetch FCM Token
      try {
        _fcmToken = await messaging.getToken();
        if (kDebugMode) {
          print("Firebase FCM Token: $_fcmToken");
        }
      } catch (tokenErr) {
        if (kDebugMode) {
          print("Could not fetch FCM token: $tokenErr");
        }
      }

      // Listen to token refreshes
      messaging.onTokenRefresh.listen((newToken) {
        _fcmToken = newToken;
        if (kDebugMode) {
          print("FCM Token Refreshed: $newToken");
        }
      });

      // Handle foreground notifications
      FirebaseMessaging.onMessage.listen((RemoteMessage message) {
        if (kDebugMode) {
          print('Foreground notification received: ${message.notification?.title}');
        }
      });

      _isInitialized = true;
      if (kDebugMode) {
        print("Firebase successfully connected to project: erpvsgoi");
      }
    } catch (e) {
      if (kDebugMode) {
        print("Firebase initialization notice: $e");
      }
    }
  }
}
