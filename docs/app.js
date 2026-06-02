// app.js - 修仙资料库 SPA v2

const DATA = {};
const CACHE = {};

// ===================== Utilities =====================

function formatNum(n) {
    if (n === null || n === undefined) return '-';
    if (typeof n !== 'number') return String(n);
    if (n === 0) return '0';
    const abs = Math.abs(n);
    if (abs >= 1e12) return (n / 1e8).toFixed(0) + '亿';
    if (abs >= 1e8) return (n / 1e8).toFixed(n % 1e8 === 0 ? 0 : 1) + '亿';
    if (abs >= 1e4) return (n / 1e4).toFixed(n % 1e4 === 0 ? 0 : 1) + '万';
    if (abs >= 1e3) return n.toLocaleString();
    return String(n);
}

function formatRate(r) {
    if (r === null || r === undefined) return '-';
    if (typeof r !== 'number') return String(r);
    if (r >= 1) return '100%';
    return (r * 100).toFixed(r * 100 === Math.floor(r * 100) ? 0 : 1) + '%';
}

function formatPercent(n) {
    if (typeof n !== 'number') return String(n);
    return (n * 100).toFixed(0) + '%';
}

function formatSpecialAttrs(w) {
    const parts = [];
    if (w.dodge_rate) parts.push('闪避' + w.dodge_rate + '%');
    if (w.crit_resist) parts.push('抗会心' + w.crit_resist + '%');
    if (w.reflect_pct) parts.push('反伤' + w.reflect_pct + '%');
    if (w.block_value) parts.push('格挡' + w.block_value);
    if (w.hp_regen_pct) parts.push('回复' + w.hp_regen_pct + '%');
    return parts.length ? parts.join('、') : '-';
}

function rankClass(rank) {
    if (!rank) return '';
    return 'rank-' + rank;
}

function rankOrder(rank) {
    const order = ['凡品','灵品','地品','天品','皇品','帝品','道品','仙品','混元先天'];
    const idx = order.indexOf(rank);
    return idx >= 0 ? idx : 99;
}

function getRankGlowClass(rank) {
    if (!rank) return '';
    if (/后天|先天|凡品/.test(rank)) return 'rank-mortal';
    if (/神丹|虚劫|灵品|地品/.test(rank)) return 'rank-spirit';
    if (/神海|神劫|神变|界主|天尊|天品|皇品/.test(rank)) return 'rank-heaven';
    if (/真神|荒神|帝品|道品/.test(rank)) return 'rank-god';
    if (/圣人|永恒|限定|仙品|混元先天/.test(rank)) return 'rank-holy';
    return '';
}

function esc(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function makeRankBadge(rank) {
    return `<span class="rank-badge ${rankClass(rank)}">${esc(rank)}</span>`;
}

function levelName(idx) {
    const levels = DATA.level_config || [];
    const bodyLevels = DATA.body_level_config || [];
    const names = [];
    if (idx < levels.length) names.push(levels[idx].level_name);
    if (idx < bodyLevels.length && bodyLevels[idx]?.level_name !== levels[idx]?.level_name) names.push(bodyLevels[idx].level_name);
    return names.join(' / ') || 'Lv' + idx;
}

function fmtDuration(seconds) {
    if (!seconds) return '-';
    const m = Math.round(seconds / 60);
    if (m < 60) return m + '分钟';
    const h = Math.floor(m / 60);
    const rm = m % 60;
    return rm ? h + '小时' + rm + '分' : h + '小时';
}

// ===================== Data Loading =====================

async function loadJSON(name) {
    if (CACHE[name]) return CACHE[name];
    const resp = await fetch(`data/${name}.json`);
    const json = await resp.json();
    CACHE[name] = json;
    return json;
}

async function loadAllData() {
    const files = [
        'level_config', 'body_level_config', 'pills', 'exp_pills',
        'utility_pills', 'items', 'weapons', 'storage_rings',
        'alchemy_recipes', 'adventure_config', 'bounty_templates', 'game_config',
        'skills', 'spiritual_roots'
    ];
    const promises = files.map(async f => {
        try {
            DATA[f] = await loadJSON(f);
        } catch (e) {
            console.warn(`Failed to load ${f}:`, e);
            DATA[f] = [];
        }
    });
    await Promise.all(promises);
}

// ===================== Navigation =====================

// 滚动浮现观察器
const cardObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
        }
    });
}, {
    rootMargin: '0px 0px -50px 0px',
    threshold: 0.1
});

function observeCards(container) {
    container.querySelectorAll('.item-card').forEach(card => cardObserver.observe(card));
}

function showPage(pageName) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    const page = document.getElementById('page-' + pageName);
    const link = document.querySelector(`.nav-link[data-page="${pageName}"]`);
    if (page) page.classList.add('active');
    if (link) link.classList.add('active');
    if (!page.dataset.rendered) {
        renderPage(pageName);
        page.dataset.rendered = 'true';
        observeCards(page);
    }
}

// ===================== Table Helpers =====================

function createTable(headers, rows, options = {}) {
    const { sortable = true, onRowClick, emptyText = '暂无数据', rankData } = options;
    if (rows.length === 0) {
        return `<div class="table-wrapper"><div style="padding:24px;text-align:center;color:var(--text-muted)">${emptyText}</div></div>`;
    }
    let html = '<div class="table-wrapper"><table class="data-table"><thead><tr>';
    headers.forEach((h, i) => {
        const sortAttr = sortable ? ` data-col="${i}"` : '';
        const cls = sortable ? ' class="sortable-header"' : '';
        html += `<th${cls}${sortAttr}>${esc(h)}${sortable ? '<span class="sort-arrow">&#9650;</span>' : ''}</th>`;
    });
    html += '</tr></thead><tbody>';
    rows.forEach((row, ri) => {
        const glowCls = rankData && rankData[ri] ? getRankGlowClass(rankData[ri]) : '';
        const clickAttr = onRowClick ? ' class="clickable' + (glowCls ? ' ' + glowCls : '') + `" data-row="${ri}"` : (glowCls ? ` class="${glowCls}"` : '');
        html += `<tr${clickAttr}>`;
        row.forEach(cell => { html += `<td>${cell}</td>`; });
        html += '</tr>';
    });
    html += '</tbody></table></div>';
    return html;
}

function makeTableSortable(container) {
    container.querySelectorAll('.sortable-header').forEach(th => {
        th.addEventListener('click', () => {
            const table = th.closest('table');
            const tbody = table.querySelector('tbody');
            const col = parseInt(th.dataset.col);
            const rows = Array.from(tbody.rows);
            const isAsc = th.classList.contains('sorted') && th.dataset.dir === 'asc';
            table.querySelectorAll('th').forEach(h => { h.classList.remove('sorted'); h.dataset.dir = ''; });
            th.classList.add('sorted');
            th.dataset.dir = isAsc ? 'desc' : 'asc';
            rows.sort((a, b) => {
                const aVal = a.cells[col].dataset.sortvalue || a.cells[col].textContent.trim();
                const bVal = b.cells[col].dataset.sortvalue || b.cells[col].textContent.trim();
                const aNum = parseFloat(aVal);
                const bNum = parseFloat(bVal);
                let cmp = (!isNaN(aNum) && !isNaN(bNum)) ? aNum - bNum : aVal.localeCompare(bVal, 'zh');
                return isAsc ? -cmp : cmp;
            });
            rows.forEach(r => tbody.appendChild(r));
        });
    });
}

// ===================== Modal =====================

function showModal(title, html) {
    const modal = document.getElementById('detail-modal');
    const content = modal.querySelector('.modal-content');
    content.className = 'modal-content';
    document.getElementById('modal-body').innerHTML = `<div class="modal-title">${title}</div>${html}`;
    modal.classList.remove('hidden');
}

function hideModal() {
    document.getElementById('detail-modal').classList.add('hidden');
}

function setupModal() {
    document.querySelector('.modal-close').addEventListener('click', hideModal);
    document.querySelector('.modal-overlay').addEventListener('click', hideModal);
}

function modalField(label, value) {
    return `<div class="modal-field"><span class="label">${esc(label)}</span><span class="value">${value}</span></div>`;
}

function modalSection(title, content) {
    return `<div class="modal-section"><div class="modal-section-title">${esc(title)}</div>${content}</div>`;
}

// ===================== Overview =====================

function renderOverview() {
    const page = document.getElementById('page-overview');
    const levels = DATA.level_config || [];
    const bodyLevels = DATA.body_level_config || [];
    const pills = DATA.pills || [];
    const expPills = DATA.exp_pills || [];
    const utilPills = DATA.utility_pills || [];
    const weapons = DATA.weapons || [];
    const itemsObj = DATA.items || {};
    const items = Object.values(itemsObj);
    const rings = DATA.storage_rings || {};
    const recipes = DATA.alchemy_recipes || [];

    const weaponsOnly = weapons.filter(w => w.type === 'weapon');
    const armorsOnly = weapons.filter(w => w.type === 'armor');
    const techniques = items.filter(i => i.type === 'main_technique');
    const subTechniques = items.filter(i => i.type === 'technique');
    const oldPills = items.filter(i => i.type === '丹药');
    const materials = items.filter(i => i.type === '材料');
    const artifacts = items.filter(i => i.type === '法器');
    const manuals = items.filter(i => i.type === '功法');
    const ringCount = typeof rings === 'object' && !Array.isArray(rings) ? Object.keys(rings).length : (Array.isArray(rings) ? rings.length : 0);
    const recipeCount = Array.isArray(recipes) ? recipes.length : 0;

    const permPills = utilPills.filter(p => p.effect_type === 'permanent');
    const tempPills = utilPills.filter(p => p.effect_type === 'temporary');
    const instantPills = utilPills.filter(p => p.effect_type === 'instant');
    const rootsData = DATA.spiritual_roots || [];
    const rootCount = rootsData.reduce((sum, r) => sum + r.roots.length, 0);

    page.innerHTML = `
        <h2 class="page-title">总览</h2>
        <div class="info-box">
            <strong>模拟修仙2</strong> 是一款功能丰富的修仙模拟游戏插件，包含 <strong>30+</strong> 个游戏系统、<strong>80+</strong> 条指令。
            本资料库汇总了所有数值配置，方便查阅与平衡性分析。
        </div>
        <h3 class="section-title">数据统计</h3>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value">${levels.length + bodyLevels.length}</div><div class="stat-label">境界总数</div></div>
            <div class="stat-card"><div class="stat-value">${pills.length}</div><div class="stat-label">突破丹药</div></div>
            <div class="stat-card"><div class="stat-value">${expPills.length}</div><div class="stat-label">修为丹药</div></div>
            <div class="stat-card"><div class="stat-value">${utilPills.length}</div><div class="stat-label">功能丹药</div></div>
            <div class="stat-card"><div class="stat-value">${weaponsOnly.length}</div><div class="stat-label">武器</div></div>
            <div class="stat-card"><div class="stat-value">${armorsOnly.length}</div><div class="stat-label">防具</div></div>
            <div class="stat-card"><div class="stat-value">${techniques.length}</div><div class="stat-label">主修心法</div></div>
            <div class="stat-card"><div class="stat-value">${subTechniques.length}</div><div class="stat-label">辅助功法</div></div>
            <div class="stat-card"><div class="stat-value">${ringCount}</div><div class="stat-label">储物戒</div></div>
            <div class="stat-card"><div class="stat-value">${recipeCount}</div><div class="stat-label">炼丹配方</div></div>
            <div class="stat-card"><div class="stat-value">${materials.length}</div><div class="stat-label">材料</div></div>
            <div class="stat-card"><div class="stat-value">${oldPills.length + artifacts.length + manuals.length}</div><div class="stat-label">旧系统道具</div></div>
            <div class="stat-card"><div class="stat-value">${rootCount}</div><div class="stat-label">灵根</div></div>
        </div>
        <h3 class="section-title">丹药分布</h3>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value num-green">${permPills.length}</div><div class="stat-label">永久属性丹</div></div>
            <div class="stat-card"><div class="stat-value num-cyan">${tempPills.length}</div><div class="stat-label">临时增益丹</div></div>
            <div class="stat-card"><div class="stat-value num-gold">${instantPills.length}</div><div class="stat-label">瞬时效果丹</div></div>
        </div>
        <h3 class="section-title">品阶体系</h3>
        <div class="info-box">
            凡品 → 灵品 → 地品 → 天品 → 皇品 → 帝品 → 道品 → 仙品 → 混元先天<br>
            共 <strong>9</strong> 个品阶，覆盖从凡人到混元先天的全部修仙之路。
        </div>
    `;
}

