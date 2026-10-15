import { getSupabaseClient } from './supabaseClient.js';

const BUTTON_COOLDOWN_MS = 30000;
const USERNAME_RE = /^[a-zA-Z0-9_]{3,20}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD_LENGTH = 6;   // keep in sync with Supabase > Auth > Password policy

// Where Supabase sends people after they click a link in a confirmation or
// password-reset email. This URL must be listed under Supabase > Authentication
// > URL Configuration > Redirect URLs, or Supabase silently falls back to the
// Site URL. The Flask app serves index.html at this path (see app.py).
const AUTH_REDIRECT_URL = `${window.location.origin}/auth/callback`;

// Supabase puts the outcome of an email link in the URL #fragment, e.g.
//   #access_token=...&type=recovery
//   #error=access_denied&error_code=otp_expired&error_description=...
// The client library strips the fragment while it initialises, so we read it
// first (this runs before the client exists).
function readAuthRedirect() {
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    return {
        isRecovery: params.get('type') === 'recovery',
        errorCode: params.get('error_code'),
    };
}

export class AuthController {
    constructor() {
        this.supabase = null;
        this.session = null;
        this.onChange = null;
        this.username = null;
        this.profileLoaded = false;
        this.redirect = readAuthRedirect();
    }

    async init(onChange) {
        this.onChange = onChange;
        this.supabase = await getSupabaseClient();

        // Register BEFORE getSession so PASSWORD_RECOVERY isn't missed.
        this.supabase.auth.onAuthStateChange(async (event, session) => {
            this.session = session;
            this._render();
            this._loadProfile();
            this.onChange?.();

            if (event === 'PASSWORD_RECOVERY') {
                const pw = window.prompt('Enter your new password (min 6 characters):');
                if (pw) {
                    const { error } = await this.supabase.auth.updateUser({ password: pw });
                    alert(error ? error.message : 'Password updated!');
                }
            }
        });

        const { data: { session } } = await this.supabase.auth.getSession();
        this.session = session;
        this._render();
        this._loadProfile();

        this._wireForm();
    }

    getAccessToken() {
        return this.session?.access_token || null;
    }

    // ---- small helpers ---------------------------------------------------

    _setStatus(text, tone = 'error') {
        const el = document.getElementById('auth-status');
        if (!el) return;
        el.dataset.tone = tone;
        el.textContent = text;
    }

    _toast(text) {
        window.uiController?.showMessage(text);
    }

    // Disables a button immediately (so a double-click can't fire a second
    // request) and re-enables it after BUTTON_COOLDOWN_MS.
    _startCooldown(button, ms = BUTTON_COOLDOWN_MS) {
        if (!button) return;
        button.disabled = true;
        setTimeout(() => { button.disabled = false; }, ms);
    }

    // Asks our own backend whether an account with this email exists, so a
    // failed login can say "no account" vs "wrong password". Returns
    // true/false, or null if it couldn't be determined; callers must treat
    // null as "unknown".
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

    // ---- password reset ---------------------------------------------------

    // Step 1: ask Supabase to email a reset link.
    async _sendResetEmail(email, button) {
        if (!EMAIL_RE.test(email)) {
            this._setStatus('Enter your email address above, then choose "Forgot password?".');
            return;
        }
        this._startCooldown(button);
        this._setStatus('Sending reset email…', 'info');

        // supabase-js reads `redirectTo` here. (`emailRedirectTo` is the name
        // used by signUp, and is silently ignored by resetPasswordForEmail.)
        const { error } = await this.supabase.auth.resetPasswordForEmail(email, {
            redirectTo: AUTH_REDIRECT_URL,
        });

        if (error) {
            console.error('resetPasswordForEmail failed:', error);
            if (error.status === 429 || error.code === 'over_email_send_rate_limit') {
                this._setStatus('Too many reset emails requested. Please wait a few minutes and try again.');
            } else {
                this._setStatus('We could not send the reset email. Please try again later.');
            }
            return;
        }
        // Supabase answers the same way whether or not the address has an
        // account, so say it the same way too.
        this._setStatus('If an account exists for that email, a reset link is on its way. Check your spam folder too.', 'ok');
    }

    // Step 2: the person clicked the link, so Supabase gave us a temporary
    // session. Ask for the new password in a dialog.
    _openResetDialog() {
        const dialog = document.getElementById('reset-dialog');
        if (!dialog || dialog.open) return;
        document.getElementById('reset-error').textContent = '';
        dialog.showModal();
        document.getElementById('reset-password')?.focus();
    }

