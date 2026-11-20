(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const base = location.pathname.replace(/\/testpage\/?$/, '');
  const TOKEN_KEY = 'abr_test_client_token_v2';
  const SESSION_KEY = 'abr_test_sessions_v2';
  const ACTIVE_KEY = 'abr_test_active_phone_v2';
  const VIEW_KEY = 'abr_test_view_v2';
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let clientToken = sessionStorage.getItem(TOKEN_KEY) || '';
  let sessions = readStore(sessionStorage, SESSION_KEY, {});
  let accounts = [];
  let activePhone = localStorage.getItem(ACTIVE_KEY) || '';
  let activeView = clientToken ? (localStorage.getItem(VIEW_KEY) || 'dashboard') : 'settings';
  let items = [];
  let selectedFolder = '';
  let modalMode = 'otp';
  let modalAccount = null;
  let modalStep = 'request';
  let challengeId = '';
  let pendingPassword = '';

  $('docsLink').href = base + '/docs';
  $('tokenPageLink').href = base + '/admin/tokens';

  function readStore(store, key, fallback) {
    try { return JSON.parse(store.getItem(key)) || fallback; } catch { return fallback; }
  }
  function saveSessions() { sessionStorage.setItem(SESSION_KEY, JSON.stringify(sessions)); }
  function esc(value) { return String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
  function normalizePhone(value) { let d=String(value||'').replace(/\D/g,''); if(d.startsWith('0098'))d=d.slice(4); else if(d.startsWith('98')&&d.length>10)d=d.slice(2); if(d.startsWith('0'))d=d.slice(1); return d; }
  function displayPhone(value) { const p=normalizePhone(value); return p.length===10 ? '0'+p : String(value||''); }
  function faNumber(value) { return new Intl.NumberFormat('fa-IR').format(Number(value)||0); }
  function activeAccount() { return accounts.find(a => a.phone === activePhone) || null; }
  function activeSession() { return sessions[activePhone] || ''; }
  function motionFrom(targets, vars) { if(window.gsap && !reduceMotion) gsap.from(targets, vars); }
  function motionTo(targets, vars) { if(window.gsap && !reduceMotion) gsap.to(targets, vars); }
  function toast(message, type='') {
    const el=$('toast'); el.textContent=message; el.className='toast '+type; clearTimeout(el._timer);
    if(window.gsap&&!reduceMotion) gsap.fromTo(el,{x:-24,opacity:0},{x:0,opacity:1,duration:.3,ease:'power2.out'});
    el._timer=setTimeout(()=>{ if(window.gsap&&!reduceMotion) gsap.to(el,{x:-18,opacity:0,duration:.25,onComplete:()=>el.classList.add('hidden')}); else el.classList.add('hidden'); },5200);
  }
  function setBusy(button, busy, label) {
    if(!button)return;
    if(busy){button.dataset.label=button.textContent;button.innerHTML='<span class="spinner"></span> '+label;button.disabled=true;}
    else{button.textContent=button.dataset.label||label;button.disabled=false;}
  }
  function errorMessage(data, fallback='درخواست ناموفق بود') {
    if(typeof data?.detail==='string'){
      const upstream=data?.upstream_detail;
      if(upstream){
        const extra=typeof upstream==='string'?upstream:JSON.stringify(upstream);
        return `${data.detail}: ${extra}`;
      }
      return data.detail;
    }
    if(typeof data?.message==='string')return data.message;
    return fallback;
  }
  async function adminApi(path, options={}) {
    const response=await fetch(base+path,{credentials:'same-origin',...options,headers:{...(options.headers||{})}});
    const text=await response.text(); let data=null; try{data=text?JSON.parse(text):null}catch{data=text;}
    if(!response.ok)throw new Error(errorMessage(data,'نشست مدیریت معتبر نیست؛ صفحه را دوباره باز کنید.'));
    return data;
  }
  function commonHeaders(auth=true) {
    const headers={'X-ABR-Client-Token':clientToken};
    if(auth&&activeSession())headers.Authorization='Bearer '+activeSession();
    return headers;
  }
  async function api(path, options={}) {
    if(!clientToken)throw new Error('ابتدا توکن سایت را در تنظیمات وارد کنید.');
    const response=await fetch(base+path,{credentials:'same-origin',...options,headers:{...commonHeaders(options.auth!==false),...(options.headers||{})}});
    const text=await response.text(); let data=null; try{data=text?JSON.parse(text):null}catch{data=text;}
    if(!response.ok){const suffix=data?.upstream_status?` (کد ابرهمراهی: ${data.upstream_status})`:'';throw new Error(errorMessage(data)+suffix);}
    return data;
  }

  function navigate(name) {
    const next=document.querySelector('#view-'+name); if(!next)return;
    activeView=name; localStorage.setItem(VIEW_KEY,name);
    document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v===next));
    document.querySelectorAll('.nav-item').forEach(n=>n.classList.toggle('active',n.dataset.view===name));
    $('pageTitle').textContent=next.dataset.title; $('eyebrow').textContent=next.dataset.eyebrow;
    if(window.gsap&&!reduceMotion)gsap.fromTo(next,{opacity:0,y:13},{opacity:1,y:0,duration:.38,ease:'power2.out'});
    closeMobileMenu();
    if(name==='accounts')loadAccounts();
  }
  document.querySelectorAll('.nav-item').forEach(button=>button.addEventListener('click',()=>navigate(button.dataset.view)));
  $('chooseAccount').onclick=()=>navigate('accounts'); $('activeAccountButton').onclick=()=>navigate('accounts');

  function toggleSidebar() {
    const shell=$('appShell'); shell.classList.toggle('collapsed');
    localStorage.setItem('abr_sidebar_collapsed',shell.classList.contains('collapsed')?'1':'0');
    if(window.gsap&&!reduceMotion)gsap.fromTo('.main-area',{opacity:.86},{opacity:1,duration:.3});
  }
  function openMobileMenu() {$('sidebar').classList.add('mobile-open');$('mobileOverlay').classList.add('open');}
  function closeMobileMenu() {$('sidebar').classList.remove('mobile-open');$('mobileOverlay').classList.remove('open');}
  $('collapseSidebar').onclick=toggleSidebar; $('mobileMenu').onclick=openMobileMenu; $('mobileOverlay').onclick=closeMobileMenu;
  if(localStorage.getItem('abr_sidebar_collapsed')==='1')$('appShell').classList.add('collapsed');

  function updateTokenUI() {
    $('clientToken').value=clientToken;
    const status=$('tokenStatus'),dot=status.querySelector('i'),text=status.querySelector('span');
    dot.className='status-dot '+(clientToken?'ok':'warning'); text.textContent=clientToken?'توکن برای این تب فعال است':'توکن وارد نشده است';
    $('settingsDot').className='status-dot '+(clientToken?'ok':'warning');
  }
  $('saveToken').onclick=()=>{const value=$('clientToken').value.trim();if(!value.startsWith('abrc_'))return toast('قالب توکن سایت درست نیست.','error');clientToken=value;sessionStorage.setItem(TOKEN_KEY,value);updateTokenUI();toast('توکن با موفقیت برای این تب ذخیره شد.','success');};
  $('clearToken').onclick=()=>{clientToken='';sessionStorage.removeItem(TOKEN_KEY);updateTokenUI();toast('توکن از این تب پاک شد.');};
  $('toggleToken').onclick=()=>{$('clientToken').type=$('clientToken').type==='password'?'text':'password';};

  async function loadAccounts() {
    const button=$('reloadAccounts'); try{setBusy(button,true,'دریافت');const data=await adminApi('/testpage/api/accounts');accounts=Array.isArray(data?.accounts)?data.accounts:[];if(activePhone&&!accounts.some(a=>a.phone===activePhone)){activePhone='';localStorage.removeItem(ACTIVE_KEY);}renderAccounts();updateActiveAccountUI();}
    catch(e){toast(e.message,'error');}finally{setBusy(button,false,'بازخوانی');}
  }
  function accountStatus(account) {
    if(sessions[account.phone])return {text:'فعال در این تب',className:'ok'};
    if(account.connected)return {text:'متصل؛ نیازمند ورود',className:'warn'};
    return {text:'نیازمند وریفای',className:''};
  }
  function renderAccounts() {
    const query=$('accountSearch').value.trim().toLowerCase();
    const filtered=accounts.filter(a=>(a.display_name||'').toLowerCase().includes(query)||displayPhone(a.phone).includes(query));
    $('accountsNavCount').textContent=faNumber(accounts.length);$('accountsTotal').textContent=faNumber(accounts.length);$('accountsConnected').textContent=faNumber(accounts.filter(a=>a.connected).length);$('accountsActive').textContent=faNumber(accounts.filter(a=>sessions[a.phone]).length);
    $('accountsEmpty').classList.toggle('hidden',accounts.length>0);$('accountsTableBody').innerHTML=filtered.map(account=>{
      const status=accountStatus(account),name=account.display_name||('حساب '+displayPhone(account.phone)),avatar=esc(name.trim().charAt(0)||'ا');
      const passwordWarning=account.password_sync_error?'<span class="status-badge warn" title="'+esc(account.password_sync_error)+'">رمز ابر همگام نشد</span>':'';
      return `<tr data-id="${account.id}"><td><div class="account-cell"><span class="avatar">${avatar}</span><div><b>${esc(name)}</b><small>شناسه ${account.id}</small></div></div></td><td dir="ltr">${esc(displayPhone(account.phone))}</td><td><span class="status-badge ${status.className}"><i class="status-dot ${status.className==='ok'?'ok':status.className==='warn'?'warning':''}"></i>${status.text}</span> ${passwordWarning}</td><td>${faNumber(account.active_sessions)}</td><td>${formatDate(account.last_login_at)}</td><td><div class="table-actions"><button class="table-action" data-action="manage">مدیریت</button><button class="table-action" data-action="edit">ویرایش</button><button class="table-action" data-action="verify">وریفای مجدد</button><button class="table-action" data-action="logout">حذف نشست</button><button class="table-action red" data-action="delete">حذف</button></div></td></tr>`;
    }).join('');
    document.querySelectorAll('#accountsTableBody tr').forEach(row=>row.querySelectorAll('[data-action]').forEach(button=>button.onclick=()=>handleAccountAction(Number(row.dataset.id),button.dataset.action)));
    motionFrom('#accountsTableBody tr',{opacity:0,y:9,stagger:.035,duration:.3,ease:'power2.out'});
  }
  function formatDate(timestamp) {if(!timestamp)return '—';try{return new Intl.DateTimeFormat('fa-IR',{dateStyle:'short',timeStyle:'short'}).format(new Date(timestamp*1000));}catch{return '—';}}
  $('accountSearch').oninput=renderAccounts; $('reloadAccounts').onclick=loadAccounts; $('addAccount').onclick=()=>openAccountModal('otp');

  async function handleAccountAction(id, action) {
    const account=accounts.find(a=>a.id===id);if(!account)return;
    if(action==='manage'){setActiveAccount(account);if(activeSession())navigate('dashboard');else openAccountModal('login',account);return;}
    if(action==='edit'){openAccountModal('edit',account);return;}
    if(action==='verify'){openAccountModal('otp',account);return;}
    if(action==='logout'){
      if(!confirm(`همه نشست‌های محلی «${account.display_name||displayPhone(account.phone)}» حذف شوند؟`))return;
      try{await adminApi(`/testpage/api/accounts/${id}/logout`,{method:'POST'});delete sessions[account.phone];saveSessions();await loadAccounts();updateActiveAccountUI();toast('نشست‌های حساب حذف شدند.','success');}catch(e){toast(e.message,'error');}return;
    }
    if(action==='delete'){
      if(!confirm(`حساب «${account.display_name||displayPhone(account.phone)}» فقط از این درگاه و دیتابیس محلی حذف شود؟ فایل‌های ابرهمراهی حذف نمی‌شوند.`))return;
      try{await adminApi(`/testpage/api/accounts/${id}`,{method:'DELETE'});delete sessions[account.phone];saveSessions();if(activePhone===account.phone){activePhone='';localStorage.removeItem(ACTIVE_KEY);clearDashboard();}await loadAccounts();toast('حساب از درگاه محلی حذف شد.','success');}catch(e){toast(e.message,'error');}
    }
  }
  function setActiveAccount(account) {activePhone=account.phone;localStorage.setItem(ACTIVE_KEY,activePhone);updateActiveAccountUI();}
  function updateActiveAccountUI() {
    const account=activeAccount(),name=account?.display_name||'حسابی انتخاب نشده';$('activeAccountName').textContent=name;$('activeAccountPhone').textContent=account?displayPhone(account.phone):'برای شروع حساب را انتخاب کنید';$('activeAccountAvatar').textContent=account?(name.trim().charAt(0)||'ا'):'—';$('activeAccountDot').className='status-dot '+(activeSession()?'ok':'');
    $('heroTitle').textContent=account?`فضای ابری ${name}`:'مدیریت فایل‌های ابرهمراهی، ساده و سریع';$('heroDescription').textContent=account?(activeSession()?'اتصال این حساب فعال است؛ ظرفیت و فایل‌ها آماده مدیریت هستند.':'برای مشاهده فایل‌ها یک‌بار با رمز یا پیامک وارد این حساب شوید.'):'یک حساب را انتخاب کنید تا ظرفیت، پوشه‌ها و لینک‌های پایدار آن را ببینید.';
  }

  function openAccountModal(mode, account=null) {
    modalMode=mode;modalAccount=account;modalStep='request';challengeId='';pendingPassword='';$('modalWarning').classList.add('hidden');$('modalOtpField').classList.add('hidden');$('modalAccountFields').classList.remove('hidden');$('modalPasswordField').classList.toggle('hidden',mode==='edit');$('accountLabel').disabled=mode==='login';$('phone').disabled=Boolean(account);$('futurePassword').disabled=false;$('accountLabel').value=account?.display_name||'';$('phone').value=account?displayPhone(account.phone):'';$('futurePassword').value='';$('futurePassword').autocomplete=mode==='login'?'current-password':'new-password';$('otpCode').value='';
    if(mode==='edit'){$('modalKicker').textContent='ویرایش حساب';$('modalTitle').textContent='نام نمایشی حساب';$('modalDescription').textContent='این نام فقط در کنسول مدیریتی نمایش داده می‌شود.';$('modalSymbol').textContent='✎';$('modalPrimary').textContent='ذخیره تغییرات';}
    else if(mode==='login'){$('modalKicker').textContent='ورود مجدد';$('modalTitle').textContent=account?.display_name||'ورود به حساب';$('modalDescription').textContent='رمزی را که هنگام وریفای تعیین کرده‌اید وارد کنید.';$('modalSymbol').textContent='⌁';$('modalPrimary').textContent='ورود با رمز';}
    else{$('modalKicker').textContent=account?'وریفای مجدد':'حساب جدید';$('modalTitle').textContent=account?'تأیید دوباره حساب':'افزودن حساب ابرهمراهی';$('modalDescription').textContent='شماره و رمز آینده را وارد کنید تا کد تأیید ارسال شود.';$('modalSymbol').textContent='◎';$('modalPrimary').textContent='ارسال کد تأیید';}
    $('accountModal').classList.remove('hidden');motionFrom('.modal-card',{opacity:0,y:28,scale:.97,duration:.35,ease:'back.out(1.4)'});setTimeout(()=>$(mode==='edit'?'accountLabel':mode==='login'?'futurePassword':'accountLabel').focus(),80);
  }
  function closeModal() {$('accountModal').classList.add('hidden');}
  document.querySelectorAll('[data-close-modal]').forEach(el=>el.onclick=closeModal);
  $('modalPrimary').onclick=async()=>{if(modalMode==='edit')return saveAccountEdit();if(modalMode==='login')return passwordLogin();if(modalStep==='request')return requestOtp();return verifyOtp();};
  async function saveAccountEdit() {const name=$('accountLabel').value.trim();if(!name)return showModalWarning('نام حساب را وارد کنید.');try{setBusy($('modalPrimary'),true,'در حال ذخیره');await adminApi(`/testpage/api/accounts/${modalAccount.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({display_name:name})});closeModal();await loadAccounts();toast('نام حساب ویرایش شد.','success');}catch(e){showModalWarning(e.message);}finally{setBusy($('modalPrimary'),false,'ذخیره تغییرات');}}
  async function requestOtp() {const phone=normalizePhone($('phone').value),password=$('futurePassword').value,name=$('accountLabel').value.trim();if(!clientToken){closeModal();navigate('settings');return toast('ابتدا توکن سایت را وارد کنید.','error');}if(phone.length!==10||!phone.startsWith('9'))return showModalWarning('شماره موبایل معتبر وارد کنید.');if(password.length<8)return showModalWarning('رمز آینده باید حداقل ۸ نویسه باشد.');try{setBusy($('modalPrimary'),true,'در حال ارسال');const data=await api('/v1/auth/sms/request',{method:'POST',auth:false,headers:{'Content-Type':'application/json'},body:JSON.stringify({phone})});challengeId=data.challenge_id;pendingPassword=password;modalStep='verify';$('phone').disabled=true;$('futurePassword').disabled=true;$('modalOtpField').classList.remove('hidden');$('modalPrimary').textContent='تأیید کد و ورود';$('modalDescription').textContent='کد پیامک‌شده را وارد کنید. ورود موفق مستقل از نتیجه تنظیم رمز حفظ می‌شود.';$('otpCode').focus();toast('کد تأیید ارسال شد.','success');}catch(e){showModalWarning(e.message);}finally{setBusy($('modalPrimary'),false,modalStep==='verify'?'تأیید کد و ورود':'ارسال کد تأیید');}}
  async function verifyOtp() {const code=Number($('otpCode').value),phone=normalizePhone($('phone').value),name=$('accountLabel').value.trim();if(!challengeId||!code)return showModalWarning('کد تأیید را وارد کنید.');try{setBusy($('modalPrimary'),true,'در حال تأیید');const data=await api('/v1/auth/sms/verify',{method:'POST',auth:false,headers:{'Content-Type':'application/json'},body:JSON.stringify({challenge_id:challengeId,code,new_password:pendingPassword,display_name:name||('حساب '+displayPhone(phone))})});sessions[phone]=data.session_token;saveSessions();activePhone=phone;localStorage.setItem(ACTIVE_KEY,phone);closeModal();await loadAccounts();updateActiveAccountUI();navigate('dashboard');await refreshDashboard();if(data.password_warning)toast('ورود موفق بود؛ تنظیم رمز ابرهمراهی جداگانه تأیید نشد، اما نشست شما حفظ شد.','warning');else toast('ورود و تنظیم رمز با موفقیت انجام شد.','success');}catch(e){showModalWarning(e.message);}finally{setBusy($('modalPrimary'),false,'تأیید کد و ورود');}}
  async function passwordLogin() {const password=$('futurePassword').value,account=modalAccount;if(!account||password.length<8)return showModalWarning('رمز حساب را وارد کنید.');setActiveAccount(account);try{setBusy($('modalPrimary'),true,'در حال ورود');const data=await api('/v1/auth/login',{method:'POST',auth:false,headers:{'Content-Type':'application/json'},body:JSON.stringify({phone:account.phone,password})});sessions[account.phone]=data.session_token;saveSessions();closeModal();await loadAccounts();updateActiveAccountUI();navigate('dashboard');await refreshDashboard();toast('ورود با رمز موفق بود.','success');}catch(e){showModalWarning(e.message);}finally{setBusy($('modalPrimary'),false,'ورود با رمز');}}
  function showModalWarning(message) {$('modalWarning').textContent=message;$('modalWarning').classList.remove('hidden');motionFrom('#modalWarning',{opacity:0,y:-5,duration:.25});}

  function itemId(x){return String(x?.id??x?.object_id??'');} function itemName(x){return String(x?.name??x?.title??x?.filename??'بدون نام');}
  function parentId(x){let p=x?.parent_id??x?.parent??x?.parent_uuid??'';if(p&&typeof p==='object')p=p.id??p.uuid??'';return p==null?'':String(p);}
  function isFolder(x){for(const k of ['is_folder','is_dir','folder']){const v=x?.[k];if(typeof v==='boolean')return v;if(v===0||v===1||v==='0'||v==='1')return String(v)==='1';}if(x?.is_file===true)return false;const kind=['type','object_type','obj_type','kind','mime_type'].map(k=>String(x?.[k]??'').toLowerCase()).join(' ');return kind.includes('folder')||kind.includes('directory')||kind.trim()==='dir';}
  function itemSize(x){const n=Number(x?.size??x?.obj_size??x?.file_size);return Number.isFinite(n)?n:null;}
  function formatBytes(value){let n=Number(value);if(!Number.isFinite(n)||n<0)return '—';const units=['بایت','کیلوبایت','مگابایت','گیگابایت','ترابایت'];let i=0;while(n>=1024&&i<units.length-1){n/=1024;i++;}return `${new Intl.NumberFormat('fa-IR',{maximumFractionDigits:i?2:0}).format(n)} ${units[i]}`;}
  function clearDashboard(){items=[];selectedFolder='';$('tree').innerHTML='<div class="empty-state compact"><span>☁</span><b>برای مشاهده فایل‌ها وارد حساب شوید</b><p>حساب را از بخش حساب‌ها انتخاب کنید.</p></div>';$('itemCount').textContent='—';setQuota(null,null,null);updateTargets();}
  function setQuota(total,used,remaining){$('quotaTotal').textContent=formatBytes(total);$('quotaUsed').textContent=formatBytes(used);$('quotaRemaining').textContent=formatBytes(remaining);const percent=total>0&&used>=0?Math.min(100,used/total*100):0;$('quotaPercent').textContent=total>0?`${new Intl.NumberFormat('fa-IR',{maximumFractionDigits:1}).format(percent)}٪ مصرف شده`:'بدون اطلاعات';$('usageRingText').textContent=`${faNumber(Math.round(percent))}٪`;const offset=182.2-(182.2*percent/100);motionTo('#usageCircle',{strokeDashoffset:offset,duration:.8,ease:'power2.out'});}
  async function loadFiles(){let all=[],offset=0,total=null;for(let page=0;page<100;page++){const data=await api(`/v1/files?recursive=true&limit=100&offset=${offset}`);const batch=Array.isArray(data)?data:(Array.isArray(data?.results)?data.results:[]);all.push(...batch);total=Number(data?.count??data?.total??NaN);offset+=batch.length;if(!batch.length||batch.length<100||(Number.isFinite(total)&&offset>=total))break;}items=all;renderTree();}
  async function loadQuota(){const q=await api('/v1/quota');setQuota(q.total,q.used,q.remaining);}
  async function refreshDashboard(){const account=activeAccount();if(!account)return navigate('accounts');if(!activeSession()){openAccountModal('login',account);return;}const button=$('refreshDashboard');try{setBusy(button,true,'در حال دریافت');const results=await Promise.allSettled([loadFiles(),loadQuota()]);const failure=results.find(r=>r.status==='rejected');if(failure)throw failure.reason;toast('اطلاعات فضای ابری به‌روز شد.','success');}catch(e){toast(e.message,'error');}finally{setBusy(button,false,'بازخوانی اطلاعات');}}
  $('refreshDashboard').onclick=refreshDashboard;
  function updateTargets(){const folder=items.find(x=>itemId(x)===selectedFolder),name=folder?itemName(folder):'ریشه';$('folderTargetName').textContent=name;$('uploadTargetName').textContent=name;}
  function renderTree(){const tree=$('tree');$('itemCount').textContent=`${faNumber(items.length)} مورد`;if(!items.length){tree.innerHTML='<div class="empty-state compact"><span>◇</span><b>فضای این حساب خالی است</b><p>یک پوشه بسازید یا نخستین فایل را بارگذاری کنید.</p></div>';return;}const byParent=new Map(),ids=new Set(items.map(itemId));for(const x of items){let p=parentId(x);if(!ids.has(p))p='';if(!byParent.has(p))byParent.set(p,[]);byParent.get(p).push(x);}for(const list of byParent.values())list.sort((a,b)=>(Number(!isFolder(a))-Number(!isFolder(b)))||itemName(a).localeCompare(itemName(b),'fa'));const seen=new Set();const draw=parent=>(byParent.get(parent)||[]).map(x=>{const id=itemId(x);if(!id||seen.has(id))return'';seen.add(id);const folder=isFolder(x),url=x.cdn_url||'';return `<div class="node"><div class="node-row ${folder?'folder':''} ${folder&&id===selectedFolder?'selected-folder':''}" data-id="${esc(id)}"><span class="node-icon">${folder?'📁':'📄'}</span><span class="node-name">${esc(itemName(x))}</span><span class="node-meta">${folder?'پوشه':formatBytes(itemSize(x))}</span><span class="node-actions">${folder?'':`<button class="table-action" data-action="download" data-id="${esc(id)}">دانلود</button><button class="table-action" data-action="copy" data-id="${esc(id)}" data-url="${esc(url)}">کپی لینک</button>`}<button class="table-action red" data-action="delete" data-id="${esc(id)}" data-name="${esc(itemName(x))}">حذف</button></span></div>${folder?`<div class="children">${draw(id)}</div>`:''}</div>`;}).join('');let html=draw('');const leftovers=items.filter(x=>!seen.has(itemId(x)));if(leftovers.length){byParent.set('',leftovers);html+=draw('');}tree.innerHTML=html||'<div class="empty-state compact">ساختار فایل‌ها قابل نمایش نیست.</div>';tree.querySelectorAll('.node-row.folder').forEach(row=>row.onclick=e=>{if(e.target.closest('button'))return;selectedFolder=row.dataset.id;updateTargets();renderTree();});tree.querySelectorAll('[data-action]').forEach(button=>button.onclick=e=>{e.stopPropagation();const action=button.dataset.action;if(action==='download')downloadFile(button.dataset.id);if(action==='copy')copyLink(button.dataset.id,button.dataset.url);if(action==='delete')deleteObject(button.dataset.id,button.dataset.name);});motionFrom('#tree .node-row',{opacity:0,x:8,stagger:.018,duration:.25});updateTargets();}
  $('selectRoot').onclick=()=>{selectedFolder='';updateTargets();renderTree();};
  async function getFileUrl(id,known=''){if(known)return known;const object=items.find(x=>itemId(x)===id);if(object?.cdn_url)return object.cdn_url;return (await api(`/v1/files/${encodeURIComponent(id)}/download-link`)).download_url;}
  async function downloadFile(id){try{window.open(await getFileUrl(id),'_blank','noopener');}catch(e){toast(e.message,'error');}}
  async function copyLink(id,known){try{await navigator.clipboard.writeText(await getFileUrl(id,known));toast('لینک پایدار کپی شد.','success');}catch(e){toast(e.message||'کپی انجام نشد.','error');}}
  async function deleteObject(id,name){const permanent=$('permanentDelete').checked;if(!confirm(permanent?`«${name}» برای همیشه حذف شود؟`:`«${name}» به زباله‌دان منتقل شود؟`))return;try{await api(`/v1/files/${encodeURIComponent(id)}?permanent=${permanent}`,{method:'DELETE'});if(selectedFolder===id)selectedFolder='';toast(permanent?'مورد برای همیشه حذف شد.':'مورد به زباله‌دان منتقل شد.','success');await refreshDashboard();}catch(e){toast(e.message,'error');}}
  $('createFolder').onclick=async()=>{const name=$('folderName').value.trim(),button=$('createFolder');if(!name)return toast('نام پوشه را وارد کنید.','error');try{setBusy(button,true,'ایجاد');await api('/v1/folders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,parent:selectedFolder||null})});$('folderName').value='';toast('پوشه ایجاد شد.','success');await refreshDashboard();}catch(e){toast(e.message,'error');}finally{setBusy(button,false,'ایجاد');}};
  $('uploadFile').onchange=()=>{$('uploadFileName').textContent=$('uploadFile').files[0]?.name||'انتخاب فایل';};
  $('upload').onclick=async()=>{const file=$('uploadFile').files[0],button=$('upload');if(!file)return toast('یک فایل انتخاب کنید.','error');const form=new FormData();form.append('file',file);form.append('parent',selectedFolder);form.append('force_overwrite','false');form.append('is_hidden','false');try{setBusy(button,true,'بارگذاری');const data=await api('/v1/files/upload',{method:'POST',body:form});const url=data.cdn_url||data.download_url||'';$('uploadResult').classList.remove('hidden');$('uploadResult').innerHTML=`<b>بارگذاری کامل شد</b><code>${esc(url)}</code><button id="copyUploaded" class="table-action">کپی لینک نهایی</button>`;$('copyUploaded').onclick=async()=>{await navigator.clipboard.writeText(url);toast('لینک نهایی کپی شد.','success');};$('uploadFile').value='';$('uploadFileName').textContent='انتخاب فایل';toast('فایل بارگذاری و لینک پایدار ساخته شد.','success');await refreshDashboard();}catch(e){toast(e.message,'error');}finally{setBusy(button,false,'بارگذاری');}};

  async function init(){updateTokenUI();navigate(activeView);await loadAccounts();updateActiveAccountUI();if(activeAccount()&&activeSession()&&activeView==='dashboard')await refreshDashboard();else clearDashboard();motionFrom('.sidebar',{x:35,opacity:0,duration:.55,ease:'power2.out'});motionFrom('.topbar',{y:-20,opacity:0,duration:.45,ease:'power2.out'});motionFrom('.view.active .reveal-card',{y:20,opacity:0,stagger:.08,duration:.5,ease:'power2.out'});}
  init();
})();