// ===================== Levels =====================

function renderLevels() {
    const page = document.getElementById('page-levels');
    page.innerHTML = `
        <h2 class="page-title">境界系统</h2>
        <div class="sub-tabs">
            <div class="sub-tab active" data-level-type="spiritual">灵修境界 (${(DATA.level_config || []).length}层)</div>
            <div class="sub-tab" data-level-type="body">体修境界 (${(DATA.body_level_config || []).length}层)</div>
        </div>
        <div id="levels-content"></div>
    `;
    const tabs = page.querySelectorAll('.sub-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            renderLevelTable(tab.dataset.levelType);
        });
    });
    renderLevelTable('spiritual');
}

function renderLevelTable(type) {
    const container = document.getElementById('levels-content');
    const data = type === 'spiritual' ? (DATA.level_config || []) : (DATA.body_level_config || []);
    const isQiRefine = type === 'spiritual';

    const headers = ['#', '境界名称', '所需修为', '基础成功率', '突破寿命', '突破精神力',
        isQiRefine ? '突破灵气' : '突破气血',
        '突破物伤', '突破法伤', '突破物防', '突破法防'];

    const rows = data.map((lv, i) => [
        `<span data-sortvalue="${i}">${i}</span>`,
        `<strong>${esc(lv.level_name)}</strong>`,
        `<span data-sortvalue="${lv.exp_needed}">${formatNum(lv.exp_needed)}</span>`,
        `<span data-sortvalue="${lv.success_rate}">${formatRate(lv.success_rate)}</span>`,
        `<span data-sortvalue="${lv.breakthrough_lifespan_gain || 0}">${formatNum(lv.breakthrough_lifespan_gain || 0)}</span>`,
        `<span data-sortvalue="${lv.breakthrough_mental_power_gain || 0}">${formatNum(lv.breakthrough_mental_power_gain || 0)}</span>`,
        isQiRefine
            ? `<span data-sortvalue="${lv.breakthrough_spiritual_qi_gain || 0}">${formatNum(lv.breakthrough_spiritual_qi_gain || 0)}</span>`
            : `<span data-sortvalue="${lv.breakthrough_blood_qi_gain || 0}">${formatNum(lv.breakthrough_blood_qi_gain || 0)}</span>`,
        `<span data-sortvalue="${lv.breakthrough_physical_damage_gain || 0}">${formatNum(lv.breakthrough_physical_damage_gain || 0)}</span>`,
        `<span data-sortvalue="${lv.breakthrough_magic_damage_gain || 0}">${formatNum(lv.breakthrough_magic_damage_gain || 0)}</span>`,
        `<span data-sortvalue="${lv.breakthrough_physical_defense_gain || 0}">${formatNum(lv.breakthrough_physical_defense_gain || 0)}</span>`,
        `<span data-sortvalue="${lv.breakthrough_magic_defense_gain || 0}">${formatNum(lv.breakthrough_magic_defense_gain || 0)}</span>`
    ]);

    container.innerHTML = createTable(headers, rows);
    makeTableSortable(container);
}

// ===================== Pills =====================

function renderPills() {
    const page = document.getElementById('page-pills');
    page.classList.add('scroll-wide');
    page.innerHTML = `
        <h2 class="page-title">丹药系统</h2>
        <div class="sub-tabs" id="pills-tabs">
            <div class="sub-tab active" data-pill-tab="breakthrough">突破丹 (${(DATA.pills || []).length})</div>
            <div class="sub-tab" data-pill-tab="exp">修为丹 (${(DATA.exp_pills || []).length})</div>
            <div class="sub-tab" data-pill-tab="utility">功能丹 (${(DATA.utility_pills || []).length})</div>
            <div class="sub-tab" data-pill-tab="legacy">传统丹药</div>
        </div>
        <div id="pills-content"></div>
    `;
    const tabs = page.querySelectorAll('.sub-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            renderPillTab(tab.dataset.pillTab);
        });
    });
    renderPillTab('breakthrough');
}

function renderPillTab(tab) {
    const container = document.getElementById('pills-content');
    switch (tab) {
        case 'breakthrough': renderBreakthroughPills(container); break;
        case 'exp': renderExpPills(container); break;
        case 'utility': renderUtilityPills(container); break;
        case 'legacy': renderLegacyPills(container); break;
    }
}

function renderBreakthroughPills(container) {
    const pills = DATA.pills || [];

    const headers = ['ID', '名称', '品阶', '价格', '突破路径', '突破加成', '最高成功率'];
    const rows = pills.map(p => {
        const fromLv = levelName(p.required_level_index);
        const toLv = levelName(p.target_level_index);
        return [
            `<code>${esc(p.id)}</code>`,
            `<strong>${esc(p.name)}</strong>`,
            makeRankBadge(p.rank),
            `<span data-sortvalue="${p.price}">${formatNum(p.price)}</span>`,
            `<span class="level-path">${esc(fromLv)} <span class="level-arrow">&rarr;</span> ${esc(toLv)}</span>`,
            `<span data-sortvalue="${p.breakthrough_bonus}">+${formatRate(p.breakthrough_bonus)}</span>`,
            `<span data-sortvalue="${p.max_success_rate}">${formatRate(p.max_success_rate)}</span>`
        ];
    });

    const rankData = pills.map(p => p.rank);
    container.innerHTML = createTable(headers, rows, { rankData });
    makeTableSortable(container);
    addPillRowClicks(container, pills, 'breakthrough');
}

function renderExpPills(container) {
    const pills = DATA.exp_pills || [];
    const headers = ['ID', '名称', '品阶', '价格', '修为增益', '最低境界'];
    const rows = pills.map(p => [
        `<code>${esc(p.id)}</code>`,
        `<strong>${esc(p.name)}</strong>`,
        makeRankBadge(p.rank),
        `<span data-sortvalue="${p.price}">${formatNum(p.price)}</span>`,
        `<span data-sortvalue="${p.exp_gain}" class="num-green">+${formatNum(p.exp_gain)}</span>`,
        esc(levelName(p.required_level_index))
    ]);

    const rankData = pills.map(p => p.rank);
    container.innerHTML = createTable(headers, rows, { rankData });
    makeTableSortable(container);
    addPillRowClicks(container, pills, 'exp');
}

function renderUtilityPills(container) {
    const pills = DATA.utility_pills || [];
    const subtypeGroups = {};
    const subtypeLabels = {
        'resurrection': '复活丹', 'cultivation_boost': '修炼加速丹',
        'permanent_attribute': '永久属性丹', 'combat_boost': '战斗临时丹·进攻',
        'defensive_boost': '战斗临时丹·防御', 'instant_restore': '瞬回丹',
        'regeneration': '回复丹', 'breakthrough_boost': '突破辅助丹',
        'breakthrough_debuff': '突破负面丹', 'special': '特殊丹药',
        'reset': '重置丹', 'protection': '防护丹', 'chaos_boost': '随机丹',
        'debuff': '负面丹', 'buff': '增益丹'
    };

    pills.forEach(p => {
        const sub = p.subtype || 'other';
        if (!subtypeGroups[sub]) subtypeGroups[sub] = [];
        subtypeGroups[sub].push(p);
    });

    let filterHtml = '<div class="filter-bar"><span class="filter-label">品阶：</span>';
    const ranks = [...new Set(pills.map(p => p.rank))].sort((a, b) => rankOrder(a) - rankOrder(b));
    filterHtml += '<button class="filter-btn active" data-rank="all">全部</button>';
    ranks.forEach(r => { filterHtml += `<button class="filter-btn" data-rank="${esc(r)}">${esc(r)}</button>`; });
    filterHtml += '</div>';

    let html = filterHtml;
    const order = ['cultivation_boost', 'permanent_attribute', 'resurrection', 'combat_boost', 'defensive_boost',
        'instant_restore', 'regeneration', 'breakthrough_boost', 'breakthrough_debuff',
        'special', 'reset', 'protection', 'chaos_boost', 'debuff', 'buff'];

    const sortedSubtypes = Object.keys(subtypeGroups).sort((a, b) => {
        const ai = order.indexOf(a), bi = order.indexOf(b);
        return (ai >= 0 ? ai : 99) - (bi >= 0 ? bi : 99);
    });

    sortedSubtypes.forEach(sub => {
        const group = subtypeGroups[sub];
        const label = subtypeLabels[sub] || sub;
        html += `<h3 class="section-title">${esc(label)} (${group.length}种)</h3>`;
        html += renderUtilityPillTable(group);
    });

    container.innerHTML = html;

    container.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            container.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const rank = btn.dataset.rank;
            container.querySelectorAll('.data-table tbody tr').forEach(row => {
                if (rank === 'all') { row.style.display = ''; }
                else {
                    const badge = row.querySelector('.rank-badge');
                    row.style.display = (badge && badge.textContent === rank) ? '' : 'none';
                }
            });
        });
    });

    makeTableSortable(container);
    addPillRowClicks(container, pills, 'utility');
}

function renderUtilityPillTable(pills) {
    const headers = ['ID', '名称', '品阶', '类型', '价格', '效果'];
    const rows = pills.map(p => {
        const effectType = p.effect_type === 'permanent' ? '永久' : p.effect_type === 'temporary' ? '临时' : p.effect_type === 'instant' ? '瞬时' : '其他';
        return [
            `<code>${esc(p.id)}</code>`,
            `<strong>${esc(p.name)}</strong>`,
            makeRankBadge(p.rank),
            esc(effectType),
            `<span data-sortvalue="${p.price}">${formatNum(p.price)}</span>`,
            `<span>${esc(getPillEffectSummary(p))}</span>`
        ];
    });
    const rankData = pills.map(p => p.rank);
    return createTable(headers, rows, { rankData });
}

