/* ScamCheck browser controller logic.
   Shared constants/state now live in app-data.js, and rendering helpers live in
   app-render.js. This file keeps the routing, API calls, and event wiring. */


function readDisplayPreferences(){
  try{
    const saved=JSON.parse(localStorage.getItem(DISPLAY_PREFERENCES_KEY)||'{}');
    return {
      highContrast:saved.highContrast===true,
      largeText:saved.largeText===true
    };
  }catch(error){
    return {highContrast:false,largeText:false};
  }
}

function applyDisplayPreferences(preferences,{announce=false}={}){
  document.documentElement.toggleAttribute('data-high-contrast',preferences.highContrast);
  document.documentElement.toggleAttribute('data-large-text',preferences.largeText);
  contrastToggle.setAttribute('aria-pressed',String(preferences.highContrast));
  fontSizeToggle.setAttribute('aria-pressed',String(preferences.largeText));
  contrastToggle.setAttribute('aria-label',`${preferences.highContrast?'Tắt':'Bật'} chế độ tương phản cao`);
  fontSizeToggle.setAttribute('aria-label',`${preferences.largeText?'Tắt':'Bật'} chế độ chữ lớn`);
  if(announce){
    const enabled=[];
    if(preferences.highContrast)enabled.push('tương phản cao');
    if(preferences.largeText)enabled.push('chữ lớn');
    displayPreferenceStatus.textContent=enabled.length
      ?`Đã bật ${enabled.join(' và ')}.`
      :'Đã dùng chế độ hiển thị mặc định.';
  }
}

function saveDisplayPreferences(preferences){
  try{
    localStorage.setItem(DISPLAY_PREFERENCES_KEY,JSON.stringify(preferences));
  }catch(error){
    // The current choice still applies when browser storage is unavailable.
  }
}

let displayPreferences=readDisplayPreferences();
applyDisplayPreferences(displayPreferences);
contrastToggle.addEventListener('click',()=>{
  displayPreferences={...displayPreferences,highContrast:!displayPreferences.highContrast};
  applyDisplayPreferences(displayPreferences,{announce:true});
  saveDisplayPreferences(displayPreferences);
});
fontSizeToggle.addEventListener('click',()=>{
  displayPreferences={...displayPreferences,largeText:!displayPreferences.largeText};
  applyDisplayPreferences(displayPreferences,{announce:true});
  saveDisplayPreferences(displayPreferences);
});
window.addEventListener('storage',event=>{
  if(event.key!==DISPLAY_PREFERENCES_KEY)return;
  displayPreferences=readDisplayPreferences();
  applyDisplayPreferences(displayPreferences);
});

function renderRemainingAnalyses(){
  usage.textContent=`Số lượt phân tích còn lại: ${remainingAnalyses} lần`;
}

function saveRemainingAnalyses(){
  try{
    sessionStorage.setItem(ANALYSIS_REMAINING_KEY,String(remainingAnalyses));
  }catch(error){
    // Keep the in-memory counter when tab storage is unavailable.
  }
}

function restoreRemainingAnalyses(){
  try{
    const storedValue=sessionStorage.getItem(ANALYSIS_REMAINING_KEY);
    const saved=storedValue===null?ANALYSIS_LIMIT:Number(storedValue);
    if(Number.isInteger(saved)&&saved>=0&&saved<=ANALYSIS_LIMIT){
      remainingAnalyses=saved;
    }
  }catch(error){
    remainingAnalyses=ANALYSIS_LIMIT;
  }
  sessionAtLimit=remainingAnalyses===0;
  renderRemainingAnalyses();
}

function decrementRemainingAnalyses(){
  if(isOffline||remainingAnalyses===0)return;
  remainingAnalyses=Math.max(0,remainingAnalyses-1);
  sessionAtLimit=remainingAnalyses===0;
  saveRemainingAnalyses();
  renderRemainingAnalyses();
}

// Move quick sample cards below the main submit button on small screens.
function syncQuickInputLayout(){
  if(mobileLayoutQuery.matches){
    mobileQuickCards.forEach(card=>checkButton.after(card));
    return;
  }
  mobileQuickCards.forEach(card=>toolsColumn.append(card));
}

syncQuickInputLayout();
mobileLayoutQuery.addEventListener('change',syncQuickInputLayout);

// Hash routing keeps the app single-page while still allowing direct links.
function routeFromHash(){
  const candidate=window.location.hash.slice(1);
  if(candidate==='library')return {view:'library',detailId:null};
  if(candidate.startsWith('library/')){
    try{
      return {view:'library',detailId:decodeURIComponent(candidate.slice(8))};
    }catch(error){
      return {view:'library',detailId:null};
    }
  }
  return {view:Object.hasOwn(viewTitles,candidate)?candidate:'analyze',detailId:null};
}

// Swap visible panels and trigger any page-specific refresh work.
function switchView(view,{focus=false}={}){
  const target=Object.hasOwn(viewTitles,view)?view:'analyze';
  pageViews.forEach(panel=>{
    panel.hidden=panel.dataset.viewPanel!==target;
  });
  navLinks.forEach(link=>{
    if(link.dataset.view===target)link.setAttribute('aria-current','page');
    else link.removeAttribute('aria-current');
  });
  if(target==='history'){
    selectedHistoryIds.clear();
    void loadHistory();
  }
  document.title=`${viewTitles[target]} · ScamCheck`;
  if(focus){
    const panel=document.querySelector(`[data-view-panel="${target}"]`);
    panel?.focus({preventScroll:true});
    window.scrollTo({top:0,behavior:'smooth'});
  }
  updateResultScrollButton();
}

function resultViewIsVisible(){
  const view=resultFrame.closest('[data-view-panel]');
  return resultFrame.classList.contains('active')&&!view?.hidden;
}

function updateResultScrollButton(){
  resultScrollButton.hidden=!resultViewIsVisible()||autoFollowResult;
}

function resetResultAutoFollow(){
  autoFollowResult=true;
  latestResultMessage=signalList.firstElementChild;
  lastResultScrollY=window.scrollY;
  resultScrollGuardUntil=Date.now()+900;
  resultScrollButton.hidden=true;
}

