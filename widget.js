(function () {
    const scriptTag = document.currentScript;
    const siteId    = scriptTag.getAttribute('data-site-id');
    const apiBase   = (scriptTag.getAttribute('data-api-url') || 'http://127.0.0.1:5000').replace(/\/$/, '');

    // Live user info — mutable so login/logout after page load is reflected immediately.
    // Page calls window.acmeWidget.setUser({name,email,address,id}) on login,
    // and window.acmeWidget.clearUser() on logout.
    let _userInfo = {
        name:    scriptTag.getAttribute('data-user-name')    || '',
        email:   scriptTag.getAttribute('data-user-email')   || '',
        address: scriptTag.getAttribute('data-user-address') || '',
        user_id: scriptTag.getAttribute('data-user-id')      || ''
    };
    window.acmeWidget = {
        setUser:   function(u) { _userInfo = { name:u.name||'', email:u.email||'', address:u.address||'', user_id:u.id||'' }; },
        clearUser: function()  { _userInfo = { name:'', email:'', address:'', user_id:'' }; }
    };
    function getUserInfo() { return _userInfo; }

    fetch(`${apiBase}/config/${siteId}`)
        .then(r => r.ok ? r.json() : null)
        .catch(() => null)
        .then(cfg => initWidget(cfg || {}));

    // ── Markdown renderer ────────────────────────────────────
    function renderMarkdown(text) {
        const lines = text.split('\n');
        let html = '', inList = false;
        for (let raw of lines) {
            const bullet = raw.match(/^[\s]*[•\-\*]\s+(.+)/);
            if (bullet) {
                if (!inList) { html += '<ul>'; inList = true; }
                html += '<li>' + inline(bullet[1]) + '</li>';
                continue;
            }
            if (inList) { html += '</ul>'; inList = false; }
            if (!raw.trim()) { html += '<br>'; continue; }
            html += '<p>' + inline(raw) + '</p>';
        }
        if (inList) html += '</ul>';
        return html;
    }

    function inline(t) {
        return t
            .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
            .replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g,
                (_,label,url) => `<a href="${url}" target="_blank" rel="noopener">${label}</a>`)
            .replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>')
            .replace(/\*([^*\n]+)\*/g,'<em>$1</em>')
            .replace(/_([^_]+)_/g,'<em>$1</em>');
    }

    function normalizeMessageText(text) {
        return String(text || '')
            .replace(/\r\n?/g, '\n')
            .replace(/Â£/g, '£')
            .replace(/â€¢/g, '•')
            .replace(/â€”/g, '—')
            .replace(/â€“/g, '–')
            .replace(/âœ…/g, '✅')
            .replace(/Ã—/g, '×');
    }

    function formatMessageHtml(text) {
        const lines = normalizeMessageText(text).split('\n');
        let html = '';
        let listType = null;

        function closeList() {
            if (listType) {
                html += `</${listType}>`;
                listType = null;
            }
        }

        for (const raw of lines) {
            const line = raw.trimEnd();
            const bullet = line.match(/^\s*[•\-*]\s+(.+)/);
            const numbered = line.match(/^\s*(\d+)\.\s+(.+)/);
            const labelLine = line.match(/^([A-Za-z][A-Za-z0-9 /&'-]{1,40}):\s*(.+)$/);

            if (bullet) {
                if (listType !== 'ul') {
                    closeList();
                    html += '<ul>';
                    listType = 'ul';
                }
                html += `<li>${inline(bullet[1])}</li>`;
                continue;
            }

            if (numbered) {
                if (listType !== 'ol') {
                    closeList();
                    html += '<ol>';
                    listType = 'ol';
                }
                html += `<li>${inline(numbered[2])}</li>`;
                continue;
            }

            closeList();

            if (!line.trim()) {
                html += '<div class="cb-spacer"></div>';
                continue;
            }

            if (labelLine) {
                html += `<p><strong>${inline(labelLine[1])}:</strong> ${inline(labelLine[2])}</p>`;
                continue;
            }

            html += `<p>${inline(line)}</p>`;
        }

        closeList();
        return html;
    }

    function initWidget(cfg) {
        const botName     = cfg.bot_name       || 'AI Assistant';
        const statusText  = cfg.status_text    || 'Online now';
        const greeting    = cfg.greeting       || 'Hi! How can I help you today?';
        const c1          = cfg.accent_color    || '#667eea';
        const c2          = cfg.accent_color_2   || '#764ba2';
        const hbg1        = cfg.header_bg_1    || '#1a1a2e';
        const hbg2        = cfg.header_bg_2    || '#16213e';
        const winBg       = cfg.window_bg      || '#0f0f1a';
        const placeholder = cfg.placeholder    || 'Type a message...';
        const footerTxt   = cfg.footer_text    || 'Powered by AI';
        const iconType      = cfg.icon_type       || 'svg';
        const iconValue     = cfg.icon_value      || '';
        const bubbleR       = cfg.bubble_radius   || 16;
        const fontSize      = cfg.font_size       || 13;
        const showTs        = cfg.show_timestamps || false;
        const winWidth      = cfg.window_width    || 420;
        const winHeight     = cfg.window_height   || 580;
        const launcherPos   = cfg.launcher_pos    || 'right';
        const launcherSize  = cfg.launcher_size   || 60;
        const fontFamily    = cfg.font_family      || 'DM Sans';
        const botBubbleBg   = cfg.bot_bubble_bg    || 'rgba(255,255,255,0.08)';
        const botTextColor  = cfg.bot_text_color   || '#ddddf0';
        const userTextColor = cfg.user_text_color  || '#ffffff';
        const inputBg       = cfg.input_bg         || winBg;
        const optBtnColor   = cfg.opt_btn_color    || 'rgba(255,255,255,0.07)';
        const linkColor     = cfg.link_color       || c1;
        const onlineDotClr  = cfg.online_dot_color || '#4ade80';
        const autoOpenDelay = cfg.auto_open_delay  || 0;
        const soundEnabled  = cfg.sound_enabled    || false;
        const lineHeight    = cfg.line_height      || 1.45;
        const bubblePadH    = cfg.bubble_pad_h     || 12;
        const bubblePadV    = cfg.bubble_pad_v     || 8;
        const msgGap        = cfg.message_gap      || 6;
        const headerPad     = cfg.header_pad       || 14;
        const optBtnRadius  = cfg.opt_btn_radius   || 50;
        const inputRadius   = cfg.input_radius     || 12;

        // ── Icon renderer ──────────────────────────────────
        function getIcon(size) {
            if (iconType === 'emoji' && iconValue) {
                return `<span style="font-size:${Math.round(size*0.8)}px;line-height:1">${iconValue}</span>`;
            }
            if (iconType === 'url' && iconValue) {
                return `<img src="${iconValue}" width="${size}" height="${size}" style="border-radius:50%;object-fit:cover" alt="bot">`;
            }
            // Default SVG robot
            return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none">
                <rect x="3" y="8" width="18" height="13" rx="3" fill="white" opacity="0.92"/>
                <rect x="7" y="11" width="3" height="3" rx="1.5" fill="${c1}"/>
                <rect x="14" y="11" width="3" height="3" rx="1.5" fill="${c1}"/>
                <rect x="9" y="15" width="6" height="2" rx="1" fill="${c1}"/>
                <rect x="10" y="3" width="4" height="5" rx="1" fill="white" opacity="0.92"/>
                <circle cx="8" cy="5" r="1.5" fill="white" opacity="0.92"/>
                <circle cx="16" cy="5" r="1.5" fill="white" opacity="0.92"/>
                <line x1="8" y1="5" x2="10" y2="5" stroke="white" stroke-width="1.5" opacity="0.92"/>
                <line x1="14" y1="5" x2="16" y2="5" stroke="white" stroke-width="1.5" opacity="0.92"/>
            </svg>`;
        }

        const style = document.createElement('style');
        style.innerHTML = `
            @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&display=swap');

            #cb-root * { box-sizing:border-box; margin:0; font-family:'${fontFamily}',sans-serif; }

            #cb-launcher {
                position:fixed; bottom:28px; ${launcherPos==='left'?'left:28px':'right:28px'}; z-index:9999;
                width:${launcherSize}px; height:${launcherSize}px; border-radius:50%; cursor:pointer;
                background:linear-gradient(135deg,${hbg1},${hbg2});
                border:none; display:flex; align-items:center; justify-content:center;
                box-shadow:0 8px 32px rgba(0,0,0,.3),0 0 0 1px rgba(255,255,255,.07);
                transition:transform .25s cubic-bezier(.34,1.56,.64,1);
                padding:0;
            }
            #cb-launcher:hover { transform:scale(1.1); }
            #cb-launcher .icon-chat { transition:transform .3s cubic-bezier(.34,1.56,.64,1),opacity .2s; }
            #cb-launcher .icon-close { transform:scale(0) rotate(90deg); opacity:0; position:absolute; transition:transform .3s cubic-bezier(.34,1.56,.64,1),opacity .2s; }
            #cb-launcher.open .icon-chat { transform:scale(0) rotate(-90deg); opacity:0; position:absolute; }
            #cb-launcher.open .icon-close { transform:scale(1) rotate(0); opacity:1; position:relative; }
            #cb-online-dot { position:absolute; top:4px; right:4px; width:12px; height:12px; background:${onlineDotClr}; border-radius:50%; border:2px solid ${hbg1}; animation:pulse-dot 2s infinite; padding:0; }
            @keyframes pulse-dot { 0%,100%{box-shadow:0 0 0 0 ${onlineDotClr}80}50%{box-shadow:0 0 0 5px ${onlineDotClr}00} }

            #cb-window {
                position:fixed; bottom:104px; ${launcherPos==='left'?'left:28px':'right:28px'}; z-index:9998;
                width:${winWidth}px; height:${winHeight}px; background:${winBg};
                border-radius:20px; border:1px solid rgba(255,255,255,.08);
                box-shadow:0 24px 80px rgba(0,0,0,.5);
                display:flex; flex-direction:column; overflow:hidden;
                transform:scale(.92) translateY(16px); opacity:0;
                transform-origin:bottom right; pointer-events:none;
                transition:transform .3s cubic-bezier(.34,1.56,.64,1),opacity .25s;
            }
            #cb-window.open { transform:scale(1) translateY(0); opacity:1; pointer-events:all; }

            #cb-header {
                padding:${headerPad}px 18px;
                background:linear-gradient(135deg,${hbg1},${hbg2});
                border-bottom:1px solid rgba(255,255,255,.06);
                display:flex; align-items:center; gap:12px; flex-shrink:0;
            }
            #cb-avatar {
                width:38px; height:38px; border-radius:50%;
                background:linear-gradient(135deg,${c1},${c2});
                display:flex; align-items:center; justify-content:center;
                flex-shrink:0; box-shadow:0 0 0 2px ${c1}55; overflow:hidden; padding:0;
            }
            #cb-header-name { font-size:14px; font-weight:500; color:#f0f0f0; }
            #cb-header-status { font-size:11px; color:#4ade80; display:flex; align-items:center; gap:5px; margin-top:2px; }
            #cb-header-status::before { content:''; width:6px; height:6px; border-radius:50%; background:#4ade80; display:inline-block; }
            #cb-close-btn { margin-left:auto; background:rgba(255,255,255,.07); border:none; border-radius:8px; color:rgba(255,255,255,.5); cursor:pointer; padding:6px; display:flex; align-items:center; justify-content:center; transition:background .15s,color .15s; }
            #cb-close-btn:hover { background:rgba(255,255,255,.13); color:#fff; }
            #cb-user-tag { font-size:10px; color:rgba(255,255,255,.45); margin-top:1px; display:flex; align-items:center; gap:4px; }
            #cb-user-tag::before { content:''; width:5px; height:5px; border-radius:50%; background:${c1}; display:inline-block; }

            /* ── Messages ── */
            #cb-messages {
                flex:1; overflow-y:auto; padding:10px 12px 6px;
                display:flex; flex-direction:column; gap:${msgGap}px;
                scrollbar-width:thin; scrollbar-color:rgba(255,255,255,.1) transparent;
            }
            #cb-messages::-webkit-scrollbar { width:4px; }
            #cb-messages::-webkit-scrollbar-thumb { background:rgba(255,255,255,.1); border-radius:4px; }

            .cb-msg { display:flex; gap:8px; align-items:flex-end; animation:msg-in .3s cubic-bezier(.34,1.56,.64,1); }
            @keyframes msg-in { from{opacity:0;transform:translateY(10px) scale(.95)}to{opacity:1;transform:translateY(0) scale(1)} }
            .cb-msg.user { flex-direction:row-reverse; }

            /* Bot message wrapper: constrain width so bubble doesn't sprawl */
            .cb-msg-body { max-width:75%; min-width:0; }

            /* ── Bubbles ── */
            /* Use class-only selectors so padding isn't killed by #cb-root * margin:0 */
            .cb-bubble {
                padding:${bubblePadV}px ${bubblePadH}px;
                border-radius:${bubbleR}px;
                font-size:${fontSize}px;
                line-height:${lineHeight};
                word-break:break-word;
            }
            .cb-msg.bot .cb-bubble {
                background:${botBubbleBg}; color:${botTextColor};
                border-bottom-left-radius:${Math.max(4,Math.round(bubbleR*0.3))}px; border:1px solid rgba(255,255,255,.09);
            }
            .cb-msg.user .cb-bubble {
                max-width:75%;
                background:linear-gradient(135deg,${c1},${c2}); color:${userTextColor};
                border-bottom-right-radius:${Math.max(4,Math.round(bubbleR*0.3))}px; box-shadow:0 4px 16px ${c1}4d;
            }

            /* Markdown resets — explicit so browser defaults don't leak in */
            .cb-bubble p { margin:0 0 7px; padding:0; }
            .cb-bubble p:last-child { margin-bottom:0; }
            .cb-bubble ul,
            .cb-bubble ol { margin:6px 0 3px; padding:0; list-style:none; }
            .cb-bubble ul li { padding:0 0 0 14px; margin:0 0 3px; position:relative; line-height:1.45; }
            .cb-bubble ol { counter-reset:cb-ol; }
            .cb-bubble ol li { padding:0 0 0 20px; margin:0 0 4px; position:relative; line-height:1.45; }
            .cb-bubble ul li:last-child { margin-bottom:0; }
            .cb-bubble ol li:last-child { margin-bottom:0; }
            .cb-bubble ul li::before { content:''; position:absolute; left:2px; top:6px; width:5px; height:5px; border-radius:50%; background:${c1}; }
            .cb-bubble ol li::before { counter-increment:cb-ol; content:counter(cb-ol) "."; position:absolute; left:0; top:0; color:${c1}; font-weight:600; }
            .cb-bubble strong { font-weight:600; color:#fff; }
            .cb-bubble em { font-style:italic; opacity:.85; }
            .cb-bubble a { color:${linkColor}; text-decoration:none; font-weight:500; border-bottom:1px solid ${c1}55; transition:color .15s; }
            .cb-bubble a:hover { color:#fff; }
            .cb-bubble br { display:block; content:''; margin:2px 0; }
            .cb-spacer { height:6px; }

            /* Inline links inside bubble */
            .cb-bubble-links { margin:10px 0 0; padding:8px 0 0; border-top:1px solid rgba(255,255,255,.1); display:flex; flex-direction:column; gap:5px; }
            .cb-bubble-link { display:inline-flex; align-items:center; gap:5px; color:${c1}; font-size:12.5px; font-weight:500; text-decoration:none; transition:color .15s; }
            .cb-bubble-link:hover { color:#fff; }
            .cb-bubble-link svg { flex-shrink:0; }

            /* ── Inline auth form ── */
            .cb-auth-form { min-width:220px; }
            .cb-auth-field { margin-bottom:8px; }
            .cb-auth-input {
                width:100%; background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.15);
                border-radius:8px; padding:8px 11px; color:#f0f0f0; font-size:12.5px;
                font-family:'DM Sans',sans-serif; outline:none; transition:border-color .2s;
            }
            .cb-auth-input:focus { border-color:${c1}; }
            .cb-auth-input::placeholder { color:rgba(255,255,255,.3); }
            .cb-auth-submit {
                flex:1; padding:8px 14px; border:none; border-radius:8px; cursor:pointer;
                background:linear-gradient(135deg,${c1},${c2}); color:#fff;
                font-size:12px; font-weight:600; font-family:'DM Sans',sans-serif; transition:opacity .15s;
            }
            .cb-auth-submit:hover { opacity:.88; }
            .cb-auth-submit:disabled { opacity:.45; cursor:default; }
            .cb-auth-switch {
                padding:8px 12px; border:1px solid rgba(255,255,255,.15); border-radius:8px;
                background:transparent; color:rgba(255,255,255,.55); font-size:11.5px;
                cursor:pointer; font-family:'DM Sans',sans-serif; transition:color .15s,border-color .15s;
                white-space:nowrap;
            }
            .cb-auth-switch:hover { color:#fff; border-color:rgba(255,255,255,.3); }

            /* ── Timestamps ── */
            .cb-ts { font-size:9.5px; color:rgba(255,255,255,.22); text-align:center; padding:2px 0; }

            /* ── Avatar ── */
            .cb-msg-av { width:26px; height:26px; border-radius:50%; background:linear-gradient(135deg,${c1},${c2}); display:flex; align-items:center; justify-content:center; flex-shrink:0; overflow:hidden; padding:0; }

            /* ── Option buttons ── */
            .cb-options {
                display:none; flex-wrap:wrap; gap:8px;
                padding:10px 14px 13px;
                border-top:1px solid rgba(255,255,255,.08); flex-shrink:0;
            }
            .cb-opt-btn {
                padding:8px 18px;
                background:${optBtnColor};
                border:1.5px solid rgba(255,255,255,.22);
                border-radius:${optBtnRadius}px;
                color:rgba(255,255,255,.88);
                font-size:13px; font-weight:500;
                cursor:pointer; font-family:'${fontFamily}',sans-serif;
                transition:background .18s, border-color .18s, color .18s;
                white-space:nowrap; letter-spacing:.01em;
            }
            .cb-opt-btn:hover { background:linear-gradient(135deg,${c1},${c2}); border-color:transparent; color:#fff; }
            .cb-opt-btn:active { opacity:.85; }

            /* ── Typing indicator ── */
            #cb-typing { display:none; align-items:flex-end; gap:8px; padding:0 14px 10px; }
            #cb-typing.show { display:flex; animation:msg-in .3s ease; }
            .cb-typing-bubble { background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.07); border-radius:16px; border-bottom-left-radius:4px; padding:11px 15px; display:flex; gap:5px; align-items:center; }
            .cb-dot-a { width:7px; height:7px; border-radius:50%; background:rgba(255,255,255,.4); animation:typing-b 1.2s infinite; padding:0; }
            .cb-dot-a:nth-child(2){animation-delay:.2s}.cb-dot-a:nth-child(3){animation-delay:.4s}
            @keyframes typing-b{0%,60%,100%{transform:translateY(0);opacity:.4}30%{transform:translateY(-5px);opacity:1}}

            /* ── Input ── */
            #cb-input-area { padding:10px 14px; border-top:1px solid rgba(255,255,255,.06); display:flex; gap:8px; align-items:flex-end; flex-shrink:0; background:rgba(255,255,255,.02); }
            #cb-input { flex:1; background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.09); border-radius:${inputRadius}px; padding:10px 13px; color:#f0f0f0; font-size:${fontSize}px; font-family:'DM Sans',sans-serif; outline:none; resize:none; min-height:42px; max-height:100px; line-height:1.5; transition:border-color .2s,background .2s; }
            #cb-input::placeholder { color:rgba(255,255,255,.25); }
            #cb-input:focus { border-color:${c1}88; background:rgba(255,255,255,.1); }
            #cb-send { width:42px; height:42px; border-radius:12px; border:none; padding:0; cursor:pointer; background:linear-gradient(135deg,${c1},${c2}); display:flex; align-items:center; justify-content:center; flex-shrink:0; box-shadow:0 4px 16px ${c1}4d; transition:transform .2s cubic-bezier(.34,1.56,.64,1),opacity .2s; }
            #cb-send:hover { transform:scale(1.08); }
            #cb-send:active { transform:scale(.95); }
            #cb-send:disabled { opacity:.4; transform:none; cursor:default; }
            #cb-footer { text-align:center; padding:7px; font-size:10px; color:rgba(255,255,255,.16); flex-shrink:0; }
        `;
        document.head.appendChild(style);

        const root = document.createElement('div');
        root.id = 'cb-root';
        const userDisplay = getUserInfo().name || getUserInfo().email || '';
        root.innerHTML = `
            <div id="cb-window">
                <div id="cb-header">
                    <div id="cb-avatar">${getIcon(20)}</div>
                    <div style="flex:1">
                        <div id="cb-header-name">${botName}</div>
                        <div id="cb-header-status">${statusText}</div>
                        ${userDisplay ? `<div id="cb-user-tag">${userDisplay}</div>` : ''}
                    </div>
                    <button id="cb-close-btn">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                            <path d="M12 4L4 12M4 4l8 8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                        </svg>
                    </button>
                </div>
                <div id="cb-messages"></div>
                <div id="cb-typing">
                    <div class="cb-msg-av">${getIcon(14)}</div>
                    <div class="cb-typing-bubble">
                        <div class="cb-dot-a"></div><div class="cb-dot-a"></div><div class="cb-dot-a"></div>
                    </div>
                </div>
                <div id="cb-options-bar" class="cb-options" style="display:none"></div>
                <div id="cb-input-area">
                    <textarea id="cb-input" placeholder="${placeholder}" rows="1"></textarea>
                    <button id="cb-send">
                        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                            <path d="M15.5 9L3 2.5l2.5 6.5L3 15.5 15.5 9z" fill="white"/>
                        </svg>
                    </button>
                </div>
                <div id="cb-footer">${footerTxt} · ${botName}</div>
            </div>
            <button id="cb-launcher">
                <div id="cb-online-dot"></div>
                <svg class="icon-chat" width="26" height="26" viewBox="0 0 26 26" fill="none">
                    <path d="M13 2C7.477 2 3 6.03 3 11c0 2.5 1.1 4.76 2.89 6.39L5 22l4.5-2.25A11.3 11.3 0 0013 20c5.523 0 10-4.03 10-9S18.523 2 13 2z" fill="white" opacity=".92"/>
                </svg>
                <svg class="icon-close" width="22" height="22" viewBox="0 0 22 22" fill="none">
                    <path d="M17 5L5 17M5 5l12 12" stroke="white" stroke-width="2.2" stroke-linecap="round"/>
                </svg>
            </button>
        `;
        document.body.appendChild(root);

        const win       = document.getElementById('cb-window');
        const launcher  = document.getElementById('cb-launcher');
        const msgs      = document.getElementById('cb-messages');
        const input     = document.getElementById('cb-input');
        const sendBtn   = document.getElementById('cb-send');
        const typingEl  = document.getElementById('cb-typing');
        const closeBtn  = document.getElementById('cb-close-btn');
        const optBar    = document.getElementById('cb-options-bar');

        let isOpen = false, welcomed = false, isSending = false;
        // Conversation history kept locally for context
        const history = [];

        function toggleChat() {
            isOpen = !isOpen;
            win.classList.toggle('open', isOpen);
            launcher.classList.toggle('open', isOpen);
            if (isOpen && !welcomed) {
                const personalGreeting = getUserInfo().name
                    ? greeting.replace('Hi!', `Hi ${getUserInfo().name}!`)
                    : greeting;
                setTimeout(() => addBotMessage(personalGreeting, [], []), 350);
                welcomed = true;
            }
            if (isOpen) setTimeout(() => input.focus(), 300);
        }
        launcher.onclick = toggleChat;
        closeBtn.onclick = toggleChat;

        // Auto-open after delay if configured
        if (autoOpenDelay > 0) {
            setTimeout(() => { if (!isOpen) toggleChat(); }, autoOpenDelay * 1000);
        }

        function ts() {
            if (!showTs) return '';
            const d = new Date();
            return `<div class="cb-ts">${d.getHours()}:${String(d.getMinutes()).padStart(2,'0')}</div>`;
        }

        function addUserMessage(text) {
            clearOptions();
            const div = document.createElement('div');
            div.className = 'cb-msg user';
            div.innerHTML = `${ts()}<div class="cb-bubble"></div>`;
            div.querySelector('.cb-bubble').textContent = text;
            msgs.appendChild(div);
            msgs.scrollTop = msgs.scrollHeight;
        }

        function addBotMessage(text, options, links) {
            const div = document.createElement('div');
            div.className = 'cb-msg bot';
            const av = document.createElement('div');
            av.className = 'cb-msg-av';
            av.innerHTML = getIcon(14);
            const right = document.createElement('div');
            right.className = 'cb-msg-body';

            const bubble = document.createElement('div');
            bubble.className = 'cb-bubble';
            bubble.innerHTML = formatMessageHtml(text);
            right.appendChild(bubble);

            // Inline links inside the bubble
            if (links && links.length) {
                const ldiv = document.createElement('div');
                ldiv.className = 'cb-bubble-links';
                links.forEach(l => {
                    const a = document.createElement('a');
                    a.className = 'cb-bubble-link';
                    a.href = l.url; a.target = '_blank'; a.rel = 'noopener';
                    a.innerHTML = `<svg width="11" height="11" viewBox="0 0 11 11" fill="none"><path d="M1.5 9.5L9.5 1.5M9.5 1.5H5M9.5 1.5V6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>${l.label}`;
                    ldiv.appendChild(a);
                });
                bubble.appendChild(ldiv);
            }

            div.appendChild(av);
            div.appendChild(right);
            if (ts()) {
                const t = document.createElement('div');
                t.innerHTML = ts();
                div.prepend(t);
            }
            msgs.appendChild(div);
            msgs.scrollTop = msgs.scrollHeight;

            // Show option buttons
            if (options && options.length) {
                showOptions(options);
            }
        }

        function showOptions(options) {
            optBar.innerHTML = '';
            optBar.style.display = 'flex';
            options.forEach(opt => {
                const btn = document.createElement('button');
                btn.className = 'cb-opt-btn';
                btn.textContent = opt;
                const lc = opt.toLowerCase();

                // Auth interceptions
                if (lc === 'log in' || lc === 'sign in') {
                    btn.onclick = () => showInlineAuth('login');
                } else if (lc === 'sign up' || lc === 'create account') {
                    btn.onclick = () => showInlineAuth('signup');

                // Order confirmation — gate on login state
                } else if (lc === 'yes, order this' || lc === 'yes order this' || lc === 'confirm order' || lc === 'yes, confirm order' || lc === 'place order') {
                    btn.onclick = () => {
                        if (!getUserInfo().email) {
                            clearOptions();
                            addBotMessage('You need to be logged in to place an order.', ['Log In', 'Sign Up'], []);
                        } else {
                            sendMessage(opt);
                        }
                    };
                } else {
                    btn.onclick = () => sendMessage(opt);
                }
                optBar.appendChild(btn);
            });
        }

        function clearOptions() {
            optBar.innerHTML = '';
            optBar.style.display = 'none';
        }

        // ── Inline auth forms ─────────────────────────────────
        function showInlineAuth(mode) {
            clearOptions();
            const isLogin = mode === 'login';
            const formId = 'cb-inline-auth-' + Date.now();

            const div = document.createElement('div');
            div.className = 'cb-msg bot';

            const av = document.createElement('div');
            av.className = 'cb-msg-av';
            av.innerHTML = getIcon(14);

            const body = document.createElement('div');
            body.className = 'cb-msg-body';

            const form = document.createElement('div');
            form.className = 'cb-bubble cb-auth-form';
            form.id = formId;
            form.innerHTML = `
                <div style="font-weight:600;margin-bottom:10px;font-size:13px">${isLogin ? 'Sign In' : 'Create Account'}</div>
                ${!isLogin ? `
                <div class="cb-auth-field">
                  <input class="cb-auth-input" type="text" placeholder="Full name" id="${formId}-name">
                </div>` : ''}
                <div class="cb-auth-field">
                  <input class="cb-auth-input" type="email" placeholder="Email address" id="${formId}-email">
                </div>
                <div class="cb-auth-field">
                  <input class="cb-auth-input" type="password" placeholder="Password" id="${formId}-pass">
                </div>
                ${!isLogin ? `
                <div class="cb-auth-field">
                  <input class="cb-auth-input" type="password" placeholder="Confirm password" id="${formId}-pass2">
                </div>` : ''}
                <div id="${formId}-err" style="color:#f87171;font-size:11px;margin:6px 0;display:none"></div>
                <div style="display:flex;gap:8px;margin-top:10px">
                  <button class="cb-auth-submit" id="${formId}-btn" onclick="cbSubmitAuth('${formId}','${mode}')">
                    ${isLogin ? 'Sign In' : 'Create Account'}
                  </button>
                  <button class="cb-auth-switch" onclick="cbSwitchAuth('${formId}','${isLogin?'signup':'login'}')">
                    ${isLogin ? 'Sign up instead' : 'Sign in instead'}
                  </button>
                </div>`;

            body.appendChild(form);
            div.appendChild(av);
            div.appendChild(body);
            msgs.appendChild(div);
            msgs.scrollTop = msgs.scrollHeight;

            // Focus first input
            setTimeout(() => {
                const first = document.getElementById(isLogin ? `${formId}-email` : `${formId}-name`);
                if (first) first.focus();
            }, 100);
        }

        // Expose auth handlers globally so onclick can reach them
        window.cbSubmitAuth = async function(formId, mode) {
            const errEl = document.getElementById(formId + '-err');
            const btn   = document.getElementById(formId + '-btn');
            errEl.style.display = 'none';

            const email = (document.getElementById(formId + '-email')?.value || '').trim();
            const pass  = (document.getElementById(formId + '-pass')?.value  || '');

            if (!email || !pass) { errEl.textContent = 'Please fill in all fields.'; errEl.style.display = 'block'; return; }

            btn.disabled = true; btn.textContent = mode === 'login' ? 'Signing in...' : 'Creating account...';

            try {
                let res, data;
                if (mode === 'login') {
                    res  = await fetch(`${apiBase}/auth/login`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({email, password: pass}) });
                    data = await res.json();
                } else {
                    const name  = (document.getElementById(formId + '-name')?.value  || '').trim();
                    const pass2 = (document.getElementById(formId + '-pass2')?.value || '');
                    if (!name)         { errEl.textContent = 'Please enter your name.'; errEl.style.display = 'block'; btn.disabled=false; btn.textContent='Create Account'; return; }
                    if (pass !== pass2) { errEl.textContent = 'Passwords do not match.'; errEl.style.display = 'block'; btn.disabled=false; btn.textContent='Create Account'; return; }
                    if (pass.length < 8){ errEl.textContent = 'Password must be 8+ characters.'; errEl.style.display = 'block'; btn.disabled=false; btn.textContent='Create Account'; return; }
                    res  = await fetch(`${apiBase}/auth/register`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name, email, password: pass}) });
                    data = await res.json();
                }

                if (!res.ok || data.error) {
                    errEl.textContent = data.error || 'Something went wrong.';
                    errEl.style.display = 'block';
                    btn.disabled = false;
                    btn.textContent = mode === 'login' ? 'Sign In' : 'Create Account';
                    return;
                }

                // Success — update widget user state
                const user = data.user;
                localStorage.setItem('acme_token', data.token);
                localStorage.setItem('acme_user', JSON.stringify(user));
                _userInfo = { name: user.name||'', email: user.email||'', address: user.address||'', user_id: user.id||'' };
                if (window.acmeWidget) window.acmeWidget.setUser(user);

                // Notify the host page so its nav/auth state updates too
                window.dispatchEvent(new CustomEvent('acme:login', { detail: { user, token: data.token } }));

                // Replace form with success message
                const formEl = document.getElementById(formId);
                if (formEl) {
                    formEl.innerHTML = `<span style="color:#4ade80;font-size:13px">✓ Signed in as <strong>${user.name}</strong>. You can now place your order.</span>`;
                }

                // Auto-send a follow-up so the bot knows the user is now logged in
                // Include a snapshot of the history so the bot remembers what was being ordered
                setTimeout(() => sendMessage('I am now logged in. Please continue where we left off.'), 600);

            } catch(e) {
                errEl.textContent = 'Could not reach server.';
                errEl.style.display = 'block';
                btn.disabled = false;
                btn.textContent = mode === 'login' ? 'Sign In' : 'Create Account';
            }
        };

        window.cbSwitchAuth = function(oldFormId, newMode) {
            const formEl = document.getElementById(oldFormId);
            if (formEl) {
                const wrap = formEl.closest('.cb-msg-body');
                if (wrap) wrap.remove();
            }
            showInlineAuth(newMode);
        };

        function unlock() {
            isSending = false;
            sendBtn.disabled = false;
            typingEl.classList.remove('show');
            input.focus();
        }

        input.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 100) + 'px';
        });

        async function sendMessage(overrideText) {
            const text = (overrideText || input.value).trim();
            if (!text || isSending) return;

            const lc = text.toLowerCase();

            // ── Client-side login/signup intent interception ──────────────
            // If the user types login-related text, show the inline form immediately
            // without sending to the LLM (prevents hallucination + circular loops).
            const loginTriggers  = ['log in','login','sign in','signin','i want to login','i want to log in','login please','please log in'];
            const signupTriggers = ['sign up','signup','register','create account','create an account','i want to sign up','new account'];

            const isLoginIntent  = loginTriggers.some(t => lc === t || lc.startsWith(t + ' ') || lc.endsWith(' ' + t));
            const isSignupIntent = signupTriggers.some(t => lc === t || lc.startsWith(t + ' ') || lc.endsWith(' ' + t));

            if (isLoginIntent || isSignupIntent) {
                if (!overrideText) { input.value = ''; input.style.height = 'auto'; }
                clearOptions();
                addUserMessage(text);
                setTimeout(() => showInlineAuth(isSignupIntent ? 'signup' : 'login'), 200);
                return;
            }

            // ── Order confirmation gate: block if not logged in ───────────
            const orderConfirmTriggers = ['yes, order this','yes order this','confirm order','yes, confirm order','place order','order now','place the order'];
            const isOrderConfirm = orderConfirmTriggers.some(t => lc === t);
            if (isOrderConfirm && !getUserInfo().email) {
                if (!overrideText) { input.value = ''; input.style.height = 'auto'; }
                clearOptions();
                addUserMessage(text);
                setTimeout(() => addBotMessage('You need to be logged in to place an order.', ['Log In', 'Sign Up'], []), 200);
                return;
            }
            // ─────────────────────────────────────────────────────────────

            isSending = true;
            sendBtn.disabled = true;
            clearOptions();
            addUserMessage(text);
            if (!overrideText) { input.value = ''; input.style.height = 'auto'; }
            typingEl.classList.add('show');
            msgs.scrollTop = msgs.scrollHeight;

            // Add to history
            history.push({ role: 'user', content: text });

            try {
                const res = await fetch(`${apiBase}/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        site_id:   siteId,
                        message:   text,
                        user_info: getUserInfo(),
                        history:   history.slice(-10)  // last 10 turns
                    })
                });
                const data = await res.json();
                const replyText = data.message || 'No response received.';
                addBotMessage(replyText, data.options || [], data.links || []);
                // Add assistant reply to history
                history.push({ role: 'assistant', content: replyText });
            } catch (err) {
                addBotMessage('Sorry, I had trouble connecting. Please try again.', [], []);
                console.error('Chat error:', err);
            }

            unlock();
        }

        sendBtn.onclick = () => sendMessage();
        input.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
        });
    }
})();
