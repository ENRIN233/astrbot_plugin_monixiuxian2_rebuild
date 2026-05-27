// app.js - 修仙资料库 SPA

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

function rankClass(rank) {
    if (!rank) return '';
    return 'rank-' + rank;
}

function rankOrder(rank) {
    const order = ['凡品','灵品','珍品','圣品','地品','天品','皇品','帝品','道品','仙品','神品','混元先天'];
    const idx = order.indexOf(rank);
    return idx >= 0 ? idx : 99;
}

function esc(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function makeRankBadge(rank) {
    return `<span class="rank-badge ${rankClass(rank)}">${esc(rank)}</span>`;
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
        'alchemy_recipes', 'adventure_config', 'bounty_templates', 'game_config'
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
    }
}

// ===================== Table Helpers =====================

function createTable(headers, rows, options = {}) {
    const { sortable = true, onRowClick, emptyText = '暂无数据' } = options;
    if (rows.length === 0) {
        return `<div class="table-wrapper"><div style="padding:24px;text-align:center;color:var(--text-muted)">${emptyText}</div></div>`;
    }
    let html = '<div class="table-wrapper"><table class="data-table"><thead><tr>';
    headers.forEach((h, i) => {
        const sortAttr = sortable ? ` data-col="${i}"` : '';
        const cls = sortable ? ' class="sortable-header"' : '';
        html += `<th${cls}${sortAttr}>${esc(h.label)}${sortable ? '<span class="sort-arrow">&#9650;</span>' : ''}</th>`;
    });
    html += '</tr></thead><tbody>';
    rows.forEach((row, ri) => {
        const clickAttr = onRowClick ? ` class="clickable" data-row="${ri}"` : '';
        html += `<tr${clickAttr}>`;
        row.forEach(cell => {
            html += `<td>${cell}</td>`;
        });
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

            table.querySelectorAll('th').forEach(h => {
                h.classList.remove('sorted');
                h.dataset.dir = '';
            });
            th.classList.add('sorted');
            th.dataset.dir = isAsc ? 'desc' : 'asc';

            rows.sort((a, b) => {
                const aVal = a.cells[col].dataset.sortvalue || a.cells[col].textContent.trim();
                const bVal = b.cells[col].dataset.sortvalue || b.cells[col].textContent.trim();
                const aNum = parseFloat(aVal);
                const bNum = parseFloat(bVal);
                let cmp;
                if (!isNaN(aNum) && !isNaN(bNum)) {
                    cmp = aNum - bNum;
                } else {
                    cmp = aVal.localeCompare(bVal, 'zh');
                }
                return isAsc ? -cmp : cmp;
            });
            rows.forEach(r => tbody.appendChild(r));
        });
    });
}

// ===================== Modal =====================

function showModal(title, html) {
    const modal = document.getElementById('detail-modal');
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

    page.innerHTML = `
        <h2 class="page-title">总览</h2>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value">${levels.length}</div><div class="stat-label">灵修境界</div></div>
            <div class="stat-card"><div class="stat-value">${bodyLevels.length}</div><div class="stat-label">体修境界</div></div>
            <div class="stat-card"><div class="stat-value">${pills.length}</div><div class="stat-label">突破丹药</div></div>
            <div class="stat-card"><div class="stat-value">${expPills.length}</div><div class="stat-label">修为丹药</div></div>
            <div class="stat-card"><div class="stat-value">${utilPills.length}</div><div class="stat-label">功能丹药</div></div>
            <div class="stat-card"><div class="stat-value">${weapons.length}</div><div class="stat-label">武器</div></div>
            <div class="stat-card"><div class="stat-value">${techniques.length}</div><div class="stat-label">主修心法</div></div>
            <div class="stat-card"><div class="stat-value">${subTechniques.length}</div><div class="stat-label">辅助功法</div></div>
            <div class="stat-card"><div class="stat-value">${ringCount}</div><div class="stat-label">储物戒</div></div>
            <div class="stat-card"><div class="stat-value">${recipeCount}</div><div class="stat-label">炼丹配方</div></div>
            <div class="stat-card"><div class="stat-value">${materials.length}</div><div class="stat-label">材料</div></div>
            <div class="stat-card"><div class="stat-value">${artifacts.length + manuals.length + oldPills.length}</div><div class="stat-label">旧系统道具</div></div>
        </div>
        <h3 class="section-title">丹药分布</h3>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value num-green">${permPills.length}</div><div class="stat-label">永久属性丹</div></div>
            <div class="stat-card"><div class="stat-value num-cyan">${tempPills.length}</div><div class="stat-label">临时增益丹</div></div>
            <div class="stat-card"><div class="stat-value num-gold">${instantPills.length}</div><div class="stat-label">瞬时效果丹</div></div>
        </div>
    `;
}

