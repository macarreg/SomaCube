import { getSupabaseClient } from './supabaseClient.js';

const BUTTON_COOLDOWN_MS = 30000;
const USERNAME_RE = /^[a-zA-Z0-9_]{3,20}$/;

export class AuthController {
    constructor() {
        this.supabase = null;
        this.session = null;
        this.onChange = null;
        this.username = null;
        this.profileLoaded = false;
    }

    async init(onChange) {
        this.onChange = onChange;
        this.supabase = await getSupabaseClient();

        const { data: { session } } = await this.supabase.auth.getSession();
        this.session = session;
        this._render();
        this._loadProfile();

        this.supabase.auth.onAuthStateChange((_event, session) => {
            this.session = session;
            this._render();
            this._loadProfile();      // intentionally not awaited
            this.onChange?.();
        });

        this._wireForm();
    }

    getAccessToken() {
        return this.session?.access_token || null;
    }

    // Disables a button immediately (so a double-click can't fire a second
    // request) and re-enables it after BUTTON_COOLDOWN_MS. This never delays
    // when a status message appears — that still happens as soon as the
    // network call resolves.
    _startCooldown(button, ms = BUTTON_COOLDOWN_MS) {
        if (!button) return;
        button.disabled = true;
        setTimeout(() => {
            button.disabled = false;
        }, ms);
    }

