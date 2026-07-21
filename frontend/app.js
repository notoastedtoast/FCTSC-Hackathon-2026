const MIN_LENGTH=10,MAX_LENGTH=10000,DETECTIVE_MESSAGE_START_MS=180,DETECTIVE_MESSAGE_GAP_MS=650,MESSAGE_ANIMATION_MS=580,DRAFT_KEY='scamcheck-message-draft',OFFLINE_HISTORY_KEY='scamcheck-offline-history-v1',PENDING_ANALYSIS_KEY='scamcheck-pending-analysis-v1',MAX_OFFLINE_HISTORY=10;
const messageInput=document.getElementById('message'),clearButton=document.getElementById('clear-button'),checkButton=document.getElementById('check-button'),processingFrame=document.getElementById('processing-frame'),characterCount=document.getElementById('character-count'),feedback=document.getElementById('message-feedback'),usage=document.getElementById('usage'),connectivityStatus=document.getElementById('connectivity-status'),connectivityMessage=document.getElementById('connectivity-message'),voiceButton=document.getElementById('voice-button'),voiceButtonLabel=document.getElementById('voice-button-label'),voiceStatus=document.getElementById('voice-status'),inputFrame=document.getElementById('input-frame'),resultFrame=document.getElementById('result-frame'),riskCard=document.getElementById('risk-card'),riskLabel=document.getElementById('risk-label'),riskDescription=document.getElementById('risk-description'),signalList=document.getElementById('signal-list'),resultContextLabel=document.getElementById('result-context-label'),resultScrollButton=document.getElementById('result-scroll-button'),historyReturnButton=document.getElementById('history-return-button'),sampleButtons=document.querySelectorAll('.sample-button'),historyList=document.getElementById('history-list'),historySelectedCount=document.getElementById('history-selected-count'),historyDeleteButton=document.getElementById('history-delete-button'),deleteConfirmModal=document.getElementById('delete-confirm-modal'),deleteConfirmText=document.getElementById('delete-confirm-text'),deletePreview=document.getElementById('delete-preview'),deleteCancelButton=document.getElementById('delete-cancel-button'),deleteConfirmButton=document.getElementById('delete-confirm-button');
const psychologyBlock=document.getElementById('psychology-block'),psychologyMessage=document.getElementById('psychology-message'),actionSection=document.getElementById('action-section');
const practiceContent=document.getElementById('practice-content'),practiceMessage=document.getElementById('practice-message'),practiceProgress=document.getElementById('practice-progress'),practiceScore=document.getElementById('practice-score'),practiceAnswerButtons=document.querySelectorAll('.practice-answer-button'),practiceFeedback=document.getElementById('practice-feedback'),practiceNextButton=document.getElementById('practice-next-button');
const libraryListFrame=document.getElementById('library-list-frame'),libraryDetailFrame=document.getElementById('library-detail-frame'),librarySearch=document.getElementById('library-search'),libraryFilters=document.querySelectorAll('.library-filter'),libraryResultCount=document.getElementById('library-result-count'),libraryLoadError=document.getElementById('library-load-error'),libraryRetryButton=document.getElementById('library-retry-button'),scamTypeList=document.getElementById('scam-type-list'),libraryEmpty=document.getElementById('library-empty'),libraryResetButton=document.getElementById('library-reset-button'),libraryDetailBack=document.getElementById('library-detail-back'),libraryDetailError=document.getElementById('library-detail-error'),libraryDetailContent=document.getElementById('library-detail-content'),libraryDetailIcon=document.getElementById('library-detail-icon'),libraryDetailGroup=document.getElementById('library-detail-group'),libraryDetailTitle=document.getElementById('library-detail-title'),libraryDetailDescription=document.getElementById('library-detail-description'),libraryDetailSigns=document.getElementById('library-detail-signs'),libraryDetailExample=document.getElementById('library-detail-example'),libraryDetailDo=document.getElementById('library-detail-do'),libraryDetailDont=document.getElementById('library-detail-dont');
const navLinks=document.querySelectorAll('.nav-link[data-view]'),pageViews=document.querySelectorAll('[data-view-panel]');
const toolsColumn=document.querySelector('.tools-column'),mobileQuickCards=document.querySelectorAll('.sample-card'),mobileLayoutQuery=window.matchMedia('(max-width: 620px)');
let recognition=null,isRecording=false,selectedHistoryIds=new Set(),isAnalyzing=false,sessionAtLimit=false,isOffline=!navigator.onLine,historyCache=[],psychologySequenceTimer=null;
let autoFollowResult=true,latestResultMessage=null,lastResultScrollY=window.scrollY,resultScrollGuardUntil=0,resultTouchY=null;
let practiceIndex=0,practiceCorrect=0,practiceAnswered=0,practiceLocked=false;
let scamTypes=[],scamTypesPromise=null,selectedScamGroup='all',libraryQuery='',libraryScrollPosition=0;
const samples={bank:'NGÂN HÀNG THÔNG BÁO: Tài khoản của quý khách đang bị tạm khóa. Vui lòng truy cập đường link bên dưới và nhập mã OTP để xác minh ngay.',delivery:'Đơn hàng của bạn chưa thể giao vì thiếu phí vận chuyển 25.000 đồng. Hãy bấm vào liên kết và thanh toán trong hôm nay để tránh hoàn hàng.',prize:'Chúc mừng bạn đã trúng giải thưởng 100 triệu đồng. Vui lòng chuyển trước 2 triệu đồng phí hồ sơ vào tài khoản cá nhân để nhận thưởng.'};
const practicePrompts=[
  {
    "id":"scam-bank-security-upgrade",
    "text":"Hệ thống ngân hàng yêu cầu nâng cấp bảo mật trước 20 giờ tại vietcom-bank-login.com, nếu không tài khoản sẽ ngừng hoạt động.",
    "label":"scam",
    "reason":"Tin tạo áp lực thời gian và dùng tên miền chèn dấu gạch ngang để mạo danh ngân hàng."
  },
  {
    "id":"scam-police-secret-call",
    "text":"Cán bộ điều tra yêu cầu bác giữ bí mật cuộc gọi, bật chia sẻ màn hình và chuyển tiền để chứng minh trong sạch.",
    "label":"scam",
    "reason":"Cơ quan công an không điều tra bí mật qua cuộc gọi và không yêu cầu chuyển tiền chứng minh."
  },
  {
    "id":"scam-prize-activation",
    "text":"Bác được chọn nhận tivi miễn phí; hãy mua thẻ quà tặng 500.000 đồng làm phí kích hoạt giải.",
    "label":"scam",
    "reason":"Phần thưởng bất ngờ đi kèm khoản phí trả trước bằng phương thức khó truy vết."
  },
  {
    "id":"scam-delivery-short-link",
    "text":"Kiện hàng đang chờ bổ sung địa chỉ, cập nhật trong 15 phút tại bit.ly/nhan-hang-482.",
    "label":"scam",
    "reason":"Tin giả giao hàng dùng đường dẫn rút gọn để che giấu tên miền đích và thúc giục thao tác."
  },
  {
    "id":"scam-bank-remote-access",
    "text":"Nhân viên kỹ thuật ngân hàng cần bác cài AnyDesk để xử lý khoản tiền treo và khôi phục số dư.",
    "label":"scam",
    "reason":"Ngân hàng không yêu cầu khách cài phần mềm điều khiển từ xa để xử lý giao dịch."
  },
  {
    "id":"safe-bank-balance-notice",
    "text":"Tài khoản thanh toán vừa nhận 1.250.000 đồng lúc 09:12. Nếu không nhận ra giao dịch, bác tự mở ứng dụng ngân hàng để kiểm tra.",
    "label":"safe",
    "reason":"Tin chỉ thông báo biến động và hướng người dùng tự mở ứng dụng chính thức, không xin dữ liệu hay gửi liên kết."
  },
  {
    "id":"safe-police-office-appointment",
    "text":"Hồ sơ cấp căn cước của bác đã có lịch trả vào thứ Sáu; vui lòng mang giấy hẹn đến đúng trụ sở đã đăng ký.",
    "label":"safe",
    "reason":"Nội dung cung cấp lịch hẹn tại trụ sở, không đe dọa, không xin tiền và không yêu cầu làm việc bí mật."
  },
  {
    "id":"safe-store-drawing-result",
    "text":"Kết quả quay số đã đăng công khai tại cửa hàng. Khách giữ hóa đơn có thể tới quầy dịch vụ đối chiếu, không cần đóng phí.",
    "label":"safe",
    "reason":"Thông tin có điểm đối chiếu trực tiếp và nói rõ không thu phí hay yêu cầu cung cấp thông tin nhạy cảm."
  },
  {
    "id":"safe-delivery-schedule",
    "text":"Bưu tá dự kiến giao đơn vào sáng thứ Hai. Bác có thể xem trạng thái bằng mã đơn trong ứng dụng nơi đã mua hàng.",
    "label":"safe",
    "reason":"Tin chỉ báo lịch giao và hướng kiểm tra trong ứng dụng mua hàng, không kèm liên kết hay phí phát sinh."
  },
  {
    "id":"safe-family-pickup",
    "text":"Chiều nay con đón bác ở cổng bệnh viện lúc 16 giờ như đã hẹn, xe vẫn mang biển số quen thuộc.",
    "label":"safe",
    "reason":"Đây là lịch đón cụ thể phù hợp ngữ cảnh, không có yêu cầu tiền, dữ liệu hoặc hành động khẩn cấp bất thường."
  }
];
const scamGroupDetails={
  fake_bank:{
    label:'Giả ngân hàng',
    iconPath:'M4 10h16v9H4v-9Zm2 2v5h2v-5H6Zm5 0v5h2v-5h-2Zm5 0v5h2v-5h-2ZM3 7l9-5 9 5v2H3V7Z',
    signs:['Tự xưng là nhân viên ngân hàng và tạo áp lực phải xử lý ngay.','Yêu cầu cung cấp mật khẩu, thông tin thẻ hoặc mã OTP.','Gửi đường dẫn có tên miền gần giống nhưng không phải website chính thức.','Đề nghị cài ứng dụng hoặc chia sẻ màn hình để “hỗ trợ” tài khoản.']
  },
  fake_police:{
    label:'Giả công an',
    iconPath:'M12 2 4 5v6c0 5 3.4 9.7 8 11 4.6-1.3 8-6 8-11V5l-8-3Zm0 4 4 1.5V11c0 3.2-1.8 6.2-4 7.3-2.2-1.1-4-4.1-4-7.3V7.5L12 6Z',
    signs:['Thông báo bác liên quan vụ án, lệnh bắt hoặc khoản tiền bất hợp pháp.','Yêu cầu giữ bí mật, không nói với người thân hay cơ quan địa phương.','Đòi chuyển tiền vào tài khoản để kiểm tra hoặc chứng minh trong sạch.','Gửi giấy tờ qua mạng và ép cài ứng dụng lạ để làm việc từ xa.']
  },
  prize:{
    label:'Trúng thưởng',
    iconPath:'M20 6h-2.2A3 3 0 0 0 12 4.9 3 3 0 0 0 6.2 6H4a2 2 0 0 0-2 2v3h9V8h2v3h9V8a2 2 0 0 0-2-2Zm-5-2a1 1 0 0 1 0 2h-2c0-1.1.9-2 2-2ZM9 4c1.1 0 2 .9 2 2H9a1 1 0 0 1 0-2ZM3 13h8v9H5a2 2 0 0 1-2-2v-7Zm10 0h8v7a2 2 0 0 1-2 2h-6v-9Z',
    signs:['Thông báo nhận giải dù bác không tham gia chương trình nào.','Yêu cầu đóng thuế, phí hồ sơ, phí vận chuyển hoặc phí kích hoạt trước.','Mạo danh thương hiệu lớn nhưng liên hệ bằng tài khoản cá nhân.','Gửi biểu mẫu hoặc đường link đòi giấy tờ, thông tin thẻ hay mã xác thực.']
  },
  fake_delivery:{
    label:'Giả giao hàng',
    iconPath:'M3 5h12v4h3l3 4v6h-2.2a3 3 0 0 1-5.6 0H9.8a3 3 0 0 1-5.6 0H3V5Zm2 2v8.2A3 3 0 0 1 9.8 17h3.4c.4-.8 1-1.4 1.8-1.7V7H5Zm12 4v4.2c.8.3 1.4.9 1.8 1.8H19v-3.3L17 11ZM7 17a1 1 0 1 0 0 2 1 1 0 0 0 0-2Zm9 0a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z',
    signs:['Thông báo một đơn hàng bác không đặt hoặc thông tin giao hàng mơ hồ.','Yêu cầu chuyển khoản trước một khoản phí nhỏ để giao lại hoặc hủy đơn.','Gửi đường dẫn thanh toán không thuộc ứng dụng hay website đã mua hàng.','Xin mã OTP, thông tin ngân hàng hoặc yêu cầu quét mã QR để nhận hàng.']
  }
};
const librarySafeActions=['Bình tĩnh, dừng lại và kiểm tra yêu cầu qua kênh chính thức.','Tự tìm số điện thoại của ngân hàng, cơ quan hoặc đơn vị vận chuyển để xác minh.','Kiểm tra kỹ tên người gửi, tên miền và thông tin chương trình.','Báo cho người thân hoặc cơ quan chức năng khi thấy dấu hiệu đe dọa.'];
const libraryUnsafeActions=['Không cung cấp mật khẩu, mã OTP hoặc thông tin thẻ.','Không chuyển tiền theo yêu cầu của người lạ.','Không cài ứng dụng từ đường link hoặc tệp không rõ nguồn gốc.','Không bấm vào đường link đáng ngờ trong tin nhắn.'];
const normalizedValue=()=>messageInput.value.replace(/\s+/g,' ').trim();
const viewTitles={analyze:'Kiểm tra',library:'Thư viện lừa đảo',history:'Lịch sử',practice:'Luyện tập'};