function pauseResultAutoFollow(){
  if(!resultViewIsVisible())return;
  autoFollowResult=false;
  updateResultScrollButton();
}

function scrollToResultMessage(message,{force=false}={}){
  if(!message||!autoFollowResult)return;
  const rect=message.getBoundingClientRect();
  if(!force&&rect.bottom<=window.innerHeight-20)return;
  resultScrollGuardUntil=Date.now()+800;
  message.scrollIntoView({
    behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',
    block:'end'
  });
}

function revealResultMessage(message){
  if(!message)return;
  latestResultMessage=message;
  if(autoFollowResult)scrollToResultMessage(message);
  else updateResultScrollButton();
}

function resumeResultAutoFollow(){
  autoFollowResult=true;
  updateResultScrollButton();
  const visibleMessages=[...resultFrame.querySelectorAll(
    '.detective-message-row,.psychology-message-row,.responder-message-row,.post-analysis-question:not([hidden])'
  )].filter(message=>message.offsetParent!==null);
  latestResultMessage=visibleMessages.at(-1)||latestResultMessage;
  scrollToResultMessage(latestResultMessage,{force:true});
}

function handleResultWindowScroll(){
  const currentScrollY=window.scrollY;
  if(resultViewIsVisible()){
    if(currentScrollY<lastResultScrollY-3&&Date.now()>resultScrollGuardUntil){
      pauseResultAutoFollow();
    }else if(!autoFollowResult&&currentScrollY>lastResultScrollY+2&&latestResultMessage){
      const latestRect=latestResultMessage.getBoundingClientRect();
      if(latestRect.bottom<=window.innerHeight-16){
        autoFollowResult=true;
        updateResultScrollButton();
      }
    }
  }
  lastResultScrollY=currentScrollY;
}

function clearMessageRevealTimers(){
  messageRevealTimers.forEach(timer=>window.clearTimeout(timer));
  messageRevealTimers=[];
}

function revealRowsSequentially(rows,{onComplete=null}={}){
  const messages=[...rows];
  messages.forEach(message=>{
    message.hidden=true;
    message.removeAttribute('aria-busy');
  });
  if(messages.length===0){
    if(onComplete)onComplete();
    return;
  }

  let index=0;
  const revealNext=()=>{
    const message=messages[index];
    message.hidden=false;
    revealResultMessage(message);
    index+=1;
    if(index>=messages.length){
      if(onComplete)onComplete();
      return;
    }
    const timer=window.setTimeout(revealNext,MESSAGE_REVEAL_INTERVAL_MS);
    messageRevealTimers.push(timer);
  };
  revealNext();
}

function showComposerFrame(){
  clearMessageRevealTimers();
  downloadResultImageButton.disabled=true;
  resultImageStatus.textContent='';
  processingFrame.hidden=true;
  resultFrame.classList.remove('active');
  latestResultMessage=null;
  autoFollowResult=true;
  resultScrollButton.hidden=true;
  inputFrame.style.display='block';
  updateInputState();
}

function showProcessingFrame(){
  clearMessageRevealTimers();
  currentShareSummary=null;
  downloadResultImageButton.disabled=true;
  resultImageStatus.textContent='';
  inputFrame.style.display='none';
  resultFrame.classList.remove('active');
  resultScrollButton.hidden=true;
  processingFrame.hidden=false;
  processingFrame.setAttribute('aria-busy','true');
  window.scrollTo({top:0,behavior:'smooth'});
}

function hideProcessingFrame(){
  processingFrame.hidden=true;
  processingFrame.setAttribute('aria-busy','false');
}

function showFeedback(message,type='error'){feedback.textContent=message;feedback.className=`feedback ${type}`}
function hideFeedback(){feedback.textContent='';feedback.className='feedback'}
function saveDraft(){
  try{
    if(messageInput.value)sessionStorage.setItem(DRAFT_KEY,messageInput.value);
    else sessionStorage.removeItem(DRAFT_KEY);
  }catch(error){
    return;
  }
}
function restoreDraft(){
  try{
    const draft=sessionStorage.getItem(DRAFT_KEY);
    if(draft&&!messageInput.value)messageInput.value=draft.slice(0,MAX_LENGTH);
  }catch(error){
    return;
  }
}
function updateInputState(){const rawLength=messageInput.value.length,clean=normalizedValue();characterCount.textContent=`${rawLength} / ${MAX_LENGTH}`;checkButton.disabled=isAnalyzing||(!isOffline&&sessionAtLimit)||clean.length<MIN_LENGTH;if(rawLength===0){hideFeedback();messageInput.removeAttribute('aria-invalid')}else if(clean.length===0){showFeedback('Nội dung không thể chỉ gồm khoảng trắng.');messageInput.setAttribute('aria-invalid','true')}else if(clean.length<MIN_LENGTH){showFeedback(`Nội dung còn quá ngắn. Vui lòng nhập ít nhất ${MIN_LENGTH} ký tự.`);messageInput.setAttribute('aria-invalid','true')}else{hideFeedback();messageInput.removeAttribute('aria-invalid')}}
function setupSpeechRecognition(){const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SpeechRecognition){voiceButton.disabled=true;voiceStatus.textContent='Trình duyệt này chưa hỗ trợ nhập bằng giọng nói. Bạn vẫn có thể nhập hoặc dán nội dung.';return}recognition=new SpeechRecognition();recognition.lang='vi-VN';recognition.interimResults=true;recognition.continuous=true;let finalTranscript='';recognition.onstart=()=>{isRecording=true;finalTranscript='';voiceButton.classList.add('recording');voiceButton.setAttribute('aria-pressed','true');voiceButton.title='Tắt micro';voiceButtonLabel.textContent='Tắt micro';voiceStatus.textContent='Đang ghi âm… Hãy đọc rõ nội dung tin nhắn.'};recognition.onresult=(event)=>{let interimTranscript='';for(let i=event.resultIndex;i<event.results.length;i++){const transcript=event.results[i][0].transcript;if(event.results[i].isFinal)finalTranscript+=transcript+' ';else interimTranscript+=transcript}const combined=`${finalTranscript}${interimTranscript}`.trim();if(combined){const base=messageInput.dataset.beforeVoice||'';messageInput.value=base?`${base} ${combined}`:combined;messageInput.dispatchEvent(new Event('input'))}};recognition.onerror=(event)=>{isRecording=false;voiceButton.classList.remove('recording');voiceButton.setAttribute('aria-pressed','false');voiceButton.title='Bật micro';voiceButtonLabel.textContent='Bật micro';if(event.error==='not-allowed'||event.error==='service-not-allowed')voiceStatus.textContent='Không thể dùng micro vì quyền truy cập đã bị từ chối. Bạn vẫn có thể nhập nội dung bằng bàn phím.';else if(event.error==='no-speech')voiceStatus.textContent='Chưa nhận được giọng nói. Vui lòng thử lại và nói gần micro hơn.';else voiceStatus.textContent='Tính năng giọng nói tạm thời chưa hoạt động. Vui lòng nhập nội dung thủ công.'};recognition.onend=()=>{isRecording=false;voiceButton.classList.remove('recording');voiceButton.setAttribute('aria-pressed','false');voiceButton.title='Bật micro';voiceButtonLabel.textContent='Bật micro';if(!voiceStatus.textContent.includes('từ chối')&&!voiceStatus.textContent.includes('tạm thời')&&!voiceStatus.textContent.includes('Chưa nhận'))voiceStatus.textContent='Đã dừng ghi âm.';delete messageInput.dataset.beforeVoice}}
function getHistory(){
  return historyCache;
}