    _wireResetDialog() {
        const dialog = document.getElementById('reset-dialog');
        const form = document.getElementById('reset-form');
        if (!dialog || !form) return;

        const password = document.getElementById('reset-password');
        const confirm = document.getElementById('reset-password-confirm');
        const errorEl = document.getElementById('reset-error');
        const submit = document.getElementById('reset-submit');
        const cancel = document.getElementById('reset-cancel');

        const close = () => { dialog.close(); form.reset(); errorEl.textContent = ''; };

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            errorEl.textContent = '';

            if (password.value.length < MIN_PASSWORD_LENGTH) {
                errorEl.textContent = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
                return;
            }
            if (password.value !== confirm.value) {
                errorEl.textContent = 'The two passwords do not match.';
                return;
            }

            submit.disabled = true;
            const { error } = await this.supabase.auth.updateUser({ password: password.value });
            submit.disabled = false;

            if (error) {
                errorEl.textContent = error.message;
                return;
            }
            close();
            this._toast('Password updated. You are logged in.');
        });

        cancel?.addEventListener('click', close);
    }

    // ---- forms --------------------------------------------------------------

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
        const forgotBtn = document.getElementById('auth-forgot');

        forgotBtn?.addEventListener('click', () => {
            this._sendResetEmail(emailInput.value.trim(), forgotBtn);
        });

        signupBtn?.addEventListener('click', async () => {
            this._setStatus('');

            // First click just reveals the username field.
            if (usernameInput.hidden) {
                usernameInput.hidden = false;
                usernameInput.focus();
                this._setStatus('Choose a username, then click Sign Up again.', 'info');
                return;
            }

            const username = usernameInput.value.trim();
            if (!USERNAME_RE.test(username)) {
                this._setStatus('Username must be 3–20 letters, numbers, or underscores.');
                return;
            }

            signupBtn.disabled = true;   // block double-clicks while we check
            const check = await this._checkUsernameAvailable(username);
            if (check.available !== true) {
                signupBtn.disabled = false;
                this._setStatus(check.message || 'That username is taken.');
                return;
            }

            this._startCooldown(signupBtn);   // cooldown starts only once we really sign up
            const email = emailInput.value.trim();

            // `emailRedirectTo` belongs inside `options` for signUp.
            const { data, error } = await this.supabase.auth.signUp({
                email,
                password: passwordInput.value,
                options: {
                    data: { username },
                    emailRedirectTo: AUTH_REDIRECT_URL,
                },
            });

            if (error) {
                this._setStatus(error.message);
            } else if (data?.user?.identities?.length === 0) {
                this._setStatus('This email is already registered. Try logging in instead.');
            } else {
                this._setStatus('Check your email to confirm your account.', 'ok');
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
            this._setStatus('');
            statusEl.replaceChildren();

            const email = emailInput.value.trim();
            const password = passwordInput.value;

            const { error } = await this.supabase.auth.signInWithPassword({ email, password });
            if (!error) {
                this._setStatus('');
                return; // onAuthStateChange handles re-rendering as logged in
            }

            // Supabase returns the same generic error for "no such email" and
            // "wrong password". We ask our backend which it was, which is a
            // deliberate trade-off (it reveals whether an email has an account).
            const exists = await this._checkEmailExists(email);

            if (exists === false) {
                this._setStatus('No account found with that email.');
            } else if (exists === true) {
                const msg = document.createTextNode('Incorrect password. ');
                const resetBtn = document.createElement('button');
                resetBtn.type = 'button';
                resetBtn.className = 'link-button';
                resetBtn.textContent = 'Send password reset email';
                resetBtn.addEventListener('click', () => this._sendResetEmail(email, resetBtn));
                statusEl.dataset.tone = 'error';
                statusEl.replaceChildren(msg, resetBtn);
            } else {
                // Couldn't tell; fall back to Supabase's own message. The
                // always-visible "Forgot password?" button still works.
                this._setStatus(error.message);
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

        // Toggle the `hidden` attribute (not inline display styles) so the
        // stylesheet's responsive layouts keep working.
        loggedOut.hidden = !!this.session;
        loggedIn.hidden = !this.session;

        if (this.session) {
            document.getElementById('auth-user-email').textContent = this.session.user.email;
            const u = document.getElementById('auth-username');
            if (u) { u.hidden = true; u.value = ''; }
        }
    }
}