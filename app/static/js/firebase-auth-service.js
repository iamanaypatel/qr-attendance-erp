// Firebase Authentication & Client Service for ERP
// Project: erpvsgoi | App ID: 1:574936907832:web:65332fbb59cd2d3dfae6cd

import { initializeApp, getApps, getApp } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js";
import {
  getAuth,
  signInWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut,
  onAuthStateChanged
} from "https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js";
import {
  getFirestore,
  doc,
  getDoc,
  setDoc,
  collection,
  query,
  getDocs
} from "https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyB7a8nt-kYYiT97sruPGD6-gCSErpRqTPg",
  authDomain: "erpvsgoi.firebaseapp.com",
  projectId: "erpvsgoi",
  storageBucket: "erpvsgoi.firebasestorage.app",
  messagingSenderId: "574936907832",
  appId: "1:574936907832:web:65332fbb59cd2d3dfae6cd",
  measurementId: "G-T4B0WJ3E7P"
};

const app = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: 'select_account' });

class FirebaseAuthService {
  constructor() {
    this.auth = auth;
    this.db = db;
  }

  // 1. Email & Password Sign In
  async signInWithEmail(email, password) {
    const userCredential = await signInWithEmailAndPassword(this.auth, email, password);
    const idToken = await userCredential.user.getIdToken();
    return this.syncWithBackend(idToken, userCredential.user);
  }

  // 2. Verified Google Sign-In
  async signInWithGoogle() {
    try {
      const result = await signInWithPopup(this.auth, googleProvider);
      const idToken = await result.user.getIdToken();
      return this.syncWithBackend(idToken, result.user);
    } catch (err) {
      if (err.code === 'auth/unauthorized-domain' || (err.message && err.message.includes('unauthorized-domain'))) {
        const host = window.location.hostname;
        const enhancedError = new Error(
          `Domain "${host}" is not in Firebase's Authorized Domains list for project 'erpvsgoi'. ` +
          `Please add "${host}" under Firebase Console > Authentication > Settings > Authorized domains.`
        );
        enhancedError.code = 'auth/unauthorized-domain';
        enhancedError.unauthorizedHost = host;
        throw enhancedError;
      }
      throw err;
    }
  }

  // 3. Synchronize Verified Google Token with Flask Backend
  async syncWithBackend(idToken, user) {
    const payload = {
      id_token: idToken,
      uid: user.uid,
      email: user.email || '',
      display_name: user.displayName || '',
      photo_url: user.photoURL || ''
    };

    const res = await fetch('/api/auth/google', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.message || 'Failed to authenticate session with ERP backend.');
    }

    return data;
  }

  // 4. Sign Out
  async signOutUser() {
    try {
      await signOut(this.auth);
    } catch (e) {
      console.warn("Firebase sign out warning:", e);
    }
  }
}

export const firebaseAuthService = new FirebaseAuthService();
window.FirebaseAuthService = firebaseAuthService;
