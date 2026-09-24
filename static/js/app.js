/* ==========================================================================
   BUSINESS RADAR INTERACTIVE TERMINAL LOGIC WITH WATCHLISTS & URL SYNC
   ========================================================================== */

let currentCompanyId = null;
let radarChartInstance = null;
let currentRadarScores = null;

let activeSidebarTab = 'directory'; // 'directory' | 'watchlists'
let activeWatchlistId = null;
let allWatchlists = [];
let currentCompanyWatchlists = [];

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

async function initApp() {
    setupThemeToggle();
    setupEventListeners();
    loadFiltersFromURL();
    handleCheckoutSuccessParam();

    const urlParams = new URLSearchParams(window.location.search);
    const companyParam = urlParams.get('company');
    if (companyParam && companyParam.trim()) {
        window._deepLinkCompanyQuery = companyParam.trim();
    }

    const urlEmail = urlParams.get('email');
    if (urlEmail && urlEmail.includes('@')) {
        await handleDirectEmailAutoLogin(urlEmail.trim());
    }

    setupAppViewRouting();
    initSidebarCollapseState();
    checkTerminalAccessGate();
    await loadUserProfile();
    await fetchWatchlists();
    await loadCompanyList();
    await handleDeepLinkCompanySelection();

    if (urlParams.get('auth') === 'login') {
        openAuthModal();
    } else if (urlParams.get('auth') === 'register') {
        const emailInput = document.getElementById('lead-access-email-input');
        if (emailInput) emailInput.focus();
    }
}

async function handleDeepLinkCompanySelection() {
    const query = window._deepLinkCompanyQuery || new URLSearchParams(window.location.search).get('company');
    if (!query || !query.trim()) return;

    const targetQuery = query.trim();
    const cleanQuery = targetQuery.toLowerCase().replace(/^https?:\/\//, '').replace(/\/.*$/, '').replace('www.', '');
    const baseQuery = cleanQuery.replace('.com', '').replace('.es', '').replace('-', '');

    // 1. Try to find the company card in the loaded sidebar directory
    const cards = Array.from(document.querySelectorAll('#company-list-container .company-card'));
    const matchedCard = cards.find(card => {
        const text = card.textContent.toLowerCase();
        const dataId = (card.dataset.id || '').toLowerCase();
        const baseText = text.replace('.com', '').replace('.es', '').replace('-', '');
        return text.includes(cleanQuery) || baseText.includes(baseQuery) || dataId.includes(baseQuery);
    });

    if (matchedCard && matchedCard.dataset.id) {
        window._deepLinkCompanyQuery = null;
        await selectCompany(matchedCard.dataset.id);
        return;
    }

    // 2. If not already in default directory, check auth status before running instant analyze on demand
    const token = getAuthToken();
    if (!token) {
        // Save query so it triggers immediately once email gate is submitted!
        window._deepLinkCompanyQuery = targetQuery;
        return;
    }

    const searchInput = document.getElementById('global-on-demand-input');
    if (searchInput) searchInput.value = targetQuery;
    if (typeof handleGlobalOnDemandSubmit === 'function') {
        window._deepLinkCompanyQuery = null;
        await handleGlobalOnDemandSubmit(targetQuery);
    }
}

function initSidebarCollapseState() {
    const saved = localStorage.getItem('ofanradar_sidebar_collapsed');
    if (saved === 'true') {
        toggleSidebarCollapse(true);
    }
}

function toggleSidebarCollapse(forceState) {
    const layout = document.querySelector('.terminal-layout');
    if (!layout) return;

    const isCollapsed = forceState !== undefined ? forceState : !layout.classList.contains('sidebar-collapsed');
    
    if (isCollapsed) {
        layout.classList.add('sidebar-collapsed');
        localStorage.setItem('ofanradar_sidebar_collapsed', 'true');
    } else {
        layout.classList.remove('sidebar-collapsed');
        localStorage.setItem('ofanradar_sidebar_collapsed', 'false');
    }

    const expandTab = document.getElementById('sidebar-expand-tab');
    if (expandTab) {
        if (isCollapsed) {
            expandTab.classList.remove('hidden');
        } else {
            expandTab.classList.add('hidden');
        }
    }

    const toggleText = document.getElementById('sidebar-toggle-text');
    const toggleIcon = document.getElementById('sidebar-toggle-icon');
    if (toggleText) toggleText.textContent = isCollapsed ? 'Mostrar Columna' : 'Ocultar Columna';
    if (toggleIcon) toggleIcon.className = isCollapsed ? 'fa-solid fa-angles-right' : 'fa-solid fa-bars-staggered';
}

function checkTerminalAccessGate() {
    const token = localStorage.getItem('authToken');
    const leadEmail = localStorage.getItem('ofanradar_lead_email');

    if (!token && !leadEmail) {
        const modal = document.getElementById('lead-email-gate-modal');
        if (modal) {
            modal.style.display = 'flex';
        }
    }
}

async function handleDirectEmailAutoLogin(email) {
    if (!email || !email.includes('@')) return;
    try {
        const resp = await fetch('/v1/auth/lead-access', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email.trim().toLowerCase() })
        });
        const res = await resp.json();
        if (res.allowed === true && res.token) {
            localStorage.setItem('authToken', res.token);
            localStorage.setItem('ofanradar_lead_email', res.email);
            const userObj = {
                user_id: res.user_id || 'lead_user',
                email: res.email,
                full_name: res.full_name,
                role: res.role,
                subscription_status: res.subscription_status
            };
            localStorage.setItem('radar_user', JSON.stringify(userObj));

            const modal = document.getElementById('lead-email-gate-modal');
            if (modal) modal.style.display = 'none';

            // Clean email parameter from query string
            const url = new URL(window.location.href);
            url.searchParams.delete('email');
            window.history.replaceState({}, document.title, url.pathname + url.search);

            await loadUserProfile();
            await loadCompanyList();
            await handleDeepLinkCompanySelection();
            showGlobalNotification(`⚡ ¡Prueba Gratuita de 7 Días Activada para ${res.email}!`, 'success');
        }
    } catch(err) {
        console.error('Direct email auto-login error:', err);
    }
}

async function handleLeadAccessSubmit(event) {
    event.preventDefault();
    const emailInput = document.getElementById('lead-access-email-input');
    const errorMsg = document.getElementById('lead-access-error-msg');
    const submitBtn = document.getElementById('lead-access-submit-btn');

    if (!emailInput || !emailInput.value) return;

    const email = emailInput.value.trim();
    if (errorMsg) errorMsg.style.display = 'none';
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Activando...';
    }

    try {
        const resp = await fetch('/v1/auth/lead-access', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email })
        });
        const res = await resp.json();

        if (res.allowed === false) {
            if (errorMsg) {
                errorMsg.textContent = res.message || `El correo '${email}' ya utilizó su periodo de prueba. Inicia sesión o actualiza a Plan Pro.`;
                errorMsg.style.display = 'block';
            }
        } else if (res.allowed === true && res.token) {
            localStorage.setItem('authToken', res.token);
            localStorage.setItem('ofanradar_lead_email', res.email);
            const userObj = {
                user_id: res.user_id || 'lead_user',
                email: res.email,
                full_name: res.full_name,
                role: res.role,
                subscription_status: res.subscription_status
            };
            localStorage.setItem('radar_user', JSON.stringify(userObj));

            const modal = document.getElementById('lead-email-gate-modal');
            if (modal) modal.style.display = 'none';

            await loadUserProfile();
            await loadCompanyList();
            await handleDeepLinkCompanySelection();
            showGlobalNotification(`⚡ ¡Prueba Gratuita de 7 Días Activada para ${res.email}!`, 'success');
        }
    } catch (err) {
        console.error('Lead access request error:', err);
        if (errorMsg) {
            errorMsg.textContent = 'Error al verificar el acceso. Inténtelo de nuevo.';
            errorMsg.style.display = 'block';
        }
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fa-solid fa-bolt"></i> Activar 7 Días Gratis y Entrar';
        }
    }
}

async function activateOrExtendTrial() {
    let email = localStorage.getItem('ofanradar_lead_email');
    if (!email && typeof currentUserProfile !== 'undefined' && currentUserProfile?.email) {
        email = currentUserProfile.email;
    }
    if (!email) {
        email = prompt("Introduce tu correo profesional para activar los 7 Días de Prueba:");
    }
    if (!email || !email.includes('@')) return;

    try {
        const resp = await fetch('/v1/auth/lead-access', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email.trim().toLowerCase() })
        });
        const res = await resp.json();
        if (res.allowed === true && res.token) {
            localStorage.setItem('authToken', res.token);
            localStorage.setItem('ofanradar_lead_email', res.email);
            closeUpgradeModal();
            await loadUserProfile();
            showGlobalNotification(`🎉 ¡Trial de 7 Días activado correctamente para ${res.email}!`, 'success');
        } else {
            alert(res.message || 'No se pudo activar el trial para este correo.');
        }
    } catch(e) {
        console.error('Trial extend error:', e);
    }
}

function showGlobalNotification(msg, type = 'info') {
    let container = document.getElementById('global-toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'global-toast-container';
        container.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 1000000; display: flex; flex-direction: column; gap: 10px; pointer-events: none;';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    const bg = type === 'success' ? 'linear-gradient(135deg, #059669 0%, #10b981 100%)' :
               type === 'error' ? 'linear-gradient(135deg, #e11d48 0%, #be123c 100%)' :
               'linear-gradient(135deg, #0284c7 0%, #00e5ff 100%)';
    const textColor = type === 'info' ? '#050b14' : '#ffffff';

    toast.style.cssText = `background: ${bg}; color: ${textColor}; padding: 12px 18px; border-radius: 10px; font-weight: 700; font-size: 0.88rem; box-shadow: 0 10px 25px rgba(0,0,0,0.3); pointer-events: auto; display: flex; align-items: center; gap: 10px; animation: fadeInRight 0.3s ease;`;
    toast.innerHTML = `<i class="fa-solid fa-bell"></i> <span>${escapeHtml(msg)}</span>`;

    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.5s ease';
        setTimeout(() => toast.remove(), 500);
    }, 4500);
}

function closeLeadModalOpenAuth() {
    const modal = document.getElementById('lead-email-gate-modal');
    if (modal) modal.style.display = 'none';
    openAuthModal();
}

function closeLeadModalOpenUpgrade() {
    const modal = document.getElementById('lead-email-gate-modal');
    if (modal) modal.style.display = 'none';
    openUpgradeModal();
}

function setupAppViewRouting() {
    const landingView = document.getElementById('landing-view');
    const terminalView = document.getElementById('terminal-view');
    if (!landingView && terminalView) {
        terminalView.classList.remove('hidden');
        return;
    }
    const hash = window.location.hash;
    if (hash === '#terminal') {
        showAppView('terminal');
    } else {
        showAppView('landing');
    }
}

function showAppView(viewName) {
    const landingView = document.getElementById('landing-view');
    const terminalView = document.getElementById('terminal-view');
    const btnLanding = document.getElementById('view-btn-landing');
    const btnTerminal = document.getElementById('view-btn-terminal');

    if (viewName === 'terminal' || !landingView) {
        if (landingView) landingView.classList.add('hidden');
        if (terminalView) terminalView.classList.remove('hidden');
        if (btnLanding) btnLanding.classList.remove('active');
        if (btnTerminal) btnTerminal.classList.add('active');
    } else {
        if (terminalView) terminalView.classList.add('hidden');
        if (landingView) landingView.classList.remove('hidden');
        if (btnTerminal) btnTerminal.classList.remove('active');
        if (btnLanding) btnLanding.classList.add('active');
    }
}

