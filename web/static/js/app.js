/**
 * 雪球交易系统 - 管理后台 JavaScript
 */

// ============ 常量定义 ============
const SCRIPTS = {
    'auto_track': '自动跟踪同步',
    'simulator': '模拟仓操作',
    'follower': '组合跟踪',
    'trader': '交易演示'
};

// ============ 状态管理 ============
const state = {
    runningScripts: {},
    systemLogs: [],
    scriptLogs: {}
};

// ============ 工具函数 ============
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function toast(msg, type = 'success') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = `toast ${type}`;
    el.style.display = 'block';
    setTimeout(() => el.style.display = 'none', 3000);
}

// ============ 日志管理 (SSE) ============
let eventSource = null;

function toggleLog(id) {
    document.getElementById(`log-${id}`).classList.toggle('expanded');
}

function clearLog(id) {
    state.scriptLogs[id] = [];
    document.getElementById(`content-${id}`).innerHTML = '<div class="empty-log">日志已清空</div>';
}

function clearSystemLog() {
    fetch('/api/logs/clear', { method: 'POST' });
    state.systemLogs = [];
    document.getElementById('system-log').innerHTML = '<div class="empty-log">日志已清空</div>';
}

function appendLogEntry(log) {
    // 判断日志类型
    if (log.script === 'system') {
        state.systemLogs.push(log);
        appendToContainer('system-log', log);
    } else {
        const id = Object.keys(SCRIPTS).find(k => SCRIPTS[k] === log.script);
        if (id) {
            if (!state.scriptLogs[id]) state.scriptLogs[id] = [];
            state.scriptLogs[id].push(log);
            appendToContainer(`content-${id}`, log);
        } else {
            state.systemLogs.push(log);
            appendToContainer('system-log', log);
        }
    }
}

function appendToContainer(containerId, log) {
    const el = document.getElementById(containerId);
    if (!el) return;

    // 如果是空状态，先清空
    if (el.querySelector('.empty-log')) {
        el.innerHTML = '';
    }

    const entry = document.createElement('div');
    entry.className = `log-entry ${log.level}`;
    entry.innerHTML = `<span class="log-time">${log.time}</span><span class="log-msg">${escapeHtml(log.message)}</span>`;
    el.appendChild(entry);
    el.scrollTop = el.scrollHeight;

    // 限制日志条数，避免内存溢出
    while (el.children.length > 200) {
        el.removeChild(el.firstChild);
    }
}

function connectSSE() {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource('/api/logs/stream');

    // 监听日志事件
    eventSource.addEventListener('log', function (event) {
        try {
            const log = JSON.parse(event.data);
            appendLogEntry(log);
        } catch (e) {
            console.error('解析日志失败', e);
        }
    });

    // 监听脚本状态事件
    eventSource.addEventListener('script_status', function (event) {
        try {
            const data = JSON.parse(event.data);
            updateScriptUI(data.scripts);
        } catch (e) {
            console.error('解析脚本状态失败', e);
        }
    });

    eventSource.onerror = function (e) {
        console.error('SSE连接错误，5秒后重连...');
        eventSource.close();
        setTimeout(connectSSE, 5000);
    };

    console.log('SSE事件流已连接');
}

// ============ 脚本控制 ============
async function toggleScript(id) {
    const isRunning = state.runningScripts[id];
    try {
        const res = await fetch(`/api/scripts/${id}/${isRunning ? 'stop' : 'start'}`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            toast(isRunning ? '脚本已停止' : '脚本启动成功!');
            if (!isRunning) {
                document.getElementById(`log-${id}`).classList.add('expanded');
            }
            // 状态将通过SSE推送，不需要主动请求
        } else {
            toast(data.error || '操作失败', 'error');
        }
    } catch (e) {
        toast('请求失败', 'error');
    }
}

function updateScriptUI(scripts) {
    // 通过SSE推送的状态更新UI
    scripts.forEach(s => {
        state.runningScripts[s.id] = s.running;
        const card = document.getElementById(`card-${s.id}`);
        const badge = document.getElementById(`badge-${s.id}`);
        const btn = document.getElementById(`btn-${s.id}`);

        if (!card || !badge || !btn) return;

        if (s.running) {
            card.classList.add('running');
            badge.style.display = 'inline';
            btn.textContent = '停止';
            btn.className = 'btn btn-danger btn-sm';
        } else {
            card.classList.remove('running');
            badge.style.display = 'none';
            btn.textContent = '启动';
            btn.className = 'btn btn-success btn-sm';
        }
    });
}