function frontendRiskLevel(level){
  return {low:'safe',medium:'suspicious',high:'dangerous'}[level]||'suspicious';
}

function backendAnalysisToPayload(result,{guideOutput=null,guideUnavailable=false,guidePending=false}={}){
  const analysis=result?.analysis||{};
  const evidence=analysis.excerpts&&typeof analysis.excerpts==='object'
    ?Object.entries(analysis.excerpts).slice(0,4).map(([excerpt,reason])=>({
      label:String(reason||'Dấu hiệu đáng chú ý'),
      excerpt:String(excerpt)
    })).filter(item=>item.excerpt)
    :[];
  const riskLevel=frontendRiskLevel(result?.risk_level);

  return {
    id:String(result?.id||''),
    offline:false,
    detective:{
      title:'Thám tử',
      analysis_mode:'online',
      risk_level:riskLevel,
      confidence:Number.isFinite(analysis.risk_level)?analysis.risk_level:0.5,
      reasoning:String(analysis.reasoning||'Không có phần giải thích được lưu.'),
      indicator_evidence:evidence,
      indicators:evidence.map(item=>item.label),
      actions:Array.isArray(analysis.suggestions)
        ?analysis.suggestions.slice(0,3).map(String)
        :[]
    },
    deterministic_findings:Array.isArray(result?.deterministic_findings)
      ?result.deterministic_findings
      :[],
    character:guideOutput?{
      character_id:'calming-guide',
      title:'Cô tâm lý',
      message:String(guideOutput)
    }:null,
    character_notice:guideUnavailable
      ?'Cô tâm lý chưa thể tải hướng dẫn bổ sung lúc này.'
      :null,
    character_pending:guidePending
  };
}

function backendHistoryToItem(entry){
  const result=backendAnalysisToPayload(entry?.analysis,{guideOutput:entry?.guide_output});
  result.id=String(entry?.id||'');
  return {
    id:String(entry?.id||''),
    message:String(entry?.message||''),
    date:String(entry?.created_at||''),
    result,
    offline:false
  };
}

function readOfflineHistory(){
  try{
    const parsed=JSON.parse(localStorage.getItem(OFFLINE_HISTORY_KEY)||'[]');
    return Array.isArray(parsed)?parsed.slice(0,MAX_OFFLINE_HISTORY):[];
  }catch(error){
    return [];
  }
}

function writeOfflineHistory(entries){
  try{
    localStorage.setItem(OFFLINE_HISTORY_KEY,JSON.stringify(entries.slice(0,MAX_OFFLINE_HISTORY)));
  }catch(error){
    return;
  }
}

