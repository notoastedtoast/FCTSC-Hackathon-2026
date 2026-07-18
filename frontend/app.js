const scanStage = document.getElementById("scan-stage");
const scanMessage = document.getElementById("scan-message");
const scanLayer = document.getElementById("scan-layer");
const CHECK_COOLDOWN_MS=5000,MIN_LENGTH=10,MAX_LENGTH=10000;
const messageInput=document.getElementById('message'),clearButton=document.getElementById('clear-button'),checkButton=document.getElementById('check-button'),characterCount=document.getElementById('character-count'),feedback=document.getElementById('message-feedback'),usage=document.getElementById('usage'),connectivityStatus=document.getElementById('connectivity-status'),voiceButton=document.getElementById('voice-button'),voiceButtonLabel=document.getElementById('voice-button-label'),voiceStatus=document.getElementById('voice-status'),inputFrame=document.getElementById('input-frame'),processingFrame=document.getElementById('processing-frame'),resultFrame=document.getElementById('result-frame'),riskCard=document.getElementById('risk-card'),riskLabel=document.getElementById('risk-label'),riskDescription=document.getElementById('risk-description'),signalList=document.getElementById('signal-list'),originalMessage=document.getElementById('original-message'),resultBackButton=document.getElementById('result-back-button'),sampleButtons=document.querySelectorAll('.sample-button'),historyList=document.getElementById('history-list'),historySelectedCount=document.getElementById('history-selected-count'),historyDeleteButton=document.getElementById('history-delete-button'),deleteConfirmModal=document.getElementById('delete-confirm-modal'),deleteConfirmText=document.getElementById('delete-confirm-text'),deletePreview=document.getElementById('delete-preview'),deleteCancelButton=document.getElementById('delete-cancel-button'),deleteConfirmButton=document.getElementById('delete-confirm-button');
const cancelCheckButton=document.getElementById('cancel-check-button'),psychologyMessage=document.getElementById('psychology-message'),recommendations=document.getElementById('recommendations');
const practiceContent=document.getElementById('practice-content'),practiceMessage=document.getElementById('practice-message'),practiceProgress=document.getElementById('practice-progress'),practiceScore=document.getElementById('practice-score'),practiceAnswerButtons=document.querySelectorAll('.practice-answer-button'),practiceFeedback=document.getElementById('practice-feedback'),practiceNextButton=document.getElementById('practice-next-button');
const navLinks=document.querySelectorAll('.nav-link[data-view]'),pageViews=document.querySelectorAll('[data-view-panel]');
let lastCheckAt=Number(sessionStorage.getItem('scamcheck-last-check-at')||0),cooldownTimer=null,recognition=null,isRecording=false,selectedHistoryIds=new Set(),activeCheckController=null,sessionAtLimit=false,isOffline=!navigator.onLine;
let practiceIndex=0,practiceCorrect=0,practiceAnswered=0,practiceLocked=false;
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
const normalizedValue=()=>messageInput.value.replace(/\s+/g,' ').trim();
const viewTitles={analyze:'Kiểm tra',history:'Lịch sử',practice:'Luyện tập'};

function viewFromHash(){
  const candidate=window.location.hash.slice(1);
  return Object.hasOwn(viewTitles,candidate)?candidate:'analyze';
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
    renderHistory();
  }
  document.title=`${viewTitles[target]} · ScamCheck`;
  if(focus){
    const panel=document.querySelector(`[data-view-panel="${target}"]`);
    panel?.focus({preventScroll:true});
    window.scrollTo({top:0,behavior:'smooth'});
  }
}

