/**
 * Yo Scraper App i18n Engine
 * Language stored in localStorage key: 'lp_lang' (shared with landing page)
 * Usage:
 *   - HTML:  <span data-i18n="key">Türkçe metin</span>
 *   - HTML:  <input data-i18n-ph="key" placeholder="Türkçe">
 *   - JS:    t('key', 'Türkçe fallback')
 */
(function () {
    var DICT = {
        en: {
            // ── HEADER ──
            'h-scanning':   'Scanning...',
            'h-go-scanner': 'Go to Scanner →',
            'h-found':      'found',

            // ── LOGIN ──
            'login-title':    'Sign In',
            'login-subtitle': 'Sign in to your Yo Scraper account',
            'email-label':    'Email',
            'email-ph':       'example@company.com',
            'pw-label':       'Password',
            'login-btn':      'Sign In',
            'no-account':     "Don't have an account?",
            'reg-link':       'Register',
            'back-home':      '← Back to Home',

            // ── REGISTER ──
            'reg-title':       'Register',
            'reg-subtitle':    'Create your free Yo Scraper account',
            'fullname-label':  'Full Name',
            'fullname-ph':     'John Doe',
            'company-label':   'Company',
            'company-ph':      'Company name (optional)',
            'phone-label':     'Phone',
            'pw-new-label':    'Password',
            'pw-new-ph':       'At least 8 characters',
            'pw-confirm-label':'Confirm Password',
            'pw-confirm-ph':   'Re-enter your password',
            'terms-text':      'I have read and agree to the Privacy Policy and Terms of Service.',
            'reg-btn':         'Register',
            'no-cc':           'No credit card required.',
            'have-account':    'Already have an account?',
            'login-link':      'Sign In',

            // ── SCANNER (index.html) ──
            'sector-label':  'Select Sector',
            'city-label':    'City',
            'city-ph':       'Select city...',
            'min-res-label': 'Min. Results',
            'start-btn':     'Start',
            'pause-btn':     'Pause',
            'stop-btn':      'Stop',
            'ready-status':  'Ready — select a sector and city to begin',
            'stat-scanned':  'Scanned',
            'stat-found':    'Found',
            'stat-sheets':   'Added to Sheets',
            'found-biz':     'Found Businesses',
            'del-sel':       'Delete Selected',
            'clear-btn':     'Clear',
            'th-date':       'Date',
            'th-sector':     'Sector',
            'th-company':    'Company',
            'th-phone':      'Phone',
            'th-email':      'Email',
            'th-domain':     'Domain',
            'no-scans':      'No scans yet',
            'sys-log':       'System ready. Select a sector and city from the left panel to start scanning.',
            'selected-pfx':  'Selected: ',
            'results-sfx':   ' results',

            // ── IMPORT WIZARD (external.html) ──
            'import-title':      'Import',
            'import-sub':        'Upload data from file or Google Sheets, map columns, and import to Database.',
            'step-source':       'Source',
            'step-cols':         'Columns',
            'step-preview':      'Preview',
            'step-result':       'Result',
            'tab-file':          'Upload File',
            'tab-sheets':        'Google Sheets',
            'drag-title':        'Drag & drop or click to upload',
            'gs-nc-title':       'Connect your Google account',
            'gs-nc-sub':         'Sign in with Google to access your Sheets files on Drive.',
            'gs-conn-btn':       'Connect with Google',
            'gs-connected-lbl':  'Google account connected',
            'gs-disc-btn':       'Disconnect',
            'gs-search-ph':      'Search file...',
            'gs-sel-tab':        'Select Sheet',
            'gs-auto-sel':       'Auto-selected',
            'next-btn':          'Continue →',
            'map-title':         'Column Mapping',
            'map-sub':           'Map source columns to Database fields',
            'src-col':           'Source Column',
            'db-field-col':      'Database Field',
            'auto-mapped':       '✓ Auto-mapped',
            'back-btn':          '← Back',
            'preview-btn':       'Preview →',
            'import-btn':        'Start Import',
            'importing-msg':     'Importing data...',
            'created-lbl':       'Created',
            'skipped-lbl':       'Skipped (duplicate)',
            'total-lbl':         'Total Rows',
            'new-import':        'New Import',
            'go-db':             'Go to Database →',
            'import-failed':     'Import failed',
            'retry-btn':         'Retry',

            // ── IMPORT WIZARD – JS dynamic strings ──
            'ext-fmt-err':      'Unsupported format. Use .xlsx, .xls or .csv.',
            'parsing':          'Parsing...',
            'ext-rows':         'rows',
            'ext-cols':         'columns',
            'ext-read-err':     'Could not read file: ',
            'ext-no-files':     'No files found.',
            'ext-loading':      'Loading...',
            'ext-skip':         'Skip',
            'ext-auto-match':   'auto-matched',
            'ext-map-required': 'Please map at least one column.',
            'ext-db-date':      'Date',
            'ext-db-first':     'First Name',
            'ext-db-last':      'Last Name',
            'ext-db-phone':     'Phone Number',
            'ext-db-email':     'Email Address',
            'ext-db-city':      'City',
            'ext-preview-meta': 'Showing first 10 rows',
            'ext-total':        'Total',
            'ext-gs-fail':      'Google connection failed',

            // ── DATABASE ──
            'db-search-ph':  'Search company, email, domain...',
            'all-sources':   'All Sources',
            'all-sectors':   'All Sectors',
            'del-sel-btn':   'Delete Selected',
            'refresh-btn':   'Refresh',
            'src-filter-ph': 'Filter source...',
            'clear-filter':  'Clear',

            // ── SENDMAIL ──
            'sm-db-co':     'DB Companies',
            'sm-w-email':   'With Email',
            'sm-sent':      'Sent',
            'sm-failed':    'Failed',
            'sm-compose':   'Compose Mail',
            'sm-from':      'From',
            'sm-subject':   'Subject',
            'sm-subj-ph':   'Email subject...',
            'sm-content':   'Content (HTML)',
            'sm-cont-ph':   'HTML email content...',
            'sm-vars':      'Variables:',
            'sm-recipients':'Recipients',
            'sm-sel-all':   'Select all',
            'sm-desel':     'Deselect all',
            'sm-sel-unsent':'Select unsent',
            'sm-srch-ph':   'Search company, email or sector...',
            'sm-history':   'Send History',
            'sm-th-time':   'Time',
            'sm-th-co':     'Company',
            'sm-th-email':  'Email',
            'sm-th-subj':   'Subject',
            'sm-th-status': 'Status',
            'sm-no-hist':   'No emails sent yet.',
            'sm-loading':   'Loading...',

            // ── DOMAINS ──
            'dom-title':    'Scanned Domains',
            'dom-back':     '← Back to Dashboard',
            'dom-sel-all':  'Select All',
            'dom-del':      'Delete Selected',
            'dom-refresh':  'Refresh',
            'dom-srch-ph':  'Search...',
            'dom-loading':  'Loading...',
            'dom-th-co':    'Company Name',
            'dom-th-email': 'Email',
            'dom-th-phone': 'Phone',
            'dom-th-domain':'Domain',

            // ── CLICKBOT ──
            'cb-loc-hdr':     'LOCATION',
            'cb-no-city':     'No city selected yet',
            'cb-loc-count':   ' locations selected',
            'cb-kw-hdr':      'KEYWORDS',
            'cb-kw-ph':       'Enter one keyword per line',
            'cb-not-sel':     'NOT SELECTED',
            'cb-mode-hdr':    'SCAN MODE',
            'cb-ads':         'Ad',
            'cb-organic':     'Organic',
            'cb-power':       'Power',
            'cb-sched-hdr':   'SCHEDULE',
            'cb-hourly-badge':'HOURLY',
            'cb-freq-lbl':    'Repeat Frequency',
            'cb-once':        'One-time',
            'cb-hourly':      'Hourly',
            'cb-daily':       'Daily',
            'cb-weekly':      'Weekly',
            'cb-monthly':     'Monthly',
            'cb-every-h':     'Every how many hours?',
            'cb-h1':          'Every 1 hour',
            'cb-h2':          'Every 2 hours',
            'cb-h3':          'Every 3 hours',
            'cb-h4':          'Every 4 hours',
            'cb-h6':          'Every 6 hours',
            'cb-daily-cnt':   'How many scans per day?',
            'cb-1x':          '1 time',
            'cb-2x':          '2 times',
            'cb-3x':          '3 times',
            'cb-4x':          '4 times',
            'cb-6x':          '6 times',
            'cb-slots-lbl':   'Scan times (auto)',
            'cb-days-lbl':    'Days',
            'cb-mon':         'Mon', 'cb-tue': 'Tue', 'cb-wed': 'Wed',
            'cb-thu':         'Thu', 'cb-fri': 'Fri',
            'cb-sat':         'Sat', 'cb-sun': 'Sun',
            'cb-loc-sfx':     'locations selected',

            // ── LOGIN JS ──
            'login-email-req':  'Email and password are required.',
            'login-signing-in': 'Signing in...',
            'login-err':        'Invalid credentials.',
            'login-retry':      'An error occurred. Please try again.',

            // ── REGISTER JS ──
            'reg-name-req':  'Full name is required.',
            'reg-email-inv': 'Please enter a valid email address.',
            'reg-pw-short':  'Password must be at least 8 characters.',
            'reg-pw-mism':   'Passwords do not match.',
            'reg-terms-req': 'You must accept the terms of service.',
            'reg-saving':    'Registering...',
            'reg-err':       'An error occurred during registration.',

            // ── TERMS links ──
            'terms-pp':  'Privacy Policy',
            'terms-tos': 'Terms of Service',

            // ── EXTERNAL JS ──
            'ext-fmt-err':  'Unsupported format. Use .xlsx, .xls or .csv.',
            'parsing':      'Parsing...',
            'gs-auto-sel':  'Auto-selected',

            // ── SENDMAIL JS ──
            'sm-no-email-co':  'No companies with email found.',
            'sm-db-load-err':  'Failed to load database.',
            'sm-status-sent':  'Sent',
            'sm-status-fail':  'Failed',
            'sm-status-snd':   'Sending',
            'sm-selected':     'selected',
            'sm-send-prefix':  'Send',
            'sm-recipient':    'recipient',
            'sm-send-init':    'Send (0 recipients)',
            'sm-alert-no-rcpt':'Please select recipients.',
            'sm-alert-no-subj':'Please enter a subject.',
            'sm-alert-no-body':'Please enter email content.',
            'sm-confirm':      'companies will be emailed. Continue?',
            'sm-sending':      'Sending...',
            'sm-send-err':     'Send error: ',
            'sm-records':      'records',

            // ── DOMAINS JS ──
            'dom-total':          'Total:',
            'dom-records':        'records',
            'dom-no-records':     'No records found',
            'dom-delete-confirm': 'records will be deleted. Are you sure?',
            'cb-month-day':   'Which day of month?',
            'cb-start-lbl':   'Start time',
            'cb-end-lbl':     'End time',
            'cb-lock-msg':    'Unlock to activate scheduling.',
            'cb-start-btn':   'Start',
            'cb-pause-btn':   'Pause',
            'cb-stop-btn':    'Stop',
            'cb-live-log':    'LIVE LOG',
            'cb-clear':       '🗑 Clear',
            'cb-click-hist':  'CLICK HISTORY',
            'cb-clear-hist':  '🗑 Clear',
            'cb-bot-ready':   'Bot ready. Enter city and keyword then press "Start".',
            'cb-no-clicks':   'No clicks yet.',
            'cb-th-time':     'TIME',
            'cb-th-city':     'CITY',
            'cb-th-dist':     'DISTRICT',
            'cb-th-kw':       'KEYWORD',
            'cb-th-co':       'COMPANY',
            'cb-th-ad':       'AD SLOT',
            'cb-th-url':      'URL',
            'cb-th-status':   'STATUS',
        }
    };

    // Expose current language globally
    window.APP_LANG = localStorage.getItem('lp_lang') || 'tr';

    /**
     * t(key, trFallback)
     * Returns English translation if lang=en, otherwise returns the Turkish fallback.
     * Usage in JS: element.textContent = t('start-btn', 'Başlat');
     */
    window.t = function (key, trFallback) {
        if (window.APP_LANG === 'en' && DICT.en[key] !== undefined) {
            return DICT.en[key];
        }
        return trFallback !== undefined ? trFallback : key;
    };

    // Apply data-i18n translations to the DOM
    function applyLang() {
        if (window.APP_LANG !== 'en') return;
        var dict = DICT.en;

        document.querySelectorAll('[data-i18n]').forEach(function (el) {
            var key = el.getAttribute('data-i18n');
            if (dict[key] !== undefined) el.textContent = dict[key];
        });
        document.querySelectorAll('[data-i18n-ph]').forEach(function (el) {
            var key = el.getAttribute('data-i18n-ph');
            if (dict[key] !== undefined) el.placeholder = dict[key];
        });
        document.querySelectorAll('[data-i18n-val]').forEach(function (el) {
            var key = el.getAttribute('data-i18n-val');
            if (dict[key] !== undefined) el.value = dict[key];
        });
        document.querySelectorAll('[data-i18n-title]').forEach(function (el) {
            var key = el.getAttribute('data-i18n-title');
            if (dict[key] !== undefined) el.title = dict[key];
        });

        document.documentElement.lang = 'en';
    }

    // Switch language and reload
    window.setAppLang = function (lang) {
        localStorage.setItem('lp_lang', lang);
        window.APP_LANG = lang;
        location.reload();
    };

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyLang);
    } else {
        applyLang();
    }
    // Second pass for dynamically rendered content
    setTimeout(applyLang, 80);
})();