function saveOfflineHistory(message,result){
  const entry={
    id:`offline-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    message:message.slice(0,MAX_LENGTH),
    date:new Date().toISOString(),
    result,
    offline:true
  };
  writeOfflineHistory([entry,...readOfflineHistory()]);
  return entry;
}

async function loadHistory(){
  historyList.replaceChildren();
  const loading=document.createElement('p');
  loading.className='history-empty';
  loading.textContent='Đang tải lịch sử…';
  historyList.appendChild(loading);
  const offlineEntries=readOfflineHistory();
  if(isOffline){
    historyCache=offlineEntries;
    renderHistory();
    return;
  }
  try{
    const entries=await requestJson('/history/');
    const onlineEntries=Array.isArray(entries)?entries.map(backendHistoryToItem):[];
    historyCache=[...onlineEntries,...offlineEntries].sort(
      (a,b)=>new Date(b.date).getTime()-new Date(a.date).getTime()
    );
    renderHistory();
  }catch(error){
    historyCache=offlineEntries;
    renderHistory();
    if(!offlineEntries.length)historyList.firstChild.textContent='Không thể tải lịch sử lúc này.';
  }
}

async function showSavedHistoryResult(item){
  if(!item?.result)return;
  window.location.hash='analyze';
  switchView('analyze');
  showResultFrame(item.message,item.result,{fromHistory:true});
}

function updateHistorySelectionUi(){
  const count=selectedHistoryIds.size;
  historySelectedCount.textContent=`Đã chọn ${count} tin nhắn`;
  historyDeleteButton.disabled=count===0;
}

function renderHistory(){
  const history=getHistory();
  const validIds=new Set(history.map(item=>item.id));
  selectedHistoryIds=new Set([...selectedHistoryIds].filter(id=>validIds.has(id)));
  historyList.replaceChildren();

  if(history.length===0){
    selectedHistoryIds.clear();
    updateHistorySelectionUi();
    const empty=document.createElement('p');
    empty.className='history-empty';
    empty.textContent='Chưa có tin nhắn nào trong lịch sử.';
    historyList.appendChild(empty);
    return;
  }

  history.forEach((item,index)=>{
    const article=document.createElement('article');
    article.className='history-item';
    if(selectedHistoryIds.has(item.id))article.classList.add('is-selected');

    const row=document.createElement('label');
    row.className='history-select-row';

    const checkbox=document.createElement('input');
    checkbox.className='history-checkbox';
    checkbox.type='checkbox';
    checkbox.checked=selectedHistoryIds.has(item.id);
    checkbox.setAttribute('aria-label',`Chọn tin nhắn lịch sử số ${index+1} để xóa`);

    const content=document.createElement('div');
    const result=item.result&&typeof item.result==='object'?item.result:null;
    const riskLevel=['safe','suspicious','dangerous'].includes(result?.detective?.risk_level)
      ?result.detective.risk_level
      :null;
    const riskLabels={safe:'An toàn',suspicious:'Nghi ngờ',dangerous:'Nguy hiểm'};
    const meta=document.createElement('div');
    meta.className='history-meta';
    const status=document.createElement('span');
    status.className=`history-status ${riskLevel||'unavailable'}`;
    status.textContent=riskLevel?riskLabels[riskLevel]:'Chưa lưu kết quả';
    const mode=document.createElement('span');
    mode.className='history-mode';
    mode.textContent=item.offline?'Ngoại tuyến':'Trực tuyến';
    meta.append(status,mode);
    const message=document.createElement('div');
    message.className='history-message-text';
    message.textContent=item.message;

    const time=document.createElement('time');
    time.className='history-time';
    const date=new Date(item.date);
    time.dateTime=item.date||'';
    time.textContent=Number.isNaN(date.getTime())?'':date.toLocaleString('vi-VN',{
      timeZone:'Asia/Ho_Chi_Minh'
    });

    checkbox.addEventListener('change',()=>{
      if(checkbox.checked){
        selectedHistoryIds.add(item.id);
        article.classList.add('is-selected');
      }else{
        selectedHistoryIds.delete(item.id);
        article.classList.remove('is-selected');
      }
      updateHistorySelectionUi();
    });

    content.append(meta,message,time);
    row.append(checkbox,content);

    const actions=document.createElement('div');
    actions.className='history-item-actions';
    const reviewButton=document.createElement('button');
    reviewButton.className=`history-review-button ${riskLevel||'unavailable'}`;
    reviewButton.type='button';
    reviewButton.textContent=result?'Xem kết quả':'Kết quả chưa lưu';
    reviewButton.disabled=!result;
    if(result){
      reviewButton.addEventListener('click',()=>void showSavedHistoryResult(item));
    }else{
      const explanation='Mục lịch sử cũ này không có kết quả đã lưu. Hãy kiểm tra lại để tạo kết quả mới.';
      reviewButton.title=explanation;
      reviewButton.setAttribute('aria-label',explanation);
    }
    const reuseButton=document.createElement('button');
    reuseButton.className='history-reuse-button';
    reuseButton.type='button';
    reuseButton.textContent='Kiểm tra lại';
    reuseButton.addEventListener('click',()=>{
      messageInput.value=item.message;
      messageInput.dispatchEvent(new Event('input'));
      resultFrame.classList.remove('active');
      inputFrame.style.display='block';
      window.location.hash='analyze';
      switchView('analyze');
      window.setTimeout(()=>messageInput.focus(),0);
    });
    actions.append(reviewButton,reuseButton);
    article.append(row,actions);
    historyList.appendChild(article);
  });

  updateHistorySelectionUi();
}

function openDeleteConfirmation(){
  if(selectedHistoryIds.size===0)return;
  const selectedItems=getHistory().filter(item=>selectedHistoryIds.has(item.id));
  if(selectedItems.length===0){
    selectedHistoryIds.clear();
    renderHistory();
    return;
  }

  deleteConfirmText.textContent=`Bạn đang chuẩn bị xóa ${selectedItems.length} tin nhắn đã chọn. Hãy kiểm tra lại danh sách bên dưới. Thao tác này không thể hoàn tác.`;
  deletePreview.replaceChildren();

  selectedItems.forEach((item,index)=>{
    const preview=document.createElement('p');
    preview.className='delete-preview-item';
    preview.textContent=`${index+1}. ${item.message}`;
    preview.title=item.message;
    deletePreview.appendChild(preview);
  });

  deleteConfirmModal.classList.add('open');
  deleteConfirmModal.setAttribute('aria-hidden','false');
  document.body.style.overflow='hidden';
  deleteCancelButton.focus();
}

function closeDeleteConfirmation(){
  deleteConfirmModal.classList.remove('open');
  deleteConfirmModal.setAttribute('aria-hidden','true');
  document.body.style.overflow='';
  historyDeleteButton.focus();
}

async function confirmDeleteSelectedHistory(){
  if(selectedHistoryIds.size===0){
    closeDeleteConfirmation();
    return;
  }

  const ids=[...selectedHistoryIds];
  deleteCancelButton.disabled=true;
  deleteConfirmButton.disabled=true;
  try{
    const selected=getHistory().filter(item=>selectedHistoryIds.has(item.id));
    const onlineIds=selected.filter(item=>!item.offline).map(item=>item.id);
    const offlineIds=new Set(selected.filter(item=>item.offline).map(item=>item.id));
    await Promise.all(onlineIds.map(id=>requestJson(`/history/${encodeURIComponent(id)}`,{
      method:'DELETE'
    })));
    if(offlineIds.size){
      writeOfflineHistory(readOfflineHistory().filter(item=>!offlineIds.has(item.id)));
    }
    selectedHistoryIds.clear();
    deleteConfirmModal.classList.remove('open');
    deleteConfirmModal.setAttribute('aria-hidden','true');
    document.body.style.overflow='';
    await loadHistory();
    historySelectedCount.textContent=`Đã xóa ${ids.length} tin nhắn`;
    document.querySelector('.nav-link[data-view="history"]')?.focus();
  }catch(error){
    deleteConfirmText.textContent='Không thể xóa các mục đã chọn lúc này. Bác vui lòng thử lại.';
  }finally{
    deleteCancelButton.disabled=false;
    deleteConfirmButton.disabled=false;
  }
}

function apiErrorMessage(statusCode,detail){
  if(statusCode===409)return 'Yêu cầu này vẫn đang được xử lý. Bác vui lòng thử lại sau ít phút.';
  if(statusCode===429)return 'Phiên này đã dùng hết lượt kiểm tra AI. Bác vui lòng xem lại các kết quả đã lưu.';
  if(statusCode===502)return 'Dịch vụ phân tích đang tạm thời gián đoạn. Bác vui lòng thử lại sau.';
  if(statusCode===503)return 'Không thể lưu kết quả lúc này. Bác vui lòng thử lại sau.';
  if(statusCode===422)return 'Nội dung gửi lên chưa hợp lệ. Bác hãy kiểm tra và thử lại.';
  return typeof detail==='string'&&detail?'Không thể hoàn tất yêu cầu lúc này.':'Không thể kết nối tới máy chủ.';
}

async function requestJson(path,options={}){
  const requestOptions={credentials:'same-origin',...options};
  const onAnalysisResult=typeof requestOptions.onAnalysisResult==='function'
    ?requestOptions.onAnalysisResult
    :null;
  delete requestOptions.onAnalysisResult;
  let requestPath=path;
  let submittedText=null;
  if(path==='/analyze'){
    try{
      const parsed=JSON.parse(String(requestOptions.body||'null'));
      if(parsed&&typeof parsed==='object'&&typeof parsed.text==='string'){
        submittedText=parsed.text;
        requestPath='/analyze/';
        requestOptions.body=JSON.stringify(submittedText);
        if(requestOptions.headers&&typeof requestOptions.headers==='object'){
          delete requestOptions.headers['X-ScamCheck-Request-ID'];
        }
      }
    }catch(error){
      // Leave the request untouched when the body is not the expected frontend shape.
    }
  }

  const response=await fetch(requestPath,requestOptions);
  let payload=null;
  try{
    payload=await response.json();
  }catch(error){
    payload=null;
  }
  if(!response.ok){
    const requestError=new Error(apiErrorMessage(response.status,payload?.detail));
    requestError.status=response.status;
    throw requestError;
  }
  if(requestPath==='/analyze/'&&submittedText!==null){
    if(onAnalysisResult){
      onAnalysisResult(backendAnalysisToPayload(
        payload,
        {guidePending:['medium','high'].includes(payload?.risk_level)}
      ));
    }
    return prepareOnlineResult(submittedText,payload);
  }
  return payload;
}

async function loadUsageCompat(){
  renderRemainingAnalyses();
}

async function prepareOnlineResult(submittedText,analysisResult){
  const needsGuide=['medium','high'].includes(analysisResult?.risk_level);
  let entries=[];
  try{
    const history=await requestJson('/history/');
    entries=Array.isArray(history)?history:[];
  }catch(error){
    return backendAnalysisToPayload(analysisResult,{guideUnavailable:needsGuide});
  }

  const entry=entries.find(item=>item?.message===submittedText)||entries[0];
  let guideOutput=entry?.guide_output||null;
  let guideUnavailable=needsGuide&&!entry;
  if(needsGuide&&entry&&!guideOutput){
    try{
      const guide=await requestJson('/guide/',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(entry.id)
      });
      guideOutput=guide?.data||null;
      if(guideOutput)entry.guide_output=guideOutput;
    }catch(error){
      guideUnavailable=true;
    }
  }
  historyCache=entries.map(backendHistoryToItem);
  const payload=backendAnalysisToPayload(analysisResult,{guideOutput,guideUnavailable});
  if(entry){
    payload.id=String(entry.id||'');
    payload.date=String(entry.created_at||new Date().toISOString());
  }
  return payload;
}

function applyUsage(aiUsage){
  const used=Number(aiUsage?.used||0);
  const limit=Number(aiUsage?.limit||0);
  sessionAtLimit=limit>0&&used>=limit;
  if(sessionAtLimit){
    remainingAnalyses=0;
    saveRemainingAnalyses();
  }
  renderRemainingAnalyses();
}

function showConnectivityNotice(message){
  connectivityMessage.textContent=message;
  connectivityStatus.hidden=false;
}

function updateConnectivityState(){
  isOffline=!navigator.onLine;
  if(isOffline){
    showConnectivityNotice('Thiết bị đang mất kết nối. ScamCheck sẽ phân tích sơ bộ ngay trên thiết bị.');
  }else{
    connectivityStatus.hidden=true;
  }
  void loadUsageCompat();
  updateInputState();
}

function registerServiceWorker(){
  if(!('serviceWorker' in navigator))return;
  void navigator.serviceWorker.register('/service-worker.js').catch(()=>{});
}

function setPracticeAnswersDisabled(disabled){
  practiceAnswerButtons.forEach(button=>{button.disabled=disabled});
}

function renderPracticePrompt(){
  const prompt=practicePrompts[practiceIndex];
  practiceLocked=false;
  practiceContent.hidden=false;
  practiceMessage.textContent=prompt.text;
  practiceProgress.textContent=`Câu ${practiceIndex+1}/${practicePrompts.length}`;
  practiceScore.textContent=`Điểm ${practiceCorrect}/${practiceAnswered}`;
  practiceFeedback.hidden=true;
  practiceFeedback.textContent='';
  practiceFeedback.className='practice-feedback';
  practiceNextButton.hidden=true;
  practiceAnswerButtons.forEach(button=>{
    button.disabled=false;
    button.classList.remove('is-correct','is-incorrect');
  });
}

function submitPracticeAnswer(answer,selectedButton){
  if(practiceLocked)return;
  const prompt=practicePrompts[practiceIndex];
  practiceLocked=true;
  setPracticeAnswersDisabled(true);
  practiceFeedback.hidden=true;

  const isCorrect=answer===prompt.label;
  practiceAnswered+=1;
  if(isCorrect)practiceCorrect+=1;
  practiceScore.textContent=`Điểm ${practiceCorrect}/${practiceAnswered}`;

  const correctButton=[...practiceAnswerButtons].find(
    button=>button.dataset.answer===prompt.label
  );
  if(correctButton)correctButton.classList.add('is-correct');
  if(!isCorrect)selectedButton.classList.add('is-incorrect');

  const answerLabel=prompt.label==='scam'?'Lừa đảo':'An toàn';
  practiceFeedback.textContent=isCorrect
    ?`Chính xác. ${prompt.reason}`
    :`Chưa đúng. Đáp án là ${answerLabel}. ${prompt.reason}`;
  practiceFeedback.className=`practice-feedback ${isCorrect?'correct':'incorrect'}`;
  practiceFeedback.hidden=false;
  practiceNextButton.textContent=practiceIndex===practicePrompts.length-1
    ?'Làm lại từ đầu'
    :'Câu tiếp theo →';
  practiceNextButton.hidden=false;
  practiceNextButton.focus();
}

messageInput.addEventListener('input',()=>{saveDraft();updateInputState()});
sampleButtons.forEach(button=>button.addEventListener('click',()=>{messageInput.value=samples[button.dataset.sample];messageInput.focus();messageInput.dispatchEvent(new Event('input'))}));
voiceButton.addEventListener('click',()=>{if(!recognition)return;try{if(isRecording)recognition.stop();else{messageInput.dataset.beforeVoice=messageInput.value.trim();recognition.start()}}catch(error){voiceStatus.textContent='Không thể khởi động micro lúc này. Vui lòng thử lại sau.'}});
postAnalysisOptions.forEach(option=>option.addEventListener('click',async()=>{
  if(option.disabled)return;
  postAnalysisOptions.forEach(item=>{
    item.disabled=true;
    item.classList.toggle('selected',item===option);
    item.setAttribute('aria-pressed',String(item===option));
  });
  try{
    const text=postAnalysisQuestion.dataset.message.toLocaleLowerCase('vi-VN').replaceAll(' ','');
    const hotlines=Object.fromEntries(Object.entries(await loadTelephones()).filter(([name])=>text.includes(name.toLocaleLowerCase('vi-VN').replaceAll(' ',''))));
    const output=await requestJson('/responder/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({history_id:postAnalysisQuestion.dataset.analysisId,choice:option.dataset.postAnalysisChoice,hotlines})});
    renderResponderGuidance(output.steps);
  }catch(error){showFeedback('Chưa thể tải các bước ứng cứu. Bác hãy thử lại sau.');}
}));
downloadResultImageButton.addEventListener('click',async()=>{
  downloadResultImageButton.disabled=true;
  resultImageStatus.textContent='Đang tạo ảnh PNG…';
  try{
    const outcome=await saveCurrentResultImage();
    if(outcome==='shared'){
      resultImageStatus.textContent='Đã mở bảng chia sẻ. Trên iPhone, chọn “Lưu hình ảnh” để đưa ảnh vào thư viện Ảnh.';
    }else if(outcome==='preview'){
      resultImageStatus.textContent='Ảnh đã được mở. Trên iPhone, chạm và giữ ảnh rồi chọn “Lưu vào Ảnh”.';
    }else if(outcome==='cancelled'){
      resultImageStatus.textContent='Đã đóng bảng chia sẻ; ảnh chưa được lưu.';
    }else{
      resultImageStatus.textContent='Đã tải ảnh PNG về thiết bị.';
    }
  }catch(error){
    resultImageStatus.textContent='Chưa thể tạo ảnh lúc này. Bác vui lòng thử lại.';
  }finally{
    downloadResultImageButton.disabled=false;
  }
});
historyDeleteButton.addEventListener('click',openDeleteConfirmation);
deleteCancelButton.addEventListener('click',closeDeleteConfirmation);
deleteConfirmButton.addEventListener('click',confirmDeleteSelectedHistory);
deleteConfirmModal.addEventListener('click',event=>{if(event.target===deleteConfirmModal)closeDeleteConfirmation()});
librarySearch.addEventListener('input',()=>{
  libraryQuery=librarySearch.value.trim();
  renderScamTypeList();
});
libraryFilters.forEach(button=>button.addEventListener('click',()=>{
  selectedScamGroup=button.dataset.scamGroup||'all';
  renderScamTypeList();
}));
libraryResetButton.addEventListener('click',()=>{
  selectedScamGroup='all';
  libraryQuery='';
  librarySearch.value='';
  renderScamTypeList();
  librarySearch.focus();
});
libraryRetryButton.addEventListener('click',()=>void loadScamTypes({force:true}));
libraryDetailBack.addEventListener('click',()=>{
  if(window.history.state?.scamLibraryFromList){
    window.history.back();
    return;
  }
  window.location.hash='library';
});
navLinks.forEach(link=>link.addEventListener('click',event=>{
  const target=link.dataset.view;
  if(target==='analyze'&&resultFrame.classList.contains('active')){
    showComposerFrame();
  }
  if(window.location.hash===`#${target}`){
    event.preventDefault();
    syncRoute({focus:true});
  }
}));
practiceAnswerButtons.forEach(button=>button.addEventListener('click',()=>{
  submitPracticeAnswer(button.dataset.answer,button);
}));
practiceNextButton.addEventListener('click',()=>{
  if(practiceIndex===practicePrompts.length-1){
    practiceIndex=0;
    practiceCorrect=0;
    practiceAnswered=0;
  }else{
    practiceIndex+=1;
  }
  renderPracticePrompt();
  practiceMessage.focus();
});
document.addEventListener('keydown',event=>{
  if(event.key!=='Escape')return;
  if(deleteConfirmModal.classList.contains('open')){
    closeDeleteConfirmation();
  }
});

