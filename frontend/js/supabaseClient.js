let clientPromise = null;

export function getSupabaseClient() {
    if (!clientPromise) {
        clientPromise = fetch('/api/config')
            .then(res => {
                if (!res.ok) throw new Error(`/api/config returned ${res.status}`);
                return res.json();
            })
            .then(async ({ supabaseUrl, supabaseAnonKey }) => {
                if (!supabaseUrl || !supabaseAnonKey) {
                    throw new Error(
                        `Supabase not configured: supabaseUrl=${supabaseUrl}, supabaseAnonKey=${supabaseAnonKey ? '[set]' : '[missing]'}`
                    );
                }
                // Loaded lazily so a CDN failure only disables login,
                // not the whole app.
                const { createClient } = await import('@supabase/supabase-js');
                const client = createClient(supabaseUrl, supabaseAnonKey);
                if (!client) throw new Error('createClient() returned a falsy value');
                return client;
            })
            .catch(err => {
                console.error('getSupabaseClient failed:', err);
                clientPromise = null;
                throw err;
            });
    }
    return clientPromise;
}