function getPillEffectSummary(p) {
    const effects = [];
    if (p.exp_gain) effects.push(`修为+${formatNum(p.exp_gain)}`);
    if (p.cultivation_multiplier) effects.push(`修炼${formatPercent(p.cultivation_multiplier)}`);
    if (p.physical_damage_gain) effects.push(`物伤+${formatNum(p.physical_damage_gain)}`);
    if (p.magic_damage_gain) effects.push(`法伤+${formatNum(p.magic_damage_gain)}`);
    if (p.physical_defense_gain) effects.push(`物防+${formatNum(p.physical_defense_gain)}`);
    if (p.magic_defense_gain) effects.push(`法防+${formatNum(p.magic_defense_gain)}`);
    if (p.mental_power_gain) effects.push(`精神+${formatNum(p.mental_power_gain)}`);
    if (p.lifespan_gain) effects.push(`寿命+${formatNum(p.lifespan_gain)}`);
    if (p.max_spiritual_qi_gain) effects.push(`灵气+${formatNum(p.max_spiritual_qi_gain)}`);
    if (p.max_blood_qi_gain) effects.push(`气血+${formatNum(p.max_blood_qi_gain)}`);
    if (p.physical_damage_multiplier) effects.push(`物伤${formatPercent(p.physical_damage_multiplier)}`);
    if (p.magic_damage_multiplier) effects.push(`法伤${formatPercent(p.magic_damage_multiplier)}`);
    if (p.physical_defense_multiplier) effects.push(`物防${formatPercent(p.physical_defense_multiplier)}`);
    if (p.magic_defense_multiplier) effects.push(`法防${formatPercent(p.magic_defense_multiplier)}`);
    if (p.spiritual_qi_restore !== undefined) effects.push(p.spiritual_qi_restore === -1 ? '灵气回满' : `灵气+${formatNum(p.spiritual_qi_restore)}`);
    if (p.blood_qi_restore !== undefined) effects.push(p.blood_qi_restore === -1 ? '气回满' : `气血+${formatNum(p.blood_qi_restore)}`);
    if (p.spiritual_qi_regen) effects.push(`灵气+${formatNum(p.spiritual_qi_regen)}/分`);
    if (p.blood_qi_regen) effects.push(`气血+${formatNum(p.blood_qi_regen)}/分`);
    if (p.lifespan_regen) effects.push(`寿命+${formatNum(p.lifespan_regen)}/分`);
    if (p.duration_minutes) effects.push(`${p.duration_minutes}分`);
    if (effects.length === 0 && p.description) return p.description.substring(0, 40);
    return effects.join('，') || '-';
}

function renderLegacyPills(container) {
    const itemsObj = DATA.items || {};
    const pills = Object.entries(itemsObj)
        .filter(([_, v]) => v.type === '丹药')
        .map(([id, v]) => ({ ...v, id }));

    const headers = ['ID', '名称', '品阶', '价格', '效果'];
    const rows = pills.map(p => {
        const eff = p.effect || {};
        const effects = [];
        if (eff.add_hp) effects.push(`气血+${formatNum(eff.add_hp)}`);
        if (eff.add_experience) effects.push(`修为+${formatNum(eff.add_experience)}`);
        if (eff.add_attack) effects.push(`攻击+${formatNum(eff.add_attack)}`);
        if (eff.add_defense) effects.push(`防御+${formatNum(eff.add_defense)}`);
        if (eff.add_breakthrough_bonus) effects.push(`突破+${eff.add_breakthrough_bonus}%`);
        if (eff.add_lifespan) effects.push(`寿命+${formatNum(eff.add_lifespan)}`);
        if (eff.add_mp) effects.push(`真元+${formatNum(eff.add_mp)}`);
        return [
            `<code>${esc(p.id)}</code>`,
            `<strong>${esc(p.name)}</strong>`,
            makeRankBadge(p.rank || ''),
            `<span data-sortvalue="${p.price || 0}">${formatNum(p.price || 0)}</span>`,
            effects.join('，') || '-'
        ];
    });

    const rankData = pills.map(p => p.rank || '');
    container.innerHTML = createTable(headers, rows, { rankData });
    makeTableSortable(container);
}

function addPillRowClicks(container, pills, type) {
    container.querySelectorAll('tr.clickable').forEach(row => {
        row.addEventListener('click', () => {
            const idx = parseInt(row.dataset.row);
            showPillDetail(pills[idx], type);
        });
    });
}

function showPillDetail(pill, type) {
    let html = '';
    html += modalSection('基本信息',
        modalField('ID', pill.id || '-') +
        modalField('品阶', makeRankBadge(pill.rank)) +
        modalField('价格', `<span class="num-gold">${formatNum(pill.price)} 灵石</span>`) +
        modalField('描述', esc(pill.description || '-'))
    );

    const fields = [];
    if (type === 'breakthrough') {
        if (pill.breakthrough_bonus) fields.push(modalField('突破加成', '+' + formatRate(pill.breakthrough_bonus)));
        if (pill.max_success_rate) fields.push(modalField('最高成功率', formatRate(pill.max_success_rate)));
    } else if (type === 'exp') {
        if (pill.exp_gain) fields.push(modalField('修为增益', '+' + formatNum(pill.exp_gain)));
        if (pill.required_level_index !== undefined) fields.push(modalField('最低境界', levelName(pill.required_level_index)));
    } else {
        if (pill.effect_type) fields.push(modalField('效果类型', pill.effect_type));
        if (pill.subtype) fields.push(modalField('子类型', pill.subtype));
        if (pill.duration_minutes) fields.push(modalField('持续时间', pill.duration_minutes + ' 分钟'));
        if (pill.physical_damage_gain) fields.push(modalField('物伤', '+' + formatNum(pill.physical_damage_gain)));
        if (pill.magic_damage_gain) fields.push(modalField('法伤', '+' + formatNum(pill.magic_damage_gain)));
        if (pill.physical_defense_gain) fields.push(modalField('物防', '+' + formatNum(pill.physical_defense_gain)));
        if (pill.magic_defense_gain) fields.push(modalField('法防', '+' + formatNum(pill.magic_defense_gain)));
        if (pill.mental_power_gain) fields.push(modalField('精神力', '+' + formatNum(pill.mental_power_gain)));
        if (pill.lifespan_gain) fields.push(modalField('寿命', '+' + formatNum(pill.lifespan_gain)));
        if (pill.cultivation_multiplier) fields.push(modalField('修炼倍率', formatPercent(pill.cultivation_multiplier)));
        if (pill.max_spiritual_qi_gain) fields.push(modalField('灵气容量', '+' + formatNum(pill.max_spiritual_qi_gain)));
        if (pill.max_blood_qi_gain) fields.push(modalField('气血容量', '+' + formatNum(pill.max_blood_qi_gain)));
        if (pill.exp_gain) fields.push(modalField('修为增益', '+' + formatNum(pill.exp_gain)));
    }
    if (pill.shop_weight !== undefined) fields.push(modalField('商店权重', pill.shop_weight));
    if (fields.length) html += modalSection('效果属性', fields.join(''));

    showModal(pill.name, html);
    const glowCls = getRankGlowClass(pill.rank);
    if (glowCls) {
        document.querySelector('.modal-content').classList.add(glowCls);
    }
}

// ===================== Equipment =====================

function renderEquipment() {
    const page = document.getElementById('page-equipment');
    const allWeapons = DATA.weapons || [];
    const weaponCount = allWeapons.filter(w => w.type === 'weapon').length;
    const armorCount = allWeapons.filter(w => w.type === 'armor').length;

    page.innerHTML = `
        <h2 class="page-title">装备系统</h2>
        <div class="sub-tabs" id="equip-tabs">
            <div class="sub-tab active" data-equip-tab="weapons">武器 (${weaponCount}) / 防具 (${armorCount})</div>
            <div class="sub-tab" data-equip-tab="techniques">心法 (${countTechniques()})</div>
            <div class="sub-tab" data-equip-tab="rings">储物戒 (${countRings()})</div>
        </div>
        <div id="equip-content"></div>
    `;
    const tabs = page.querySelectorAll('.sub-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            renderEquipTab(tab.dataset.equipTab);
        });
    });
    renderEquipTab('weapons');
}

function countTechniques() {
    const items = Object.values(DATA.items || {});
    return items.filter(i => i.type === 'main_technique' || i.type === 'technique').length;
}

function countRings() {
    const rings = DATA.storage_rings;
    if (!rings) return 0;
    return typeof rings === 'object' && !Array.isArray(rings) ? Object.keys(rings).length : rings.length;
}

function renderEquipTab(tab) {
    const container = document.getElementById('equip-content');
    switch (tab) {
        case 'weapons': renderWeapons(container); break;
        case 'techniques': renderTechniques(container); break;
        case 'rings': renderRings(container); break;
    }
}

function renderWeapons(container) {
    const allItems = DATA.weapons || [];
    const weapons = allItems.filter(w => w.type === 'weapon');
    const armors = allItems.filter(w => w.type === 'armor');
    const categories = {};
    weapons.forEach(w => {
        const cat = w.weapon_category || '未知';
        if (!categories[cat]) categories[cat] = [];
        categories[cat].push(w);
    });

    let filterHtml = '<div class="filter-bar"><span class="filter-label">品阶：</span>';
    const ranks = [...new Set(allItems.map(w => w.rank).filter(Boolean))].sort((a, b) => rankOrder(a) - rankOrder(b));
    filterHtml += '<button class="filter-btn active" data-rank="all">全部</button>';
    ranks.forEach(r => { filterHtml += `<button class="filter-btn" data-rank="${esc(r)}">${esc(r)}</button>`; });
    filterHtml += '</div>';

    let html = filterHtml;

    const catOrder = ['剑','刀','阔刀','琴','匕首','符箓','鼎','棍','枪','笔'];
    const sortedCats = Object.keys(categories).sort((a, b) => {
        const ai = catOrder.indexOf(a), bi = catOrder.indexOf(b);
        return (ai >= 0 ? ai : 99) - (bi >= 0 ? bi : 99);
    });

    sortedCats.forEach(cat => {
        const group = categories[cat];
        html += `<h3 class="section-title">${esc(cat)}类武器 (${group.length}把)</h3>`;
        const headers = ['名称', '品阶', '需求境界', '价格', '物伤', '法伤', '物防', '法防', '精神力', '特殊属性'];
        const rows = group.map(w => [
            `<strong>${esc(w.name)}</strong>`,
            makeRankBadge(w.rank),
            `<span class="level-req">${esc(w.required_level_name || '-')}</span>`,
            `<span data-sortvalue="${w.price || 0}">${formatNum(w.price || 0)}</span>`,
            `<span data-sortvalue="${w.physical_damage || 0}">${w.physical_damage || 0}</span>`,
            `<span data-sortvalue="${w.magic_damage || 0}">${w.magic_damage || 0}</span>`,
            `<span data-sortvalue="${w.physical_defense || 0}">${w.physical_defense || 0}</span>`,
            `<span data-sortvalue="${w.magic_defense || 0}">${w.magic_defense || 0}</span>`,
            `<span data-sortvalue="${w.mental_power || 0}">${w.mental_power || 0}</span>`,
            `<span class="special-attrs">${formatSpecialAttrs(w)}</span>`
        ]);
        const rankData = group.map(w => w.rank);
        html += createTable(headers, rows, { onRowClick: true, rankData });
    });

    if (armors.length) {
        html += `<h3 class="section-title">防具 (${armors.length}件)</h3>`;
        const headers = ['名称', '品阶', '需求境界', '价格', '物防', '法防', '物伤', '法伤', '精神力', '特殊属性'];
        const rows = armors.map(a => [
            `<strong>${esc(a.name)}</strong>`,
            makeRankBadge(a.rank),
            `<span class="level-req">${esc(a.required_level_name || '-')}</span>`,
            `<span data-sortvalue="${a.price || 0}">${formatNum(a.price || 0)}</span>`,
            `<span data-sortvalue="${a.physical_defense || 0}">${a.physical_defense || 0}</span>`,
            `<span data-sortvalue="${a.magic_defense || 0}">${a.magic_defense || 0}</span>`,
            `<span data-sortvalue="${a.physical_damage || 0}">${a.physical_damage || 0}</span>`,
            `<span data-sortvalue="${a.magic_damage || 0}">${a.magic_damage || 0}</span>`,
            `<span data-sortvalue="${a.mental_power || 0}">${a.mental_power || 0}</span>`,
            `<span class="special-attrs">${formatSpecialAttrs(a)}</span>`
        ]);
        const armorRankData = armors.map(a => a.rank);
        html += createTable(headers, rows, { onRowClick: true, rankData: armorRankData });
    }

    container.innerHTML = html;

    container.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            container.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const rank = btn.dataset.rank;
            container.querySelectorAll('.data-table tbody tr').forEach(row => {
                if (rank === 'all') { row.style.display = ''; }
                else {
                    const badge = row.querySelector('.rank-badge');
                    row.style.display = (badge && badge.textContent === rank) ? '' : 'none';
                }
            });
        });
    });

    makeTableSortable(container);

    container.querySelectorAll('tr.clickable').forEach(row => {
        row.addEventListener('click', () => {
            const cat = row.closest('table').previousElementSibling?.textContent || '';
            const idx = parseInt(row.dataset.row);
            if (cat.includes('防具')) {
                if (armors[idx]) showWeaponDetail(armors[idx]);
                return;
            }
            const catName = Object.keys(categories).find(c => cat.includes(c));
            if (catName) showWeaponDetail(categories[catName][idx]);
        });
    });
}