function pendingAnalysisFor(message){
  try{
    const pending=JSON.parse(sessionStorage.getItem(PENDING_ANALYSIS_KEY)||'null');
    if(pending?.message===message&&typeof pending.requestId==='string')return pending;
  }catch(error){
    // Ignore damaged or unavailable tab storage and create a fresh identifier.
  }
  const requestId=typeof crypto.randomUUID==='function'
    ?crypto.randomUUID()
    :Array.from(crypto.getRandomValues(new Uint8Array(16)),value=>value.toString(16).padStart(2,'0')).join('');
  const pending={message,requestId};
  try{
    sessionStorage.setItem(PENDING_ANALYSIS_KEY,JSON.stringify(pending));
  }catch(error){
    return pending;
  }
  return pending;
}

async function runAnalysis(submittedText){
  if(isAnalyzing)return;
  isAnalyzing=true;
  decrementRemainingAnalyses();
  updateInputState();
  showProcessingFrame();

  try{
    let payload;
    let resultShown=false;
    if(isOffline){
      payload=ScamCheckOffline.analyze(submittedText);
      saveOfflineHistory(submittedText,payload);
    }else{
      try{
        const pending=pendingAnalysisFor(submittedText);
        payload=await requestJson('/analyze',{
          method:'POST',
          headers:{
            'Content-Type':'application/json',
            'X-ScamCheck-Request-ID':pending.requestId
          },
          onAnalysisResult:initialPayload=>{
            resultShown=true;
            connectivityStatus.hidden=true;
            showResultFrame(submittedText,initialPayload);
          },
          body:JSON.stringify({text:submittedText,source:'web'})
        });
        try{
          sessionStorage.removeItem(PENDING_ANALYSIS_KEY);
        }catch(error){
          // The response is still valid when tab storage is unavailable.
        }
        if(payload?.usage)applyUsage(payload.usage);
        if(payload?.id&&!historyCache.some(item=>item.id===payload.id))historyCache.unshift({
          id:payload.id,
          message:submittedText,
          date:payload.date||new Date().toISOString(),
          result:payload,
          offline:false
        });
      }catch(error){
        if(Number.isInteger(error.status))throw error;
        const interruptedError=new Error('Kết nối mạng không ổn định. Nội dung vẫn được giữ trong ô nhập; bác hãy thử lại khi đường truyền ổn định.');
        interruptedError.networkInterrupted=true;
        throw interruptedError;
      }
    }
    connectivityStatus.hidden=true;
    if(resultShown)completeResultFrame(submittedText,payload);
    else showResultFrame(submittedText,payload);
  }catch(error){
    hideProcessingFrame();
    inputFrame.style.display='block';
    if(error.networkInterrupted){
      showConnectivityNotice('Kết nối mạng không ổn định. Bác hãy kiểm tra Wi-Fi hoặc dữ liệu di động rồi thử lại.');
      showFeedback(error.message,'info');
    }else{
      if(error.status===429){
        sessionAtLimit=true;
        remainingAnalyses=0;
        saveRemainingAnalyses();
        renderRemainingAnalyses();
      }
      if(navigator.onLine)connectivityStatus.hidden=true;
      showFeedback(Number.isInteger(error.status)?error.message:'Không thể kết nối tới máy chủ.');
    }
    void loadUsageCompat();
    messageInput.focus();
  }finally{
    hideProcessingFrame();
    isAnalyzing=false;
    updateInputState();
  }
}

