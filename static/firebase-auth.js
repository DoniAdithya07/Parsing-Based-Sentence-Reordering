import { initializeApp, getApps } from "https://www.gstatic.com/firebasejs/10.13.2/firebase-app.js";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  signOut,
  onAuthStateChanged,
  setPersistence,
  browserLocalPersistence,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
} from "https://www.gstatic.com/firebasejs/10.13.2/firebase-auth.js";
import { getAnalytics, isSupported } from "https://www.gstatic.com/firebasejs/10.13.2/firebase-analytics.js";

let auth = null;
let isSigningIn = false;
let backendSessionEmail = "";

const REQUIRED_AUTH_CONFIG_FIELDS = ["apiKey", "authDomain", "projectId", "appId"];
const OPTIONAL_CONFIG_FIELDS = ["storageBucket", "messagingSenderId"];

function isValidAuthConfig(cfg) {
  if (!cfg) return false;
  const missingRequired = REQUIRED_AUTH_CONFIG_FIELDS.filter((field) => !cfg[field]);
  return missingRequired.length === 0;
}

function readFirebaseConfig() {
  const node = document.getElementById("firebase-config");

  if (node) {
    try {
      const cfg = JSON.parse(node.textContent || "{}");
      if (isValidAuthConfig(cfg)) {
        const missingOptional = OPTIONAL_CONFIG_FIELDS.filter((field) => !cfg[field]);
        if (missingOptional.length) {
          console.warn("Firebase optional config missing:", missingOptional.join(", "));
        }
        return cfg;
      }
      console.warn("Template Firebase config invalid.");
    } catch (error) {
      console.error("Failed to parse template Firebase config:", error);
    }
  }

  console.info("Firebase config not available. Auth will stay in guest mode.");
  return null;
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(body || {}),
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const errorMessage = payload && payload.error ? payload.error : `Request failed (${response.status})`;
    throw new Error(errorMessage);
  }
  return payload;
}

function ensureToastContainer() {
  let container = document.getElementById("toast-container");
  if (container) return container;

  container = document.createElement("div");
  container.id = "toast-container";
  container.className = "toast-container";
  document.body.appendChild(container);
  return container;
}

function showToast(message, type = "success") {
  const container = ensureToastContainer();
  const toast = document.createElement("div");
  toast.className = `toast toast-${type === "error" ? "error" : "success"}`;
  toast.textContent = message;
  container.appendChild(toast);

  requestAnimationFrame(() => {
    toast.classList.add("show");
  });

  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 220);
  }, 3200);
}

function getInitials(nameOrEmail) {
  const value = (nameOrEmail || "U").trim();
  if (!value) return "U";

  const words = value.split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return value.slice(0, 2).toUpperCase();
}

function setAuthButtonsState({ busy, text }) {
  const loginBtn = document.getElementById("login-btn");
  const emailLoginBtn = document.getElementById("email-login-btn");
  const emailRegisterBtn = document.getElementById("email-register-btn");

  const buttons = [loginBtn, emailLoginBtn, emailRegisterBtn].filter(Boolean);
  buttons.forEach((btn) => {
    btn.disabled = Boolean(busy);
    btn.classList.toggle("auth-disabled", Boolean(busy));
  });

  if (loginBtn) {
    if (!loginBtn.dataset.defaultText) {
      loginBtn.dataset.defaultText = loginBtn.textContent || "Login with Google";
    }
    loginBtn.textContent = text || loginBtn.dataset.defaultText;
  }
}

function ensureSessionMessage() {
  const authSection = document.querySelector(".auth-section");
  if (!authSection) return null;

  let note = document.getElementById("session-note");
  if (note) return note;

  note = document.createElement("small");
  note.id = "session-note";
  note.className = "session-note";
  note.textContent = "Session saved automatically";
  note.style.display = "none";
  authSection.appendChild(note);
  return note;
}

function setGuestMode(isGuest) {
  const form = document.getElementById("reorder-form");
  if (!form) return;

  const submitButtons = form.querySelectorAll('button[type="submit"]');
  submitButtons.forEach((button) => {
    button.disabled = false;
    button.classList.toggle("guest-mode-btn", isGuest);
  });

  const message = document.getElementById("auth-required-msg");
  if (message) {
    message.textContent = isGuest ? "Login is optional. Sign in to save personal history." : "";
    message.style.display = isGuest ? "block" : "none";
  }
}