function showWeaponDetail(w) {
    let html = '';
    html += modalSection('基本信息',
        modalField('名称', `<strong>${esc(w.name)}</strong>`) +
        modalField('品阶', makeRankBadge(w.rank)) +
        modalField('类别', esc(w.weapon_category || '-')) +
        modalField('需求境界', `<span class="level-req">${esc(w.required_level_name || '-')}</span>`) +
        modalField('价格', `<span class="num-gold">${formatNum(w.price || 0)} 灵石</span>`) +
        modalField('描述', esc(w.description || '-'))
    );

    let attrHtml = '';
    if (w.physical_damage) attrHtml += modalField('物伤', `+${w.physical_damage}`);
    if (w.magic_damage) attrHtml += modalField('法伤', `+${w.magic_damage}`);
    if (w.physical_defense) attrHtml += modalField('物防', `+${w.physical_defense}`);
    if (w.magic_defense) attrHtml += modalField('法防', `+${w.magic_defense}`);
    if (w.mental_power) attrHtml += modalField('精神力', `+${w.mental_power}`);
    if (attrHtml) html += modalSection('基础属性', attrHtml);

    let combatHtml = '';
    if (w.atk_bonus) combatHtml += modalField('攻击加成', `+${formatPercent(w.atk_bonus)}`);
    if (w.crit_rate) combatHtml += modalField('暴击率', `+${w.crit_rate}%`);
    if (w.crit_damage) combatHtml += modalField('暴击伤害', `${formatRate(w.crit_damage)}`);
    if (w.armor_pen) combatHtml += modalField('穿透', `+${w.armor_pen}%`);
    if (w.double_hit) combatHtml += modalField('连击', `+${w.double_hit}%`);
    if (w.lifesteal) combatHtml += modalField('吸血', `+${w.lifesteal}%`);
    if (w.dodge_rate) combatHtml += modalField('闪避率', `+${w.dodge_rate}%`);
    if (w.crit_resist) combatHtml += modalField('暴击抗性', `+${w.crit_resist}%`);
    if (w.reflect_pct) combatHtml += modalField('反伤', `+${w.reflect_pct}%`);
    if (w.block_value) combatHtml += modalField('格挡值', `+${w.block_value}`);
    if (w.hp_regen_pct) combatHtml += modalField('生命回复', `+${w.hp_regen_pct}%`);
    if (combatHtml) html += modalSection('战斗属性', combatHtml);

    if (w.shop_weight !== undefined) html += modalSection('其他', modalField('商店权重', w.shop_weight));

    showModal(w.name, html);
    const glowCls = getRankGlowClass(w.rank);
    if (glowCls) {
        document.querySelector('.modal-content').classList.add(glowCls);
    }
}

function renderTechniques(container) {
    const items = DATA.items || {};
    const techniques = Object.entries(items)
        .filter(([_, v]) => v.type === 'main_technique' || v.type === 'technique')
        .map(([id, v]) => ({ ...v, id }));

    const mainTechs = techniques.filter(t => t.type === 'main_technique');
    const subTechs = techniques.filter(t => t.type === 'technique');

    let filterHtml = '<div class="filter-bar"><span class="filter-label">品阶：</span>';
    const ranks = [...new Set(techniques.map(t => t.rank).filter(Boolean))].sort((a, b) => rankOrder(a) - rankOrder(b));
    filterHtml += '<button class="filter-btn active" data-rank="all">全部</button>';
    ranks.forEach(r => { filterHtml += `<button class="filter-btn" data-rank="${esc(r)}">${esc(r)}</button>`; });
    filterHtml += '</div>';

    let html = filterHtml;
    html += `<h3 class="section-title">主修心法 (${mainTechs.length}种)</h3>`;
    html += renderTechniqueTable(mainTechs, true);
    html += `<h3 class="section-title">辅助功法 (${subTechs.length}种)</h3>`;
    html += renderTechniqueTable(subTechs, false);

    container.innerHTML = html;

    container.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            container.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const rank = btn.dataset.rank;
            container.querySelectorAll('.data-table tbody tr').forEach(row => {
                if (rank === 'all') { row.style.display = ''; }
                else {
                    const badge = row.querySelector('.rank-badge');
                    row.style.display = (badge && badge.textContent === rank) ? '' : 'none';
                }
            });
        });
    });

    makeTableSortable(container);
}

function renderTechniqueTable(techs, isMain) {
    const headers = isMain
        ? ['名称', '品阶', '修炼加成', '突破成功率', '攻击力', '生命值', '最低境界', '价格']
        : ['名称', '品阶', '修炼加成', '最低境界', '价格'];
    const rows = techs.map(t => {
        const base = [
            `<strong>${esc(t.name)}</strong>`,
            makeRankBadge(t.rank || ''),
            `<span data-sortvalue="${t.exp_multiplier || 0}">${t.exp_multiplier ? '+' + ((t.exp_multiplier - 1) * 100).toFixed(0) + '%' : '-'}</span>`,
        ];
        if (isMain) {
            base.push(
                `<span data-sortvalue="${t.breakthrough_bonus || 0}">${t.breakthrough_bonus ? '+' + (t.breakthrough_bonus * 100).toFixed(0) + '%' : '-'}</span>`,
                `<span data-sortvalue="${t.atk_bonus || 0}">${t.atk_bonus ? '+' + t.atk_bonus : '-'}</span>`,
                `<span data-sortvalue="${t.hp_bonus || 0}">${t.hp_bonus ? '+' + (t.hp_bonus * 100).toFixed(0) + '%' : '-'}</span>`
            );
        }
        base.push(
            t.required_level_index ? levelName(t.required_level_index) : '-',
            `<span data-sortvalue="${t.price || 0}">${formatNum(t.price || 0)}</span>`
        );
        return base;
    });
    return createTable(headers, rows, { emptyText: '暂无心法数据', rankData: techs.map(t => t.rank || '') });
}

function renderRings(container) {
    const rings = DATA.storage_rings;
    let ringArr = [];
    if (Array.isArray(rings)) ringArr = rings;
    else if (rings && typeof rings === 'object') ringArr = Object.values(rings);

    const headers = ['名称', '品阶', '容量', '需求境界', '价格'];
    const rows = ringArr.map(r => [
        `<strong>${esc(r.name)}</strong>`,
        makeRankBadge(r.rank || ''),
        `<span data-sortvalue="${r.capacity || 0}">${r.capacity || 0} 格</span>`,
        r.required_level_index !== undefined ? levelName(r.required_level_index) : '-',
        `<span data-sortvalue="${r.price || 0}">${formatNum(r.price || 0)}</span>`
    ]);

    const rankData = ringArr.map(r => r.rank || '');
    container.innerHTML = createTable(headers, rows, { rankData });
    makeTableSortable(container);
}

// ===================== Combat =====================