function createLibraryIcon(group,className=''){
  const details=scamGroupDetails[group]||scamGroupDetails.fake_bank;
  const wrapper=document.createElement('span');
  wrapper.className=`library-icon ${group} ${className}`.trim();
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 24 24');
  svg.setAttribute('aria-hidden','true');
  const path=document.createElementNS('http://www.w3.org/2000/svg','path');
  path.setAttribute('fill','currentColor');
  path.setAttribute('d',details.iconPath);
  svg.appendChild(path);
  wrapper.appendChild(svg);
  return wrapper;
}

function appendLibraryItems(container,items){
  container.replaceChildren();
  items.forEach(textValue=>{
    const item=document.createElement('li');
    item.textContent=textValue;
    container.appendChild(item);
  });
}

function normalizedSearchText(value){
  return String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('vi-VN');
}

function renderScamTypeList(){
  const query=normalizedSearchText(libraryQuery);
  const visible=scamTypes.filter(item=>{
    const inGroup=selectedScamGroup==='all'||item.group===selectedScamGroup;
    const searchable=normalizedSearchText(`${item.name} ${item.description}`);
    return inGroup&&(!query||searchable.includes(query));
  });

  libraryFilters.forEach(button=>{
    const active=button.dataset.scamGroup===selectedScamGroup;
    button.classList.toggle('active',active);
    button.setAttribute('aria-pressed',String(active));
  });
  scamTypeList.replaceChildren();
  visible.forEach(item=>{
    const details=scamGroupDetails[item.group]||scamGroupDetails.fake_bank;
    const card=document.createElement('button');
    card.type='button';
    card.className='scam-type-card';
    card.setAttribute('aria-label',`Xem chi tiết: ${item.name}`);
    const icon=createLibraryIcon(item.group);
    const body=document.createElement('span');
    body.className='scam-type-card-body';
    const group=document.createElement('span');
    group.className=`scam-group-label ${item.group}`;
    group.textContent=details.label;
    const title=document.createElement('span');
    title.className='scam-type-card-title';
    title.textContent=item.name;
    const description=document.createElement('span');
    description.className='scam-type-card-description';
    description.textContent=item.description;
    const action=document.createElement('span');
    action.className='scam-type-card-action';
    action.textContent='Xem chi tiết →';
    body.append(group,title,description,action);
    card.append(icon,body);
    card.addEventListener('click',()=>{
      libraryScrollPosition=window.scrollY;
      window.history.pushState({scamLibraryFromList:true},'',`#library/${encodeURIComponent(item.id)}`);
      syncRoute({focus:true});
    });
    scamTypeList.appendChild(card);
  });
  libraryResultCount.textContent=`${visible.length} kiểu lừa đảo`;
  libraryEmpty.hidden=visible.length!==0;
}