// ===================== Levels =====================

function renderLevels() {
    const page = document.getElementById('page-levels');
    page.innerHTML = `
        <h2 class="page-title">境界系统</h2>
        <div class="sub-tabs">
            <div class="sub-tab active" data-level-type="spiritual">灵修境界</div>
            <div class="sub-tab" data-level-type="body">体修境界</div>
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
    const levels = DATA.level_config || [];
    const bodyLevels = DATA.body_level_config || [];

    function levelName(idx) {
        const names = [];
        if (idx < levels.length) names.push(levels[idx].level_name);
        if (idx < bodyLevels.length && bodyLevels[idx].level_name !== levels[idx]?.level_name) names.push(bodyLevels[idx].level_name);
        return names.join(' / ') || '未知';
    }

    const headers = ['ID', '名称', '品阶', '价格', '突破路径', '突破加成', '最高成功率'];
    const rows = pills.map(p => {
        const fromLv = levelName(p.required_level_index);
        const toLv = levelName(p.target_level_index);
        return [
            `<code>${esc(p.id)}</code>`,
            `<strong>${esc(p.name)}</strong>`,
            makeRankBadge(p.rank),
            `<span data-sortvalue="${p.price}">${formatNum(p.price)}</span>`,
            `<span class="level-path">${esc(fromLv)} <span class="level-arrow">→</span> ${esc(toLv)}</span>`,
            `<span data-sortvalue="${p.breakthrough_bonus}">+${formatRate(p.breakthrough_bonus)}</span>`,
            `<span data-sortvalue="${p.max_success_rate}">${formatRate(p.max_success_rate)}</span>`
        ];
    });

    container.innerHTML = createTable(headers, rows);
    makeTableSortable(container);
    addPillRowClicks(container, pills, 'breakthrough');
}

function renderExpPills(container) {
    const pills = DATA.exp_pills || [];
    const levels = DATA.level_config || [];
    const bodyLevels = DATA.body_level_config || [];

    function levelName(idx) {
        const names = [];
        if (idx < levels.length) names.push(levels[idx].level_name);
        if (idx < bodyLevels.length && bodyLevels[idx].level_name !== levels[idx]?.level_name) names.push(bodyLevels[idx].level_name);
        return names.join(' / ') || '未知';
    }

    const headers = ['ID', '名称', '品阶', '价格', '修为增益', '最低境界'];
    const rows = pills.map(p => [
        `<code>${esc(p.id)}</code>`,
        `<strong>${esc(p.name)}</strong>`,
        makeRankBadge(p.rank),
        `<span data-sortvalue="${p.price}">${formatNum(p.price)}</span>`,
        `<span data-sortvalue="${p.exp_gain}" class="num-green">+${formatNum(p.exp_gain)}</span>`,
        esc(levelName(p.required_level_index))
    ]);

    container.innerHTML = createTable(headers, rows);
    makeTableSortable(container);
    addPillRowClicks(container, pills, 'exp');
}

function renderUtilityPills(container) {
    const pills = DATA.utility_pills || [];
    const subtypeGroups = {};
    const subtypeLabels = {
        'resurrection': '复活丹',
        'cultivation_boost': '修炼加速丹',
        'permanent_attribute': '永久属性丹',
        'combat_boost': '战斗临时丹·进攻',
        'defensive_boost': '战斗临时丹·防御',
        'instant_restore': '瞬回丹',
        'regeneration': '回复丹',
        'breakthrough_boost': '突破辅助丹',
        'breakthrough_debuff': '突破负面丹',
        'special': '特殊丹药',
        'reset': '重置丹',
        'protection': '防护丹',
        'chaos_boost': '随机丹',
        'debuff': '负面丹',
        'buff': '增益丹'
    };

    pills.forEach(p => {
        const sub = p.subtype || 'other';
        if (!subtypeGroups[sub]) subtypeGroups[sub] = [];
        subtypeGroups[sub].push(p);
    });

    let filterHtml = '<div class="filter-bar"><span class="filter-label">品阶：</span>';
    const ranks = [...new Set(pills.map(p => p.rank))].sort((a, b) => rankOrder(a) - rankOrder(b));
    filterHtml += '<button class="filter-btn active" data-rank="all">全部</button>';
    ranks.forEach(r => {
        filterHtml += `<button class="filter-btn" data-rank="${esc(r)}">${esc(r)}</button>`;
    });
    filterHtml += '</div>';

    let html = filterHtml;
    const order = ['cultivation_boost', 'permanent_attribute', 'resurrection', 'combat_boost', 'defensive_boost',
        'instant_restore', 'regeneration', 'breakthrough_boost', 'breakthrough_debuff',
        'special', 'reset', 'protection', 'chaos_boost', 'debuff', 'buff'];

    const sortedSubtypes = Object.keys(subtypeGroups).sort((a, b) => {
        const ai = order.indexOf(a);
        const bi = order.indexOf(b);
        return (ai >= 0 ? ai : 99) - (bi >= 0 ? bi : 99);
    });

    sortedSubtypes.forEach(sub => {
        const group = subtypeGroups[sub];
        const label = subtypeLabels[sub] || sub;
        html += `<h3 class="section-title">${esc(label)} (${group.length}种)</h3>`;
        html += renderUtilityPillTable(group);
    });

    container.innerHTML = html;

    // Rank filter
    container.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            container.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const rank = btn.dataset.rank;
            container.querySelectorAll('.data-table tbody tr').forEach(row => {
                if (rank === 'all') {
                    row.style.display = '';
                } else {
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
    return createTable(headers, rows);
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

    container.innerHTML = createTable(headers, rows);
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
        if (pill.required_level_index !== undefined) fields.push(modalField('最低境界', 'level_index ' + pill.required_level_index));
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

    if (fields.length) {
        html += modalSection('效果属性', fields.join(''));
    }

    showModal(pill.name, html);
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
    ranks.forEach(r => {
        filterHtml += `<button class="filter-btn" data-rank="${esc(r)}">${esc(r)}</button>`;
    });
    filterHtml += '</div>';

    let html = filterHtml;

    // Weapons by category
    const catOrder = ['剑','刀','阔刀','琴','匕首','符箓','鼎','棍','枪','笔'];
    const sortedCats = Object.keys(categories).sort((a, b) => {
        const ai = catOrder.indexOf(a);
        const bi = catOrder.indexOf(b);
        return (ai >= 0 ? ai : 99) - (bi >= 0 ? bi : 99);
    });

    sortedCats.forEach(cat => {
        const group = categories[cat];
        html += `<h3 class="section-title">${esc(cat)}类武器 (${group.length}把)</h3>`;
        const headers = ['名称', '品阶', '价格', '物伤', '法伤', '物防', '法防', '精神力'];
        const rows = group.map(w => [
            `<strong>${esc(w.name)}</strong>`,
            makeRankBadge(w.rank),
            `<span data-sortvalue="${w.price || 0}">${formatNum(w.price || 0)}</span>`,
            `<span data-sortvalue="${w.physical_damage || 0}">${w.physical_damage || 0}</span>`,
            `<span data-sortvalue="${w.magic_damage || 0}">${w.magic_damage || 0}</span>`,
            `<span data-sortvalue="${w.physical_defense || 0}">${w.physical_defense || 0}</span>`,
            `<span data-sortvalue="${w.magic_defense || 0}">${w.magic_defense || 0}</span>`,
            `<span data-sortvalue="${w.mental_power || 0}">${w.mental_power || 0}</span>`
        ]);
        html += createTable(headers, rows, { onRowClick: true });
    });

    // Armor section
    if (armors.length) {
        html += `<h3 class="section-title">防具 (${armors.length}件)</h3>`;
        const headers = ['名称', '品阶', '价格', '物防', '法防', '物伤', '法伤', '精神力'];
        const rows = armors.map(a => [
            `<strong>${esc(a.name)}</strong>`,
            makeRankBadge(a.rank),
            `<span data-sortvalue="${a.price || 0}">${formatNum(a.price || 0)}</span>`,
            `<span data-sortvalue="${a.physical_defense || 0}">${a.physical_defense || 0}</span>`,
            `<span data-sortvalue="${a.magic_defense || 0}">${a.magic_defense || 0}</span>`,
            `<span data-sortvalue="${a.physical_damage || 0}">${a.physical_damage || 0}</span>`,
            `<span data-sortvalue="${a.magic_damage || 0}">${a.magic_damage || 0}</span>`,
            `<span data-sortvalue="${a.mental_power || 0}">${a.mental_power || 0}</span>`
        ]);
        html += createTable(headers, rows);
    }

    container.innerHTML = html;

    container.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            container.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const rank = btn.dataset.rank;
            container.querySelectorAll('.data-table tbody tr').forEach(row => {
                if (rank === 'all') {
                    row.style.display = '';
                } else {
                    const badge = row.querySelector('.rank-badge');
                    row.style.display = (badge && badge.textContent === rank) ? '' : 'none';
                }
            });
        });
    });

    makeTableSortable(container);

    // Row click for weapon detail
    container.querySelectorAll('tr.clickable').forEach(row => {
        row.addEventListener('click', () => {
            const cat = row.closest('table').previousElementSibling?.textContent || '';
            const idx = parseInt(row.dataset.row);
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
    if (w.atk_bonus) combatHtml += modalField('攻击加成', `+${w.atk_bonus}`);
    if (w.crit_rate) combatHtml += modalField('暴击率', `+${formatRate(w.crit_rate)}`);
    if (w.crit_damage) combatHtml += modalField('暴击伤害', `+${formatRate(w.crit_damage)}`);
    if (w.armor_pen) combatHtml += modalField('穿透', `+${w.armor_pen}`);
    if (w.double_hit) combatHtml += modalField('连击', `+${formatRate(w.double_hit)}`);
    if (w.lifesteal) combatHtml += modalField('吸血', `+${formatRate(w.lifesteal)}`);
    if (combatHtml) html += modalSection('战斗属性', combatHtml);

    if (w.shop_weight !== undefined) {
        html += modalSection('其他', modalField('商店权重', w.shop_weight));
    }

    showModal(w.name, html);
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
    ranks.forEach(r => {
        filterHtml += `<button class="filter-btn" data-rank="${esc(r)}">${esc(r)}</button>`;
    });
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
                if (rank === 'all') {
                    row.style.display = '';
                } else {
                    const badge = row.querySelector('.rank-badge');
                    row.style.display = (badge && badge.textContent === rank) ? '' : 'none';
                }
            });
        });
    });

    makeTableSortable(container);
}

function renderTechniqueTable(techs, isMain) {
    const headers = ['名称', '品阶', '修为倍率', '灵气加成', '气血加成', '最低境界', '价格'];
    const rows = techs.map(t => [
        `<strong>${esc(t.name)}</strong>`,
        makeRankBadge(t.rank || ''),
        `<span data-sortvalue="${t.exp_multiplier || 0}">${t.exp_multiplier ? (t.exp_multiplier * 100).toFixed(1) + '%' : '-'}</span>`,
        `<span data-sortvalue="${t.spiritual_qi || 0}">${t.spiritual_qi || 0}</span>`,
        `<span data-sortvalue="${t.blood_qi || 0}">${t.blood_qi || 0}</span>`,
        `level_index ${t.required_level_index || 0}`,
        `<span data-sortvalue="${t.price || 0}">${formatNum(t.price || 0)}</span>`
    ]);
    return createTable(headers, rows, { emptyText: '暂无心法数据' });
}

function renderRings(container) {
    const rings = DATA.storage_rings;
    let ringArr = [];
    if (Array.isArray(rings)) {
        ringArr = rings;
    } else if (rings && typeof rings === 'object') {
        ringArr = Object.values(rings);
    }

    const headers = ['名称', '品阶', '容量', '需求境界', '价格'];
    const rows = ringArr.map(r => [
        `<strong>${esc(r.name)}</strong>`,
        makeRankBadge(r.rank || ''),
        `<span data-sortvalue="${r.capacity || 0}">${r.capacity || 0} 格</span>`,
        `level_index ${r.required_level_index || 0}`,
        `<span data-sortvalue="${r.price || 0}">${formatNum(r.price || 0)}</span>`
    ]);

    container.innerHTML = createTable(headers, rows);
    makeTableSortable(container);
}

// ===================== Alchemy =====================

function renderAlchemy() {
    const page = document.getElementById('page-alchemy');
    const recipes = DATA.alchemy_recipes || [];

    const headers = ['配方名称', '需求境界', '材料', '成功率'];
    const rows = recipes.map(r => {
        const materials = r.materials || {};
        const matStr = Object.entries(materials).map(([name, qty]) => `${name}×${qty}`).join('，');
        return [
            `<strong>${esc(r.name)}</strong>`,
            `level_index ${r.level_required || 0}`,
            esc(matStr || '-'),
            `<span data-sortvalue="${r.success_rate || 0}">${r.success_rate || 0}%</span>`
        ];
    });

    page.innerHTML = `
        <h2 class="page-title">炼丹配方</h2>
        ${createTable(headers, rows)}
    `;
    makeTableSortable(page);
}

// ===================== Adventure =====================

function renderAdventure() {
    const page = document.getElementById('page-adventure');
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
        `<span data-sortvalue="${r.duration || 0}">${r.duration ? Math.round(r.duration / 60) + '分' : '-'}</span>`,
        `<span data-sortvalue="${r.base_exp_per_min || 0}">${r.base_exp_per_min || 0}</span>`,
        `<span data-sortvalue="${r.base_gold_per_min || 0}">${formatNum(r.base_gold_per_min || 0)}</span>`,
        `<span data-sortvalue="${r.level_bonus_exp || 0}">${r.level_bonus_exp || 0}</span>`,
        `<span data-sortvalue="${r.level_bonus_gold || 0}">${formatNum(r.level_bonus_gold || 0)}</span>`,
        `<span data-sortvalue="${r.completion_bonus?.exp || 0}">${formatNum(r.completion_bonus?.exp || 0)}</span>`,
        `<span data-sortvalue="${r.completion_bonus?.gold || 0}">${formatNum(r.completion_bonus?.gold || 0)}</span>`,
        `<span data-sortvalue="${r.fatigue_cooldown || 0}">${r.fatigue_cooldown ? Math.round(r.fatigue_cooldown / 60) + '分' : '-'}</span>`
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
        html += `<h4 style="color:var(--text-secondary);margin:12px 0 8px">${esc(group)} (${events.length}个事件)</h4>`;
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
        html += `<h4 style="color:var(--text-secondary);margin:12px 0 8px">${esc(table)}</h4>`;
        if (Array.isArray(drops)) {
            const drHeaders = ['物品', '权重'];
            const drRows = drops.map(d => [
                esc(d.item || d.name || d.id || '-'),
                `<span data-sortvalue="${d.weight || 0}">${d.weight || '-'}</span>`
            ]);
            html += createTable(drHeaders, drRows);
        }
    });

    page.innerHTML = html;
    makeTableSortable(page);
}

// ===================== System =====================

function renderSystem() {
    const page = document.getElementById('page-system');
    const config = DATA.game_config || {};
    const bounties = DATA.bounty_templates || {};

    let html = '<h2 class="page-title">系统配置</h2>';

    // Game config cards
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

    // Bounties
    html += '<h3 class="section-title">悬赏任务</h3>';
    if (bounties.difficulties) {
        const headers = ['难度', '名称', '灵石倍率', '修为倍率', '最低境界'];
        const rows = Object.entries(bounties.difficulties).map(([key, d]) => [
            esc(key),
            esc(d.name || '-'),
            `<span data-sortvalue="${d.stone_scale || 1}">${d.stone_scale || 1}x</span>`,
            `<span data-sortvalue="${d.exp_scale || 1}">${d.exp_scale || 1}x</span>`,
            `level_index ${d.min_level || 0}`
        ]);
        html += createTable(headers, rows);
    }

    if (bounties.templates && bounties.templates.length) {
        html += '<h4 style="color:var(--text-secondary);margin:16px 0 8px">任务模板</h4>';
        const headers = ['任务', '类别', '难度', '目标数', '时间限制', '灵石奖励', '修为奖励', '权重'];
        const rows = bounties.templates.map(t => [
            `<strong>${esc(t.name || '-')}</strong><br><span style="font-size:11px;color:var(--text-muted)">${esc(t.description || '')}</span>`,
            esc(t.category || '-'),
            esc(t.difficulty || '-'),
            `${t.min_target || 0}~${t.max_target || 0}`,
            `<span data-sortvalue="${t.time_limit || 0}">${t.time_limit ? Math.round(t.time_limit / 60) + '分' : '-'}</span>`,
            `<span data-sortvalue="${t.reward?.stone || 0}">${formatNum(t.reward?.stone || 0)}</span>`,
            `<span data-sortvalue="${t.reward?.exp || 0}">${formatNum(t.reward?.exp || 0)}</span>`,
            `<span data-sortvalue="${t.weight || 0}">${t.weight || 0}</span>`
        ]);
        html += createTable(headers, rows);
    }

    if (bounties.item_tables) {
        html += '<h4 style="color:var(--text-secondary);margin:16px 0 8px">奖励掉落表</h4>';
        Object.entries(bounties.item_tables).forEach(([table, drops]) => {
            html += `<p style="color:var(--cyan);margin:8px 0 4px">${esc(table)}</p>`;
            if (Array.isArray(drops)) {
                const drHeaders = ['物品', '权重'];
                const drRows = drops.map(d => [
                    esc(d.item || d.name || d.id || '-'),
                    `<span data-sortvalue="${d.weight || 0}">${d.weight || '-'}</span>`
                ]);
                html += createTable(drHeaders, drRows);
            }
        });
    }

    page.innerHTML = html;
    makeTableSortable(page);
}

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
                    // One level deeper (e.g., spirit_eye.types.1)
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
        // Clear search highlights and restore all rows
        document.querySelectorAll('.search-match').forEach(el => el.classList.remove('search-match'));
        document.querySelectorAll('.data-table tbody tr').forEach(tr => tr.style.display = '');
        return;
    }

    const lower = query.toLowerCase();

    // Search across current page tables
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

// ===================== Render Dispatcher =====================

function renderPage(name) {
    switch (name) {
        case 'overview': renderOverview(); break;
        case 'levels': renderLevels(); break;
        case 'pills': renderPills(); break;
        case 'equipment': renderEquipment(); break;
        case 'alchemy': renderAlchemy(); break;
        case 'adventure': renderAdventure(); break;
        case 'system': renderSystem(); break;
    }
}

// ===================== Init =====================

async function init() {
    const loading = document.getElementById('loading');
    try {
        await loadAllData();
        loading.classList.add('hidden');

        // Setup navigation
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const pageName = link.dataset.page;
                showPage(pageName);
            });
        });

        // Setup modal
        setupModal();

        // Setup search
        setupSearch();

        // Render initial page
        showPage('overview');

    } catch (err) {
        loading.innerHTML = `<p style="color:var(--red)">加载失败: ${err.message}</p>`;
        console.error(err);
    }
}

document.addEventListener('DOMContentLoaded', init);