function renderCombat() {
    const page = document.getElementById('page-combat');
    const config = DATA.game_config || {};
    const combatCfg = config.combat || {};

    let html = '<h2 class="page-title">战斗系统</h2>';

    // Combat formulas
    html += '<h3 class="section-title">核心公式</h3>';
    html += '<div class="formula-grid">';

    html += `<div class="formula-card">
        <h3>生命值 (HP)</h3>
        <div class="formula-expr">HP = (base_hp + level_hp + blood_qi) &times; (1 + hp_bonus)</div>
        <div class="formula-note">基础生命 + 境界提升 + 气血值，乘以加成系数</div>
    </div>`;

    html += `<div class="formula-card">
        <h3>真元 (MP)</h3>
        <div class="formula-expr">MP = (base_mp + level_mp + spiritual_qi) &times; (1 + mp_bonus)</div>
        <div class="formula-note">基础真元 + 境界提升 + 灵气值，乘以加成系数</div>
    </div>`;

    html += `<div class="formula-card">
        <h3>攻击力 (ATK)</h3>
        <div class="formula-expr">ATK = physical_damage + magic_damage</div>
        <div class="formula-note">物伤 + 法伤 = 总攻击力</div>
    </div>`;

    html += `<div class="formula-card">
        <h3>防御减伤</h3>
        <div class="formula-expr">减伤率 = defense / (defense + 100 + level&times;10)</div>
        <div class="formula-note">防御值越高减伤越多，存在边际递减效应</div>
    </div>`;

    html += `<div class="formula-card">
        <h3>暴击系统</h3>
        <div class="formula-expr">暴击伤害 = ATK &times; crit_damage_multiplier<br>默认倍率 = ${combatCfg.crit_damage_multiplier || 1.5}x</div>
        <div class="formula-note">Boss基础暴击率 ${combatCfg.boss_crit_rate || 30}%，暴击伤害默认 1.5 倍</div>
    </div>`;

    html += `<div class="formula-card">
        <h3>战斗冷却</h3>
        <div class="formula-expr">决斗冷却: ${fmtDuration(combatCfg.duel_cooldown)}<br>切磋冷却: ${fmtDuration(combatCfg.spar_cooldown)}</div>
        <div class="formula-note">决斗有击杀/被杀判定，切磋为友好比武</div>
    </div>`;

    html += '</div>';

    // Combat attributes table
    html += '<h3 class="section-title">战斗属性一览</h3>';
    const attrHeaders = ['属性', '说明', '来源'];
    const attrRows = [
        ['<span class="num-red">physical_damage</span>', '物理伤害', '境界突破、装备、丹药'],
        ['<span class="num-purple">magic_damage</span>', '法术伤害', '境界突破、装备、丹药'],
        ['<span class="num-cyan">physical_defense</span>', '物理防御', '境界突破、装备、丹药'],
        ['<span class="num-cyan">magic_defense</span>', '法术防御', '境界突破、装备、丹药'],
        ['<span class="num-gold">mental_power</span>', '精神力', '境界突破、装备、丹药'],
        ['<span class="num-green">blood_qi</span>', '气血值 (影响HP)', '境界突破、装备、丹药'],
        ['<span class="num-green">spiritual_qi</span>', '灵气值 (影响MP)', '境界突破、装备、丹药'],
        ['<span class="num-red">lifespan</span>', '寿命', '境界突破、丹药、回复'],
        ['<span class="num-gold">crit_rate</span>', '暴击率', '装备（武器属性）'],
        ['<span class="num-gold">crit_damage</span>', '暴击伤害加成', '装备（武器属性）'],
        ['<span class="num-purple">armor_pen</span>', '护甲穿透', '装备（武器属性）'],
        ['<span class="num-cyan">double_hit</span>', '连击率', '装备（武器属性）'],
        ['<span class="num-green">lifesteal</span>', '吸血率', '装备（武器属性）'],
        ['<span class="num-gold">atk_bonus</span>', '攻击加成', '装备（武器属性）'],
        ['<span class="num-cyan">dodge_rate</span>', '闪避率', '装备（防具属性）'],
        ['<span class="num-cyan">crit_resist</span>', '暴击抗性', '装备（防具属性）'],
        ['<span class="num-red">reflect_pct</span>', '反伤百分比', '装备（防具属性）'],
        ['<span class="num-green">block_value</span>', '格挡值', '装备（防具属性）'],
        ['<span class="num-green">hp_regen_pct</span>', '生命回复百分比', '装备（防具属性）'],
    ];
    html += createTable(attrHeaders, attrRows, { sortable: false });

    // PVP types
    html += '<h3 class="section-title">PVP 类型</h3>';
    html += '<div class="info-box">';
    html += '<strong>决斗</strong>：消耗灵石发起，胜利方可掠夺败方灵石、经验，有击杀/被杀记录。<br>';
    html += '<strong>切磋</strong>：友好比武，无损失，仅消耗冷却时间。<br>';
    html += '<strong>稻草人</strong>：15回合练习战，稻草人防御为0、固定反伤1，统计总输出。<br>';
    html += '<strong>Boss</strong>：挑战世界Boss，按伤害排名发放奖励，Boss有暴击加成。';
    html += '</div>';

    // Equipment combat stats - weapons
    const weapons = (DATA.weapons || []).filter(w => w.type === 'weapon');
    const withCrit = weapons.filter(w => w.crit_rate || w.crit_damage || w.armor_pen || w.double_hit || w.lifesteal);
    if (withCrit.length) {
        html += '<h3 class="section-title">含战斗属性的武器 (' + withCrit.length + '把)</h3>';
        const wHeaders = ['名称', '品阶', '暴击率', '暴伤', '穿透', '连击', '吸血'];
        const wRows = withCrit.map(w => [
            `<strong>${esc(w.name)}</strong>`,
            makeRankBadge(w.rank),
            `<span data-sortvalue="${w.crit_rate || 0}">${w.crit_rate ? w.crit_rate + '%' : '-'}</span>`,
            `<span data-sortvalue="${w.crit_damage || 0}">${w.crit_damage ? formatRate(w.crit_damage) : '-'}</span>`,
            `<span data-sortvalue="${w.armor_pen || 0}">${w.armor_pen ? w.armor_pen + '%' : '-'}</span>`,
            `<span data-sortvalue="${w.double_hit || 0}">${w.double_hit ? w.double_hit + '%' : '-'}</span>`,
            `<span data-sortvalue="${w.lifesteal || 0}">${w.lifesteal ? w.lifesteal + '%' : '-'}</span>`
        ]);
        html += createTable(wHeaders, wRows, { rankData: withCrit.map(w => w.rank) });
    }

    // Armor with special attributes
    const armors = (DATA.weapons || []).filter(w => w.type === 'armor');
    const withSpecial = armors.filter(a => a.dodge_rate || a.crit_resist || a.reflect_pct || a.block_value || a.hp_regen_pct);
    if (withSpecial.length) {
        html += '<h3 class="section-title">含特殊属性的防具 (' + withSpecial.length + '件)</h3>';
        const aHeaders = ['名称', '品阶', '闪避', '抗会心', '反伤', '格挡', '回复'];
        const aRows = withSpecial.map(a => [
            `<strong>${esc(a.name)}</strong>`,
            makeRankBadge(a.rank),
            `<span data-sortvalue="${a.dodge_rate || 0}">${a.dodge_rate ? formatRate(a.dodge_rate) : '-'}</span>`,
            `<span data-sortvalue="${a.crit_resist || 0}">${a.crit_resist ? a.crit_resist + '%' : '-'}</span>`,
            `<span data-sortvalue="${a.reflect_pct || 0}">${a.reflect_pct ? a.reflect_pct + '%' : '-'}</span>`,
            `<span data-sortvalue="${a.block_value || 0}">${a.block_value || '-'}</span>`,
            `<span data-sortvalue="${a.hp_regen_pct || 0}">${a.hp_regen_pct ? a.hp_regen_pct + '%' : '-'}</span>`
        ]);
        html += createTable(aHeaders, aRows, { rankData: withSpecial.map(a => a.rank) });
    }

    page.innerHTML = html;
    makeTableSortable(page);
}

// ===================== Systems =====================

function renderSystems() {
    const page = document.getElementById('page-systems');
    const config = DATA.game_config || {};

    let html = '<h2 class="page-title">游戏系统</h2>';

    // System overview cards
    html += '<div class="system-grid">';

    // Cultivation
    const cult = config.cultivation || {};
    html += `<div class="system-card">
        <h3>修炼系统</h3>
        <p>通过闭关修炼积累修为值，提升境界。支持双修加成、修炼加速丹、心法倍率、灵眼加成、洞天福地等。</p>
        <ul class="detail-list">
            <li><span>闭关时长上限</span><span>${fmtDuration((cult.max_cultivation_minutes || 21600) * 60)}</span></li>
            <li><span>修炼公式</span><span>修为 = 基础 × 根速 × (1+心法) × 丹药 × (1+灵眼) × (1+福地)</span></li>
        </ul>
    </div>`;

    // Bank
    const bank = config.bank || {};
    html += `<div class="system-card">
        <h3>银行系统</h3>
        <p>存取灵石获取利息，也可申请贷款周转资金。支持突破专项贷款。</p>
        <ul class="detail-list">
            <li><span>日利率</span><span>${((bank.daily_interest_rate || 0.001) * 100).toFixed(1)}%</span></li>
            <li><span>存款上限</span><span>${formatNum(bank.max_deposit || 0)}</span></li>
            <li><span>贷款利率</span><span>${((bank.loan_interest_rate || 0.005) * 100).toFixed(1)}%/日</span></li>
            <li><span>贷款期限</span><span>${bank.loan_duration_days || 7}天</span></li>
            <li><span>贷款额度</span><span>${formatNum(bank.min_loan_amount || 0)} ~ ${formatNum(bank.max_loan_amount || 0)}</span></li>
            <li><span>突破贷利率</span><span>${((bank.breakthrough_loan_rate || 0.008) * 100).toFixed(1)}%/日</span></li>
            <li><span>突破贷期限</span><span>${bank.breakthrough_loan_duration || 3}天</span></li>
        </ul>
    </div>`;

    // Dual Cultivation
    const dual = config.dual_cultivation || {};
    html += `<div class="system-card">
        <h3>双修系统</h3>
        <p>两位修士结为道侣共同修炼，双方各获得双方修为之和的1%。可服用龙精虎猛丹使下次双修修为翻倍。</p>
        <ul class="detail-list">
            <li><span>每日上限</span><span>${dual.max_per_day || 3} 次</span></li>
            <li><span>冷却时间</span><span>${fmtDuration(dual.cooldown || 3600)}</span></li>
            <li><span>修为公式</span><span>双方各获得 (A修为+B修为) × 1%</span></li>
            <li><span>请求有效期</span><span>${fmtDuration(dual.request_expire || 300)}</span></li>
        </ul>
    </div>`;

    // Spirit Eye
    const eye = config.spirit_eye || {};
    const eyeTypes = eye.types || {};
    html += `<div class="system-card">
        <h3>灵眼系统</h3>
        <p>定时在群内刷新灵眼，修士抢占后提升闭关修炼效率。灵眼品阶越高加成越大。</p>
        <ul class="detail-list">
            <li><span>刷新间隔</span><span>${fmtDuration(eye.spawn_interval || 7200)}</span></li>
            ${Object.values(eyeTypes).map(t => `<li><span>${esc(t.name)}</span><span>修炼效率+${((t.cultivation_bonus || 0) * 100).toFixed(0)}%（概率${t.spawn_rate || 0}%）</span></li>`).join('')}
        </ul>
    </div>`;

    // Spirit Farm
    html += `<div class="system-card">
        <h3>灵田系统</h3>
        <p>开辟灵田种植灵草，收获后用于炼丹或交易。灵田等级越高产出越丰富。</p>
        <ul class="detail-list">
            <li><span>核心玩法</span><span>种植 / 浇水 / 收获</span></li>
            <li><span>产出</span><span>灵草、稀有材料</span></li>
        </ul>
    </div>`;

    // Rift / Secret Realm
    const rift = config.rift || {};
    html += `<div class="system-card">
        <h3>秘境系统</h3>
        <p>组队或单人探索秘境，击败怪物获取装备和材料。秘境等级越高掉落越好。</p>
        <ul class="detail-list">
            <li><span>默认时长</span><span>${fmtDuration(rift.default_duration || 1800)}</span></li>
            <li><span>掉落类型</span><span>灵草、丹药、装备</span></li>
            <li><span>装备掉落</span><span>按品阶权重随机</span></li>
        </ul>
    </div>`;

    // Sect System
    html += `<div class="system-card">
        <h3>宗门系统</h3>
        <p>创建或加入宗门，参与宗门战、宗门任务，获取宗门贡献和专属奖励。</p>
        <ul class="detail-list">
            <li><span>核心玩法</span><span>创建 / 加入 / 宗门战</span></li>
            <li><span>奖励</span><span>宗门贡献、专属物品</span></li>
        </ul>
    </div>`;

    // Bounty
    html += `<div class="system-card">
        <h3>悬赏系统</h3>
        <p>每日可选2个悬赏任务，完成后获取灵石、修为及随机功法奖励。功法奖励在列出时已预判。</p>
        <ul class="detail-list">
            <li><span>每日限制</span><span>2 次</span></li>
            <li><span>难度等级</span><span>简单 / 普通 / 困难 / 精英</span></li>
            <li><span>任务类型</span><span>巡山 / 采集 / 猎杀 / 探险</span></li>
            <li><span>功法掉落</span><span>动态爆率，按品阶权重随机</span></li>
        </ul>
    </div>`;

    // Adventure
    html += `<div class="system-card">
        <h3>冒险系统</h3>
        <p>选择探险路线出发冒险，途中遭遇随机事件，完成冒险获取丰厚回报。</p>
        <ul class="detail-list">
            <li><span>路线数</span><span>${(DATA.adventure_config?.routes || []).length} 条</span></li>
            <li><span>事件类型</span><span>安全 / 标准 / 危险 / 灾难</span></li>
        </ul>
    </div>`;

    // Alchemy
    html += `<div class="system-card">
        <h3>炼丹系统</h3>
        <p>收集材料按配方炼制丹药，品阶越高的丹药成功率越低但效果越好。</p>
        <ul class="detail-list">
            <li><span>配方数</span><span>${(DATA.alchemy_recipes || []).length} 个</span></li>
            <li><span>核心</span><span>材料收集 + 成功率</span></li>
        </ul>
    </div>`;

    // Trade & Consignment
    html += `<div class="system-card">
        <h3>交易系统</h3>
        <p>玩家间自由交易物品和灵石，支持寄售行上架出售。市场价格由供需决定。</p>
        <ul class="detail-list">
            <li><span>交易方式</span><span>面对面 / 寄售行</span></li>
            <li><span>货币</span><span>灵石</span></li>
        </ul>
    </div>`;

    // Blessed Land
    html += `<div class="system-card">
        <h3>福地系统</h3>
        <p>占领福地获得持续修炼加成，福地品质越高加成越大。可被其他玩家挑战夺取。</p>
        <ul class="detail-list">
            <li><span>核心</span><span>占领 / 防守 / 加成</span></li>
            <li><span>收益</span><span>修炼速度加成</span></li>
        </ul>
    </div>`;

    // Impart
    html += `<div class="system-card">
        <h3>传功系统</h3>
        <p>高境界修士可向低境界修士传功，帮助后辈快速提升修为。</p>
        <ul class="detail-list">
            <li><span>核心</span><span>前辈传功给后辈</span></li>
            <li><span>限制</span><span>境界差距要求</span></li>
        </ul>
    </div>`;

    // Ranking
    html += `<div class="system-card">
        <h3>排行榜系统</h3>
        <p>按修为、灵石、战力等维度排名，展示服务器顶尖修士。</p>
        <ul class="detail-list">
            <li><span>排名维度</span><span>修为 / 灵石 / 战力</span></li>
            <li><span>更新</span><span>实时更新</span></li>
        </ul>
    </div>`;

    html += '</div>';

    // Game config detail
    html += '<h3 class="section-title">详细配置参数</h3>';
    html += '<div class="config-grid">';
    const sectionLabels = {
        cultivation: '修炼配置', combat: '战斗配置', bank: '银行配置',
        dual_cultivation: '双修配置', spirit_eye: '灵眼配置', rift: '裂隙配置'
    };
    Object.entries(config).forEach(([section, data]) => {
        if (typeof data !== 'object' || data === null) return;
        html += `<div class="config-card"><h3>${esc(sectionLabels[section] || section)}</h3>`;
        html += renderConfigFields(data);
        html += '</div>';
    });
    html += '</div>';

    page.innerHTML = html;
    makeTableSortable(page);
}