async function loadScamTypes({force=false}={}){
  if(scamTypes.length&&!force){
    renderScamTypeList();
    return scamTypes;
  }
  if(scamTypesPromise&&!force)return scamTypesPromise;
  libraryLoadError.hidden=true;
  libraryResultCount.textContent='Đang tải thư viện…';
  scamTypeList.replaceChildren();
  libraryEmpty.hidden=true;
  scamTypesPromise=(async()=>{
    try{
      const payload=await requestJson('/scam-types');
      scamTypes=Array.isArray(payload)?payload:[];
      renderScamTypeList();
      return scamTypes;
    }catch(error){
      scamTypes=[];
      libraryResultCount.textContent='Chưa tải được dữ liệu';
      libraryLoadError.hidden=false;
      return [];
    }finally{
      scamTypesPromise=null;
    }
  })();
  return scamTypesPromise;
}

function showLibraryList(){
  void loadTelephones();
  libraryDetailFrame.hidden=true;
  libraryListFrame.hidden=false;
  void loadScamTypes().then(()=>{
    requestAnimationFrame(()=>window.scrollTo({top:libraryScrollPosition,behavior:'auto'}));
  });
}

async function loadTelephones(){
  const grid=byId('hotline-grid');
  if(telephoneCatalog)return telephoneCatalog;
  grid.replaceChildren();
  try{telephoneCatalog=await requestJson('/telephones');grid.replaceChildren(...Object.entries(telephoneCatalog).map(([name,number])=>{
    const card=document.createElement('article'),title=document.createElement('h3'),link=document.createElement('a');
    card.className='hotline-card';title.textContent=name;link.href=`tel:${number}`;link.textContent=number;link.setAttribute('aria-label',`Gọi tổng đài ${name}: ${number}`);card.append(title,link);return card;
  }));return telephoneCatalog;}catch(error){grid.textContent='Chưa tải được danh sách tổng đài.';return {};}
}