// ============ 弹窗管理 ============
function openModal(title) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = '<div class="loading">加载中...</div>';
    document.getElementById('modal').classList.add('show');
}

function closeModal(e) {
    if (!e || e.target.id === 'modal') {
        document.getElementById('modal').classList.remove('show');
    }
}

async function showPortfolioDetail(inputId) {
    const code = document.getElementById(inputId).value.trim();
    if (!code) {
        toast('请先输入组合代码', 'error');
        return;
    }
    openModal(`组合详情: ${code}`);

    try {
        const res = await fetch(`/api/portfolio/${code}`);
        const data = await res.json();
        if (data.success) {
            const p = data.portfolio;
            const html = `
                <div class="detail-row"><span class="detail-label">组合代码</span><span class="detail-value">${p.code}</span></div>
                <div class="detail-row"><span class="detail-label">组合名称</span><span class="detail-value">${p.name || '-'}</span></div>
                <div class="detail-row"><span class="detail-label">净值</span><span class="detail-value">${p.net_value?.toFixed(4) || '-'}</span></div>
                <div class="detail-row"><span class="detail-label">今日涨幅</span><span class="detail-value" style="color:${(p.daily_gain || 0) >= 0 ? 'var(--success)' : 'var(--error)'}">${((p.daily_gain || 0) * 100).toFixed(2)}%</span></div>
                <div class="detail-row"><span class="detail-label">现金比例</span><span class="detail-value">${p.cash_weight?.toFixed(2) || 0}%</span></div>
                <h4 style="margin-top:20px;margin-bottom:10px;">持仓明细 (${p.holdings?.length || 0})</h4>
                <table class="holdings-table">
                    <thead><tr><th>名称</th><th>代码</th><th>权重</th></tr></thead>
                    <tbody>${(p.holdings || []).map(h => `<tr><td>${h.name}</td><td>${h.symbol}</td><td>${h.weight?.toFixed(2)}%</td></tr>`).join('')}</tbody>
                </table>`;
            document.getElementById('modal-body').innerHTML = html;
        } else {
            document.getElementById('modal-body').innerHTML = `<div class="empty-log">获取失败: ${data.error}</div>`;
        }
    } catch (e) {
        document.getElementById('modal-body').innerHTML = '<div class="empty-log">请求失败</div>';
    }
}

async function showSimulatorDetail() {
    const gid = document.getElementById('simulator_gid').value.trim();
    if (!gid) {
        toast('请先输入模拟仓GID', 'error');
        return;
    }
    openModal(`模拟仓详情: ${gid}`);

    try {
        const res = await fetch(`/api/simulator/${gid}`);
        const data = await res.json();
        if (data.success) {
            const s = data.simulator;
            const html = `
                <div class="detail-row"><span class="detail-label">模拟仓 GID</span><span class="detail-value">${s.gid}</span></div>
                <div class="detail-row"><span class="detail-label">总资产</span><span class="detail-value">¥${s.total_assets?.toLocaleString() || 0}</span></div>
                <div class="detail-row"><span class="detail-label">现金</span><span class="detail-value">¥${s.cash?.toLocaleString() || 0}</span></div>
                <div class="detail-row"><span class="detail-label">市值</span><span class="detail-value">¥${s.market_value?.toLocaleString() || 0}</span></div>
                <div class="detail-row"><span class="detail-label">收益</span><span class="detail-value" style="color:${(s.profit || 0) >= 0 ? 'var(--success)' : 'var(--error)'}">¥${s.profit?.toLocaleString() || 0}</span></div>
                <div class="detail-row"><span class="detail-label">收益率</span><span class="detail-value" style="color:${(s.profit_rate || 0) >= 0 ? 'var(--success)' : 'var(--error)'}">${((s.profit_rate || 0) * 100).toFixed(2)}%</span></div>
                <h4 style="margin-top:20px;margin-bottom:10px;">持仓明细 (${s.holdings?.length || 0})</h4>
                <table class="holdings-table">
                    <thead><tr><th>名称</th><th>代码</th><th>股数</th><th>市值</th></tr></thead>
                    <tbody>${(s.holdings || []).map(h => `<tr><td>${h.name || '-'}</td><td>${h.symbol || '-'}</td><td>${h.shares || 0}</td><td>¥${(h.market_value || 0).toLocaleString()}</td></tr>`).join('')}</tbody>
                </table>`;
            document.getElementById('modal-body').innerHTML = html;
        } else {
            document.getElementById('modal-body').innerHTML = `<div class="empty-log">获取失败: ${data.error}</div>`;
        }
    } catch (e) {
        document.getElementById('modal-body').innerHTML = '<div class="empty-log">请求失败</div>';
    }
}