    // Asks our own backend (not Supabase directly) whether an account with
    // this email exists, so a failed login can say "no account" vs "wrong
    // password" instead of Supabase's deliberately generic error. Returns
    // true/false, or null if it couldn't be determined (backend not
    // configured, network error, rate-limited, etc.) — callers must treat
    // null as "unknown", never as a definitive answer.
    async _checkEmailExists(email) {
        try {
            const res = await fetch('/api/auth/check-email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            });
            if (!res.ok) return null;
            const data = await res.json();
            return typeof data.exists === 'boolean' ? data.exists : null;
        } catch {
            return null;
        }
    }

    async _checkUsernameAvailable(username) {
        try {
            const res = await fetch('/api/auth/check-username', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username }),
            });
            if (res.status === 429) return { available: null, message: 'Too many attempts. Please wait a moment.' };
            if (!res.ok) return { available: null, message: 'Could not check that username right now.' };
            return await res.json();
        } catch {
            return { available: null, message: 'Could not check that username right now.' };
        }
    }
    
    async _loadProfile() {
        this.username = null;
        this.profileLoaded = false;
        const token = this.getAccessToken();
        if (token) {
            try {
                const res = await fetch('/api/me', { headers: { Authorization: `Bearer ${token}` } });
                if (res.ok) {
                    this.username = (await res.json()).username || null;
                    this.profileLoaded = true;
                }
            } catch { /* leave profileLoaded false: don't show the prompt on a failed load */ }
        }
        this._renderUsername();
    }
    
    _renderUsername() {
        const label = document.getElementById('auth-user-email');
        const prompt = document.getElementById('auth-username-prompt');
        if (!label || !prompt) return;
        if (!this.session) { prompt.hidden = true; return; }
        label.textContent = this.username || this.session.user.email;
        prompt.hidden = !(this.profileLoaded && !this.username);
    }

    _wireForm() {
        const emailInput = document.getElementById('auth-email');
        const passwordInput = document.getElementById('auth-password');
        const usernameInput = document.getElementById('auth-username');
        const setUsernameInput = document.getElementById('auth-set-username');
        const setUsernameBtn = document.getElementById('auth-set-username-btn');
        const profileStatusEl = document.getElementById('auth-profile-status');
        const statusEl = document.getElementById('auth-status');
        const signupBtn = document.getElementById('auth-signup');
        const loginBtn = document.getElementById('auth-login');
        const logoutBtn = document.getElementById('auth-logout');

        signupBtn?.addEventListener('click', async () => {
            statusEl.textContent = '';
        
            // First click just reveals the username field.
            if (usernameInput.hidden) {
                usernameInput.hidden = false;
                usernameInput.focus();
                statusEl.textContent = 'Choose a username, then click Sign Up again.';
                return;
            }
        
            const username = usernameInput.value.trim();
            if (!USERNAME_RE.test(username)) {
                statusEl.textContent = 'Username must be 3–20 letters, numbers, or underscores.';
                return;
            }
        
            signupBtn.disabled = true;   // block double-clicks while we check
            const check = await this._checkUsernameAvailable(username);
            if (check.available !== true) {
                signupBtn.disabled = false;
                statusEl.textContent = check.message || 'That username is taken.';
                return;
            }
        
            this._startCooldown(signupBtn);   // cooldown starts only once we really sign up
            const email = emailInput.value.trim();
        
            const { data, error } = await this.supabase.auth.signUp({
                email,
                password: passwordInput.value,
                options: { data: { username } },
            });
        
            if (error) {
                statusEl.textContent = error.message;
            } else if (data?.user?.identities?.length === 0) {
                statusEl.textContent = 'This email is already registered. Try logging in instead.';
            } else {
                statusEl.textContent = 'Check your email to confirm your account.';
            }
        });

        setUsernameBtn?.addEventListener('click', async () => {
            const name = setUsernameInput.value.trim();
            profileStatusEl.textContent = '';
            if (!USERNAME_RE.test(name)) {
                profileStatusEl.textContent = 'Username must be 3–20 letters, numbers, or underscores.';
                return;
            }
            setUsernameBtn.disabled = true;
            try {
                const res = await fetch('/api/me/username', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        Authorization: `Bearer ${this.getAccessToken()}`,
                    },
                    body: JSON.stringify({ username: name }),
                });
                const body = await res.json().catch(() => ({}));
                if (res.ok) {
                    this.username = body.username;
                    this._renderUsername();
                    window.dispatchEvent(new Event('profile-changed'));
                } else {
                    profileStatusEl.textContent = body.message || 'Could not save username.';
                }
            } catch {
                profileStatusEl.textContent = 'Could not save username.';
            } finally {
                setUsernameBtn.disabled = false;
            }
        });

        loginBtn?.addEventListener('click', async () => {
            this._startCooldown(loginBtn);
            statusEl.textContent = '';
            statusEl.replaceChildren();

            const email = emailInput.value.trim();
            const password = passwordInput.value;

            const { error } = await this.supabase.auth.signInWithPassword({ email, password });
            if (!error) {
                statusEl.textContent = '';
                return; // onAuthStateChange handles re-rendering as logged in
            }

            // Supabase's signInWithPassword deliberately returns the same
            // generic error whether the email doesn't exist or the password
            // is wrong, to avoid revealing which emails have accounts. We
            // check separately to give a more specific message, which
            // reverses that protection — a deliberate choice made here, not
            // Supabase's default.
            const exists = await this._checkEmailExists(email);

            if (exists === false) {
                statusEl.textContent = 'No account found with that email.';
            } else if (exists === true) {
                const msg = document.createTextNode('Incorrect password. ');
                const resetBtn = document.createElement('button');
                resetBtn.type = 'button';
                resetBtn.textContent = 'Send password reset email';
                resetBtn.addEventListener('click', async () => {
                    this._startCooldown(resetBtn);
                    const { error: resetErr } = await this.supabase.auth.resetPasswordForEmail(email);
                    statusEl.textContent = resetErr ? resetErr.message : 'Password reset email sent — check your inbox.';
                });
                statusEl.replaceChildren(msg, resetBtn);
            } else {
                // Couldn't determine either way (service role key not
                // configured, network error, rate-limited) — fall back to
                // Supabase's own generic message rather than guessing.
                statusEl.textContent = error.message;
            }
        });

        logoutBtn?.addEventListener('click', async () => {
            this._startCooldown(logoutBtn);
            await this.supabase.auth.signOut();
        });
    }

    _render() {
        const loggedOut = document.getElementById('auth-logged-out');
        const loggedIn = document.getElementById('auth-logged-in');
        if (!loggedOut || !loggedIn) return;

        if (this.session) {
            loggedOut.style.display = 'none';
            loggedIn.style.display = 'flex';
            document.getElementById('auth-user-email').textContent = this.session.user.email;
            const u = document.getElementById('auth-username');
            if (u) { u.hidden = true; u.value = ''; }
        } else {
            loggedOut.style.display = 'flex';
            loggedIn.style.display = 'none';
        }
    }
}