// ===================== Commands =====================

function renderCommands() {
    const page = document.getElementById('page-commands');

    let html = '<h2 class="page-title">指令大全</h2>';
    html += '<div class="info-box">共收录 <strong>133</strong> 条游戏指令，按系统分类整理。指令前缀默认为 <strong>#</strong> 或 <strong>/</strong>，具体以机器人配置为准。</div>';

    const groups = [
        {
            title: '基础操作',
            icon: '◈',
            cmds: [
                ['我要修仙 [灵修/体修]', '创建角色，选择修炼路线'],
                ['我的信息', '查看境界、修为、战力等完整信息面板'],
                ['签到', '每日领取灵石(50-500)'],
                ['我的装备', '查看已装备的武器/防具/心法'],
                ['修仙帮助', '查看帮助信息'],
                ['改道号 <名称>', '修改你的仙道称号'],
                ['弃道重修 [确认]', '7天仅一次，追加"确认"后删除角色重新入道'],
                ['重铸灵根', '花费25万灵石重新随机灵根'],
                ['补偿', '领取管理员发放的全服补偿（每人限领一次）'],
            ]
        },
        {
            title: '修炼突破',
            icon: '▲',
            cmds: [
                ['闭关', '开始闭关修炼，离线也能积累修为'],
                ['出关', '结算闭关时间，获取对应修为'],
                ['突破信息', '查看当前境界突破条件、成功率与风险'],
                ['突破', '尝试突破境界'],
                ['突破 [丹药名]', '服用丹药增加成功率后突破'],
            ]
        },
        {
            title: '装备 & 功法',
            icon: '⚔',
            cmds: [
                ['我的装备', '查看已装备的武器/防具/心法'],
                ['装备 <名称>', '从储物戒应用到身上'],
                ['卸下 <名称>', '从身上放回储物戒'],
                ['查看 <名称>', '查看任意物品详细信息'],
                ['服用丹药 <名称> [数量]', '使用丹药获得增益效果'],
                ['丹药信息 <名称>', '查看指定丹药的详细信息'],
            ]
        },
        {
            title: '商店系统',
            icon: '●',
            cmds: [
                ['丹阁', '丹药专卖（破境丹/修为丹/功能丹）'],
                ['器阁', '装备专卖（武器/防具/饰品）'],
                ['百宝阁', '综合商店（功法/材料/杂物）'],
                ['购买 <物品名> [数量]', '从当前商店购买物品'],
            ]
        },
        {
            title: '储物戒',
            icon: '◈',
            cmds: [
                ['储物戒', '查看储物空间和物品（分类显示）'],
                ['搜索物品 <关键词>', '模糊搜索储物戒物品'],
                ['炼金 <物品名> [数量]', '将物品转化为灵石（市场价20%）'],
                ['更换储物戒 <名称>', '升级储物戒（需支付灵石）'],
                ['丢弃 <物品名>', '丢弃储物戒中的物品'],
                ['赠予 <@某人> <物品> [数量]', '将物品赠送给其他玩家'],
                ['接收', '接收他人赠送的物品'],
                ['拒绝', '拒收他人赠送的物品'],
            ]
        },
        {
            title: '宗门系统',
            icon: '♚',
            cmds: [
                ['创建宗门 <名>', '消耗灵石创建宗门'],
                ['加入宗门 <名>', '申请加入已有宗门'],
                ['退出宗门', '退出当前宗门'],
                ['我的宗门', '查看宗门信息和成员列表'],
                ['宗门列表', '查看所有宗门排名'],
                ['宗门捐献 <数量>', '捐献灵石增加宗门建设度'],
                ['踢出成员 <@某人>', '宗主踢出宗门成员'],
                ['宗主传位 <@某人>', '将宗主之位传给他人'],
                ['宗门任务', '查看并执行宗门任务'],
                ['职位变更 <@某人> <职位>', '变更成员在宗门中的职位'],
            ]
        },
        {
            title: '战斗竞技',
            icon: '✦',
            cmds: [
                ['切磋 <@某人>', '友好切磋，无气血消耗，1分钟冷却'],
                ['决斗 <@某人>', '生死之战，消耗气血，败者损修为，5分钟冷却'],
                ['稻草人', '15回合练习战，防御为0，稻草人固定反伤1，统计总输出'],
                ['世界Boss', '查看当前Boss信息和血量'],
                ['挑战Boss', '挑战世界Boss获取丰厚奖励'],
                ['生成Boss', '手动刷新世界Boss（管理员）'],
                ['传承挑战 <@某人>', '争夺对方传承加成'],
                ['传承排行', '查看传承排行榜'],
            ]
        },
        {
            title: '排行榜',
            icon: '♛',
            cmds: [
                ['境界排行', '查看境界排行榜'],
                ['战力排行', '查看战力排行榜'],
                ['灵石排行', '查看灵石排行榜'],
                ['宗门排行', '查看宗门排行榜'],
                ['存款排行', '查看银行存款排行榜'],
                ['贡献排行', '查看宗门贡献排行榜'],
            ]
        },
        {
            title: '历练系统',
            icon: '❧',
            cmds: [
                ['开始历练 <路线名>', '巡山问道/云游四方/猎魔肃清/九死一生'],
                ['历练状态', '查看当前路线进度与剩余时间'],
                ['完成历练', '领取路线奖励与奇遇掉落'],
                ['历练信息', '查看各路线风险、可玩性与收益说明'],
            ]
        },
        {
            title: '秘境探索',
            icon: '◎',
            cmds: [
                ['探索秘境', '进入今日秘境（每日限1次）'],
                ['完成探索', '领取秘境奖励'],
                ['退出秘境', '放弃探索（无奖励）'],
            ]
        },
        {
            title: '炼丹系统',
            icon: '●',
            cmds: [
                ['丹药配方', '查看炼丹配方及成功率'],
                ['炼丹 <配方ID>', '炼制丹药（成功后存入丹药背包）'],
            ]
        },
        {
            title: '传承系统',
            icon: '☀',
            cmds: [
                ['传承信息', '查看传承给你的属性加成'],
            ]
        },
        {
            title: '灵石银行',
            icon: '◆',
            cmds: [
                ['银行信息', '查看存款余额、利息和贷款状态'],
                ['存灵石 <数量>', '存入灵石（上限10亿）'],
                ['取灵石 <数量>', '取出存款'],
                ['领取利息', '每日可领一次利息'],
                ['贷款 <金额>', '普通贷款(0.5%日利率，7天)'],
                ['突破贷款 <金额>', '短期贷款(0.8%日利率，3天)'],
                ['还款', '偿还贷款(本金+利息)'],
                ['银行流水', '查看历史交易记录'],
                ['升级会员', '升级银行VIP会员等级'],
            ]
        },
        {
            title: '悬赏任务',
            icon: '⚑',
            cmds: [
                ['悬赏令', '查看当期多难度悬赏任务'],
                ['接取悬赏 <编号>', '接取指定悬赏任务'],
                ['悬赏状态', '查看任务进度、剩余时间和奖励'],
                ['完成悬赏', '提交任务领取灵石/修为/掉落'],
                ['放弃悬赏', '取消当前任务（触发冷却）'],
            ]
        },
        {
            title: '洞天福地',
            icon: '⛰',
            cmds: [
                ['我的洞天', '查看洞天信息和修炼加成'],
                ['购买洞天 <1-5>', '1:小洞天 2:中洞天 3:大洞天 4:福地 5:洞天福地'],
                ['升级洞天', '提升修炼加成比例'],
            ]
        },
        {
            title: '灵田种植',
            icon: '✿',
            cmds: [
                ['我的灵田', '查看灵田和种植情况'],
                ['开垦灵田', '花费2,000,000灵石开垦灵田'],
                ['种植 <灵草名>', '种植灵草'],
                ['收获', '收获成熟的灵草获取修为'],
                ['升级灵田', '增加种植格数'],
            ]
        },
        {
            title: '双修系统',
            icon: '♥',
            cmds: [
                ['双修 <@某人>', '向对方发起双修请求'],
                ['接受双修', '接受双修，双方各获修为奖励'],
                ['拒绝双修', '拒绝对方的双修请求'],
            ]
        },
        {
            title: '天地灵眼',
            icon: '◎',
            cmds: [
                ['灵眼信息', '查看灵眼及可抢占列表'],
                ['抢占灵眼 <ID>', '占据无主灵眼提升闭关效率'],
                ['释放灵眼', '释放已占据的灵眼'],
            ]
        },
        {
            title: '成就系统',
            icon: '🏆',
            cmds: [
                ['成就列表', '查看成就列表（自动检测新解锁）'],
                ['装备成就 <名称>', '装备成就作为展示称号'],
                ['卸下成就', '卸下当前装备的成就'],
            ]
        },
        {
            title: '玩家交易',
            icon: '⇄',
            cmds: [
                ['交易 @某人', '在当前群发起交易请求（仅群聊）'],
                ['接受交易', '接受他人发来的交易请求'],
                ['拒绝交易', '拒绝交易请求'],
                ['添加物品 <名称> [数量]', '把物品放入交易栏'],
                ['添加灵石 <数量>', '把灵石放入交易托管'],
                ['移除物品 <名称> [数量]', '取回放入交易栏的物品'],
                ['移除灵石 <数量>', '取回放入交易托管的灵石'],
                ['查看交易', '查看双方放入的物品和灵石'],
                ['确认交易', '确认当前交易（双方都确认后结算）'],
                ['取消交易', '取消交易，物品全额返还'],
            ]
        },
        {
            title: '寄售行',
            icon: '⇄',
            cmds: [
                ['寄售 <物品名> <单价> [数量]', '上架物品（5%手续费，按总价计算）'],
                ['寄售行 [页码]', '浏览全局寄售行（价格为单价）'],
                ['购买寄售 <编号> [数量]', '购买指定编号物品'],
                ['我的寄售', '查看自己当前所有在售物品'],
                ['下架寄售 <编号>', '主动下架在售物品'],
            ]
        },
        {
            title: '管理员指令',
            icon: '⚙',
            cmds: [
                ['禁用物品 <名称>', '禁止玩家使用指定物品'],
                ['启用物品 <名称>', '解除物品的禁用状态'],
                ['禁用列表', '查看当前所有被禁用的物品'],
                ['GM指令帮助', '查看GM管理员指令帮助'],
                ['GM加灵石 <目标> <数量>', '为目标玩家增加灵石'],
                ['GM扣灵石 <目标> <数量>', '扣除目标玩家灵石'],
                ['GM加修为 <目标> <数量>', '为目标玩家增加修为'],
                ['GM设置境界 <目标> <等级>', '设置目标玩家境界等级'],
                ['GM加物品 <目标> <物品名> [数量]', '向目标储物戒添加物品'],
                ['GM扣物品 <目标> <物品名> [数量]', '从目标储物戒移除物品'],
                ['GM加丹药 <目标> <丹药名> [数量]', '向目标丹药背包添加丹药'],
                ['GM扣丹药 <目标> <丹药名> [数量]', '从目标丹药背包移除丹药'],
                ['GM查看玩家 <目标>', '查看目标玩家完整信息'],
                ['GM刷新秘境', '强制刷新秘境并重置所有玩家探索次数'],
                ['GM补偿 <物品 数量|物品 数量>', '创建全服补偿包'],
            ]
        }
    ];

    groups.forEach(g => {
        html += `<div class="cmd-group">`;
        html += `<div class="cmd-group-title"><span>${g.icon}</span> ${esc(g.title)} (${g.cmds.length})</div>`;
        html += `<div class="cmd-list">`;
        g.cmds.forEach(([cmd, desc]) => {
            html += `<div class="cmd-item"><span class="cmd-name">${esc(cmd)}</span><span class="cmd-desc">${esc(desc)}</span></div>`;
        });
        html += `</div></div>`;
    });

    page.innerHTML = html;
}