function showMyPortfolioDetail() {
    const codes = document.getElementById('my_portfolio_code').value.split(',').map(s => s.trim()).filter(s => s);
    if (!codes.length) {
        toast('请先输入组合代码', 'error');
        return;
    }
    showPortfolioDetail('my_portfolio_code');
}

// ============ 配置管理 ============
let currentConfig = {};  // 保存当前配置用于对比

async function loadConfig() {
    try {
        const res = await fetch('/api/config');
        const data = await res.json();
        if (data.success) {
            const c = data.config;
            currentConfig = { ...c };  // 保存当前配置

            document.getElementById('portfolio_code').value = c.portfolio_code || '';
            document.getElementById('target_portfolio_code').value = c.target_portfolio_code || '';
            document.getElementById('simulator_gid').value = c.simulator_gid || '';
            document.getElementById('initial_assets').value = c.initial_assets || '';
            document.getElementById('track_interval').value = c.track_interval || '';
            document.getElementById('my_portfolio_code').value = Array.isArray(c.my_portfolio_code) ? c.my_portfolio_code.join(', ') : c.my_portfolio_code || '';
            document.getElementById('cookies').value = c.cookies || '';

            // 加载组合名称
            loadPortfolioName('portfolio_code', c.portfolio_code);
            loadPortfolioName('target_portfolio_code', c.target_portfolio_code);
            loadSimulatorName(c.simulator_gid);
            if (c.my_portfolio_code) {
                const codes = Array.isArray(c.my_portfolio_code) ? c.my_portfolio_code : [c.my_portfolio_code];
                if (codes[0]) loadPortfolioName('my_portfolio_code', codes[0]);
            }
        }
    } catch (e) {
        toast('加载配置失败', 'error');
    }
}

async function validatePortfolioCode(code) {
    /**
     * 验证组合代码是否有效
     * @returns {Object|null} 组合信息或 null（无效）
     */
    if (!code || !code.trim()) return { valid: true, name: '' };

    try {
        const res = await fetch(`/api/portfolio/${code.trim()}`);
        const data = await res.json();
        if (data.success && data.portfolio && data.portfolio.name) {
            return { valid: true, name: data.portfolio.name };
        }
        return { valid: false, error: `组合 ${code} 不存在或无法获取` };
    } catch (e) {
        return { valid: false, error: `验证组合 ${code} 失败: 网络错误` };
    }
}

async function validateSimulatorGid(gid) {
    /**
     * 验证模拟仓 GID 是否有效
     */
    if (!gid) return { valid: true };

    try {
        const res = await fetch(`/api/simulator/${gid}`);
        const data = await res.json();
        if (data.success && data.simulator) {
            return { valid: true, assets: data.simulator.total_assets };
        }
        return { valid: false, error: `模拟仓 GID ${gid} 不存在或无法访问` };
    } catch (e) {
        return { valid: false, error: `验证模拟仓失败: 网络错误` };
    }
}