function syncQuickInputLayout(){
  if(mobileLayoutQuery.matches){
    mobileQuickCards.forEach(card=>checkButton.after(card));
    return;
  }
  mobileQuickCards.forEach(card=>toolsColumn.append(card));
}

syncQuickInputLayout();
mobileLayoutQuery.addEventListener('change',syncQuickInputLayout);

function viewFromHash(){
  return routeFromHash().view;
}

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
    '.detective-message-row,.psychology-message-row'
  )].filter(message=>message.offsetParent!==null);
  latestResultMessage=latestResultMessage||visibleMessages.at(-1)||null;
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

function showComposerFrame(){
  if(psychologySequenceTimer!==null){
    window.clearTimeout(psychologySequenceTimer);
    psychologySequenceTimer=null;
  }
  processingFrame.hidden=true;
  psychologyBlock.classList.remove('message-sequence-playing');
  resultFrame.classList.remove('active');
  latestResultMessage=null;
  autoFollowResult=true;
  resultScrollButton.hidden=true;
  inputFrame.style.display='block';
  updateInputState();
}

function showProcessingFrame(){
  if(psychologySequenceTimer!==null){
    window.clearTimeout(psychologySequenceTimer);
    psychologySequenceTimer=null;
  }
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
function updateInputState(){const rawLength=messageInput.value.length,clean=normalizedValue();characterCount.textContent=`${rawLength} / ${MAX_LENGTH}`;clearButton.disabled=rawLength===0;checkButton.disabled=isAnalyzing||(!isOffline&&sessionAtLimit)||clean.length<MIN_LENGTH;if(rawLength===0){hideFeedback();messageInput.removeAttribute('aria-invalid')}else if(clean.length===0){showFeedback('Nội dung không thể chỉ gồm khoảng trắng.');messageInput.setAttribute('aria-invalid','true')}else if(clean.length<MIN_LENGTH){showFeedback(`Nội dung còn quá ngắn. Vui lòng nhập ít nhất ${MIN_LENGTH} ký tự.`);messageInput.setAttribute('aria-invalid','true')}else{hideFeedback();messageInput.removeAttribute('aria-invalid')}}
function setupSpeechRecognition(){const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SpeechRecognition){voiceButton.disabled=true;voiceStatus.textContent='Trình duyệt này chưa hỗ trợ nhập bằng giọng nói. Bạn vẫn có thể nhập hoặc dán nội dung.';return}recognition=new SpeechRecognition();recognition.lang='vi-VN';recognition.interimResults=true;recognition.continuous=true;let finalTranscript='';recognition.onstart=()=>{isRecording=true;finalTranscript='';voiceButton.classList.add('recording');voiceButton.setAttribute('aria-pressed','true');voiceButton.title='Tắt micro';voiceButtonLabel.textContent='Tắt micro';voiceStatus.textContent='Đang ghi âm… Hãy đọc rõ nội dung tin nhắn.'};recognition.onresult=(event)=>{let interimTranscript='';for(let i=event.resultIndex;i<event.results.length;i++){const transcript=event.results[i][0].transcript;if(event.results[i].isFinal)finalTranscript+=transcript+' ';else interimTranscript+=transcript}const combined=`${finalTranscript}${interimTranscript}`.trim();if(combined){const base=messageInput.dataset.beforeVoice||'';messageInput.value=base?`${base} ${combined}`:combined;messageInput.dispatchEvent(new Event('input'))}};recognition.onerror=(event)=>{isRecording=false;voiceButton.classList.remove('recording');voiceButton.setAttribute('aria-pressed','false');voiceButton.title='Bật micro';voiceButtonLabel.textContent='Bật micro';if(event.error==='not-allowed'||event.error==='service-not-allowed')voiceStatus.textContent='Không thể dùng micro vì quyền truy cập đã bị từ chối. Bạn vẫn có thể nhập nội dung bằng bàn phím.';else if(event.error==='no-speech')voiceStatus.textContent='Chưa nhận được giọng nói. Vui lòng thử lại và nói gần micro hơn.';else voiceStatus.textContent='Tính năng giọng nói tạm thời chưa hoạt động. Vui lòng nhập nội dung thủ công.'};recognition.onend=()=>{isRecording=false;voiceButton.classList.remove('recording');voiceButton.setAttribute('aria-pressed','false');voiceButton.title='Bật micro';voiceButtonLabel.textContent='Bật micro';if(!voiceStatus.textContent.includes('từ chối')&&!voiceStatus.textContent.includes('tạm thời')&&!voiceStatus.textContent.includes('Chưa nhận'))voiceStatus.textContent='Đã dừng ghi âm.';delete messageInput.dataset.beforeVoice}}
function getHistory(){
  return historyCache;
}