function showFeedback(message,type='error'){feedback.textContent=message;feedback.className=`feedback ${type}`}
function hideFeedback(){feedback.textContent='';feedback.className='feedback'}
function getCooldownRemaining(){return Math.max(0,CHECK_COOLDOWN_MS-(Date.now()-lastCheckAt))}
function isCooldownActive(){return getCooldownRemaining()>0}
function updateCooldownState(){
  const remaining=getCooldownRemaining();
  if(cooldownTimer){clearTimeout(cooldownTimer);cooldownTimer=null}
  if(remaining>0){
    const seconds=Math.ceil(remaining/1000);
    checkButton.disabled=true;
    showFeedback(`Vui lòng chờ ${seconds} giây trước khi kiểm tra tin nhắn tiếp theo.`,'info');
    cooldownTimer=setTimeout(updateCooldownState,Math.min(1000,remaining));
  }else{
    updateInputState();
  }
}
function updateUsage(aiUsage){
  if(!aiUsage||!Number.isInteger(aiUsage.used)||!Number.isInteger(aiUsage.limit)){
    sessionAtLimit=false;
    usage.textContent='Chưa tải được số lượt gọi AI của phiên này.';
    updateInputState();
    return;
  }
  sessionAtLimit=aiUsage.used>=aiUsage.limit;
  usage.textContent=sessionAtLimit
    ?`Phiên này đã dùng ${aiUsage.used}/${aiUsage.limit} lượt gọi AI. Bác đã chạm giới hạn của phiên.`
    :`Phiên này đã dùng ${aiUsage.used}/${aiUsage.limit} lượt gọi AI.`;
  updateInputState();
}
function updateInputState(){const rawLength=messageInput.value.length,clean=normalizedValue();characterCount.textContent=`${rawLength} / ${MAX_LENGTH}`;clearButton.disabled=rawLength===0;checkButton.disabled=Boolean(activeCheckController)||(!isOffline&&sessionAtLimit)||!(clean.length>=MIN_LENGTH&&!isCooldownActive());if(rawLength===0){hideFeedback();messageInput.removeAttribute('aria-invalid')}else if(clean.length===0){showFeedback('Nội dung không thể chỉ gồm khoảng trắng.');messageInput.setAttribute('aria-invalid','true')}else if(clean.length<MIN_LENGTH){showFeedback(`Nội dung còn quá ngắn. Vui lòng nhập ít nhất ${MIN_LENGTH} ký tự.`);messageInput.setAttribute('aria-invalid','true')}else{if(!isCooldownActive())hideFeedback();messageInput.removeAttribute('aria-invalid')}}
function setupSpeechRecognition(){const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SpeechRecognition){voiceButton.disabled=true;voiceStatus.textContent='Trình duyệt này chưa hỗ trợ nhập bằng giọng nói. Bạn vẫn có thể nhập hoặc dán nội dung.';return}recognition=new SpeechRecognition();recognition.lang='vi-VN';recognition.interimResults=true;recognition.continuous=true;let finalTranscript='';recognition.onstart=()=>{isRecording=true;finalTranscript='';voiceButton.classList.add('recording');voiceButtonLabel.textContent='Tắt micro';voiceStatus.textContent='Đang ghi âm… Hãy đọc rõ nội dung tin nhắn.'};recognition.onresult=(event)=>{let interimTranscript='';for(let i=event.resultIndex;i<event.results.length;i++){const transcript=event.results[i][0].transcript;if(event.results[i].isFinal)finalTranscript+=transcript+' ';else interimTranscript+=transcript}const combined=`${finalTranscript}${interimTranscript}`.trim();if(combined){const base=messageInput.dataset.beforeVoice||'';messageInput.value=base?`${base} ${combined}`:combined;messageInput.dispatchEvent(new Event('input'))}};recognition.onerror=(event)=>{isRecording=false;voiceButton.classList.remove('recording');voiceButtonLabel.textContent='Bật micro';if(event.error==='not-allowed'||event.error==='service-not-allowed')voiceStatus.textContent='Không thể dùng micro vì quyền truy cập đã bị từ chối. Bạn vẫn có thể nhập nội dung bằng bàn phím.';else if(event.error==='no-speech')voiceStatus.textContent='Chưa nhận được giọng nói. Vui lòng thử lại và nói gần micro hơn.';else voiceStatus.textContent='Tính năng giọng nói tạm thời chưa hoạt động. Vui lòng nhập nội dung thủ công.'};recognition.onend=()=>{isRecording=false;voiceButton.classList.remove('recording');voiceButtonLabel.textContent='Bật micro';if(!voiceStatus.textContent.includes('từ chối')&&!voiceStatus.textContent.includes('tạm thời')&&!voiceStatus.textContent.includes('Chưa nhận'))voiceStatus.textContent='Đã dừng ghi âm.';delete messageInput.dataset.beforeVoice}}
function getHistory(){
  try{
    const data=JSON.parse(localStorage.getItem('scamcheck-history')||'[]');
    if(!Array.isArray(data))return [];
    let changed=false;
    const normalized=data.map((item,index)=>{
      if(item&&typeof item==='object'&&item.id)return item;
      changed=true;
      return {
        id:`history-${item?.date||Date.now()}-${index}-${Math.random().toString(36).slice(2,8)}`,
        message:String(item?.message||item||''),
        date:item?.date||new Date().toISOString()
      };
    });
    if(changed)localStorage.setItem('scamcheck-history',JSON.stringify(normalized.slice(0,10)));
    return normalized;
  }catch(error){
    return [];
  }
}