function updateAuthUI(user) {
  const userInfo = document.getElementById("user-info");
  const loginBtn = document.getElementById("login-btn");
  const emailLoginBtn = document.getElementById("email-login-btn");
  const emailRegisterBtn = document.getElementById("email-register-btn");
  const logoutBtn = document.getElementById("logout-btn");
  const avatar = document.getElementById("user-avatar");
  const sessionNote = ensureSessionMessage();

  if (!userInfo || !loginBtn || !logoutBtn || !avatar) return;

  if (user) {
    const displayName = user.displayName || user.email || "User";
    userInfo.textContent = displayName;
    loginBtn.style.display = "none";
    if (emailLoginBtn) emailLoginBtn.style.display = "none";
    if (emailRegisterBtn) emailRegisterBtn.style.display = "none";
    logoutBtn.style.display = "inline-flex";

    avatar.title = `Logged in as: ${displayName}`;
    if (user.photoURL) {
      avatar.textContent = "";
      avatar.style.backgroundImage = `url('${user.photoURL}')`;
      avatar.classList.add("has-photo");
    } else {
      avatar.textContent = getInitials(displayName);
      avatar.style.backgroundImage = "none";
      avatar.classList.remove("has-photo");
    }

    if (sessionNote) sessionNote.style.display = "inline-block";
    setGuestMode(false);
    setAuthButtonsState({ busy: false });
  } else {
    userInfo.textContent = "";
    loginBtn.style.display = "inline-flex";
    if (emailLoginBtn) emailLoginBtn.style.display = "inline-flex";
    if (emailRegisterBtn) emailRegisterBtn.style.display = "inline-flex";
    logoutBtn.style.display = "none";
    avatar.textContent = "U";
    avatar.style.backgroundImage = "none";
    avatar.classList.remove("has-photo");
    avatar.title = "Guest user";

    if (sessionNote) sessionNote.style.display = "none";
    setGuestMode(true);
    setAuthButtonsState({ busy: false });
  }
}

function mapAuthErrorToMessage(error) {
  if (!error) return "Login failed";

  if (error.code === "auth/popup-blocked") return "Popup was blocked. Switched to redirect login.";
  if (error.code === "auth/popup-closed-by-user") return "Login popup was closed.";
  if (error.code === "auth/network-request-failed") return "Network error. Check internet and try again.";
  if (error.code === "auth/unauthorized-domain") return "This domain is not authorized in Firebase Auth settings.";
  if (error.code === "auth/operation-not-allowed") return "Enable Google and Email/Password sign-in in Firebase console.";
  if (error.code === "auth/invalid-api-key") return "Firebase API key is invalid.";
  if (error.code === "auth/invalid-email") return "Please enter a valid email address.";
  if (error.code === "auth/user-not-found") return "No account found for this email.";
  if (error.code === "auth/wrong-password") return "Incorrect password.";
  if (error.code === "auth/invalid-credential") return "Invalid email or password.";
  if (error.code === "auth/email-already-in-use") return "This email is already registered.";
  if (error.code === "auth/weak-password") return "Password is too weak (minimum 6 characters).";

  return error.message || "Login failed. Please try again.";
}

function shouldFallbackToRedirect(error) {
  return error && ["auth/popup-blocked", "auth/popup-closed-by-user", "auth/cancelled-popup-request"].includes(error.code);
}

function isBackendAuthOptionalError(error) {
  const message = String((error && error.message) || "").toLowerCase();
  return message.includes("firebase admin is not configured") || message.includes("firebase-admin is not installed");
}

function collectEmailPassword(modeLabel) {
  const email = window.prompt(`Enter email for ${modeLabel}:`, "") || "";
  if (!email.trim()) return null;

  const password = window.prompt(`Enter password for ${modeLabel}:`, "") || "";
  if (!password) return null;

  return { email: email.trim(), password };
}

async function signInWithGoogle() {
  if (!auth) {
    showToast("Google login is unavailable in this environment.");
    return;
  }
  if (isSigningIn) return;

  isSigningIn = true;
  setAuthButtonsState({ busy: true, text: "Signing in..." });

  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: "select_account" });

  try {
    await signInWithPopup(auth, provider);
  } catch (error) {
    console.error("Google sign-in failed:", error.code, error.message);

    if (shouldFallbackToRedirect(error)) {
      showToast("Popup blocked. Redirecting to Google sign-in...", "error");
      await signInWithRedirect(auth, provider);
      return;
    }

    showToast(mapAuthErrorToMessage(error), "error");
    setAuthButtonsState({ busy: false });
  } finally {
    isSigningIn = false;
  }
}