async function saveConfig() {
    const newConfig = {
        portfolio_code: document.getElementById('portfolio_code').value.trim(),
        target_portfolio_code: document.getElementById('target_portfolio_code').value.trim(),
        simulator_gid: parseInt(document.getElementById('simulator_gid').value) || 0,
        initial_assets: parseInt(document.getElementById('initial_assets').value) || 0,
        track_interval: parseInt(document.getElementById('track_interval').value) || 30,
        my_portfolio_code: document.getElementById('my_portfolio_code').value.split(',').map(s => s.trim()).filter(s => s),
        cookies: document.getElementById('cookies').value
    };

    // 检查哪些组合代码发生了变化
    const changedCodes = [];

    if (newConfig.portfolio_code !== (currentConfig.portfolio_code || '')) {
        changedCodes.push({ field: 'portfolio_code', code: newConfig.portfolio_code, label: '组合代码' });
    }
    if (newConfig.target_portfolio_code !== (currentConfig.target_portfolio_code || '')) {
        changedCodes.push({ field: 'target_portfolio_code', code: newConfig.target_portfolio_code, label: '目标组合' });
    }

    // 检查 my_portfolio_code 变化
    const oldMyCodes = Array.isArray(currentConfig.my_portfolio_code) ? currentConfig.my_portfolio_code : [];
    const newMyCodes = newConfig.my_portfolio_code;
    const addedCodes = newMyCodes.filter(c => !oldMyCodes.includes(c));
    addedCodes.forEach(code => {
        changedCodes.push({ field: 'my_portfolio_code', code, label: '我的组合' });
    });

    // 检查模拟仓 GID 变化
    const gidChanged = newConfig.simulator_gid !== (currentConfig.simulator_gid || 0);

    // 如果有变化，验证新代码
    if (changedCodes.length > 0 || gidChanged) {
        toast('正在验证组合代码...', 'success');

        // 验证所有变化的组合代码
        for (const item of changedCodes) {
            if (!item.code) continue;  // 跳过空值

            const result = await validatePortfolioCode(item.code);
            if (!result.valid) {
                toast(`${item.label}验证失败: ${result.error}`, 'error');
                return;  // 验证失败，不保存
            }
        }

        // 验证模拟仓 GID
        if (gidChanged && newConfig.simulator_gid) {
            const gidResult = await validateSimulatorGid(newConfig.simulator_gid);
            if (!gidResult.valid) {
                toast(gidResult.error, 'error');
                return;
            }
        }
    }

    // 验证通过，保存配置
    try {
        const res = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newConfig)
        });
        const data = await res.json();

        if (data.success) {
            currentConfig = { ...newConfig };  // 更新当前配置
            toast('配置保存成功!');

            // 重新加载组合名称
            loadPortfolioName('portfolio_code', newConfig.portfolio_code);
            loadPortfolioName('target_portfolio_code', newConfig.target_portfolio_code);
            loadSimulatorName(newConfig.simulator_gid);
            if (newConfig.my_portfolio_code.length > 0) {
                loadPortfolioName('my_portfolio_code', newConfig.my_portfolio_code[0]);
            }
        } else {
            toast('保存失败: ' + data.error, 'error');
        }
    } catch (e) {
        toast('保存失败', 'error');
    }
}

async function loadPortfolioName(inputId, code) {
    if (!code) return;
    try {
        const res = await fetch(`/api/portfolio/${code}`);
        const data = await res.json();
        if (data.success && data.portfolio.name) {
            document.getElementById(`name-${inputId}`).textContent = `📈 ${data.portfolio.name}`;
        }
    } catch (e) {
        console.error('加载组合名称失败', e);
    }
}

async function loadSimulatorName(gid) {
    if (!gid) return;
    try {
        const res = await fetch(`/api/simulator/${gid}`);
        const data = await res.json();
        if (data.success) {
            document.getElementById('name-simulator_gid').textContent = `💰 总资产: ¥${data.simulator.total_assets?.toLocaleString() || 0}`;
        }
    } catch (e) {
        console.error('加载模拟仓信息失败', e);
    }
}

// ============ 初始化 ============
async function loadHistoricalLogs() {
    /**
     * 从数据库加载历史日志（页面刷新后也能看到之前的日志）
     */
    try {
        const res = await fetch('/api/logs/history?limit=100');
        const data = await res.json();
        if (data.success && data.logs) {
            data.logs.forEach(log => {
                appendLogEntry(log);
            });
            console.log(`加载了 ${data.logs.length} 条历史日志`);
        }
    } catch (e) {
        console.error('加载历史日志失败', e);
    }
}

async function init() {
    loadConfig();

    // 先加载历史日志（页面刷新后日志不丢失）
    await loadHistoricalLogs();

    // 连接SSE事件流（日志+脚本状态）
    connectSSE();

    // 零轮询！所有状态通过SSE推送
}

// DOM 加载完成后初始化
document.addEventListener('DOMContentLoaded', init);