// ===================== Alchemy =====================

function renderAlchemy() {
    const page = document.getElementById('page-alchemy');
    const recipes = DATA.alchemy_recipes || [];

    const headers = ['配方名称', '需求境界', '材料', '成功率'];
    const rows = recipes.map(r => {
        const materials = r.materials || {};
        const matStr = Object.entries(materials).map(([name, qty]) => `${name} x${qty}`).join('，');
        return [
            `<strong>${esc(r.name)}</strong>`,
            r.level_required !== undefined ? levelName(r.level_required) : '-',
            esc(matStr || '-'),
            `<span data-sortvalue="${r.success_rate || 0}">${r.success_rate || 0}%</span>`
        ];
    });

    page.innerHTML = `
        <h2 class="page-title">炼丹配方</h2>
        <div class="info-box">
            炼丹需要收集对应材料并达到需求境界，成功率随品阶提升而降低。
            失败会消耗材料但不产出丹药。
        </div>
        ${createTable(headers, rows)}
    `;
    makeTableSortable(page);
}

// ===================== Adventure =====================

function renderAdventure() {
    const page = document.getElementById('page-adventure');
    page.classList.add('scroll-wide');
    const config = DATA.adventure_config || {};
    const routes = config.routes || [];
    const eventGroups = config.event_groups || {};
    const dropTables = config.drop_tables || {};

    let html = '<h2 class="page-title">冒险系统</h2>';

    // Routes
    html += '<h3 class="section-title">探险路线</h3>';
    const headers = ['路线', '风险', '时长', '修为/分', '灵石/分', '经验加成/分', '灵石加成/分', '完成奖励修为', '完成奖励灵石', '疲劳冷却'];
    const routeRows = routes.map(r => [
        `<strong>${esc(r.name || r.key || '-')}</strong><br><span style="font-size:11px;color:var(--text-muted)">${esc(r.description || '')}</span>`,
        esc(r.risk || '-'),
        `<span data-sortvalue="${r.duration || 0}">${fmtDuration(r.duration)}</span>`,
        `<span data-sortvalue="${r.base_exp_per_min || 0}">${r.base_exp_per_min || 0}</span>`,
        `<span data-sortvalue="${r.base_gold_per_min || 0}">${formatNum(r.base_gold_per_min || 0)}</span>`,
        `<span data-sortvalue="${r.level_bonus_exp || 0}">${r.level_bonus_exp || 0}</span>`,
        `<span data-sortvalue="${r.level_bonus_gold || 0}">${formatNum(r.level_bonus_gold || 0)}</span>`,
        `<span data-sortvalue="${r.completion_bonus?.exp || 0}">${formatNum(r.completion_bonus?.exp || 0)}</span>`,
        `<span data-sortvalue="${r.completion_bonus?.gold || 0}">${formatNum(r.completion_bonus?.gold || 0)}</span>`,
        `<span data-sortvalue="${r.fatigue_cooldown || 0}">${fmtDuration(r.fatigue_cooldown)}</span>`
    ]);
    html += createTable(headers, routeRows);

    // Event weights
    html += '<h3 class="section-title">事件权重</h3>';
    const ewHeaders = ['路线', '安全', '标准', '危险', '灾难'];
    const ewRows = routes.map(r => {
        const ew = r.event_weights || {};
        return [
            `<strong>${esc(r.name || r.key || '-')}</strong>`,
            `<span data-sortvalue="${ew.safe || 0}">${ew.safe || 0}%</span>`,
            `<span data-sortvalue="${ew.standard || 0}">${ew.standard || 0}%</span>`,
            `<span data-sortvalue="${ew.risky || 0}">${ew.risky || 0}%</span>`,
            `<span data-sortvalue="${ew.disaster || 0}">${ew.disaster || 0}%</span>`
        ];
    });
    html += createTable(ewHeaders, ewRows);

    // Events
    html += '<h3 class="section-title">随机事件</h3>';
    Object.entries(eventGroups).forEach(([group, events]) => {
        if (!Array.isArray(events)) return;
        html += `<h4 style="color:var(--text-secondary);margin:12px 0 8px;font-size:14px">${esc(group)} (${events.length}个事件)</h4>`;
        const evHeaders = ['事件', '描述', '修为倍率', '灵石倍率', '物品概率', '额外进度'];
        const evRows = events.map(e => [
            `<strong>${esc(e.name || '-')}</strong>`,
            esc(e.desc || '-'),
            `<span data-sortvalue="${e.exp_mult || 1}">${e.exp_mult || 1}x</span>`,
            `<span data-sortvalue="${e.gold_mult || 1}">${e.gold_mult || 1}x</span>`,
            `<span data-sortvalue="${e.item_chance || 0}">${e.item_chance || 0}</span>`,
            `<span data-sortvalue="${e.bonus_progress || 0}">${e.bonus_progress || 0}</span>`
        ]);
        html += createTable(evHeaders, evRows);
    });

    // Drop tables
    html += '<h3 class="section-title">掉落表</h3>';
    Object.entries(dropTables).forEach(([table, drops]) => {
        html += `<h4 style="color:var(--text-secondary);margin:12px 0 8px;font-size:14px">${esc(table)}</h4>`;
        if (Array.isArray(drops)) {
            const drHeaders = ['物品', '权重'];
            const drRows = drops.map(d => [
                esc(d.item || d.name || d.id || '-'),
                `<span data-sortvalue="${d.weight || 0}">${d.weight || '-'}</span>`
            ]);
            html += createTable(drHeaders, drRows);
        }
    });

    // ====== Bounty (悬赏令) ======
    const bounties = DATA.bounty_templates || {};

    html += '<h3 class="section-title">悬赏令</h3>';
    html += '<div class="info-box">悬赏任务通过对应标签的活动累计进度：巡山/云游/猎魔等历练路线提供不同"冒险标签"，秘境探索也能推进探索类悬赏。</div>';

    // Difficulties
    if (bounties.difficulties) {
        html += '<h4 style="color:var(--text-secondary);margin:16px 0 8px;font-size:14px">难度等级</h4>';
        const bdHeaders = ['难度', '名称', '灵石倍率', '修为倍率', '最低境界'];
        const bdRows = Object.entries(bounties.difficulties).map(([key, d]) => [
            esc(key),
            `<strong>${esc(d.name || '-')}</strong>`,
            `<span data-sortvalue="${d.stone_scale || 1}">${d.stone_scale || 1}x</span>`,
            `<span data-sortvalue="${d.exp_scale || 1}">${d.exp_scale || 1}x</span>`,
            `<span data-sortvalue="${d.min_level || 0}">${levelName(d.min_level || 0)}</span>`
        ]);
        html += createTable(bdHeaders, bdRows);
    }

    // Templates
    if (bounties.templates && bounties.templates.length) {
        html += '<h4 style="color:var(--text-secondary);margin:16px 0 8px;font-size:14px">任务模板</h4>';
        const btHeaders = ['任务', '类别', '难度', '目标数', '时间限制', '灵石奖励', '修为奖励', '权重'];
        const btRows = bounties.templates.map(t => [
            `<strong>${esc(t.name || '-')}</strong><br><span style="font-size:11px;color:var(--text-muted)">${esc(t.description || '')}</span>`,
            esc(t.category || '-'),
            esc(t.difficulty || '-'),
            `${t.min_target || 0}~${t.max_target || 0}`,
            `<span data-sortvalue="${t.time_limit || 0}">${fmtDuration(t.time_limit)}</span>`,
            `<span data-sortvalue="${t.reward?.stone || 0}">${formatNum(t.reward?.stone || 0)}</span>`,
            `<span data-sortvalue="${t.reward?.exp || 0}">${formatNum(t.reward?.exp || 0)}</span>`,
            `<span data-sortvalue="${t.weight || 0}">${t.weight || 0}</span>`
        ]);
        html += createTable(btHeaders, btRows);
    }

    // Item tables
    if (bounties.item_tables) {
        html += '<h4 style="color:var(--text-secondary);margin:16px 0 8px;font-size:14px">悬赏奖励掉落表</h4>';
        Object.entries(bounties.item_tables).forEach(([table, drops]) => {
            html += `<p style="color:var(--cyan);margin:10px 0 4px;font-size:13px;font-weight:500">${esc(table)}</p>`;
            if (Array.isArray(drops)) {
                const biHeaders = ['物品', '权重', '数量'];
                const biRows = drops.map(d => [
                    esc(d.name || d.item || '-'),
                    `<span data-sortvalue="${d.weight || 0}">${d.weight || '-'}</span>`,
                    d.min !== undefined ? `${d.min}~${d.max}` : '-'
                ]);
                html += createTable(biHeaders, biRows);
            }
        });
    }

    page.innerHTML = html;
    makeTableSortable(page);
}

// ===================== Config Helpers =====================

function formatConfigVal(val) {
    if (typeof val === 'number') return formatNum(val);
    if (typeof val === 'boolean') return val ? '是' : '否';
    return esc(String(val));
}