function backendHistoryToItem(entry){
  return {
    id:String(entry?.id||''),
    message:String(entry?.message||''),
    date:String(entry?.created_at||''),
    result:entry?.response||null,
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
  const response=await fetch(path,{credentials:'same-origin',...options});
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
  return payload;
}

async function loadUsage(){
  if(isOffline){
    usage.textContent='Đang ngoại tuyến. Phân tích sơ bộ trên thiết bị không dùng lượt AI.';
    return;
  }
  try{
    const payload=await requestJson('/session/ai-calls');
    applyUsage(payload?.usage);
  }catch(error){
    usage.textContent='Chưa thể tải số lượt AI đã dùng.';
  }
  updateInputState();
}

function applyUsage(aiUsage){
  const used=Number(aiUsage?.used||0);
  const limit=Number(aiUsage?.limit||0);
  sessionAtLimit=limit>0&&used>=limit;
  usage.textContent=`Đã dùng ${used}/${limit} lượt AI trong phiên này.`;
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
  void loadUsage();
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

const riskPresentations={
  safe:{
    className:'safe',
    label:'An toàn',
    description:'Chưa phát hiện dấu hiệu lừa đảo rõ ràng, nhưng bác vẫn nên xác minh người gửi khi còn nghi ngờ.'
  },
  suspicious:{
    className:'suspicious',
    label:'Nghi ngờ',
    description:'Tin nhắn có một số dấu hiệu cần kiểm tra thêm trước khi làm theo.'
  },
  dangerous:{
    className:'danger',
    label:'Nguy hiểm',
    description:'Tin nhắn có nhiều dấu hiệu lừa đảo rõ ràng. Không nên làm theo hướng dẫn trong tin nhắn.'
  }
};

function appendHighlightedText(container,text,quotes){
  container.replaceChildren();
  const ranges=[];

  quotes.filter(Boolean).forEach(quote=>{
    let from=0;
    const lowerText=text.toLowerCase();
    const lowerQuote=quote.toLowerCase();

    while(true){
      const index=lowerText.indexOf(lowerQuote,from);
      if(index<0)break;
      ranges.push([index,index+quote.length]);
      from=index+quote.length;
    }
  });

  ranges.sort((a,b)=>a[0]-b[0]);
  const merged=[];
  ranges.forEach(range=>{
    const last=merged[merged.length-1];
    if(last&&range[0]<=last[1])last[1]=Math.max(last[1],range[1]);
    else merged.push([...range]);
  });

  let cursor=0;
  merged.forEach(([start,end])=>{
    if(start>cursor)container.appendChild(document.createTextNode(text.slice(cursor,start)));
    const mark=document.createElement('mark');
    mark.textContent=text.slice(start,end);
    container.appendChild(mark);
    cursor=end;
  });

  if(cursor<text.length)container.appendChild(document.createTextNode(text.slice(cursor)));
  if(merged.length===0)container.textContent=text;
}

function appendSignalCard(titleText,explanationText,quoteText=null,badgeText=null){
  const messageOrder=signalList.childElementCount;
  const row=document.createElement('div');
  row.className=`detective-message-row ${messageOrder===0?'summary-message':'evidence-message'}`;
  row.style.setProperty(
    '--message-delay',
    `${DETECTIVE_MESSAGE_START_MS+messageOrder*DETECTIVE_MESSAGE_GAP_MS}ms`
  );
  const avatar=document.createElement('img');
  avatar.className='detective-message-avatar';
  avatar.src='/detective-avatar.png';
  avatar.alt='';
  avatar.width=42;
  avatar.height=42;
  avatar.setAttribute('aria-hidden','true');
  const card=document.createElement('article');
  card.className='signal-card detective-message-bubble';
  const title=document.createElement('h3');
  title.textContent=titleText;
  const explanation=document.createElement('p');
  explanation.textContent=explanationText;
  card.append(title,explanation);

  if(badgeText){
    const badge=document.createElement('span');
    badge.className='severity';
    badge.textContent=badgeText;
    card.appendChild(badge);
  }

  if(quoteText){
    const quote=document.createElement('p');
    quote.className='quote';
    quote.textContent=`Đoạn liên quan: “${quoteText}”`;
    card.appendChild(quote);
  }
  row.append(avatar,card);
  signalList.appendChild(row);
  return card;
}

function appendOriginalMessageCard(text,excerpts,shouldHighlight){
  const messageOrder=signalList.childElementCount;
  const row=document.createElement('div');
  row.className='detective-message-row original-message-row';
  row.style.setProperty(
    '--message-delay',
    `${DETECTIVE_MESSAGE_START_MS+messageOrder*DETECTIVE_MESSAGE_GAP_MS}ms`
  );
  const avatar=document.createElement('img');
  avatar.className='detective-message-avatar';
  avatar.src='/detective-avatar.png';
  avatar.alt='';
  avatar.width=42;
  avatar.height=42;
  avatar.setAttribute('aria-hidden','true');
  const card=document.createElement('article');
  card.className='signal-card detective-message-bubble original-message-card';
  const title=document.createElement('h3');
  title.textContent=shouldHighlight&&excerpts.length
    ?'Tin nhắn có đoạn cần chú ý'
    :'Tin nhắn gốc';
  const message=document.createElement('div');
  message.className=`original-message ${shouldHighlight&&excerpts.length?'highlighted':''}`.trim();
  appendHighlightedText(message,text,excerpts);
  const note=document.createElement('p');
  note.className='highlight-note';
  note.textContent='Vùng tô vàng là nội dung cần đặc biệt chú ý.';
  note.hidden=!shouldHighlight||excerpts.length===0;
  card.append(title,message,note);
  row.append(avatar,card);
  signalList.appendChild(row);
  return card;
}

function revealPsychologyMessages(){
  if(psychologyMessage.childElementCount===0)return;
  actionSection.hidden=false;
  psychologyBlock.hidden=false;
  void psychologyMessage.offsetWidth;
  psychologyBlock.classList.add('message-sequence-playing');
}

function playMessageSequence(){
  if(psychologySequenceTimer!==null){
    window.clearTimeout(psychologySequenceTimer);
    psychologySequenceTimer=null;
  }
  resultFrame.classList.remove('message-sequence-playing');
  psychologyBlock.classList.remove('message-sequence-playing');
  if(window.matchMedia('(prefers-reduced-motion: reduce)').matches){
    revealPsychologyMessages();
    const visibleMessages=[...resultFrame.querySelectorAll(
      '.detective-message-row,.psychology-message-row'
    )].filter(message=>message.offsetParent!==null);
    revealResultMessage(visibleMessages.at(-1)||null);
    return;
  }
  void signalList.offsetWidth;
  resultFrame.classList.add('message-sequence-playing');
  if(psychologyMessage.childElementCount===0)return;
  const detectiveMessageCount=Math.max(1,signalList.childElementCount);
  const detectiveSequenceMs=DETECTIVE_MESSAGE_START_MS+
    (detectiveMessageCount-1)*DETECTIVE_MESSAGE_GAP_MS+
    MESSAGE_ANIMATION_MS;
  psychologySequenceTimer=window.setTimeout(()=>{
    psychologySequenceTimer=null;
    revealPsychologyMessages();
  },detectiveSequenceMs);
}

const deterministicRuleLabels={
  url_lookalike:'Tên miền có dấu hiệu giả mạo',shortened_url:'Liên kết rút gọn',
  cyrillic_hostname:'Tên miền dùng ký tự Cyrillic',cyrillic_text:'Nội dung dùng ký tự Cyrillic',
  verification_code_request:'Yêu cầu mã xác thực',transfer_request:'Yêu cầu chuyển tiền',
  account_number:'Số tài khoản xuất hiện',urgent_language:'Ngôn ngữ thúc giục'
};

function renderDeterministicFindings(findings){
  findings.forEach(finding=>appendSignalCard(
    deterministicRuleLabels[finding.kind]||finding.kind,
    'Dấu hiệu này được tìm thấy trong nội dung đã gửi.',
    finding.excerpt
  ));
}

function renderSignals(detective,deterministicFindings=[],originalText=''){
  signalList.replaceChildren();
  appendSignalCard(
    detective.analysis_mode==='offline'?'Nhận định ngoại tuyến':'Nhận định của Thám tử',
    detective.reasoning,
    null,
    detective.analysis_mode==='offline'
      ?`Ước lượng rủi ro sơ bộ: ${Math.round(detective.confidence*100)}%`
      :`Khả năng lừa đảo: ${Math.round(detective.confidence*100)}%`
  );

  const shouldHighlight=detective.risk_level==='suspicious'||detective.risk_level==='dangerous';
  const excerpts=shouldHighlight
    ?(detective.indicator_evidence||[]).map(item=>item.excerpt)
    :[];
  appendOriginalMessageCard(originalText,excerpts,shouldHighlight);

  const evidence=Array.isArray(detective.indicator_evidence)
    ?detective.indicator_evidence
    :[];
  if(evidence.length){
    evidence.forEach(item=>{
      appendSignalCard(
        item.label,
        'Dấu hiệu này được tìm thấy trong nội dung đã gửi.',
        item.excerpt
      );
    });
  }else{
    const indicators=Array.isArray(detective.indicators)?detective.indicators:[];
    if(indicators.length){
      indicators.forEach(indicator=>{
        appendSignalCard(indicator,'Dấu hiệu này được Thám tử phát hiện trong nội dung.');
      });
    }else{
      appendSignalCard(
        'Chưa phát hiện dấu hiệu nổi bật',
        'Thám tử chưa tìm thấy dấu hiệu cụ thể trong nội dung này.'
      );
    }
  }
  renderDeterministicFindings(deterministicFindings);
  renderRecommendations(detective.actions||[]);
}

function renderRecommendations(actions){
  const defaults=[
    'Không bấm vào đường dẫn trong tin nhắn.',
    'Không cung cấp mật khẩu hoặc mã OTP.',
    'Liên hệ tổ chức qua số điện thoại hoặc ứng dụng chính thức.'
  ];
  const card=appendSignalCard(
    'Ba hành động nên làm ngay',
    'Bác hãy ưu tiên ba bước an toàn này trước khi phản hồi.'
  );
  const list=document.createElement('div');
  list.className='recommendations';
  defaults.forEach((fallback,index)=>{
    const item=document.createElement('div');
    item.className='recommendation';
    const number=document.createElement('span');
    number.className='recommendation-number';
    number.textContent=String(index+1);
    const text=document.createElement('span');
    text.textContent=actions[index]||fallback;
    item.append(number,text);
    list.appendChild(item);
  });
  card.appendChild(list);
}

function splitPsychologyMessage(message){
  const normalized=String(message||'').replace(/\s+/g,' ').trim();
  if(!normalized)return [];
  let parts=(normalized.match(/[^.!?…]+(?:[.!?…]+|$)/g)||[])
    .map(part=>part.trim())
    .filter(Boolean);
  if(parts.length===1){
    const clauses=normalized
      .replace(/;\s+/g,';|')
      .replace(/,\s+/g,',|')
      .split('|')
      .map(part=>part.trim())
      .filter(Boolean);
    if(clauses.length>1)parts=clauses;
  }
  if(parts.length===1){
    const words=normalized.split(' ');
    if(words.length>=6){
      const midpoint=Math.ceil(words.length/2);
      parts=[words.slice(0,midpoint).join(' '),words.slice(midpoint).join(' ')];
    }
  }
  if(parts.length===1){
    parts.push('Bác cứ chậm lại và kiểm tra từng bước an toàn nhé.');
  }
  if(parts.length>3)parts=[parts[0],parts[1],parts.slice(2).join(' ')];
  return parts.slice(0,3);
}

function appendPsychologyMessage(message,index){
  const emojis=['🫶','🌿','🛡️'];
  const row=document.createElement('div');
  row.className='psychology-message-row';
  row.style.setProperty('--message-delay',`${index*DETECTIVE_MESSAGE_GAP_MS}ms`);
  const avatar=document.createElement('img');
  avatar.className='psychology-message-avatar';
  avatar.src='/psychologist-avatar.png';
  avatar.alt='';
  avatar.width=40;
  avatar.height=40;
  avatar.setAttribute('aria-hidden','true');
  const bubble=document.createElement('article');
  bubble.className='psychology-message-bubble';
  const paragraph=document.createElement('p');
  paragraph.className='psychology-message';
  const emoji=document.createElement('span');
  emoji.className='psychology-message-emoji';
  emoji.textContent=emojis[index]||'💜';
  emoji.setAttribute('aria-hidden','true');
  const text=document.createElement('span');
  text.textContent=message;
  paragraph.append(emoji,text);
  bubble.appendChild(paragraph);
  row.append(avatar,bubble);
  psychologyMessage.appendChild(row);
}

function renderPsychology(payload){
  const riskLevel=payload?.detective?.risk_level;
  const shouldShow=riskLevel==='suspicious'||riskLevel==='dangerous';
  psychologyMessage.replaceChildren();
  actionSection.hidden=true;
  psychologyBlock.hidden=true;
  psychologyBlock.classList.remove('message-sequence-playing');
  if(!shouldShow){
    return;
  }
  let message;
  if(payload.character){
    message=payload.character.message;
  }else if(payload.character_notice){
    message=payload.character_notice;
  }else{
    message='Cô tâm lý chưa thể gửi lời nhắn bổ sung lúc này; bác xem hướng dẫn an toàn bên dưới nhé.';
  }
  splitPsychologyMessage(message).forEach(appendPsychologyMessage);
}

function showResultFrame(text,payload,{fromHistory=false}={}){
  const detective=payload.detective;
  const risk=riskPresentations[detective.risk_level]||riskPresentations.suspicious;

  resultContextLabel.textContent=fromHistory?'Kết quả đã lưu':'Phân tích hoàn tất';
  historyReturnButton.hidden=!fromHistory;

  riskCard.className=`risk-card ${risk.className}`;
  riskLabel.textContent=payload.offline&&detective.risk_level==='safe'
    ?(detective.indicators?.length?'Rủi ro thấp':'Chưa thấy dấu hiệu')
    :risk.label;
  riskDescription.textContent=payload.offline
    ?`Đánh giá sơ bộ ngoại tuyến. ${risk.description}`
    :risk.description;

  renderSignals(detective,payload.deterministic_findings,text);
  renderPsychology(payload);

  inputFrame.style.display='none';
  hideProcessingFrame();
  resultFrame.classList.add('active');
  resetResultAutoFollow();
  window.scrollTo({top:0,behavior:'smooth'});
  playMessageSequence();
}

messageInput.addEventListener('input',()=>{saveDraft();updateInputState()});
clearButton.addEventListener('click',()=>{messageInput.value='';saveDraft();messageInput.focus();updateInputState()});
sampleButtons.forEach(button=>button.addEventListener('click',()=>{messageInput.value=samples[button.dataset.sample];messageInput.focus();messageInput.dispatchEvent(new Event('input'))}));
voiceButton.addEventListener('click',()=>{if(!recognition)return;try{if(isRecording)recognition.stop();else{messageInput.dataset.beforeVoice=messageInput.value.trim();recognition.start()}}catch(error){voiceStatus.textContent='Không thể khởi động micro lúc này. Vui lòng thử lại sau.'}});
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
  updateInputState();
  showProcessingFrame();

  try{
    let payload;
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
          body:JSON.stringify({text:submittedText,source:'web'})
        });
        try{
          sessionStorage.removeItem(PENDING_ANALYSIS_KEY);
        }catch(error){
          // The response is still valid when tab storage is unavailable.
        }
        applyUsage(payload.usage);
        historyCache.unshift({
          id:payload.id,
          message:submittedText,
          date:new Date().toISOString(),
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
    showResultFrame(submittedText,payload);
  }catch(error){
    hideProcessingFrame();
    inputFrame.style.display='block';
    if(error.networkInterrupted){
      showConnectivityNotice('Kết nối mạng không ổn định. Bác hãy kiểm tra Wi-Fi hoặc dữ liệu di động rồi thử lại.');
      showFeedback(error.message,'info');
    }else{
      if(error.status===429)sessionAtLimit=true;
      if(navigator.onLine)connectivityStatus.hidden=true;
      showFeedback(Number.isInteger(error.status)?error.message:'Không thể kết nối tới máy chủ.');
    }
    void loadUsage();
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
  libraryDetailFrame.hidden=true;
  libraryListFrame.hidden=false;
  void loadScamTypes().then(()=>{
    requestAnimationFrame(()=>window.scrollTo({top:libraryScrollPosition,behavior:'auto'}));
  });
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
resultFrame.addEventListener('animationstart',event=>{
  if(event.animationName!=='detective-message-in')return;
  if(!event.target.matches('.detective-message-row,.psychology-message-row'))return;
  revealResultMessage(event.target);
});
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
restoreDraft();setupSpeechRecognition();renderPracticePrompt();registerServiceWorker();updateConnectivityState();syncRoute();
