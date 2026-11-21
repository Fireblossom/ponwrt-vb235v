'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const views = {
    overview: ['运行概览', '从启动到联网，查看当前进度与需要处理的问题。'],
    dsl: ['DSL 启动链路', '逐阶段查看设备准备、线路同步和运营商连接的实际结果。'],
    hardware: ['网络与硬件', '区分驱动加载、链路建立与实际服务状态。'],
    logs: ['诊断日志', '按模块查找故障，保留错误代码和发生顺序。'],
    history: ['启动历史', '查看本次与之前启动停留的阶段。']
  };
  const stateNames = {done:'已完成',running:'进行中',failed:'失败',blocked:'受阻',pending:'等待前序',unknown:'尚未确认',unavailable:'不可用',online:'已连接',offline:'未连接',unsupported:'尚未接入'};
  let sid = null, requestId = 0, activeView = 'overview', source = 'system';
  let lastStatus = null, lastReceived = 0, setup = false, loading = false, loggedIn = false, logLines = [];
  const text = (id, value) => { $(id).textContent = value == null || value === '' ? '—' : String(value); };
  function node(tag, className, value) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (value != null) el.textContent = String(value);
    return el;
  }
  function duration(seconds) {
    if (!Number.isFinite(Number(seconds))) return '—';
    seconds = Math.max(0, Math.floor(Number(seconds)));
    const days = Math.floor(seconds / 86400), hours = Math.floor(seconds / 3600) % 24, minutes = Math.floor(seconds / 60) % 60;
    if (days) return `${days} 天 ${hours} 小时`;
    if (hours) return `${hours} 小时 ${minutes} 分`;
    return minutes ? `${minutes} 分 ${seconds % 60} 秒` : `${seconds} 秒`;
  }
  function badge(id, label, type = 'neutral') { text(id, label); $(id).className = `badge ${type}`; }
  async function request(url, body, timeout = 10000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, {method: body ? 'POST' : 'GET', credentials:'same-origin', cache:'no-store',
        headers: body ? {'Content-Type':'application/json'} : {}, body: body ? JSON.stringify(body) : undefined, signal:controller.signal});
      if (!response.ok) throw new Error(`服务返回 HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('设备响应超时');
      throw error;
    } finally { clearTimeout(timer); }
  }
  async function rpc(method, params = {}, object = 'ponwrt.diagnostics', token = sid) {
    const data = await request('/ubus', {jsonrpc:'2.0', id:++requestId, method:'call', params:[token || '00000000000000000000000000000000', object, method, params]});
    if (data.error) {
      if (data.error.code === -32002 && loggedIn) showLogin('登录已失效，请重新登录。');
      throw new Error(data.error.code === -32002 ? '需要有效的登录会话' : data.error.message || '接口调用失败');
    }
    if (!Array.isArray(data.result) || data.result[0] !== 0) {
      const code = data.result && data.result[0];
      if (code === 6 && loggedIn) { showLogin('登录已失效，请重新登录。'); throw new Error('登录已失效'); }
      throw new Error(code === 6 ? '账号或密码不正确' : `设备接口暂不可用（${code ?? '无结果'}）`);
    }
    return data.result[1] || {};
  }
  function showLogin(message = '') {
    sid = null; loggedIn = false; lastStatus = null; lastReceived = 0;
    $('app').hidden = true; document.querySelector('.auth-shell').hidden = false;
    text('auth-error', message); $('password').value = ''; $('password-confirm').value = '';
  }
  function setupMode(required) {
    setup = required;
    $('setup-code').closest('label').hidden = !required;
    $('confirm-label').hidden = !required;
    text('login-button',required ? '设置密码并登录 ↗' : '登录诊断系统 ↗');
    text('auth-note',required ? '首次设置需要设备初始化码。至少 12 字节；初始化完成后，码立即失效。' : '使用设备管理员密码登录。');
    $('password').autocomplete = required ? 'new-password' : 'current-password';
    if (!required) $('setup-code').value = '';
  }
  function failure(error) {
    badge('connection', '连接中断');
    const age = lastReceived ? `上次成功读取在 ${duration((Date.now() - lastReceived) / 1000)}前。` : '';
    text('connection-error', `${error.message}。${age}设备可能正在重启或失去响应；恢复后请查看启动历史。`);
    $('connection-error').hidden = false; text('backend-state', '当前状态不可确认');
  }
  function renderStages(stages) {
    $('stage-list').replaceChildren(); $('dsl-detail').replaceChildren();
    if (!stages.length) {
      $('stage-list').append(node('p','muted','DSL 服务尚未提供阶段状态，请查看诊断日志。'));
      return;
    }
    stages.forEach((stage, index) => {
      const status = stateNames[stage.state] || '未知状态';
      const row = node('div', `stage ${stage.state || 'unknown'}`);
      row.append(node('span','stage-icon',stage.state === 'done' ? '✓' : stage.state === 'failed' || stage.state === 'blocked' ? '!' : String(index + 1)));
      const body = node('div'); body.append(node('div','stage-title',stage.title || stage.id),node('p','stage-description',stage.detail || '尚无当前阶段证据'));
      row.append(body,node('span','stage-status',status)); $('stage-list').append(row);
      const detail = node('div','detail-step');
      detail.append(node('h3','',`${String(index + 1).padStart(2,'0')}  ${stage.title || stage.id} · ${status}`),node('p','',stage.detail || '尚无当前阶段证据'));
      if (stage.code) detail.append(node('code','',stage.code));
      $('dsl-detail').append(detail);
    });
    $('retry-dsl').disabled = lastStatus?.dsl?.can_retry !== true;
  }
  function keyValues(values) {
    const dl = node('dl','key-values');
    for (const [name, value] of values) dl.append(node('dt','',name),node('dd','',value == null ? '未提供' : value));
    return dl;
  }
  function renderHardware(snapshot) {
    const target = $('hardware-panels'); target.replaceChildren();
    const add = (title, pairs) => { const panel = node('article','panel'); panel.append(node('h2','',title),keyValues(pairs)); target.append(panel); };
    (snapshot.ports || []).forEach(port => add(port.label || port.name, [
      ['设备',port.name],['链路',port.carrier === true ? '已建立' : port.carrier === false ? '未建立' : '未知'],
      ['速率',Number(port.speed_mbps) > 0 ? `${port.speed_mbps} Mbps` : '尚未确认'],['双工',port.duplex || '未知'],
      ['接收错误',port.rx_errors],['发送错误',port.tx_errors],['驱动',port.driver || '未提供']
    ]));
    const cpu = snapshot.cpu || {};
    add('CPU 与温控',[['在线核心',cpu.online || '未知'],['调频',cpu.frequency_khz ? `${Math.round(cpu.frequency_khz/1000)} MHz` : '未提供有效频率'],['温度',Number.isFinite(cpu.temperature_mC) ? `${(cpu.temperature_mC/1000).toFixed(1)} °C` : '未提供传感器数据'],['调频状态',cpu.reason || '见详细数据']]);
    const flash = snapshot.storage || {};
    add('存储与保护',[['可写区',flash.overlay_available_bytes == null ? '未知' : `${(flash.overlay_available_bytes/1048576).toFixed(1)} MiB 可用`],['不可纠正 ECC',flash.ecc_failures],['保护状态',flash.protected_readonly === true ? '受保护分区为只读' : '需检查'],['已纠正位数',flash.corrected_bits]]);
    const wifi = snapshot.wifi || {};
    add('Wi-Fi',[['驱动',wifi.driver || '未确认'],['无线设备',wifi.phys],['本机校准',wifi.private_calibration === true ? '本次启动已加载' : wifi.private_calibration === false ? '未确认加载 / 检查日志' : '未知'],['默认校准回退',wifi.reference_fallback === true ? '检测到，请处理' : wifi.reference_fallback === false ? '未检测到' : '未知']]);
    const acceleration = snapshot.acceleration || {};
    add('加速与恢复',[['硬件加密',acceleration.crypto || '未确认'],['NPU',acceleration.npu || '未确认'],['硬件转发',acceleration.offload || '需要当前流量证据'],['看门狗',snapshot.watchdog?.registered ? '已注册（喂狗状态需另核对）' : '未检测到已注册设备']]);
  }
  function renderEvents(id, events, fallback) {
    const target = $(id); target.replaceChildren();
    if (!events?.length) { target.append(node('p','muted',fallback)); return; }
    events.slice().reverse().forEach(event => {
      const row = node('div','event');
      row.append(node('time','',event.time || event.boot_id || (event.uptime_s != null ? `启动后 ${duration(event.uptime_s)}` : '时间未确认')),
        node('strong','',event.title || event.code || event.stage || '阶段事件'),node('p','muted',event.message || event.detail || ''));
      target.append(row);
    });
  }
  function render(snapshot) {
    lastStatus = snapshot;
    const system = snapshot.system || {}, dsl = snapshot.dsl || {}, internet = snapshot.internet || {};
    text('revision', system.revision); text('footer-revision', system.revision || 'PonWrt');
    text('uptime', duration(system.uptime_s)); text('boot-id',system.boot_id ? `启动 ${system.boot_id.slice(0,8)}` : '启动标识不可用');
    text('dsl-summary', dsl.line?.showtime === true ? '已同步' : dsl.line?.showtime === false ? '未同步' : '尚未确认');
    text('dsl-summary-note',dsl.line?.detail || '需要当前线路状态证据');
    const online = internet.authenticated === true && (internet.ipv4 === true || internet.ipv6 === true);
    text('internet-summary', online ? '已建立会话' : stateNames[internet.state] || '未建立');
    text('internet-note',online ? `IPv4 ${internet.ipv4 ? '已连接' : '未连接'} · IPv6 ${internet.ipv6 ? '已连接' : '未连接'}` : internet.detail || '等待 DSL 与认证结果');
    const port = (snapshot.ports || []).find(item => item.management && item.carrier) || (snapshot.ports || []).find(item => item.name === 'eth2') || (snapshot.ports || [])[0];
    text('port-summary',port && port.carrier ? Number(port.speed_mbps)>0 ? `${port.speed_mbps} Mbps` : '链路已建立' : '未建立');
    text('port-note',port ? `${port.label || port.name} · ${port.duplex === 'full' ? '全双工' : port.duplex || '双工未知'}` : '尚无网口状态');
    const stages = Array.isArray(dsl.stages) ? dsl.stages : [];
    badge('chain-badge',stateNames[dsl.state] || '尚未确认'); renderStages(stages);
    const issue = (snapshot.issues || [])[0] || {title:'当前未检测到已知故障',detail:'这不代表尚未验证的功能已经通过。可查看各阶段和硬件状态。',code:'NO_CURRENT_KNOWN_ERROR'};
    text('issue-title',issue.title); text('issue-detail',issue.detail); text('issue-code',issue.code);
    const additional=$('additional-issues');additional.replaceChildren();
    (snapshot.issues || []).slice(1).forEach(item=>{const entry=node('div','additional-issue');entry.append(node('strong','',item.title),node('p','',item.detail),node('code','',item.code));additional.append(entry);});
    const list = document.querySelector('.hardware-mini dl'); list.replaceChildren();
    [['CPU 在线',system.cpu_online || snapshot.cpu?.online || '未知'],['Wi-Fi 校准',snapshot.wifi?.private_calibration ? '本机校准已加载' : '需检查'],['可写空间',snapshot.storage?.overlay_available_bytes == null ? '未知' : `${(snapshot.storage.overlay_available_bytes/1048576).toFixed(1)} MiB`],['保护分区',snapshot.storage?.protected_readonly ? '只读保护' : '需检查']].forEach(([name,value]) => { const row=node('div');row.append(node('dt','',name),node('dd','',value));list.append(row); });
    renderHardware(snapshot); renderEvents('dsl-events',dsl.events,'尚无本次 DSL 事件。');
    text('last-updated',`已更新 · 启动后 ${duration(system.uptime_s)}`); text('backend-state','诊断服务在线');
  }
  function showView(name) {
    if (!views[name]) name='overview'; activeView=name;
    document.querySelectorAll('.view').forEach(el => { el.hidden=el.id!==name; });
    document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('selected',el.dataset.view===name));
    text('page-title',views[name][0]);text('view-name',views[name][0]);text('page-description',views[name][1]);
    if (loggedIn && name==='logs') loadLogs(); if (loggedIn && name==='history') loadHistory();
  }
  async function refresh() {
    if (!loggedIn || loading) return; loading=true;
    try { const snapshot=await rpc('status');if(snapshot.schema!==1 || !snapshot.system?.boot_id)throw new Error('诊断采集服务尚未提供有效状态');render(snapshot);lastReceived=Date.now();badge('connection','设备已连接');$('connection-error').hidden=true;
      if(activeView==='logs' && $('auto-refresh').checked) await loadLogs();
    } catch(error) { if(loggedIn) failure(error); } finally { loading=false; }
  }
  function filterLogs() {
    const query=$('log-search').value.toLocaleLowerCase();
    text('log-output',logLines.filter(line=>line.toLocaleLowerCase().includes(query)).join('\n') || '没有符合条件的日志。');
  }
  async function loadLogs() {
    try { const result=await rpc('logs',{source});logLines=(result.lines || []).map(line=>typeof line==='string'?line:`${line.time || (line.uptime_s != null ? `+${line.uptime_s}s` : '')} ${line.code || ''} ${line.message || line.text || line.detail || ''}`);filterLogs();text('log-state',result.detail || `${logLines.length} 行 · 已脱敏`); }
    catch(error) { text('log-state',error.message); }
  }
  async function loadHistory() {
    try { const result=await rpc('history');renderEvents('history-list',result.boots,'尚无之前的启动记录。'); }
    catch(error) { text('history-list',error.message); }
  }
  async function retryDsl() {
    if (!confirm('重新尝试 DSL 启动？现有 DSL 会话可能中断，诊断页面会继续显示进度。')) return;
    try { const result=await rpc('retry');if(!result.accepted)throw new Error(result.detail || '当前无法重试');await refresh(); }
    catch(error) { alert(error.message); }
  }
  $('login-button').closest('form').addEventListener('submit',async event=>{
    event.preventDefault();text('auth-error','');const button=$('login-button');button.disabled=true;
    try {
      const password=$('password').value;
      if(setup) {
        if(new TextEncoder().encode(password).length<12)throw new Error('请设置至少 12 字节的密码。');
        if(password!==$('password-confirm').value)throw new Error('两次输入的密码不一致。');
        const result=await request('/cgi-bin/ponwrt-setup',{token:$('setup-code').value,password});
        if(!result.ok){if(result.code==='ALREADY_SETUP')setupMode(false);throw new Error(result.message || '初始化失败');}
        setupMode(false);
      }
      const result=await rpc('login',{username:'admin',password,timeout:900},'session',null);
      if(!result.ubus_rpc_session)throw new Error('登录服务未返回有效会话');
      sid=result.ubus_rpc_session;loggedIn=true;setupMode(false);$('password').value='';$('password-confirm').value='';
      document.querySelector('.auth-shell').hidden=true;$('app').hidden=false;showView(activeView);await refresh();
    } catch(error) {text('auth-error',error.message);}finally{button.disabled=false;}
  });
  $('refresh').addEventListener('click',refresh);
  $('retry-dsl').addEventListener('click',retryDsl);
  $('logout').addEventListener('click',async()=>{try{await rpc('destroy',{},'session');}catch(_){}showLogin();});
  document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>showView(button.dataset.view)));
  document.querySelectorAll('[data-go]').forEach(button=>button.addEventListener('click',()=>showView(button.dataset.go)));
  $('log-search').addEventListener('input',filterLogs);
  document.querySelectorAll('[data-source]').forEach(button=>button.addEventListener('click',()=>{source=button.dataset.source;document.querySelectorAll('[data-source]').forEach(item=>item.classList.toggle('active',item===button));loadLogs();}));
  $('export').addEventListener('click',async()=>{
    $('export').disabled=true;
    try {const result=await rpc('support');const blob=new Blob([JSON.stringify(result,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=node('a');a.href=url;a.download=`ponwrt-diagnostics-${lastStatus?.system?.boot_id?.slice(0,8)||'unknown'}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);}
    catch(error){failure(error);}finally{$('export').disabled=false;}
  });
  $('close-dialog').addEventListener('click',()=>$('detail-dialog').close());
  async function initialize() {
    showView('overview');
    try {
      const status=await request('/cgi-bin/ponwrt-setup');setupMode(status.setup_required===true);
      if(status.tls_required){text('auth-error','请通过设备的 HTTPS 地址打开此页面后再登录。');$('login-button').disabled=true;return;}
    }catch(error){text('auth-error',`初始化服务未响应：${error.message}`);}
  }
  setInterval(()=>{if(loggedIn)refresh();},5000);
  setInterval(()=>{if(loggedIn && lastReceived && Date.now()-lastReceived>15000)failure(new Error('当前数据已过期'));},5000);
  initialize();
})();