function saveHistory(message){
  const history=getHistory();
  history.unshift({
    id:`history-${Date.now()}-${Math.random().toString(36).slice(2,9)}`,
    message,
    date:new Date().toISOString()
  });
  localStorage.setItem('scamcheck-history',JSON.stringify(history.slice(0,10)));
  if(viewFromHash()==='history')renderHistory();
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
    const message=document.createElement('div');
    message.className='history-message-text';
    message.textContent=item.message;

    const time=document.createElement('time');
    time.className='history-time';
    const date=new Date(item.date);
    time.dateTime=item.date||'';
    time.textContent=Number.isNaN(date.getTime())?'':date.toLocaleString('vi-VN');

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

    content.append(message,time);
    row.append(checkbox,content);
    const actions=document.createElement('div');
    actions.className='history-item-actions';
    const reuseButton=document.createElement('button');
    reuseButton.className='history-reuse-button';
    reuseButton.type='button';
    reuseButton.textContent='Kiểm tra lại';
    reuseButton.addEventListener('click',()=>{
      messageInput.value=item.message;
      messageInput.dispatchEvent(new Event('input'));
      processingFrame.classList.remove('active');
      resultFrame.classList.remove('active');
      inputFrame.style.display='block';
      window.location.hash='analyze';
      switchView('analyze');
      window.setTimeout(()=>messageInput.focus(),0);
    });
    actions.appendChild(reuseButton);
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

function confirmDeleteSelectedHistory(){
  if(selectedHistoryIds.size===0){
    closeDeleteConfirmation();
    return;
  }

  const current=getHistory();
  const remaining=current.filter(item=>!selectedHistoryIds.has(item.id));
  const deletedCount=current.length-remaining.length;

  if(deletedCount<=0){
    selectedHistoryIds.clear();
    closeDeleteConfirmation();
    renderHistory();
    return;
  }

  localStorage.setItem('scamcheck-history',JSON.stringify(remaining.slice(0,10)));
  selectedHistoryIds.clear();
  deleteConfirmModal.classList.remove('open');
  deleteConfirmModal.setAttribute('aria-hidden','true');
  document.body.style.overflow='';
  renderHistory();
  historySelectedCount.textContent=`Đã xóa ${deletedCount} tin nhắn`;
  const historyNav=document.querySelector('.nav-link[data-view="history"]');
  historyNav?.focus();
}

function startScanAnimation(message){
  if(!scanStage||!scanMessage||!scanLayer){
    console.warn("Không tìm thấy vùng hiệu ứng scan.");
    return;
  }
  scanMessage.textContent=message;
  scanStage.classList.remove('scan-complete','is-scanning');
  void scanStage.offsetWidth;
  scanStage.classList.add('is-scanning');
}

function stopScanAnimation(){
  scanStage.classList.remove('is-scanning');
  scanStage.classList.add('scan-complete');
}


function apiErrorMessage(statusCode,detail){
  if(statusCode===429)return 'Phiên này đã dùng hết lượt kiểm tra AI. Bác vui lòng xem lại các kết quả đã lưu.';
  if(statusCode===502)return 'Dịch vụ phân tích đang tạm thời gián đoạn. Bác vui lòng thử lại sau.';
  if(statusCode===503)return 'Không thể lưu kết quả lúc này. Bác vui lòng thử lại sau.';
  if(statusCode===422)return 'Nội dung gửi lên chưa hợp lệ. Bác hãy kiểm tra và thử lại.';
  return typeof detail==='string'&&detail?'Không thể hoàn tất yêu cầu lúc này.':'Không thể kết nối tới máy chủ.';
}

async function requestJson(path,options={}){
  const response=await fetch(path,options);
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
  try{
    const payload=await requestJson("/session/ai-calls");
    updateUsage(payload.usage);
  }catch(error){
    if(isOffline){
      usage.textContent='Đang ngoại tuyến. Phân tích sơ bộ trên thiết bị không dùng lượt AI.';
      return;
    }
    updateUsage(null);
  }
}

function updateConnectivityState(){
  isOffline=!navigator.onLine;
  connectivityStatus.hidden=!isOffline;
  if(isOffline){
    usage.textContent='Đang ngoại tuyến. Phân tích sơ bộ trên thiết bị không dùng lượt AI.';
  }else{
    usage.textContent='Đang tải số lượt gọi AI của phiên này…';
    void loadUsage();
  }
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
  const card=document.createElement('article');
  card.className='signal-card';
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
  signalList.appendChild(card);
}

function renderSignals(detective){
  signalList.replaceChildren();
  appendSignalCard(
    detective.analysis_mode==='offline'?'Nhận định ngoại tuyến':'Nhận định của Thám tử',
    detective.reasoning,
    null,
    detective.analysis_mode==='offline'
      ?`Ước lượng rủi ro sơ bộ: ${Math.round(detective.confidence*100)}%`
      :`Khả năng lừa đảo: ${Math.round(detective.confidence*100)}%`
  );

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
    return;
  }

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

function renderRecommendations(actions){
  const actionItems=recommendations.querySelectorAll('.recommendation');
  actionItems.forEach((item,index)=>{
    const text=item.querySelector('span:last-child');
    text.textContent=actions[index]||'Dừng lại và xác minh qua một kênh chính thức.';
  });
}

function renderPsychology(payload){
  if(payload.character){
    psychologyMessage.textContent=payload.character.message;
  }else if(payload.character_notice){
    psychologyMessage.textContent=payload.character_notice;
  }else{
    psychologyMessage.textContent='Tin được đánh giá an toàn nên Cô tâm lý không cần đưa ra cảnh báo bổ sung.';
  }
}

function showResultFrame(text,payload){
  const detective=payload.detective;
  const risk=riskPresentations[detective.risk_level]||riskPresentations.suspicious;

  riskCard.className=`risk-card ${risk.className}`;
  riskLabel.textContent=payload.offline&&detective.risk_level==='safe'
    ?'Chưa thấy dấu hiệu'
    :risk.label;
  riskDescription.textContent=payload.offline
    ?`Đánh giá sơ bộ ngoại tuyến. ${risk.description}`
    :risk.description;

  renderSignals(detective);
  const excerpts=(detective.indicator_evidence||[]).map(item=>item.excerpt);
  appendHighlightedText(originalMessage,text,excerpts);
  renderRecommendations(detective.actions||[]);
  renderPsychology(payload);

  processingFrame.classList.remove('active');
  inputFrame.style.display='none';
  resultFrame.classList.add('active');
  window.scrollTo({top:0,behavior:'smooth'});
}

messageInput.addEventListener('input',updateInputState);
clearButton.addEventListener('click',()=>{messageInput.value='';messageInput.focus();updateInputState()});
sampleButtons.forEach(button=>button.addEventListener('click',()=>{messageInput.value=samples[button.dataset.sample];messageInput.focus();messageInput.dispatchEvent(new Event('input'))}));
voiceButton.addEventListener('click',()=>{if(!recognition)return;try{if(isRecording)recognition.stop();else{messageInput.dataset.beforeVoice=messageInput.value.trim();recognition.start()}}catch(error){voiceStatus.textContent='Không thể khởi động micro lúc này. Vui lòng thử lại sau.'}});
historyDeleteButton.addEventListener('click',openDeleteConfirmation);
deleteCancelButton.addEventListener('click',closeDeleteConfirmation);
deleteConfirmButton.addEventListener('click',confirmDeleteSelectedHistory);
deleteConfirmModal.addEventListener('click',event=>{if(event.target===deleteConfirmModal)closeDeleteConfirmation()});
navLinks.forEach(link=>link.addEventListener('click',event=>{
  const target=link.dataset.view;
  if(window.location.hash===`#${target}`){
    event.preventDefault();
    switchView(target,{focus:true});
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
checkButton.addEventListener('click',async()=>{
  const clean=normalizedValue();
  if(isCooldownActive()){
    updateCooldownState();
    return;
  }
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

  const submittedText=messageInput.value.trim();
  const controller=new AbortController();
  activeCheckController=controller;
  checkButton.disabled=true;
  inputFrame.style.display='none';
  resultFrame.classList.remove('active');
  startScanAnimation(submittedText);
  processingFrame.classList.add('active');

  try{
    let payload;
    if(isOffline){
      payload=ScamCheckOffline.analyze(submittedText);
    }else{
      try{
        payload=await requestJson("/analyze",{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({text:submittedText,source:'web'}),
          signal:controller.signal
        });
      }catch(error){
        if(error.name==='AbortError'||Number.isInteger(error.status))throw error;
        payload=ScamCheckOffline.analyze(submittedText);
      }
    }
    if(activeCheckController!==controller)return;
    stopScanAnimation();
    saveHistory(submittedText);
    lastCheckAt=Date.now();
    sessionStorage.setItem('scamcheck-last-check-at',String(lastCheckAt));
    if(payload.usage)updateUsage(payload.usage);
    showResultFrame(submittedText,payload);
  }catch(error){
    stopScanAnimation();
    processingFrame.classList.remove('active');
    inputFrame.style.display='block';
    if(error.name==='AbortError'){
      showFeedback('Đã dừng chờ kết quả. Nếu lượt AI đã bắt đầu, lượt đó vẫn có thể được tính.','info');
    }else{
      showFeedback(Number.isInteger(error.status)?error.message:'Không thể kết nối tới máy chủ.');
    }
    void loadUsage();
    messageInput.focus();
  }finally{
    if(activeCheckController===controller)activeCheckController=null;
    updateCooldownState();
  }
});
cancelCheckButton.addEventListener('click',()=>{
  if(activeCheckController)activeCheckController.abort();
});
resultBackButton.addEventListener('click',()=>{
  resultFrame.classList.remove('active');
  inputFrame.style.display='block';
  updateInputState();
  window.scrollTo({top:0,behavior:'smooth'});
  messageInput.focus();
});
window.addEventListener('online',updateConnectivityState);
window.addEventListener('offline',updateConnectivityState);
window.addEventListener('hashchange',()=>switchView(viewFromHash(),{focus:true}));
if(!window.location.hash)window.history.replaceState(null,'','#analyze');
setupSpeechRecognition();renderPracticePrompt();registerServiceWorker();updateConnectivityState();switchView(viewFromHash());if(isCooldownActive())updateCooldownState();