async function signInWithEmailPassword() {
  if (!auth) {
    showToast("Email login is unavailable in this environment.", "error");
    return;
  }
  if (isSigningIn) return;

  const creds = collectEmailPassword("login");
  if (!creds) return;

  isSigningIn = true;
  setAuthButtonsState({ busy: true, text: "Signing in..." });

  try {
    await signInWithEmailAndPassword(auth, creds.email, creds.password);
  } catch (error) {
    console.error("Email sign-in failed:", error.code, error.message);
    showToast(mapAuthErrorToMessage(error), "error");
    setAuthButtonsState({ busy: false });
  } finally {
    isSigningIn = false;
  }
}

async function registerWithEmailPassword() {
  if (!auth) {
    showToast("Email registration is unavailable in this environment.", "error");
    return;
  }
  if (isSigningIn) return;

  const creds = collectEmailPassword("registration");
  if (!creds) return;

  isSigningIn = true;
  setAuthButtonsState({ busy: true, text: "Creating account..." });

  try {
    await createUserWithEmailAndPassword(auth, creds.email, creds.password);
    showToast("Account created and signed in.", "success");
  } catch (error) {
    console.error("Email registration failed:", error.code, error.message);
    showToast(mapAuthErrorToMessage(error), "error");
    setAuthButtonsState({ busy: false });
  } finally {
    isSigningIn = false;
  }
}

async function logout() {
  if (!auth) return;

  const confirmed = window.confirm("Are you sure you want to logout?");
  if (!confirmed) return;

  try {
    await signOut(auth);
    await postJson("/api/auth/logout", {});
    backendSessionEmail = "";
    showToast("Logged out", "success");
  } catch (error) {
    console.error("Logout failed:", error);
    showToast("Logout failed", "error");
  }
}

async function initAnalytics(app) {
  try {
    const supported = await isSupported();
    if (supported) {
      getAnalytics(app);
      console.info("Firebase analytics initialized.");
    }
  } catch (error) {
    console.warn("Firebase analytics not initialized:", error);
  }
}

async function syncBackendSession(user) {
  const token = await user.getIdToken();
  const response = await postJson("/api/auth/firebase", { idToken: token });
  const email = response && response.user && response.user.email ? response.user.email : "";
  backendSessionEmail = String(email || "");
}

async function initFirebaseAuth() {
  const cfg = readFirebaseConfig();

  if (!cfg) {
    const loginBtn = document.getElementById("login-btn");
    const emailLoginBtn = document.getElementById("email-login-btn");
    const emailRegisterBtn = document.getElementById("email-register-btn");
    const logoutBtn = document.getElementById("logout-btn");
    const userInfo = document.getElementById("user-info");
    const avatar = document.getElementById("user-avatar");

    [loginBtn, emailLoginBtn, emailRegisterBtn].filter(Boolean).forEach((btn) => {
      btn.disabled = true;
      btn.classList.add("auth-disabled");
      btn.title = "Firebase auth is not configured";
    });

    if (loginBtn) loginBtn.textContent = "Guest Mode";
    if (logoutBtn) logoutBtn.style.display = "none";
    if (userInfo) userInfo.textContent = "Guest";
    if (avatar) {
      avatar.textContent = "U";
      avatar.style.backgroundImage = "none";
      avatar.classList.remove("has-photo");
      avatar.title = "Guest mode";
    }

    setGuestMode(true);
    return;
  }

  const app = getApps().length ? getApps()[0] : initializeApp(cfg);
  auth = getAuth(app);

  try {
    await setPersistence(auth, browserLocalPersistence);
  } catch (error) {
    console.warn("Could not set auth persistence:", error);
  }

  initAnalytics(app);

  try {
    const redirectResult = await getRedirectResult(auth);
    if (redirectResult && redirectResult.user) {
      showToast("Logged in successfully", "success");
    }
  } catch (error) {
    console.error("Redirect login result error:", error.code, error.message);
    showToast(mapAuthErrorToMessage(error), "error");
  }

  onAuthStateChanged(auth, async (user) => {
    if (user) {
      try {
        await syncBackendSession(user);
      } catch (error) {
        if (isBackendAuthOptionalError(error)) {
          console.warn("Backend Firebase admin is not configured. Continuing with client-side login only.");
        } else {
          console.error("Backend session sync failed:", error);
          showToast(error.message || "Failed to sync login state with server", "error");
        }
      }
    } else if (backendSessionEmail) {
      backendSessionEmail = "";
      try {
        await postJson("/api/auth/logout", {});
      } catch (_error) {
        // Ignore logout sync issues.
      }
    }

    updateAuthUI(user);
  });
}

window.signInWithGoogle = signInWithGoogle;
window.signInWithEmailPassword = signInWithEmailPassword;
window.registerWithEmailPassword = registerWithEmailPassword;
window.logout = logout;
window.showToast = showToast;

document.addEventListener("DOMContentLoaded", () => {
  initFirebaseAuth();
});
