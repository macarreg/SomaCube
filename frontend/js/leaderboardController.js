import { SHAPE_IDS } from './constants.js';

const TOTAL = 'total';

function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function checkBadge() {
    const badge = el('span', 'badge-complete', '✓');
    badge.title = 'Found every solution';
    badge.setAttribute('role', 'img');
    badge.setAttribute('aria-label', 'Found every solution');
    return badge;
}

export class LeaderboardController {
    constructor(authController) {
        this.auth = authController;
        this.current = TOTAL;
        this.requestId = 0;

        this.app = document.querySelector('.app');
        this.view = document.getElementById('leaderboard-view');
        this.tabPuzzle = document.getElementById('tab-puzzle');
        this.tabBoard = document.getElementById('tab-leaderboard');
        this.select = document.getElementById('leaderboard-shape');
        this.refreshBtn = document.getElementById('leaderboard-refresh');
        this.meBox = document.getElementById('leaderboard-me');
        this.table = document.getElementById('leaderboard-table');
        this.note = document.getElementById('leaderboard-note');

        this._buildSelect();
        this._wire();
    }

    _buildSelect() {
        const total = el('option', '', 'Total (all figures)');
        total.value = TOTAL;
        this.select.appendChild(total);
        SHAPE_IDS.forEach(id => {
            const opt = el('option', '', id.charAt(0).toUpperCase() + id.slice(1));
            opt.value = id;
            this.select.appendChild(opt);
        });
        this.select.value = this.current;
    }

    _wire() {
        this.tabPuzzle.addEventListener('click', () => this.showView('puzzle'));
        this.tabBoard.addEventListener('click', () => this.showView('leaderboard'));
        this.select.addEventListener('change', () => {
            this.current = this.select.value;
            this.load();
        });
        this.refreshBtn.addEventListener('click', () => this.load());
        // Fired by AuthController after a username is saved.
        window.addEventListener('profile-changed', () => this.onAuthChange());
    }

    isOpen() {
        return !this.view.hidden;
    }

    onAuthChange() {
        if (this.isOpen()) this.load();
    }

    showView(name) {
        const board = name === 'leaderboard';
        this.app.classList.toggle('app--leaderboard', board);
        this.view.hidden = !board;
        this.tabPuzzle.setAttribute('aria-selected', String(!board));
        this.tabBoard.setAttribute('aria-selected', String(board));
        if (board) this.load();
    }

    async load() {
        const requestId = ++this.requestId;
        this.note.textContent = 'Loading…';

        const headers = {};
        const token = this.auth?.getAccessToken();
        if (token) headers.Authorization = `Bearer ${token}`;

        try {
            const res = await fetch(
                `/api/leaderboard?shape_id=${encodeURIComponent(this.current)}`,
                { headers }
            );
            if (requestId !== this.requestId) return;   // a newer request superseded this one
            if (res.status === 429) {
                this.note.textContent = 'Too many requests. Please wait a moment and refresh.';
                return;
            }
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            if (requestId !== this.requestId) return;
            this._render(data);
        } catch (err) {
            if (requestId !== this.requestId) return;
            console.error('Leaderboard load failed:', err);
            this.note.textContent = 'Could not load the leaderboard. Please try again.';
        }
    }

    _stat(label, value, complete = false) {
        const box = el('div', 'me-stat');
        box.appendChild(el('span', '', label));
        const strong = el('strong', '', String(value));
        if (complete) strong.appendChild(checkBadge());
        box.appendChild(strong);
        return box;
    }

    _renderMe(data, isTotal) {
        const me = data.me;
        this.meBox.replaceChildren();

        if (!me) {
            this.meBox.appendChild(el('p', 'me-hint', 'Log in to see how you compare.'));
            return;
        }

        this.meBox.appendChild(
            el('h2', 'me-title', me.username ? `Your progress (${me.username})` : 'Your progress')
        );

        const stats = el('div', 'me-stats');
        stats.appendChild(this._stat(
            'Rank',
            me.rank ? `#${me.rank} of ${data.ranked_players}` : 'Unranked'
        ));
        if (isTotal) {
            stats.appendChild(this._stat('Solutions', me.solutions));
            stats.appendChild(this._stat('Hints', me.hints));
            stats.appendChild(this._stat('Shapes completed', me.shapes_completed));
        } else {
            const of = data.total_solutions ?? '?';
            stats.appendChild(this._stat('Solutions', `${me.solutions} / ${of}`, me.complete));
            stats.appendChild(this._stat('Hints', me.hints));
        }
        this.meBox.appendChild(stats);

        if (!me.has_username) {
            this.meBox.appendChild(el('p', 'me-hint',
                'Choose a username (top right) to appear on the leaderboard.'));
        } else if (!me.rank) {
            this.meBox.appendChild(el('p', 'me-hint',
                isTotal ? 'Find a solution to get on the board.'
                        : 'Find a solution to this figure to get on the board.'));
        }
    }

    _render(data) {
        const isTotal = data.scope === 'total';
        this._renderMe(data, isTotal);

        const headers = ['#', 'Player', 'Solutions', 'Hints'];
        if (isTotal) headers.push('Shapes completed');

        const thead = el('thead');
        const headRow = el('tr');
        headers.forEach((text, i) => headRow.appendChild(el('th', i >= 2 ? 'col-num' : '', text)));
        thead.appendChild(headRow);

        const tbody = el('tbody');
        const addRow = (e) => {
            const tr = el('tr', e.is_me ? 'is-me' : '');
            tr.appendChild(el('td', '', String(e.rank)));
            tr.appendChild(el('td', '', e.username));
            const solved = el('td', 'col-num', String(e.solutions));
            if (!isTotal && e.complete) solved.appendChild(checkBadge());
            tr.appendChild(solved);
            tr.appendChild(el('td', 'col-num', String(e.hints)));
            if (isTotal) tr.appendChild(el('td', 'col-num', String(e.shapes_completed)));
            tbody.appendChild(tr);
        };
        const addMessage = (text) => {
            const tr = el('tr');
            const td = el('td', 'table-message', text);
            td.colSpan = headers.length;
            tr.appendChild(td);
            tbody.appendChild(tr);
        };

        if (data.entries.length === 0) {
            addMessage(isTotal ? 'No one has found a solution yet.'
                               : 'No one has found a solution to this figure yet.');
        } else {
            data.entries.forEach(addRow);
        }

        // Pin the viewer's row if they're ranked below the visible list.
        const me = data.me;
        if (me && me.rank && me.rank > data.entries.length) {
            addMessage('…');
            addRow({ ...me, is_me: true });
        }

        this.table.replaceChildren(thead, tbody);

        const rules = 'Ranked by solutions, then fewest hints, then whoever reached their count first.';
        if (!isTotal && data.total_solutions) {
            this.note.textContent = `${data.total_solutions} solutions exist for this figure. ${rules}`;
        } else if (!isTotal && data.total_solutions === 0) {
            this.note.textContent = 'This figure has no known solutions.';
        } else {
            this.note.textContent = rules;
        }
    }
}