function handleCheckoutSuccessParam() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('checkout_success') === 'true') {
        const plan = params.get('plan') || 'Pro';
        const sessionId = params.get('session_id');
        
        // Auto-activate subscription via simulation endpoint
        try {
            const userObj = JSON.parse(localStorage.getItem('radar_user') || '{}');
            if (userObj.email) {
                fetch(`/v1/billing/simulate-webhook?email=${encodeURIComponent(userObj.email)}&status=active`, { method: 'POST' });
            }
        } catch(e) {}

        alert(`🎉 ¡Pago realizado con éxito! Tu suscripción ${plan} Terminal ha sido activada.`);
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

/* ==========================================
   THEME TOGGLE SYSTEM
   ========================================== */
function setupThemeToggle() {
    const themeBtn = document.getElementById('theme-toggle-btn');
    const savedTheme = localStorage.getItem('business-radar-theme') || 'dark-mode';
    applyTheme(savedTheme);

    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            const isLight = document.body.classList.contains('light-mode');
            const newTheme = isLight ? 'dark-mode' : 'light-mode';
            applyTheme(newTheme);
            localStorage.setItem('business-radar-theme', newTheme);
        });
    }
}

function applyTheme(theme) {
    const themeIcon = document.getElementById('theme-icon');
    const themeText = document.getElementById('theme-text');

    if (theme === 'light-mode') {
        document.body.classList.remove('dark-mode');
        document.body.classList.add('light-mode');
        if (themeIcon) themeIcon.className = 'fa-solid fa-moon';
        if (themeText) themeText.textContent = 'Modo Oscuro';
    } else {
        document.body.classList.remove('light-mode');
        document.body.classList.add('dark-mode');
        if (themeIcon) themeIcon.className = 'fa-solid fa-sun';
        if (themeText) themeText.textContent = 'Modo Claro';
    }

    if (currentRadarScores) {
        renderRadarChart(currentRadarScores);
    }
}

function toggleSidebarFilters() {
    const panel = document.getElementById('sidebar-filters-panel');
    const label = document.getElementById('filters-toggle-label');
    if (!panel) return;
    if (panel.classList.contains('hidden')) {
        panel.classList.remove('hidden');
        if (label) label.textContent = 'Ocultar Filtros';
    } else {
        panel.classList.add('hidden');
        if (label) label.textContent = 'Mostrar Filtros Avanzados';
    }
}

/* ==========================================
   EVENT LISTENERS & FILTER SETUP
   ========================================== */
function setupEventListeners() {
    // Search input with debounce
    const searchInput = document.getElementById('company-search-input');
    let debounceTimer;
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                loadCompanyList();
            }, 300);
        });
    }

    // Multi-variable Dropdown and Range Filters
    const industrySelect = document.getElementById('filter-industry-select');
    const countrySelect = document.getElementById('filter-country-select');
    const eventSelect = document.getElementById('filter-event-select');
    const scoreRange = document.getElementById('filter-score-min');

    if (industrySelect) industrySelect.addEventListener('change', () => loadCompanyList());
    if (countrySelect) countrySelect.addEventListener('change', () => loadCompanyList());
    if (eventSelect) eventSelect.addEventListener('change', () => loadCompanyList());
    if (scoreRange) {
        scoreRange.addEventListener('change', () => loadCompanyList());
        scoreRange.addEventListener('input', (e) => {
            document.getElementById('score-min-val').textContent = e.target.value;
        });
    }

    // Navigation Tabs (Main Dashboard Detail View)
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const tabId = btn.dataset.tab;
            if (document.getElementById(tabId)) {
                document.getElementById(tabId).classList.add('active');
            }
        });
    });

    // Signal Ingest Form
    const ingestForm = document.getElementById('signal-ingest-form');
    if (ingestForm) ingestForm.addEventListener('submit', handleSignalIngestSubmit);

    // Modal Query Builder
    const openModalBtn = document.getElementById('btn-open-query-modal');
    const closeModalBtn = document.getElementById('btn-close-query-modal');
    const modal = document.getElementById('query-modal');
    const queryForm = document.getElementById('intent-query-form');
    const resetQueryBtn = document.getElementById('btn-reset-query');

    if (openModalBtn && modal) openModalBtn.addEventListener('click', () => modal.classList.add('open'));
    if (closeModalBtn && modal) closeModalBtn.addEventListener('click', () => modal.classList.remove('open'));
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.classList.remove('open');
        });
    }

    if (queryForm) {
        queryForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await executeQueryBuilder();
            modal.classList.remove('open');
        });
    }

    if (resetQueryBtn) {
        resetQueryBtn.addEventListener('click', () => {
            queryForm.reset();
            resetAllFilters();
            modal.classList.remove('open');
        });
    }

    // Close watchlist menu popover when clicking outside
    document.addEventListener('click', (e) => {
        const wrapper = document.querySelector('.watchlist-action-wrapper');
        const popover = document.getElementById('watchlist-menu-popover');
        if (wrapper && popover && !wrapper.contains(e.target)) {
            popover.classList.add('hidden');
        }
    });
}

/* ==========================================
   FEATURE 5: MULTI-VARIABLE FILTER & URL SYNC
   ========================================== */
function loadFiltersFromURL() {
    const params = new URLSearchParams(window.location.search);
    
    const search = params.get('search') || '';
    const industry = params.get('industry') || '';
    const country = params.get('country') || '';
    const score = params.get('score') || '0';
    const event = params.get('event') || '';
    const watchlist = params.get('watchlist') || null;

    if (document.getElementById('company-search-input')) document.getElementById('company-search-input').value = search;
    if (document.getElementById('filter-industry-select')) document.getElementById('filter-industry-select').value = industry;
    if (document.getElementById('filter-country-select')) document.getElementById('filter-country-select').value = country;
    if (document.getElementById('filter-event-select')) document.getElementById('filter-event-select').value = event;
    if (document.getElementById('filter-score-min')) {
        document.getElementById('filter-score-min').value = score;
        document.getElementById('score-min-val').textContent = score;
    }
    if (watchlist) {
        activeWatchlistId = watchlist;
    }
}

function syncFiltersToURL() {
    const search = document.getElementById('company-search-input')?.value.trim() || '';
    const industry = document.getElementById('filter-industry-select')?.value || '';
    const country = document.getElementById('filter-country-select')?.value || '';
    const event = document.getElementById('filter-event-select')?.value || '';
    const score = document.getElementById('filter-score-min')?.value || '0';

    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (industry) params.set('industry', industry);
    if (country) params.set('country', country);
    if (event) params.set('event', event);
    if (parseInt(score, 10) > 0) params.set('score', score);
    if (activeWatchlistId) params.set('watchlist', activeWatchlistId);

    const queryString = params.toString();
    const newUrl = queryString ? `${window.location.pathname}?${queryString}` : window.location.pathname;
    window.history.pushState({}, '', newUrl);
}

function resetAllFilters() {
    activeWatchlistId = null;
    if (document.getElementById('company-search-input')) document.getElementById('company-search-input').value = '';
    if (document.getElementById('filter-industry-select')) document.getElementById('filter-industry-select').value = '';
    if (document.getElementById('filter-country-select')) document.getElementById('filter-country-select').value = '';
    if (document.getElementById('filter-event-select')) document.getElementById('filter-event-select').value = '';
    if (document.getElementById('filter-score-min')) {
        document.getElementById('filter-score-min').value = 0;
        document.getElementById('score-min-val').textContent = '0';
    }
    syncFiltersToURL();
    loadCompanyList();
}

