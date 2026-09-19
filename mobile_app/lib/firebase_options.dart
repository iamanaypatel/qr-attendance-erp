// File generated for Firebase project: erpvsgoi
import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kIsWeb, TargetPlatform;

/// Default [FirebaseOptions] for use with your Firebase apps.
///
/// Example:
/// ```dart
/// import 'firebase_options.dart';
/// // ...
/// await Firebase.initializeApp(
///   options: DefaultFirebaseOptions.currentPlatform,
/// );
/// ```
class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) {
      return web;
    }
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      case TargetPlatform.iOS:
        return ios;
      default:
        throw UnsupportedError(
          'DefaultFirebaseOptions are not supported for this platform.',
        );
    }
  }

  static const FirebaseOptions web = FirebaseOptions(
    apiKey: 'AIzaSyB7a8nt-kYYiT97sruPGD6-gCSErpRqTPg',
    appId: '1:574936907832:web:65332fbb59cd2d3dfae6cd',
    messagingSenderId: '574936907832',
    projectId: 'erpvsgoi',
    authDomain: 'erpvsgoi.firebaseapp.com',
    storageBucket: 'erpvsgoi.firebasestorage.app',
    measurementId: 'G-T4B0WJ3E7P',
  );

  static const FirebaseOptions android = FirebaseOptions(
    apiKey: 'AIzaSyB7a8nt-kYYiT97sruPGD6-gCSErpRqTPg',
    appId: '1:574936907832:android:65332fbb59cd2d3dfae6cd',
    messagingSenderId: '574936907832',
    projectId: 'erpvsgoi',
    storageBucket: 'erpvsgoi.firebasestorage.app',
  );

  static const FirebaseOptions ios = FirebaseOptions(
    apiKey: 'AIzaSyB7a8nt-kYYiT97sruPGD6-gCSErpRqTPg',
    appId: '1:574936907832:ios:65332fbb59cd2d3dfae6cd',
    messagingSenderId: '574936907832',
    projectId: 'erpvsgoi',
    storageBucket: 'erpvsgoi.firebasestorage.app',
  );
}