function renderConfigFields(obj) {
    let html = '';
    Object.entries(obj).forEach(([key, val]) => {
        if (key === 'comment') return;
        if (typeof val === 'object' && val !== null && !Array.isArray(val)) {
            html += `<div style="margin:8px 0"><span style="color:var(--text-muted);font-size:12px;display:block;margin-bottom:4px">${esc(key)}</span>`;
            Object.entries(val).forEach(([k, v]) => {
                if (k === 'comment') return;
                if (typeof v === 'object' && v !== null) {
                    Object.entries(v).forEach(([kk, vv]) => {
                        if (typeof vv === 'object') return;
                        html += `<div class="config-row" style="padding-left:12px"><span class="key">${esc(k)}.${esc(kk)}</span><span class="val">${formatConfigVal(vv)}</span></div>`;
                    });
                } else {
                    html += `<div class="config-row"><span class="key">${esc(k)}</span><span class="val">${formatConfigVal(v)}</span></div>`;
                }
            });
            html += '</div>';
        } else if (!Array.isArray(val)) {
            html += `<div class="config-row"><span class="key">${esc(key)}</span><span class="val">${formatConfigVal(val)}</span></div>`;
        }
    });
    return html;
}

// ===================== Global Search =====================

function setupSearch() {
    const input = document.getElementById('global-search');
    let debounce = null;
    input.addEventListener('input', () => {
        clearTimeout(debounce);
        debounce = setTimeout(() => performSearch(input.value.trim()), 200);
    });
}

function performSearch(query) {
    if (!query) {
        document.querySelectorAll('.search-match').forEach(el => el.classList.remove('search-match'));
        document.querySelectorAll('.data-table tbody tr').forEach(tr => tr.style.display = '');
        return;
    }
    const lower = query.toLowerCase();
    document.querySelectorAll('.page.active .data-table tbody tr').forEach(row => {
        const text = row.textContent.toLowerCase();
        if (text.includes(lower)) {
            row.classList.add('search-match');
            row.style.display = '';
        } else {
            row.classList.remove('search-match');
            row.style.display = 'none';
        }
    });
}

// ===================== Render Skills =====================

function renderSkills() {
    const page = document.getElementById('page-skills');
    const skills = DATA.skills || {};
    const skillList = Object.values(skills);

    if (!skillList.length) {
        page.innerHTML = '<h2 class="page-title">神通系统</h2><p>暂无神通数据</p>';
        return;
    }

    const typeLabels = {1: '攻击', 2: '持续', 3: '增益', 4: '控制'};
    const typeKeys = ['attack', 'continuous', 'buff', 'control'];

    const tabs = [1, 2, 3, 4].map((t, i) => {
        const count = skillList.filter(s => s.skill_type === t).length;
        return `<div class="sub-tab${i === 0 ? ' active' : ''}" data-skill-tab="${typeKeys[i]}">${typeLabels[t]} (${count})</div>`;
    }).join('');

    page.innerHTML = `
        <h2 class="page-title">神通系统</h2>
        <p class="page-desc">战斗前装备神通，战斗中自动触发。神通消耗MP，有冷却回合和触发概率。</p>
        <div class="sub-tabs" id="skills-tabs">${tabs}</div>
        <div id="skills-content"></div>
    `;

    function renderTab(tabKey) {
        const typeIdx = typeKeys.indexOf(tabKey) + 1;
        const filtered = skillList.filter(s => s.skill_type === typeIdx).sort((a, b) => (a.required_level_index || 0) - (b.required_level_index || 0));

        let headers, rows;
        if (typeIdx === 1) {
            headers = ['名称', '品阶', '境界', '伤害倍率', '段数', 'MP消耗', 'HP消耗', '冷却', '触发率'];
            rows = filtered.map(s => {
                const av = Array.isArray(s.atkvalue) ? s.atkvalue : [s.atkvalue || 0];
                const hpStr = s.hpcost > 0 ? `${Math.round(s.hpcost * 100)}%` : '-';
                const glowCls = getRankGlowClass(s.rank);
                return `<tr${glowCls ? ` class="${glowCls}"` : ''}>
                    <td class="item-name">${s.name}</td><td>${makeRankBadge(s.rank || '-')}</td><td>Lv${s.required_level_index || 0}</td>
                    <td>${av.join(', ')}</td><td>${av.length}</td><td>${s.mpcost || 0}</td><td>${hpStr}</td>
                    <td>${s.turncost || 0}</td><td>${s.rate || 100}%</td>
                </tr>`;
            }).join('');
        } else if (typeIdx === 2) {
            headers = ['名称', '品阶', '境界', '伤害倍率', '持续', 'MP消耗', '冷却', '触发率'];
            rows = filtered.map(s => {
                const glowCls = getRankGlowClass(s.rank);
                return `<tr${glowCls ? ` class="${glowCls}"` : ''}>
                    <td class="item-name">${s.name}</td><td>${makeRankBadge(s.rank || '-')}</td><td>Lv${s.required_level_index || 0}</td>
                    <td>${s.atkvalue || 0}</td><td>${s.turncost || 0}</td><td>${s.mpcost || 0}</td>
                    <td>${s.turncost || 0}</td><td>${s.rate || 100}%</td>
                </tr>`;
            }).join('');
        } else if (typeIdx === 3) {
            headers = ['名称', '品阶', '境界', '增益类型', '增益幅度', '持续', 'MP消耗', '冷却', '触发率'];
            rows = filtered.map(s => {
                const bt = s.bufftype === 1 ? '攻击' : '防御';
                const bv = `${Math.round((s.buffvalue || 0) * 100)}%`;
                const glowCls = getRankGlowClass(s.rank);
                return `<tr${glowCls ? ` class="${glowCls}"` : ''}>
                    <td class="item-name">${s.name}</td><td>${makeRankBadge(s.rank || '-')}</td><td>Lv${s.required_level_index || 0}</td>
                    <td>${bt}</td><td>${bv}</td><td>${s.turncost || 0}</td><td>${s.mpcost || 0}</td>
                    <td>${s.turncost || 0}</td><td>${s.rate || 100}%</td>
                </tr>`;
            }).join('');
        } else {
            headers = ['名称', '品阶', '境界', '封禁回合', '成功率', 'MP消耗', '冷却', '触发率'];
            rows = filtered.map(s => {
                const glowCls = getRankGlowClass(s.rank);
                return `<tr${glowCls ? ` class="${glowCls}"` : ''}>
                    <td class="item-name">${s.name}</td><td>${makeRankBadge(s.rank || '-')}</td><td>Lv${s.required_level_index || 0}</td>
                    <td>${s.turncost || 0}</td><td>${s.success || 50}%</td><td>${s.mpcost || 0}</td>
                    <td>${s.turncost || 0}</td><td>${s.rate || 100}%</td>
                </tr>`;
            }).join('');
        }

        return `<div class="table-wrapper"><table class="data-table">
            <thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>
            <tbody>${rows || '<tr><td colspan="99">暂无数据</td></tr>'}</tbody>
        </table></div>`;
    }

    document.getElementById('skills-content').innerHTML = renderTab('attack');

    document.getElementById('skills-tabs').addEventListener('click', e => {
        const tab = e.target.closest('.sub-tab');
        if (!tab) return;
        document.querySelectorAll('#skills-tabs .sub-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('skills-content').innerHTML = renderTab(tab.dataset.skillTab);
    });
}

// ===================== Spiritual Roots Page =====================

function getRootGlowClass(rarity) {
    if (rarity === '废柴') return 'root-废柴';
    if (rarity === '凡品' || rarity === '良品') return 'root-凡品';
    if (rarity === '上品' || rarity === '稀有') return 'root-上品';
    if (rarity === '极品' || rarity === '传说') return 'root-极品';
    if (rarity === '神话' || rarity === '禁忌') return 'root-神话';
    return '';
}

function renderRoots() {
    const page = document.getElementById('page-roots');
    const roots = DATA.spiritual_roots || [];

    if (!roots.length) {
        page.innerHTML = '<h2 class="page-title">灵根</h2><div class="info-box">暂无灵根数据</div>';
        return;
    }

    const totalRoots = roots.reduce((sum, r) => sum + r.roots.length, 0);

    // Summary stats
    let html = `
        <h2 class="page-title">灵根</h2>
        <div class="info-box">
            灵根决定修炼速度倍率，创建角色时随机获得。<br>
            使用「重铸灵根」可花费 25万灵石 重新随机，服用「换血丹」也可重置灵根。<br>
            修炼公式：<strong>基础经验 × 分钟数 × 灵根速率 × (1+功法加成) × 丹药加成 × 灵眼加成 × 福地加成</strong>
        </div>
        <h3 class="section-title">数据统计</h3>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value">${totalRoots}</div><div class="stat-label">灵根总数</div></div>
            <div class="stat-card"><div class="stat-value">${roots.length}</div><div class="stat-label">品阶数</div></div>
            <div class="stat-card"><div class="stat-value num-green">×${roots[roots.length - 1].speed}</div><div class="stat-label">最高倍率</div></div>
            <div class="stat-card"><div class="stat-value num-red">×${roots[0].speed}</div><div class="stat-label">最低倍率</div></div>
        </div>
        <h3 class="section-title">灵根品阶一览</h3>
    `;

    // Build table
    const headers = ['品阶', '灵根', '修炼速率', '单根权重', '总权重', '出现概率'];
    const rows = roots.map(r => {
        const glowClass = getRootGlowClass(r.rarity);
        const badge = `<span class="root-badge root-${r.rarity}">${esc(r.rarity)}</span>`;
        const rootNames = r.roots.map(n => `<code>${esc(n)}</code>`).join(' ');
        return [
            badge,
            rootNames,
            `<strong>${esc(r.speed_display)}</strong>`,
            r.weight,
            r.total_weight,
            `<strong>${esc(r.probability)}</strong>`
        ];
    });

    html += createTable(headers, rows, { sortable: false, emptyText: '暂无数据' });

    // Detail cards
    html += '<h3 class="section-title">品阶详情</h3>';
    html += '<div class="item-grid">';
    roots.forEach(r => {
        const glowClass = getRootGlowClass(r.rarity);
        html += `
            <div class="item-card ${glowClass}">
                <div class="item-header">
                    <span class="root-badge root-${r.rarity}">${esc(r.rarity)}</span>
                    <span class="item-rank">${esc(r.speed_display)}</span>
                </div>
                <h3 class="item-name">${esc(r.rarity)}灵根</h3>
                <div class="item-desc">${esc(r.description)}</div>
                <div class="special-attrs">
                    <div>灵根：${r.roots.map(n => '<code>' + esc(n) + '</code>').join(' ')}</div>
                    <div>出现概率：${esc(r.probability)}（单根）</div>
                </div>
            </div>
        `;
    });
    html += '</div>';

    page.innerHTML = html;
    observeCards(page);
}

// ===================== Render Dispatcher =====================

function renderPage(name) {
    switch (name) {
        case 'overview': renderOverview(); break;
        case 'levels': renderLevels(); break;
        case 'pills': renderPills(); break;
        case 'equipment': renderEquipment(); break;
        case 'combat': renderCombat(); break;
        case 'systems': renderSystems(); break;
        case 'commands': renderCommands(); break;
        case 'alchemy': renderAlchemy(); break;
        case 'adventure': renderAdventure(); break;
        case 'skills': renderSkills(); break;
        case 'roots': renderRoots(); break;
    }
}

// ===================== Init =====================

async function init() {
    const loading = document.getElementById('loading');
    try {
        await loadAllData();
        loading.classList.add('hidden');

        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                showPage(link.dataset.page);
            });
        });

        setupModal();
        setupSearch();
        showPage('overview');
    } catch (err) {
        loading.innerHTML = `<p style="color:var(--red)">加载失败: ${err.message}</p>`;
        console.error(err);
    }
}

document.addEventListener('DOMContentLoaded', init);