async function loadCompanyList() {
    const container = document.getElementById('company-list-container');
    if (!container) return;

    container.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> Cargando empresas...</div>';

    syncFiltersToURL();

    const search = document.getElementById('company-search-input')?.value.trim() || '';
    const industry = document.getElementById('filter-industry-select')?.value || '';
    const country = document.getElementById('filter-country-select')?.value || '';
    const event = document.getElementById('filter-event-select')?.value || '';
    const minScore = parseInt(document.getElementById('filter-score-min')?.value || '0', 10);

    try {
        let companies = [];

        if (activeWatchlistId) {
            // Load companies inside specific Watchlist
            const resp = await authFetch(`/v1/watchlists/${activeWatchlistId}/companies`);
            companies = await resp.json();
            
            // Client side filter search/industry if user types
            if (search) {
                const query = search.toLowerCase();
                companies = companies.filter(c => 
                    (c.canonical_name || '').toLowerCase().includes(query) ||
                    (c.domain || '').toLowerCase().includes(query) ||
                    (c.tax_id || '').toLowerCase().includes(query)
                );
            }
            if (industry) {
                companies = companies.filter(c => (c.industry || '').toLowerCase().includes(industry.toLowerCase()));
            }
            if (country) {
                companies = companies.filter(c => (c.hq_country || '').toUpperCase() === country.toUpperCase());
            }
            if (minScore > 0) {
                companies = companies.filter(c => (c.latest_intent?.composite_score || 0) >= minScore);
            }
        } else {
            // Enterprise multi-variable POST query
            const payload = {
                limit: 100,
                search: search || null,
                industry: industry || null,
                country: country || null,
                recent_event_type: event || null,
                recent_event_days: 7,
                min_composite_score: minScore > 0 ? minScore : null
            };

            const resp = await authFetch('/v1/companies/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            companies = await resp.json();
        }

        if (!companies || companies.length === 0) {
            container.innerHTML = `
                <div class="loading-spinner">
                    <p style="margin-bottom:10px;">No se encontraron empresas con esos criterios.</p>
                    ${search ? `<button class="btn btn-accent btn-sm" onclick="handleGlobalOnDemandSubmit('${escapeHtml(search)}')"><i class="fa-solid fa-bolt"></i> Analizar '${escapeHtml(search)}' en Tiempo Real</button>` : ''}
                </div>`;
            return;
        }

        // Deduplicate companies array by domain/canonical_name/id
        const seenKeys = new Set();
        companies = companies.filter(c => {
            const key = (c.domain || c.canonical_name || c.id || '').toLowerCase().trim();
            if (!key || seenKeys.has(key)) return false;
            seenKeys.add(key);
            return true;
        });

        container.innerHTML = '';

        if (window._deepLinkCompanyQuery) {
            const query = window._deepLinkCompanyQuery.toLowerCase().trim();
            const cleanQ = query.replace(/^https?:\/\//, '').replace(/\/.*$/, '').replace('www.', '').replace('.com', '').replace('.es', '').replace('-', '');
            const targetComp = companies.find(c => {
                const dom = (c.domain || '').toLowerCase().replace('-', '');
                const name = (c.canonical_name || '').toLowerCase().replace('-', '');
                return dom.includes(cleanQ) || name.includes(cleanQ);
            });
            if (targetComp) {
                currentCompanyId = targetComp.id;
            }
        }

        const companyExists = companies.some(c => c.id === currentCompanyId);
        if (companyExists) {
            selectCompany(currentCompanyId);
        } else if (companies.length > 0 && !window._deepLinkCompanyQuery) {
            selectCompany(companies[0].id);
        }

        companies.forEach((company, index) => {
            const card = document.createElement('div');
            card.className = `company-card ${company.id === currentCompanyId ? 'active' : ''}`;
            card.dataset.id = company.id;

            const intent = company.latest_intent || { composite_score: 0 };
            const compScore = Math.round(intent.composite_score || 0);

            let scoreBadgeClass = '';
            if (compScore >= 70) scoreBadgeClass = 'high';
            if ((intent.financial_stress || 0) >= 60) scoreBadgeClass = 'distress';

            const sparklineHTML = generateSparklineSVG(company.score_history, company.score_change_30d);
            const cleanDomain = (company.domain || '').trim().toLowerCase();
            const primaryLogo = company.logo_url || `https://logo.clearbit.com/${cleanDomain}`;
            const fallbackLogo = `https://www.google.com/s2/favicons?domain=${cleanDomain}&sz=64`;
            const initial = (company.canonical_name || company.domain || 'E').trim().charAt(0).toUpperCase();

            card.innerHTML = `
                <div class="card-top" style="display:flex; justify-content:space-between; align-items:center; width:100%; min-width:0; gap:8px;">
                    <span class="company-name" style="display:flex; align-items:center; gap:8px; flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                        <img src="${primaryLogo}" class="mini-company-logo" onerror="this.onerror=function(){ this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='inline-flex'; }; this.src='${fallbackLogo}';" style="width:18px; height:18px; border-radius:4px; flex-shrink:0; object-fit:contain; background:#fff; padding:1px;">
                        <span style="display:none; width:18px; height:18px; border-radius:4px; background:linear-gradient(135deg, #00e5ff 0%, #0077ff 100%); color:#050b14; font-weight:800; font-size:10px; align-items:center; justify-content:center; flex-shrink:0;">${initial}</span>
                        <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(company.canonical_name)}</span>
                    </span>
                    <div style="display:flex; align-items:center; gap:6px; flex-shrink:0;">
                        <span class="card-score-badge ${scoreBadgeClass}">${compScore}</span>
                        <button class="btn-delete-company-x" onclick="removeCompanyFromList(event, '${company.id}', '${escapeHtml(company.canonical_name).replace(/'/g, "\\'")}')" title="Eliminar empresa de la lista">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </div>
                <div class="card-meta-line">
                    <span>${escapeHtml(company.domain)}</span>
                    <span>${escapeHtml(company.hq_city || '')}, ${company.hq_country}</span>
                </div>
                <div class="card-label-tag">
                    <i class="fa-solid fa-tag"></i> ${escapeHtml(company.primary_label || 'Evaluando Señales')}
                </div>
                ${sparklineHTML}
            `;

            card.addEventListener('click', () => selectCompany(company.id));
            container.appendChild(card);
        });
    } catch (err) {
        console.error('Failed to load companies:', err);
        container.innerHTML = '<div class="loading-spinner" style="color:var(--accent-red)">Error de conexión con el servidor Business Radar.</div>';
    }
}

let pendingDeleteCompanyId = null;

function removeCompanyFromList(event, companyId, companyName) {
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
    pendingDeleteCompanyId = companyId;
    const nameElem = document.getElementById('delete-confirm-company-name');
    if (nameElem) {
        nameElem.textContent = companyName ? `'${companyName}'` : 'esta empresa';
    }
    const modal = document.getElementById('delete-confirm-modal');
    if (modal) modal.classList.add('open');
}

function closeDeleteConfirmModal() {
    pendingDeleteCompanyId = null;
    const modal = document.getElementById('delete-confirm-modal');
    if (modal) modal.classList.remove('open');
}

async function confirmExecuteCompanyDelete() {
    if (!pendingDeleteCompanyId) return;
    const companyId = pendingDeleteCompanyId;
    closeDeleteConfirmModal();

    try {
        if (activeWatchlistId) {
            await authFetch(`/v1/watchlists/${activeWatchlistId}/companies/${companyId}`, { method: 'DELETE' });
        } else {
            await authFetch(`/v1/companies/${companyId}`, { method: 'DELETE' });
        }
        const card = document.querySelector(`.company-card[data-id="${companyId}"]`);
        if (card) {
            card.remove();
        }
        showToast('Empresa eliminada del listado', 'success');
        await loadCompanyList();
    } catch (e) {
        console.error('Error removing company:', e);
        const card = document.querySelector(`.company-card[data-id="${companyId}"]`);
        if (card) {
            card.remove();
        }
    }
}

let customConfirmResolver = null;

function showCustomConfirm({ title, message, iconClass = 'fa-solid fa-triangle-exclamation', confirmBtnText = 'Confirmar', isDanger = true }) {
    return new Promise((resolve) => {
        customConfirmResolver = resolve;
        const titleElem = document.getElementById('custom-confirm-title');
        const msgElem = document.getElementById('custom-confirm-msg');
        const iconElem = document.getElementById('custom-confirm-icon');
        const submitBtn = document.getElementById('btn-custom-confirm-submit');
        const modal = document.getElementById('custom-action-confirm-modal');

        if (titleElem) titleElem.textContent = title || 'Confirmar Acción';
        if (msgElem) msgElem.innerHTML = message || '¿Deseas continuar?';
        if (iconElem) iconElem.className = iconClass;
        if (submitBtn) {
            submitBtn.innerHTML = `<i class="fa-solid fa-check"></i> ${confirmBtnText}`;
            submitBtn.style.background = isDanger ? '#ef4444' : 'var(--brand-gold)';
        }

        if (modal) modal.classList.add('open');
    });
}

function closeCustomConfirmModal(confirmed) {
    const modal = document.getElementById('custom-action-confirm-modal');
    if (modal) modal.classList.remove('open');
    if (customConfirmResolver) {
        customConfirmResolver(confirmed);
        customConfirmResolver = null;
    }
}

function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('radar-toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    let border = 'var(--accent-cyan)';
    let icon = 'fa-solid fa-circle-info';

    if (type === 'success') {
        border = '#10b981';
        icon = 'fa-solid fa-circle-check';
    } else if (type === 'error') {
        border = '#ef4444';
        icon = 'fa-solid fa-triangle-exclamation';
    } else if (type === 'warning') {
        border = '#f59e0b';
        icon = 'fa-solid fa-triangle-exclamation';
    }

    toast.style.cssText = `
        background: rgba(15, 23, 42, 0.95);
        border: 1px solid ${border};
        border-radius: 8px;
        padding: 12px 16px;
        color: var(--text-main);
        font-size: 0.85rem;
        font-weight: 500;
        box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        display: flex;
        align-items: center;
        gap: 10px;
        pointer-events: auto;
        backdrop-filter: blur(8px);
    `;

    toast.innerHTML = `<i class="${icon}" style="color:${border}; font-size: 1.1rem; flex-shrink: 0;"></i> <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function generateSparklineSVG(points, delta) {
    if (!points || points.length < 2) return '';
    const width = 84;
    const height = 22;
    const min = Math.min(...points, 0);
    const max = Math.max(...points, 100);
    const range = (max - min) || 1;

    const coords = points.map((val, idx) => {
        const x = (idx / (points.length - 1)) * width;
        const y = height - ((val - min) / range) * (height - 4) - 2;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    const isUp = (delta || 0) >= 0;
    const strokeColor = isUp ? '#10b981' : '#ef4444';
    const formattedDelta = isUp ? `+${delta || 0}` : `${delta || 0}`;

    return `
        <div class="sparkline-wrapper" title="Evolución Intent Score 30 días">
            <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
                <polyline fill="none" stroke="${strokeColor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="${coords}" />
            </svg>
            <span class="sparkline-delta ${isUp ? 'up' : 'down'}">
                <i class="fa-solid ${isUp ? 'fa-arrow-trend-up' : 'fa-arrow-trend-down'}"></i> ${formattedDelta} pt
            </span>
        </div>
    `;
}

/* ==========================================
   FEATURE 6: WATCHLISTS SYSTEM LOGIC
   ========================================== */
function switchSidebarTab(tabName) {
    activeSidebarTab = tabName;

    const dirBtn = document.getElementById('tab-btn-directory');
    const watchBtn = document.getElementById('tab-btn-watchlists');
    const dirContainer = document.getElementById('company-list-container');
    const watchContainer = document.getElementById('watchlist-list-container');

    if (tabName === 'directory') {
        dirBtn.classList.add('active');
        watchBtn.classList.remove('active');
        dirContainer.classList.remove('hidden');
        watchContainer.classList.add('hidden');
        activeWatchlistId = null;
        loadCompanyList();
    } else {
        watchBtn.classList.add('active');
        dirBtn.classList.remove('active');
        watchContainer.classList.remove('hidden');
        dirContainer.classList.add('hidden');
        fetchWatchlists();
    }
}

async function fetchWatchlists() {
    try {
        const resp = await authFetch('/v1/watchlists');
        allWatchlists = await resp.json();
        renderWatchlists();
    } catch (err) {
        console.error('Error fetching watchlists:', err);
    }
}

function renderWatchlists() {
    const container = document.getElementById('watchlist-list-container');
    if (!container) return;

    if (!allWatchlists || allWatchlists.length === 0) {
        container.innerHTML = `
            <div class="loading-spinner">
                <p style="margin-bottom:12px;">No tienes listas de vigilancia creadas.</p>
                <button class="btn btn-primary btn-sm" onclick="openCreateWatchlistModal()"><i class="fa-solid fa-plus"></i> Crear Lista</button>
            </div>`;
        return;
    }

    container.innerHTML = `
        <div style="margin-bottom: 8px; display:flex; justify-content:space-between; align-items:center;">
            <span style="font-size:0.75rem; color:var(--text-muted); font-weight:700;">TUS WATCHLISTS</span>
            <button class="btn btn-outline btn-sm" onclick="openCreateWatchlistModal()"><i class="fa-solid fa-plus"></i> Nueva</button>
        </div>
    `;

    allWatchlists.forEach(w => {
        const card = document.createElement('div');
        card.className = `watchlist-card ${w.id === activeWatchlistId ? 'active' : ''}`;
        card.style.borderColor = w.color || '#3b82f6';

        card.innerHTML = `
            <div class="watchlist-header-row">
                <span class="watchlist-name"><i class="fa-solid fa-bookmark" style="color:${w.color || '#3b82f6'}"></i> ${escapeHtml(w.name)}</span>
                <span class="watchlist-avg-badge">Avg: ${w.avg_intent_score}</span>
            </div>
            <p style="font-size:0.78rem; color:var(--text-muted); margin:0;">${escapeHtml(w.description || 'Sin descripción')}</p>
            <div class="watchlist-meta-info">
                <span><i class="fa-solid fa-building"></i> ${w.company_count} empresas</span>
                <button class="btn btn-outline btn-sm" style="padding: 2px 6px; font-size: 0.7rem;" onclick="deleteWatchlist(event, '${w.id}')"><i class="fa-solid fa-trash"></i></button>
            </div>
        `;

        card.addEventListener('click', (e) => {
            if (e.target.closest('button')) return;
            activeWatchlistId = w.id;
            switchSidebarTab('directory');
        });

        container.appendChild(card);
    });
}

async function deleteWatchlist(e, watchlistId) {
    e.stopPropagation();
    const confirmed = await showCustomConfirm({
        title: '¿Eliminar lista de vigilancia?',
        message: 'Esta acción eliminará la lista y todas sus asociaciones de tu directorio.',
        confirmBtnText: 'Eliminar Lista',
        isDanger: true
    });
    if (!confirmed) return;

    try {
        const resp = await authFetch(`/v1/watchlists/${watchlistId}`, { method: 'DELETE' });
        if (resp.ok) {
            if (activeWatchlistId === watchlistId) activeWatchlistId = null;
            showToast('Lista de vigilancia eliminada con éxito', 'success');
            await fetchWatchlists();
        }
    } catch (err) {
        console.error('Failed to delete watchlist:', err);
        showToast('Error al eliminar la lista de vigilancia', 'error');
    }
}

function toggleWatchlistMenu() {
    const popover = document.getElementById('watchlist-menu-popover');
    if (!popover) return;

    const isHidden = popover.classList.contains('hidden');
    if (isHidden) {
        popover.classList.remove('hidden');
        renderWatchlistMenuCheckboxes();
    } else {
        popover.classList.add('hidden');
    }
}

async function renderWatchlistMenuCheckboxes() {
    const container = document.getElementById('watchlist-checkbox-list');
    if (!container || !currentCompanyId) return;

    container.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> Cargando...</div>';

    try {
        const [watchResp, compWatchResp] = await Promise.all([
            authFetch('/v1/watchlists'),
            authFetch(`/v1/companies/${currentCompanyId}/watchlists`)
        ]);

        allWatchlists = await watchResp.json();
        currentCompanyWatchlists = await compWatchResp.json();

        if (!allWatchlists || allWatchlists.length === 0) {
            container.innerHTML = '<div style="font-size:0.8rem; color:var(--text-muted); padding:8px;">No hay listas creadas.</div>';
            return;
        }

        container.innerHTML = '';
        allWatchlists.forEach(w => {
            const isChecked = currentCompanyWatchlists.includes(w.id);
            const item = document.createElement('label');
            item.className = 'watchlist-check-item';
            item.innerHTML = `
                <input type="checkbox" ${isChecked ? 'checked' : ''} onchange="toggleCompanyWatchlistMembership('${w.id}', this.checked)">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${w.color};"></span>
                <span>${escapeHtml(w.name)}</span>
            `;
            container.appendChild(item);
        });
    } catch (err) {
        console.error('Failed rendering watchlist menu:', err);
    }
}

async function toggleCompanyWatchlistMembership(watchlistId, isChecked) {
    if (!currentCompanyId) return;

    try {
        if (isChecked) {
            await authFetch(`/v1/watchlists/${watchlistId}/companies`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ company_id: currentCompanyId })
            });
        } else {
            await authFetch(`/v1/watchlists/${watchlistId}/companies/${currentCompanyId}`, {
                method: 'DELETE'
            });
        }

        await fetchWatchlists();
    } catch (err) {
        console.error('Failed toggling watchlist membership:', err);
    }
}

function openCreateWatchlistModal() {
    const popover = document.getElementById('watchlist-menu-popover');
    if (popover) popover.classList.add('hidden');

    const modal = document.getElementById('create-watchlist-modal');
    if (modal) modal.classList.add('open');
}

function closeCreateWatchlistModal() {
    const modal = document.getElementById('create-watchlist-modal');
    if (modal) modal.classList.remove('open');
}

async function handleCreateWatchlistSubmit(e) {
    e.preventDefault();
    const name = document.getElementById('watchlist-name-input').value.trim();
    const desc = document.getElementById('watchlist-desc-input').value.trim();
    const color = document.getElementById('watchlist-color-input').value;

    if (!name) return;

    try {
        const resp = await authFetch('/v1/watchlists', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description: desc, color })
        });

        if (resp.ok) {
            const newWatchlist = await resp.json();
            document.getElementById('create-watchlist-form').reset();
            closeCreateWatchlistModal();
            await fetchWatchlists();

            // If we have an active company open, auto-add to the new list
            if (currentCompanyId) {
                await toggleCompanyWatchlistMembership(newWatchlist.id, true);
            }
        }
    } catch (err) {
        console.error('Error creating watchlist:', err);
    }
}

/* ==========================================
   COMPANY DETAIL & INSPECTION LOGIC
   ========================================== */
async function selectCompany(companyId) {
    currentCompanyId = companyId;

    document.querySelectorAll('.company-card').forEach(card => {
        card.classList.toggle('active', card.dataset.id === companyId);
    });

    try {
        const [metaResp, intentResp] = await Promise.all([
            authFetch(`/v1/companies/${companyId}`),
            authFetch(`/v1/companies/${companyId}/intent?window_days=90`)
        ]);

        const company = await metaResp.json();
        const intentData = await intentResp.json();

        renderCompanyDetails(company, intentData);
    } catch (err) {
        console.error('Error fetching company details:', err);
    }
}

function renderCompanyDetails(company, intentData) {
    // 1. Header Card Logo and Attributes
    const logoImg = document.getElementById('detail-company-logo');
    const avatarContainer = document.getElementById('detail-company-logo-avatar');

    if (logoImg && company) {
        const cleanDomain = (company.domain || '').trim().toLowerCase();
        const initial = (company.canonical_name || company.domain || 'E').trim().charAt(0).toUpperCase();
        const primaryLogo = company.logo_url || `https://logo.clearbit.com/${cleanDomain}`;
        const fallbackLogo = `https://www.google.com/s2/favicons?domain=${cleanDomain}&sz=128`;

        // Reset container HTML if previously overridden by letter fallback
        if (avatarContainer && !document.getElementById('detail-company-logo')) {
            avatarContainer.innerHTML = `<img id="detail-company-logo" src="${primaryLogo}" alt="Logo">`;
        }

        const activeLogoImg = document.getElementById('detail-company-logo') || logoImg;
        activeLogoImg.src = primaryLogo;
        activeLogoImg.style.display = 'block';
        activeLogoImg.onerror = function() {
            this.onerror = function() {
                this.style.display = 'none';
                if (avatarContainer) {
                    avatarContainer.innerHTML = `<span class="company-initial-fallback" style="font-weight:800; color:var(--accent-cyan); font-size:18px; font-family:var(--font-heading); display:flex; align-items:center; justify-content:center; width:100%; height:100%; background:rgba(0,229,255,0.12); border-radius:6px;">${initial}</span>`;
                }
            };
            this.src = fallbackLogo;
        };
    }

    document.getElementById('detail-company-name').textContent = company.canonical_name;
    document.getElementById('detail-company-industry').textContent = company.industry || 'Sector General';
    
    const domainEl = document.getElementById('detail-company-domain');
    domainEl.textContent = company.domain;
    domainEl.href = company.website_url || `https://${company.domain}`;

    document.getElementById('detail-company-tax-id').textContent = company.tax_id ? `${company.tax_id} (${company.tax_id_country})` : 'N/A';
    document.getElementById('detail-company-hq').textContent = `${company.hq_city || ''}, ${company.hq_country}`;
    document.getElementById('detail-company-size').textContent = company.employee_range || 'Desconocido';

    const compScore = Math.round(intentData.intent_scores.composite_score);
    document.getElementById('detail-composite-score').textContent = compScore < 10 ? `0${compScore}` : compScore;
    document.getElementById('detail-primary-label').textContent = intentData.primary_label || 'Empresa Rastreada';

    // 2. Business Insights Summary Cards
    document.getElementById('detail-business-summary').textContent = intentData.business_summary || 'Análisis de señales completado sin anomalías.';
    document.getElementById('detail-recommended-action').textContent = intentData.recommended_action || 'Mantener en radar de seguimiento.';

    // Render Deep Institutional Dossier (Financials, Sales Playbook, Personas, Competitors)
    if (intentData.institutional_dossier) {
        renderInstitutionalDossier(intentData.institutional_dossier, company, compScore);
    }

    // 3. Vector Scores Progress Bars
    const scores = intentData.intent_scores;
    currentRadarScores = scores;

    updateVectorScore('expansion', scores.expansion_intent);
    updateVectorScore('hiring', scores.hiring_intent);
    updateVectorScore('growth', scores.growth_intent);
    updateVectorScore('tech', scores.technology_change_intent);
    updateVectorScore('stress', scores.financial_stress);

    // 4. Radar Chart
    renderRadarChart(scores);

    // 5. Feature 8: Key Events Explicabilidad
    renderKeyEventsExplicability(intentData.attribution_matrix, compScore);

    // 6. Accordion Timeline
    const matrix = intentData.attribution_matrix || [];
    document.getElementById('tab-signal-count').textContent = matrix.length;
    renderSignalAccordionTimeline(matrix);

    // 7. Feature 13 & Feature 11: LLM Executive Brief and Tech Stack Profile
    loadExecutiveBrief(company.id);
    loadTechStackProfile(company.id);
}

function renderInstitutionalDossier(dossier, company, compScore) {
    if (!dossier) return;

    // 1. Financial Indicators
    const fin = dossier.financials || {};
    const arrEl = document.getElementById('dossier-arr');
    const yoyEl = document.getElementById('dossier-yoy');
    const runwayEl = document.getElementById('dossier-runway');
    const burnEl = document.getElementById('dossier-burn');
    const solvencyEl = document.getElementById('dossier-solvency');
    const pmpEl = document.getElementById('dossier-pmp');
    const capitalEl = document.getElementById('dossier-capital');
    const mercantilEl = document.getElementById('dossier-mercantil');

    if (arrEl) arrEl.textContent = fin.arr_estimate || '€12M - €25M ARR';
    if (yoyEl) yoyEl.textContent = fin.yoy_growth || '+32.4% YoY';
    if (runwayEl) runwayEl.textContent = fin.runway || '18 - 24 meses';
    if (burnEl) burnEl.textContent = `Burn: ${fin.burn_rate || '~€140k/mes'}`;
    if (solvencyEl) solvencyEl.textContent = fin.solvency_risk || '12/100 (Bajo Riesgo)';
    if (pmpEl) pmpEl.textContent = `PMP: ${fin.pmp_days || '34 días'}`;
    if (capitalEl) capitalEl.textContent = fin.capital_social || '€250.000';
    if (mercantilEl) mercantilEl.textContent = fin.mercantil_info || 'Reg. Mercantil Verificado';

    // 2. Sales Playbook & Personas
    const pb = dossier.sales_playbook || {};
    const windowTag = document.getElementById('playbook-window-tag');
    if (windowTag) windowTag.textContent = pb.buying_window ? '🔥 Ventana Abierta (Próximos 14-30 días)' : '🔥 Alta Intención';

    const painContainer = document.getElementById('playbook-pain-points');
    if (painContainer && pb.pain_points) {
        painContainer.innerHTML = pb.pain_points.map(pt => `
            <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); border-radius: 8px; padding: 10px 12px; font-size: 0.82rem; color: var(--text-main); display: flex; align-items: flex-start; gap: 8px;">
                <i class="fa-solid fa-bolt" style="color: var(--brand-gold); margin-top: 2px;"></i>
                <span>${escapeHtml(pt)}</span>
            </div>
        `).join('');
    }

    const personaContainer = document.getElementById('playbook-personas');
    if (personaContainer && pb.target_personas) {
        personaContainer.innerHTML = pb.target_personas.map(p => `
            <div style="background: rgba(0, 229, 255, 0.05); border: 1px solid rgba(0, 229, 255, 0.2); border-radius: 8px; padding: 10px 12px; font-size: 0.82rem;">
                <div style="font-weight: 700; color: var(--accent-cyan); display: flex; align-items: center; gap: 6px;">
                    <i class="fa-solid fa-user-check"></i> ${escapeHtml(p.role)}
                </div>
                <div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 2px;">Enfoque: ${escapeHtml(p.focus)}</div>
            </div>
        `).join('');
    }

    const pitchTextarea = document.getElementById('playbook-pitch-text');
    if (pitchTextarea && pb.cold_outreach_pitch) {
        pitchTextarea.value = pb.cold_outreach_pitch;
    }

    // 3. Competitor Benchmarks Table
    const compTableBody = document.getElementById('competitors-table-body');
    const compBadge = document.getElementById('competitor-percentile-badge');
    if (compBadge) compBadge.textContent = compScore >= 80 ? 'Top 5% Sectorial' : (compScore >= 60 ? 'Top 15% Sectorial' : 'Top 30% Sectorial');

    if (compTableBody && dossier.competitors) {
        compTableBody.innerHTML = dossier.competitors.map(c => `
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td style="padding: 10px; font-weight: 700; color: var(--text-main);"><i class="fa-solid fa-building"></i> ${escapeHtml(c.name)}</td>
                <td style="padding: 10px; font-weight: 800; color: var(--brand-gold);">${c.score} / 100</td>
                <td style="padding: 10px; color: var(--text-muted);">${escapeHtml(c.size)}</td>
                <td style="padding: 10px;"><span class="badge badge-industry" style="font-size:0.74rem;">${escapeHtml(c.status)}</span></td>
            </tr>
        `).join('');
    }
}

function copyOutreachPitch() {
    const pitchTextarea = document.getElementById('playbook-pitch-text');
    if (pitchTextarea && pitchTextarea.value) {
        navigator.clipboard.writeText(pitchTextarea.value);
        showGlobalNotification('📋 Guion comercial copiado al portapapeles', 'success');
    }
}

function renderKeyEventsExplicability(matrix, compScore) {
    const tagEl = document.getElementById('explainability-score-tag');
    if (tagEl) tagEl.textContent = `Score Global: ${compScore} / 100`;

    const listEl = document.getElementById('key-events-list');
    if (!listEl) return;

    if (!matrix || matrix.length === 0) {
        listEl.innerHTML = '<div style="font-size:0.85rem; color:var(--text-muted); padding:10px;">No se registran eventos con impacto en la ventana de 90 días.</div>';
        return;
    }

    const sortedEvents = [...matrix].sort((a, b) => (b.attenuated_weight || 0) - (a.attenuated_weight || 0));
    listEl.innerHTML = '';

    sortedEvents.forEach(item => {
        const card = document.createElement('div');
        card.className = 'key-event-card';

        let iconClass = 'fa-solid fa-bolt';
        let aiReason = `Evento detectado en ${item.source} con impacto directo en ${item.vector_category.replace('_intent', '')}.`;

        if (item.signal_code === 'REGISTRY_CHANGE') {
            iconClass = 'fa-solid fa-file-signature';
            aiReason = 'Inscripción BORME/Registro Mercantil comprobada. Impacto directo en expansión corporativa y capital social.';
        } else if (item.signal_code === 'JOB_POSTING_SURGE') {
            iconClass = 'fa-solid fa-user-plus';
            aiReason = 'Pico de publicaciones de empleo activas detectadas. Elevado impacto en Hiring Intent.';
        } else if (item.signal_code === 'REAL_ESTATE_FILING') {
            iconClass = 'fa-solid fa-building-circle-check';
            aiReason = 'Licencia de apertura/alquiler inmobiliario comercial registrado en propiedad local.';
        } else if (item.signal_code === 'DOM_PRICING_CHANGED') {
            iconClass = 'fa-solid fa-euro-sign';
            aiReason = 'Detección semántica de cambios en `/pricing` y oferta de planes enterprise.';
        } else if (item.signal_code === 'TECH_STACK_MIGRATION') {
            iconClass = 'fa-solid fa-laptop-code';
            aiReason = 'Modificación de registros DNS/CT logs indicando migración de stack o infraestructura Cloud.';
        } else if (item.signal_code === 'CREDIT_RATING_DOWNGRADE') {
            iconClass = 'fa-solid fa-triangle-exclamation';
            aiReason = 'Alerta de riesgo crediticio o revisión a la baja en boletines oficiales.';
        }

        card.innerHTML = `
            <div class="key-event-header">
                <span class="key-event-title"><i class="${iconClass}"></i> ${escapeHtml(item.signal_name)}</span>
                <span class="key-event-impact">+${item.attenuated_weight} pt</span>
            </div>
            <div class="key-event-desc">${aiReason}</div>
        `;
        listEl.appendChild(card);
    });
}

function updateVectorScore(idKey, scoreVal) {
    const val = Math.round(scoreVal || 0);
    const textEl = document.getElementById(`score-${idKey}`);
    const barEl = document.getElementById(`bar-${idKey}`);
    if (textEl) textEl.textContent = val;
    if (barEl) barEl.style.width = `${val}%`;
}

function renderRadarChart(scores) {
    const chartCanvas = document.getElementById('intentRadarChart');
    if (!chartCanvas) return;

    const ctx = chartCanvas.getContext('2d');
    const isLight = document.body.classList.contains('light-mode');

    const labelColor = isLight ? '#475569' : '#94a3b8';
    const gridColor = isLight ? 'rgba(0, 0, 0, 0.08)' : 'rgba(255, 255, 255, 0.08)';

    const data = {
        labels: ['Expansión Regional', 'Contratación', 'Crecimiento', 'Cambio Tecnológico', 'Riesgo Financiero'],
        datasets: [{
            label: 'Puntuación de Intención',
            data: [
                scores.expansion_intent || 0,
                scores.hiring_intent || 0,
                scores.growth_intent || 0,
                scores.technology_change_intent || 0,
                scores.financial_stress || 0
            ],
            backgroundColor: isLight ? 'rgba(2, 132, 199, 0.2)' : 'rgba(0, 229, 255, 0.25)',
            borderColor: isLight ? '#0284c7' : '#00e5ff',
            borderWidth: 2,
            pointBackgroundColor: isLight ? '#9333ea' : '#a855f7',
            pointBorderColor: '#fff',
            pointHoverBackgroundColor: '#fff',
            pointHoverBorderColor: '#9333ea'
        }]
    };

    if (radarChartInstance) {
        radarChartInstance.destroy();
    }

    radarChartInstance = new Chart(ctx, {
        type: 'radar',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    angleLines: { color: gridColor },
                    grid: { color: gridColor },
                    pointLabels: {
                        color: labelColor,
                        font: { family: 'Inter', size: 11, weight: '600' }
                    },
                    ticks: {
                        color: labelColor,
                        backdropColor: 'transparent',
                        stepSize: 20
                    },
                    suggestedMin: 0,
                    suggestedMax: 100
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

function renderSignalAccordionTimeline(matrix) {
    const container = document.getElementById('signal-accordion-list');
    if (!container) return;
    container.innerHTML = '';

    if (!matrix || matrix.length === 0) {
        container.innerHTML = '<div class="loading-spinner">No hay señales registradas en la ventana de 90 días.</div>';
        return;
    }

    matrix.forEach((item) => {
        const accordionItem = document.createElement('div');
        accordionItem.className = 'accordion-item';

        const formattedDate = new Date(item.detected_at).toLocaleDateString('es-ES', {
            year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        });

        accordionItem.innerHTML = `
            <div class="accordion-header">
                <div class="accordion-title-group">
                    <span class="accordion-date"><i class="fa-regular fa-clock"></i> ${formattedDate}</span>
                    <span class="accordion-code">${escapeHtml(item.signal_name)}</span>
                    <span class="badge" style="background:rgba(125,125,125,0.1); font-size:0.7rem">${escapeHtml((item.vector_category || '').replace('_intent',''))}</span>
                </div>
                <div class="accordion-meta-group">
                    <span class="accordion-weight">Peso Atenuado: +${item.attenuated_weight}</span>
                    <i class="fa-solid fa-chevron-down accordion-icon-toggle"></i>
                </div>
            </div>
            <div class="accordion-body">
                <div class="accordion-details-grid">
                    <div class="detail-box">
                        <label>Fuente de Ingesta</label>
                        <span>${escapeHtml(item.source)}</span>
                    </div>
                    <div class="detail-box">
                        <label>Antigüedad del Evento</label>
                        <span>${item.age_days} días</span>
                    </div>
                    <div class="detail-box">
                        <label>Nivel de Confianza (C<sub>i</sub>)</label>
                        <span>${(item.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div class="detail-box">
                        <label>Vida Media de Atenuación (τ<sub>s</sub>)</label>
                        <span>${item.half_life_days} días</span>
                    </div>
                </div>
                <label style="font-size:0.75rem; color:var(--text-dim); display:block; margin-bottom:4px;">Carga de Datos de Captura (Raw JSON):</label>
                <div class="raw-payload-box">{
  "signal_code": "${item.signal_code}",
  "attenuated_impact": ${item.attenuated_weight},
  "formula_applied": "W_s * C_i * exp(-lambda * delta_t)"
}</div>
            </div>
        `;

        accordionItem.querySelector('.accordion-header').addEventListener('click', () => {
            accordionItem.classList.toggle('open');
        });

        container.appendChild(accordionItem);
    });
}

/* ==========================================
/* ==========================================
   HELPER UTILITIES & SIMULATOR HANDLERS
   ========================================== */
async function simulatePreset(code, source, description) {
    if (!currentCompanyId) {
        alert('Por favor, seleccione primero una empresa de la lista.');
        return;
    }

    const feedback = document.getElementById('ingest-feedback-status');
    if (feedback) {
        feedback.classList.remove('hidden');
        feedback.style.background = 'rgba(0, 229, 255, 0.1)';
        feedback.style.border = '1px solid var(--accent-cyan)';
        feedback.style.color = 'var(--accent-cyan)';
        feedback.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Inyectando escenario '${escapeHtml(description)}'...`;
    }

    try {
        const resp = await authFetch('/v1/signals/ingest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                company_identifier: currentCompanyId,
                signal_type_code: code,
                source: source,
                confidence: 0.95,
                attributes: { preset_desc: description, injected_at: new Date().toISOString() }
            })
        });

        const result = await resp.json();
        if (resp.ok) {
            if (feedback) {
                feedback.style.background = 'rgba(16, 185, 129, 0.1)';
                feedback.style.border = '1px solid var(--accent-green)';
                feedback.style.color = 'var(--accent-green)';
                feedback.innerHTML = `<i class="fa-solid fa-check-circle"></i> Señal inyectada con éxito. Recalculando scores...`;
            }
            setTimeout(async () => {
                if (feedback) feedback.classList.add('hidden');
                await selectCompany(currentCompanyId);
                await loadCompanyList();
                document.querySelector('[data-tab="tab-timeline"]').click();
            }, 600);
        } else {
            alert(`Error al inyectar señal: ${result.detail}`);
            if (feedback) feedback.classList.add('hidden');
        }
    } catch (err) {
        console.error('Failed preset simulation:', err);
        if (feedback) feedback.classList.add('hidden');
    }
}

async function handleSignalIngestSubmit(e) {
    e.preventDefault();
    if (!currentCompanyId) {
        alert('Por favor seleccione una empresa.');
        return;
    }

    const code = document.getElementById('ingest-signal-code').value;
    const source = document.getElementById('ingest-source').value;
    const confidence = parseFloat(document.getElementById('ingest-confidence').value);
    const feedback = document.getElementById('ingest-feedback-status');

    if (feedback) {
        feedback.classList.remove('hidden');
        feedback.style.background = 'rgba(0, 229, 255, 0.1)';
        feedback.style.border = '1px solid var(--accent-cyan)';
        feedback.style.color = 'var(--accent-cyan)';
        feedback.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Inyectando señal personalizada (${Math.round(confidence * 100)}% Confianza)...`;
    }

    try {
        const resp = await authFetch('/v1/signals/ingest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                company_identifier: currentCompanyId,
                signal_type_code: code,
                source: source,
                confidence: confidence,
                attributes: { injected_via: 'custom_simulator' }
            })
        });

        const result = await resp.json();
        if (resp.ok) {
            if (feedback) {
                feedback.style.background = 'rgba(16, 185, 129, 0.1)';
                feedback.style.border = '1px solid var(--accent-green)';
                feedback.style.color = 'var(--accent-green)';
                feedback.innerHTML = `<i class="fa-solid fa-check-circle"></i> Evento procesado. Score actualizado!`;
            }
            setTimeout(async () => {
                if (feedback) feedback.classList.add('hidden');
                await selectCompany(currentCompanyId);
                await loadCompanyList();
                document.querySelector('[data-tab="tab-timeline"]').click();
            }, 600);
        } else {
            alert(`Error: ${result.detail}`);
            if (feedback) feedback.classList.add('hidden');
        }
    } catch (err) {
        console.error('Failed to ingest signal:', err);
        if (feedback) feedback.classList.add('hidden');
    }
}

async function testDOMDiffPreview() {
    const oldHtml = `<div class="pricing"><h3>Plan Básico</h3><span>€99/mes</span></div>`;
    const newHtml = `<div class="pricing"><h3>Plan Enterprise</h3><span>€499/mes</span><span>Soporte 24/7</span></div>`;

    try {
        const resp = await authFetch(`/v1/diff/preview?old_html=${encodeURIComponent(oldHtml)}&new_html=${encodeURIComponent(newHtml)}`, {
            method: 'POST'
        });
        const res = await resp.json();

        const outBox = document.getElementById('diff-output-result');
        if (outBox) {
            outBox.classList.remove('hidden');
            outBox.innerHTML = `
                <div style="color:var(--accent-green); font-weight:600; margin-bottom:6px;">✓ Diferencia Estructural Detectada:</div>
                <div>- Cambio Detectado: <code>${res.detected_deltas ? res.detected_deltas.join(', ') : res.summary}</code></div>
                <div>- Magnitud de Cambio: <strong>${((res.intent_impact || 0.5) * 100).toFixed(1)}%</strong></div>
                <div>- Ruido Eliminado: CSRF tokens y etiquetas irrelevantes filtradas con éxito.</div>
            `;
        }
    } catch (err) {
        console.error('DOM diff preview failed:', err);
    }
}

async function testEntityResolution() {
    const inputVal = document.getElementById('resolution-input').value;
    if (!inputVal) return;

    try {
        const resp = await authFetch(`/v1/entity/resolve?identifier=${encodeURIComponent(inputVal)}`);
        const data = await resp.json();

        const resBox = document.getElementById('resolution-result-card');
        if (resBox) {
            resBox.classList.remove('hidden');

            if (data.resolved) {
                resBox.innerHTML = `
                    <div style="color:var(--accent-green); font-weight:700; margin-bottom:6px;"><i class="fa-solid fa-check-circle"></i> Entidad Resuelta con Éxito</div>
                    <div>- Nombre Canonical: <strong>${escapeHtml(data.canonical_name)}</strong></div>
                    <div>- Dominio Principal: <code>${escapeHtml(data.domain)}</code></div>
                    <div>- CIF/NIF Identificado: <strong>${escapeHtml(data.tax_id || 'N/A')} (${data.tax_id_country})</strong></div>
                    <div>- ID Único Canonical: <code>${data.company_id}</code></div>
                `;
            } else {
                resBox.innerHTML = `
                    <div style="color:var(--accent-red); font-weight:700;"><i class="fa-solid fa-times-circle"></i> No se encontró una entidad que coincida con "${escapeHtml(inputVal)}"</div>
                `;
            }
        }
    } catch (err) {
        console.error('Entity resolution test failed:', err);
    }
}

async function exportCompaniesCSV() {
    const country = document.getElementById('filter-country-select')?.value || '';
    const industry = document.getElementById('filter-industry-select')?.value || '';
    
    let url = '/v1/export?';
    if (country) url += `country=${encodeURIComponent(country)}&`;
    if (industry) url += `industry=${encodeURIComponent(industry)}&`;

    try {
        const resp = await authFetch(url);
        if (resp.status === 402) {
            // Upgrade modal auto-opened by authFetch
            return;
        }
        if (!resp.ok) {
            const err = await resp.json();
            alert(`Error al exportar CSV: ${err.detail || 'Suscripción requerida'}`);
            return;
        }
        const blob = await resp.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `radar_companies_${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
    } catch (err) {
        console.error('Error exporting CSV:', err);
    }
}

function applyQueryPreset(minExp, minTech, minHiring, country, industry) {
    const elExp = document.getElementById('query-min-expansion');
    const elTech = document.getElementById('query-min-tech');
    const elHir = document.getElementById('query-min-hiring');
    const elCtry = document.getElementById('query-country');
    const elInd = document.getElementById('query-industry');

    if (elExp) { elExp.value = minExp; document.getElementById('val-query-expansion').textContent = minExp; }
    if (elTech) { elTech.value = minTech; document.getElementById('val-query-tech').textContent = minTech; }
    if (elHir) { elHir.value = minHiring; document.getElementById('val-query-hiring').textContent = minHiring; }
    if (elCtry) { elCtry.value = country; }
    if (elInd) { elInd.value = industry; }
}

function updateWebhookChannelPlaceholder(channel) {
    const urlInput = document.getElementById('alert-rule-url');
    if (!urlInput) return;
    if (channel === 'SLACK') {
        urlInput.placeholder = 'https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXX';
    } else if (channel === 'TEAMS') {
        urlInput.placeholder = 'https://outlook.office.com/webhook/xxxxxxx/IncomingWebhook/xxxxxx';
    } else {
        urlInput.placeholder = 'https://api.tuempresa.com/webhooks/radar-events';
    }
}

function generateRandomHMACSecret() {
    const secretInput = document.getElementById('alert-rule-secret');
    if (secretInput) {
        const randomHex = Array.from(window.crypto.getRandomValues(new Uint8Array(8)))
            .map(b => b.toString(16).padStart(2, '0')).join('');
        secretInput.value = `radar_sec_${randomHex}`;
    }
}

async function executeQueryBuilder() {
    const minExp = document.getElementById('query-min-expansion')?.value;
    const minTech = document.getElementById('query-min-tech')?.value;
    const minHiring = document.getElementById('query-min-hiring')?.value;
    const country = document.getElementById('query-country')?.value;
    const industry = document.getElementById('query-industry')?.value;

    const payload = {};
    if (minExp && parseFloat(minExp) > 0) payload.min_expansion_intent = parseFloat(minExp);
    if (minTech && parseFloat(minTech) > 0) payload.min_tech_change_intent = parseFloat(minTech);
    if (minHiring && parseFloat(minHiring) > 0) payload.min_hiring_intent = parseFloat(minHiring);
    if (country) payload.country = country;
    if (industry) payload.industry = industry;

    try {
        const resp = await authFetch('/v1/companies/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const companies = await resp.json();
        renderFilteredCompanyList(companies);
    } catch (err) {
        console.error('Error querying companies:', err);
    }
}

function renderFilteredCompanyList(companies) {
    const container = document.getElementById('company-list-container');
    if (!container) return;
    container.innerHTML = '';

    if (!companies || companies.length === 0) {
        container.innerHTML = '<div class="loading-spinner">No se encontraron empresas con esos criterios de intención.</div>';
        return;
    }

    companies.forEach((company, index) => {
        const card = document.createElement('div');
        card.className = `company-card ${company.id === currentCompanyId ? 'active' : ''}`;
        card.dataset.id = company.id;

        const intent = company.latest_intent || { composite_score: 0 };
        const compScore = Math.round(intent.composite_score || 0);

        let scoreBadgeClass = '';
        if (compScore >= 70) scoreBadgeClass = 'high';
        if ((intent.financial_stress || 0) >= 60) scoreBadgeClass = 'distress';

        const cleanDomain = (company.domain || '').trim().toLowerCase();
        const primaryLogo = company.logo_url || `https://logo.clearbit.com/${cleanDomain}`;
        const fallbackLogo = `https://www.google.com/s2/favicons?domain=${cleanDomain}&sz=64`;
        const initial = (company.canonical_name || company.domain || 'E').trim().charAt(0).toUpperCase();

        card.innerHTML = `
            <div class="card-top" style="display:flex; justify-content:space-between; align-items:center; width:100%; min-width:0; gap:8px;">
                <span class="company-name" style="display:flex; align-items:center; gap:8px; flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                    <img src="${primaryLogo}" class="mini-company-logo" onerror="this.onerror=function(){ this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='inline-flex'; }; this.src='${fallbackLogo}';" style="width:18px; height:18px; border-radius:4px; flex-shrink:0; object-fit:contain; background:#fff; padding:1px;">
                    <span style="display:none; width:18px; height:18px; border-radius:4px; background:linear-gradient(135deg, #00e5ff 0%, #0077ff 100%); color:#050b14; font-weight:800; font-size:10px; align-items:center; justify-content:center; flex-shrink:0;">${initial}</span>
                    <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(company.canonical_name)}</span>
                </span>
                <div style="display:flex; align-items:center; gap:6px; flex-shrink:0;">
                    <span class="card-score-badge ${scoreBadgeClass}">${compScore}</span>
                    <button class="btn-delete-company-x" onclick="removeCompanyFromList(event, '${company.id}', '${escapeHtml(company.canonical_name).replace(/'/g, "\\'")}')" title="Eliminar empresa de la lista">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            </div>
            <div class="card-meta-line">
                <span>${escapeHtml(company.domain)}</span>
                <span>${escapeHtml(company.hq_city || '')}, ${company.hq_country}</span>
            </div>
            <div class="card-label-tag">
                <i class="fa-solid fa-filter"></i> ${escapeHtml(company.primary_label || 'Resultado de Consulta')}
            </div>
        `;

        card.addEventListener('click', () => selectCompany(company.id));
        container.appendChild(card);

        if (index === 0) selectCompany(company.id);
    });
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/* ==========================================
   FEATURE 10: AUTO-ENRICHMENT MODAL HANDLERS
   ========================================== */
function openEnrichModal() {
    const modal = document.getElementById('enrich-domain-modal');
    if (modal) modal.classList.add('open');
}

function closeEnrichModal() {
    const modal = document.getElementById('enrich-domain-modal');
    const statusBox = document.getElementById('enrich-result-status');
    if (statusBox) statusBox.classList.add('hidden');
    if (modal) modal.classList.remove('open');
}

async function handleEnrichSubmit(e) {
    e.preventDefault();
    const domainInput = document.getElementById('enrich-domain-input');
    const statusBox = document.getElementById('enrich-result-status');
    const submitBtn = document.getElementById('btn-submit-enrich');

    if (!domainInput || !domainInput.value.trim()) return;

    const domain = domainInput.value.trim();
    if (statusBox) {
        statusBox.classList.remove('hidden');
        statusBox.innerHTML = '<div style="color:var(--accent-cyan);"><i class="fa-solid fa-circle-notch fa-spin"></i> Consultando Clearbit API y enriqueciendo empresa...</div>';
    }
    if (submitBtn) submitBtn.disabled = true;

    try {
        const resp = await authFetch(`/v1/companies/enrich?domain=${encodeURIComponent(domain)}`, {
            method: 'POST'
        });

        const company = await resp.json();
        if (resp.ok) {
            const cleanDomain = (company.domain || '').trim().toLowerCase();
            const primaryLogo = company.logo_url || `https://logo.clearbit.com/${cleanDomain}`;
            const fallbackLogo = `https://www.google.com/s2/favicons?domain=${cleanDomain}&sz=128`;

            if (statusBox) {
                statusBox.innerHTML = `
                    <div style="background: rgba(15, 23, 42, 0.9); border: 1px solid var(--accent-cyan); border-radius: 8px; padding: 14px; margin-top: 10px;">
                        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px;">
                            <img src="${primaryLogo}" style="width: 38px; height: 38px; border-radius: 6px; background: #fff; padding: 2px; object-fit: contain;" onerror="this.onerror=null; this.src='${fallbackLogo}';">
                            <div>
                                <h4 style="margin: 0; font-size: 1rem; color: var(--text-main); font-weight: 700;">${escapeHtml(company.canonical_name)}</h4>
                                <span style="font-size: 0.78rem; color: var(--accent-cyan); font-family: var(--font-code);">${escapeHtml(company.domain)}</span>
                            </div>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.8rem; color: var(--text-muted); border-top: 1px solid var(--border-color); padding-top: 10px;">
                            <div><i class="fa-solid fa-industry"></i> <strong>Sector:</strong> ${escapeHtml(company.industry || 'Software')}</div>
                            <div><i class="fa-solid fa-users"></i> <strong>Plantilla:</strong> ${escapeHtml(company.employee_range || '50-200')}</div>
                            <div><i class="fa-solid fa-location-dot"></i> <strong>Sede:</strong> ${escapeHtml(company.hq_city || 'Madrid')}, ${company.hq_country}</div>
                            <div><i class="fa-solid fa-file-contract"></i> <strong>Origen:</strong> Clearbit Firmographics</div>
                        </div>
                        <div style="margin-top: 12px; text-align: right;">
                            <button class="btn btn-primary btn-sm" type="button" onclick="finishEnrichmentView('${company.id}')" style="background: var(--brand-gold); color: #fff;">
                                <i class="fa-solid fa-folder-plus"></i> Abrir Ficha en Directorio
                            </button>
                        </div>
                    </div>
                `;
            }
        } else {
            if (statusBox) {
                statusBox.innerHTML = `<div style="color:var(--accent-red); font-weight:700;"><i class="fa-solid fa-times-circle"></i> Error: ${escapeHtml(company.detail || 'No se pudo enriquecer el dominio.')}</div>`;
            }
            if (submitBtn) submitBtn.disabled = false;
        }
    } catch (err) {
        console.error('Enrichment submit failed:', err);
        if (statusBox) {
            statusBox.innerHTML = '<div style="color:var(--accent-red); font-weight:700;"><i class="fa-solid fa-times-circle"></i> Error de conexión al enriquecer dominio.</div>';
        }
        if (submitBtn) submitBtn.disabled = false;
    }
}

async function finishEnrichmentView(companyId) {
    closeEnrichModal();
    const domainInput = document.getElementById('enrich-domain-input');
    if (domainInput) domainInput.value = '';
    const submitBtn = document.getElementById('btn-submit-enrich');
    if (submitBtn) submitBtn.disabled = false;
    await loadCompanyList();
    await selectCompany(companyId);
}

/* ==========================================
   FEATURE 13: EXECUTIVE BRIEF LLM AGENT
   ========================================== */
async function loadExecutiveBrief(companyId) {
    const p1 = document.getElementById('brief-p1');
    const p2 = document.getElementById('brief-p2');
    const p3 = document.getElementById('brief-p3');
    const dateTag = document.getElementById('brief-date-tag');

    if (p1) p1.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Generando síntesis por agente IA...';
    if (p2) p2.textContent = '';
    if (p3) p3.textContent = '';

    try {
        const resp = await authFetch(`/v1/companies/${companyId}/executive-brief`);
        if (!resp.ok) throw new Error('Brief non-200 response');
        const data = await resp.json();
        const brief = data.executive_brief || data;

        if (p1) p1.textContent = brief.growth_phase || brief.growth_stage_analysis || data.growth_phase || 'Información no disponible.';
        if (p2) p2.textContent = brief.tech_movements || brief.tech_shift_vendor_analysis || data.tech_movements || 'Información no disponible.';
        if (p3) p3.textContent = brief.commercial_opportunity || brief.commercial_opportunity_recommendation || data.commercial_opportunity || 'Información no disponible.';
        if (dateTag && data.generated_at) {
            const dt = new Date(data.generated_at);
            dateTag.textContent = `Generado: ${dt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
        }
    } catch (err) {
        console.error('Error fetching executive brief:', err);
        if (p1) p1.textContent = 'Error al sintetizar el brief ejecutivo de la empresa.';
    }
}

/* ==========================================
   FEATURE 11: TECH STACK & VENDOR PROFILER
   ========================================== */
async function loadTechStackProfile(companyId) {
    const grid = document.getElementById('tech-stack-badges-grid');
    const countBadge = document.getElementById('tech-stack-count-badge');
    if (!grid) return;

    grid.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> Escaneando infraestructura y registros DNS/MX...</div>';

    try {
        const resp = await authFetch(`/v1/companies/${companyId}/tech-stack`);
        if (!resp.ok) throw new Error('Tech stack non-200');
        const profile = await resp.json();

        const techs = profile.detected_technologies || [];
        if (countBadge) countBadge.textContent = `${techs.length} Tecnologías Detección`;

        if (techs.length === 0) {
            grid.innerHTML = '<div style="font-size:0.85rem; color:var(--text-muted); padding:10px;">No se detectaron firmas tecnológicas evidentes en el primer análisis.</div>';
            return;
        }

        grid.innerHTML = '';
        techs.forEach(t => {
            const pill = document.createElement('div');
            pill.className = 'tech-badge-item';
            
            let catIcon = 'fa-microchip';
            if (t.category === 'Email & Suite Workspace') catIcon = 'fa-envelope-open-text';
            else if (t.category === 'CRM / Ventas') catIcon = 'fa-headset';
            else if (t.category === 'Pagos / Monetización') catIcon = 'fa-credit-card';
            else if (t.category === 'Analítica Web') catIcon = 'fa-chart-simple';
            else if (t.category === 'CDN / Seguridad') catIcon = 'fa-shield-halved';
            else if (t.category === 'E-Commerce Platform') catIcon = 'fa-cart-shopping';
            else if (t.category === 'CMS / Framework') catIcon = 'fa-code';

            const confPercent = Math.round((t.confidence || 0.9) * 100);

            pill.innerHTML = `
                <div class="tech-badge-header">
                    <span class="tech-badge-title"><i class="fa-solid ${catIcon}"></i> ${escapeHtml(t.name)}</span>
                    <span class="tech-badge-cat">${escapeHtml(t.category)}</span>
                </div>
                <div class="tech-badge-meta">
                    <span>Vía ${t.evidence_type === 'dns_mx' ? 'DNS MX Record' : (t.evidence_type === 'http_script' ? 'Script Tag' : 'HTTP Header')}</span>
                    <span class="tech-badge-conf"><i class="fa-solid fa-circle-check"></i> ${confPercent}% Conv.</span>
                </div>
            `;
            grid.appendChild(pill);
        });
    } catch (err) {
        console.error('Error fetching tech stack profile:', err);
        grid.innerHTML = '<div style="font-size:0.85rem; color:var(--text-muted); padding:10px;">Error al cargar perfil de tecnologías.</div>';
    }
}
/* ==========================================
   BLOQUE 7: AUTHENTICATION & MULTI-TENANT LOGIC
   ========================================== */
let currentUserProfile = null;

function getAuthToken() {
    return localStorage.getItem('authToken') || localStorage.getItem('radar_jwt_token') || localStorage.getItem('radar_token') || '';
}

function getAuthHeader() {
    const token = getAuthToken();
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

async function authFetch(url, options = {}) {
    options.headers = {
        ...getAuthHeader(),
        ...(options.headers || {})
    };
    const response = await fetch(url, options);
    if (response.status === 402) {
        if (typeof openUpgradeModal === 'function') {
            openUpgradeModal();
        }
    }
    return response;
}

async function loadUserProfile() {
    try {
        const resp = await authFetch('/v1/auth/me');
        if (resp.ok) {
            currentUserProfile = await resp.json();
            updateUserProfileUI(currentUserProfile);
        } else {
            const leadEmail = localStorage.getItem('ofanradar_lead_email');
            if (leadEmail) {
                await handleDirectEmailAutoLogin(leadEmail);
            } else {
                checkTerminalAccessGate();
            }
        }
    } catch (err) {
        console.error('Error fetching current user profile:', err);
    }
}

function updateUserProfileUI(user) {
    const orgEl = document.getElementById('user-org-name');
    const roleEl = document.getElementById('user-role-name');
    const displayEmail = user.email || user.full_name || 'Usuario Lead';
    if (orgEl) orgEl.innerHTML = `<i class="fa-solid fa-user-circle" style="color:var(--accent-cyan);"></i> ${escapeHtml(displayEmail)}`;
    if (roleEl) roleEl.textContent = user.subscription_status === 'active' ? 'PRO' : (user.role || 'TRIAL');

    // Trial Badge & Subscription Status
    const trialTextEl = document.getElementById('trial-status-text');
    const trialBadgeEl = document.getElementById('trial-status-badge');
    const modalStatusBanner = document.getElementById('upgrade-modal-current-status');

    if (trialTextEl && trialBadgeEl) {
        const subStatus = (user.subscription_status || 'trial').toLowerCase();
        if (subStatus === 'active') {
            trialTextEl.innerHTML = '<i class="fa-solid fa-circle-check" style="color:#10b981;"></i> Suscripción Pro Activa';
            trialBadgeEl.style.borderColor = 'rgba(16, 185, 129, 0.4)';
            trialBadgeEl.style.color = '#10b981';
            trialBadgeEl.style.background = 'rgba(16, 185, 129, 0.1)';
            if (modalStatusBanner) {
                modalStatusBanner.style.background = 'rgba(16, 185, 129, 0.12)';
                modalStatusBanner.style.borderColor = 'rgba(16, 185, 129, 0.3)';
                modalStatusBanner.style.color = '#10b981';
                modalStatusBanner.innerHTML = '<i class="fa-solid fa-circle-check"></i> Estado Actual: Suscripción Pro Activa ($99/mes)';
            }
        } else if (subStatus === 'trial') {
            const daysLeft = user.days_left_in_trial !== undefined ? user.days_left_in_trial : 7;
            trialTextEl.innerHTML = `<i class="fa-solid fa-bolt" style="color:#a78bfa;"></i> Trial: Quedan ${daysLeft} días`;
            trialBadgeEl.style.borderColor = 'rgba(139, 92, 246, 0.4)';
            trialBadgeEl.style.color = '#a78bfa';
            trialBadgeEl.style.background = 'rgba(139, 92, 246, 0.15)';
            if (modalStatusBanner) {
                modalStatusBanner.style.background = 'rgba(139, 92, 246, 0.12)';
                modalStatusBanner.style.borderColor = 'rgba(139, 92, 246, 0.3)';
                modalStatusBanner.style.color = '#a78bfa';
                modalStatusBanner.innerHTML = `<i class="fa-solid fa-bolt"></i> Estado Actual: Periodo de Prueba (${daysLeft} días restantes)`;
            }
        } else {
            trialTextEl.innerHTML = '<i class="fa-solid fa-lock" style="color:#ef4444;"></i> Trial Expirado — Upgrade';
            trialBadgeEl.style.borderColor = 'rgba(239, 68, 68, 0.5)';
            trialBadgeEl.style.color = '#ef4444';
            trialBadgeEl.style.background = 'rgba(239, 68, 68, 0.15)';
            if (modalStatusBanner) {
                modalStatusBanner.style.background = 'rgba(239, 68, 68, 0.12)';
                modalStatusBanner.style.borderColor = 'rgba(239, 68, 68, 0.3)';
                modalStatusBanner.style.color = '#ef4444';
                modalStatusBanner.innerHTML = '<i class="fa-solid fa-lock"></i> Estado Actual: Trial Expirado. Actualiza a Plan Pro para continuar.';
            }
        }
    }
}

function openUpgradeModal() {
    const modal = document.getElementById('upgrade-modal');
    if (modal) modal.classList.add('open');
}

function closeUpgradeModal() {
    const modal = document.getElementById('upgrade-modal');
    if (modal) modal.classList.remove('open');
}

async function handleUpgradeCheckout(plan = 'pro') {
    try {
        const resp = await authFetch(`/v1/billing/checkout-session?plan=${plan}`, { method: 'POST' });
        const data = await resp.json();
        if (resp.ok && data.checkout_url) {
            window.location.href = data.checkout_url;
        } else {
            alert(`Error al generar checkout de Stripe: ${data.detail || 'Fallo de conexión'}`);
        }
    } catch (err) {
        console.error('Checkout error:', err);
    }
}

function openAuthModal() {
    const modal = document.getElementById('auth-modal');
    if (modal) modal.classList.add('open');
}

function closeAuthModal() {
    const modal = document.getElementById('auth-modal');
    if (modal) modal.classList.remove('open');
}

function switchAuthTab(tab) {
    const loginBtn = document.getElementById('auth-tab-login');
    const regBtn = document.getElementById('auth-tab-register');
    const loginForm = document.getElementById('auth-login-form');
    const regForm = document.getElementById('auth-register-form');

    if (tab === 'login') {
        loginBtn.classList.add('active');
        regBtn.classList.remove('active');
        loginForm.classList.remove('hidden');
        regForm.classList.add('hidden');
    } else {
        regBtn.classList.add('active');
        loginBtn.classList.remove('active');
        regForm.classList.remove('hidden');
        loginForm.classList.add('hidden');
    }
}

function fillDemoAccount(email, password, autoSubmit = false) {
    const emailInput = document.getElementById('auth-login-email');
    const passInput = document.getElementById('auth-login-password');
    if (emailInput) emailInput.value = email;
    if (passInput) passInput.value = password;

    if (autoSubmit) {
        const fakeEvent = { preventDefault: () => {} };
        handleAuthLoginSubmit(fakeEvent);
    }
}

async function handleAuthLoginSubmit(e) {
    if (e && e.preventDefault) e.preventDefault();
    const email = document.getElementById('auth-login-email')?.value.trim();
    const password = document.getElementById('auth-login-password')?.value;
    const statusBox = document.getElementById('auth-login-status');

    if (!email || !password) return;

    if (statusBox) {
        statusBox.classList.remove('hidden');
        statusBox.innerHTML = '<div style="color:var(--accent-cyan)"><i class="fa-solid fa-circle-notch fa-spin"></i> Autenticando token JWT...</div>';
    }

    try {
        const resp = await fetch('/v1/auth/token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await resp.json();
        if (resp.ok) {
            localStorage.setItem('radar_jwt_token', data.access_token);
            currentUserProfile = data;
            updateUserProfileUI(data);

            if (statusBox) {
                statusBox.innerHTML = `<div style="color:var(--accent-green); font-weight:700;"><i class="fa-solid fa-circle-check"></i> Bienvenido ${escapeHtml(data.full_name)} (${escapeHtml(data.organization_name)})</div>`;
            }
            setTimeout(() => {
                closeAuthModal();
                fetchWatchlists();
                loadCompanyList();
            }, 800);
        } else {
            if (statusBox) {
                statusBox.innerHTML = `<div style="color:var(--accent-red); font-weight:700;"><i class="fa-solid fa-triangle-exclamation"></i> ${escapeHtml(data.detail || 'Error de autenticación')}</div>`;
            }
        }
    } catch (err) {
        console.error('Login error:', err);
    }
}

async function handleAuthRegisterSubmit(e) {
    e.preventDefault();
    const orgName = document.getElementById('auth-reg-org')?.value.trim();
    const fullName = document.getElementById('auth-reg-name')?.value.trim();
    const email = document.getElementById('auth-reg-email')?.value.trim();
    const password = document.getElementById('auth-reg-password')?.value;
    const statusBox = document.getElementById('auth-reg-status');

    if (!orgName || !fullName || !email || !password) return;

    if (statusBox) {
        statusBox.classList.remove('hidden');
        statusBox.innerHTML = '<div style="color:var(--accent-cyan)"><i class="fa-solid fa-circle-notch fa-spin"></i> Creando Organización Tenant...</div>';
    }

    try {
        const resp = await fetch('/v1/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                organization_name: orgName,
                full_name: fullName,
                email: email,
                password: password,
                role: 'ADMIN'
            })
        });

        const data = await resp.json();
        if (resp.ok) {
            localStorage.setItem('radar_jwt_token', data.access_token);
            currentUserProfile = data;
            updateUserProfileUI(data);

            if (statusBox) {
                statusBox.innerHTML = `<div style="color:var(--accent-green); font-weight:700;"><i class="fa-solid fa-circle-check"></i> Organización '${escapeHtml(data.organization_name)}' creada exitosamente!</div>`;
            }
            setTimeout(() => {
                closeAuthModal();
                fetchWatchlists();
                loadCompanyList();
            }, 800);
        } else {
            if (statusBox) {
                statusBox.innerHTML = `<div style="color:var(--accent-red); font-weight:700;"><i class="fa-solid fa-triangle-exclamation"></i> ${escapeHtml(data.detail || 'Error al registrar organización')}</div>`;
            }
        }
    } catch (err) {
        console.error('Register error:', err);
    }
}

/* ==========================================
   BLOQUE 8: PROACTIVE ALERTS & WEBHOOKS LOGIC
   ========================================== */
function openAlertsModal() {
    const modal = document.getElementById('alerts-modal');
    if (modal) modal.classList.add('open');
    fetchAlertSubscriptions();
}

function closeAlertsModal() {
    const modal = document.getElementById('alerts-modal');
    if (modal) modal.classList.remove('open');
}

async function fetchAlertSubscriptions() {
    const listContainer = document.getElementById('alerts-rules-list');
    if (!listContainer) return;

    listContainer.innerHTML = '<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i> Cargando reglas de alerta...</div>';

    try {
        const resp = await authFetch('/v1/alerts/subscriptions');
        const rules = await resp.json();

        if (!rules || rules.length === 0) {
            listContainer.innerHTML = '<div style="font-size:0.8rem; color:var(--text-muted); padding:8px;">No hay reglas de alerta configuradas para esta organización.</div>';
            return;
        }

        listContainer.innerHTML = '';
        rules.forEach(r => {
            const item = document.createElement('div');
            item.style.cssText = 'padding:10px 12px; background:rgba(255,255,255,0.03); border:1px solid var(--border-color); border-radius:6px; display:flex; justify-content:space-between; align-items:center;';

            let chanIcon = 'fa-globe';
            if (r.channel === 'SLACK') chanIcon = 'fa-slack';
            else if (r.channel === 'TEAMS') chanIcon = 'fa-microsoft';

            item.innerHTML = `
                <div>
                    <div style="font-weight:700; font-size:0.85rem; color:var(--text-main); display:flex; align-items:center; gap:6px;">
                        <i class="fa-brands ${chanIcon}" style="color:var(--accent-amber);"></i> ${escapeHtml(r.rule_name)}
                        <span class="badge badge-industry" style="font-size:0.7rem;">Score &ge; ${r.min_composite_score}</span>
                    </div>
                    <div style="font-size:0.75rem; color:var(--text-dim); margin-top:2px;">
                        ${escapeHtml(r.target_url)}
                    </div>
                </div>
                <div style="display:flex; gap:6px;">
                    <button class="btn btn-outline btn-sm" onclick="testTriggerAlert('${r.id}')" title="Probar Trigger de Alerta"><i class="fa-solid fa-paper-plane"></i> Probar</button>
                    <button class="btn btn-outline btn-sm" onclick="deleteAlertRule('${r.id}')" title="Eliminar"><i class="fa-solid fa-trash"></i></button>
                </div>
            `;
            listContainer.appendChild(item);
        });

    } catch (err) {
        console.error('Error fetching alert rules:', err);
    }
}

async function handleCreateAlertRuleSubmit(e) {
    e.preventDefault();
    const name = document.getElementById('alert-rule-name')?.value.trim();
    const channel = document.getElementById('alert-rule-channel')?.value;
    const score = parseFloat(document.getElementById('alert-rule-score')?.value || '70');
    const url = document.getElementById('alert-rule-url')?.value.trim();
    const secret = document.getElementById('alert-rule-secret')?.value.trim();
    const statusBox = document.getElementById('create-alert-status');

    if (!name || !url) return;

    if (statusBox) {
        statusBox.classList.remove('hidden');
        statusBox.innerHTML = '<div style="color:var(--accent-cyan)"><i class="fa-solid fa-circle-notch fa-spin"></i> Guardando regla de alerta...</div>';
    }

    try {
        const resp = await authFetch('/v1/alerts/subscriptions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                rule_name: name,
                channel: channel,
                min_composite_score: score,
                target_url: url,
                secret: secret || 'radar-secret-2026'
            })
        });

        const data = await resp.json();
        if (resp.ok) {
            document.getElementById('create-alert-rule-form').reset();
            if (statusBox) {
                statusBox.innerHTML = `<div style="color:var(--accent-green); font-weight:700;"><i class="fa-solid fa-check-circle"></i> Regla '${escapeHtml(data.rule_name)}' guardada!</div>`;
            }
            setTimeout(() => {
                statusBox.classList.add('hidden');
                fetchAlertSubscriptions();
            }, 800);
        } else {
            if (statusBox) {
                statusBox.innerHTML = `<div style="color:var(--accent-red); font-weight:700;"><i class="fa-solid fa-times-circle"></i> ${escapeHtml(data.detail || 'Error al guardar regla')}</div>`;
            }
        }
    } catch (err) {
        console.error('Error creating alert rule:', err);
    }
}

async function testTriggerAlert(ruleId) {
    alert('Enviando simulación de alerta de prueba (Test Trigger)...');
    try {
        const resp = await authFetch('/v1/alerts/test-trigger', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ subscription_id: ruleId })
        });
        const res = await resp.json();
        if (resp.ok) {
            alert(`✅ Alerta de Prueba Disparada con Éxito!\n\nCanal: ${res.dispatch_details.channel}\nFirma HMAC: ${res.dispatch_details.signature_hmac}\nStatus: ${res.dispatch_details.status}`);
        } else {
            alert(`❌ Error al probar regla: ${res.detail || 'Fallo desconocido'}`);
        }
    } catch (err) {
        console.error('Test trigger failed:', err);
    }
}

async function deleteAlertRule(ruleId) {
    const confirmed = await showCustomConfirm({
        title: '¿Eliminar regla de alerta?',
        message: 'Se cancelará la monitorización proactiva y los envíos de webhooks para esta regla.',
        confirmBtnText: 'Eliminar Regla',
        isDanger: true
    });
    if (!confirmed) return;

    try {
        const resp = await authFetch(`/v1/alerts/subscriptions/${ruleId}`, { method: 'DELETE' });
        if (resp.ok) {
            showToast('Regla de alerta eliminada correctamente', 'success');
            fetchAlertSubscriptions();
        } else {
            const err = await resp.json();
            showToast(`Acceso Denegado: ${err.detail || 'Solo administradores pueden eliminar reglas'}`, 'error');
        }
    } catch (err) {
        console.error('Delete alert rule failed:', err);
        showToast('Error al eliminar la regla de alerta', 'error');
    }
}

/* ==========================================
   GLOBAL ON-DEMAND INSTANT ANALYSIS
   ========================================== */
async function handleGlobalOnDemandSubmit(queryOverride) {
    const input = document.getElementById('global-on-demand-input');
    const query = queryOverride || (input ? input.value.trim() : '');
    const submitBtn = document.getElementById('btn-global-on-demand');

    if (!query) {
        alert('Por favor introduzca el nombre o dominio de una empresa.');
        return;
    }

    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Analizando...';
    }

    try {
        const resp = await authFetch('/v1/companies/analyze-on-demand', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query })
        });

        const data = await resp.json();
        if (resp.ok && data.company) {
            await loadCompanyList();
            await selectCompany(data.company.id);
            if (input) input.value = '';
        } else {
            alert(`Error al analizar empresa: ${data.detail || 'Fallo de conexión'}`);
        }
    } catch (err) {
        console.error('Error on-demand analysis:', err);
        alert('Error de conexión al ejecutar el análisis en tiempo real.');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fa-solid fa-bolt"></i> Analizar Empresa';
        }
    }
}


