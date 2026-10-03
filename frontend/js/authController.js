import { getSupabaseClient } from './supabaseClient.js';

const BUTTON_COOLDOWN_MS = 30000;

export class AuthController {
    constructor() {
        this.supabase = null;
        this.session = null;
        this.onChange = null;
    }

    async init(onChange) {
        this.onChange = onChange;
        this.supabase = await getSupabaseClient();

        const { data: { session } } = await this.supabase.auth.getSession();
        this.session = session;
        this._render();

        this.supabase.auth.onAuthStateChange((_event, session) => {
            this.session = session;
            this._render();
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

    _wireForm() {
        const emailInput = document.getElementById('auth-email');
        const passwordInput = document.getElementById('auth-password');
        const statusEl = document.getElementById('auth-status');
        const signupBtn = document.getElementById('auth-signup');
        const loginBtn = document.getElementById('auth-login');
        const logoutBtn = document.getElementById('auth-logout');

        signupBtn?.addEventListener('click', async () => {
            this._startCooldown(signupBtn);
            const email = emailInput.value.trim();

            const { data, error } = await this.supabase.auth.signUp({
                email, password: passwordInput.value,
            });

            if (error) {
                statusEl.textContent = error.message;
            } else if (data?.user?.identities?.length === 0) {
                // Supabase's anti-enumeration behavior: signing up with an
                // email that's already registered returns a success-shaped
                // response (no error) but sends no new confirmation email.
                // An empty identities array is the only way to tell — this
                // is what actually tells us "account already exists" without
                // needing our own backend/database check for signup.
                statusEl.textContent = 'This email is already registered — try logging in instead.';
            } else {
                statusEl.textContent = 'Check your email to confirm your account.';
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
        } else {
            loggedOut.style.display = 'flex';
            loggedIn.style.display = 'none';
        }
    }
}