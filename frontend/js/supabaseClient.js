import { createClient } from '@supabase/supabase-js';

let clientPromise = null;

export function getSupabaseClient() {
    if (!clientPromise) {
        clientPromise = fetch('/api/config')
            .then(res => {
                if (!res.ok) {
                    throw new Error(`/api/config returned ${res.status}`);
                }
                return res.json();
            })
            .then(({ supabaseUrl, supabaseAnonKey }) => {
                if (!supabaseUrl || !supabaseAnonKey) {
                    throw new Error(
                        `Supabase not configured: supabaseUrl=${supabaseUrl}, supabaseAnonKey=${supabaseAnonKey ? '[set]' : '[missing]'}`
                    );
                }
                const client = createClient(supabaseUrl, supabaseAnonKey);
                if (!client) {
                    throw new Error('createClient() returned a falsy value — check the @supabase/supabase-js import resolved correctly');
                }
                return client;
            })
            .catch(err => {
                console.error('getSupabaseClient failed:', err);
                clientPromise = null; // don't cache a permanent failure — let a retry try again
                throw err;
            });
    }
    return clientPromise;
}