async function showLibraryDetail(detailId){
  libraryListFrame.hidden=true;
  libraryDetailFrame.hidden=false;
  libraryDetailContent.hidden=true;
  libraryDetailError.hidden=true;
  libraryDetailBack.focus({preventScroll:true});
  window.scrollTo({top:0,behavior:'smooth'});
  try{
    const item=await requestJson(`/scam-types/${encodeURIComponent(detailId)}`);
    const currentRoute=routeFromHash();
    if(currentRoute.view!=='library'||currentRoute.detailId!==detailId)return;
    const details=scamGroupDetails[item.group]||scamGroupDetails.fake_bank;
    libraryDetailIcon.replaceChildren(createLibraryIcon(item.group,'large'));
    libraryDetailGroup.textContent=details.label;
    libraryDetailGroup.className=`scam-group-label ${item.group}`;
    libraryDetailTitle.textContent=item.name;
    libraryDetailDescription.textContent=item.description;
    libraryDetailExample.textContent=item.example_message;
    appendLibraryItems(libraryDetailSigns,details.signs);
    appendLibraryItems(libraryDetailDo,librarySafeActions);
    appendLibraryItems(libraryDetailDont,libraryUnsafeActions);
    libraryDetailContent.hidden=false;
    document.title=`${item.name} · ScamCheck`;
  }catch(error){
    const currentRoute=routeFromHash();
    if(currentRoute.view==='library'&&currentRoute.detailId===detailId)libraryDetailError.hidden=false;
  }
}

function syncLibraryRoute(){
  const route=routeFromHash();
  if(route.view!=='library')return;
  if(route.detailId)void showLibraryDetail(route.detailId);
  else showLibraryList();
}

function syncRoute({focus=false}={}){
  const route=routeFromHash();
  switchView(route.view,{focus});
  if(route.view==='library')syncLibraryRoute();
}

checkButton.addEventListener('click',async()=>{
  const clean=normalizedValue();
  if(!clean){
    showFeedback('Vui lòng dán hoặc nhập nội dung cần kiểm tra.');
    messageInput.setAttribute('aria-invalid','true');
    messageInput.focus();
    return;
  }
  if(clean.length<MIN_LENGTH){
    showFeedback(`Nội dung còn quá ngắn. Vui lòng nhập ít nhất ${MIN_LENGTH} ký tự.`);
    messageInput.setAttribute('aria-invalid','true');
    messageInput.focus();
    return;
  }
  await runAnalysis(messageInput.value.trim());
});
historyReturnButton.addEventListener('click',()=>{
  showComposerFrame();
  window.location.hash='history';
  switchView('history',{focus:true});
});
resultScrollButton.addEventListener('click',resumeResultAutoFollow);
window.addEventListener('scroll',handleResultWindowScroll,{passive:true});
window.addEventListener('wheel',event=>{
  if(event.deltaY<0)pauseResultAutoFollow();
},{passive:true});
window.addEventListener('touchstart',event=>{
  const touch=event.touches[0];
  resultTouchY=touch?touch.clientY:null;
},{passive:true});
window.addEventListener('touchmove',event=>{
  const touch=event.touches[0];
  const currentTouchY=touch?touch.clientY:null;
  if(resultTouchY!==null&&currentTouchY!==null&&currentTouchY>resultTouchY+4){
    pauseResultAutoFollow();
  }
  if(currentTouchY!==null)resultTouchY=currentTouchY;
},{passive:true});
window.addEventListener('touchend',()=>{resultTouchY=null},{passive:true});
window.addEventListener('keydown',event=>{
  if(['ArrowUp','PageUp','Home'].includes(event.key)||(event.key===' '&&event.shiftKey)){
    pauseResultAutoFollow();
  }
});
window.addEventListener('online',updateConnectivityState);
window.addEventListener('offline',updateConnectivityState);
window.addEventListener('hashchange',()=>syncRoute({focus:true}));
if(!window.location.hash)window.history.replaceState(null,'','#analyze');
restoreRemainingAnalyses();restoreDraft();setupSpeechRecognition();renderPracticePrompt();registerServiceWorker();updateConnectivityState();syncRoute();
