/* ScamCheck browser rendering helpers.
   This file only handles presentation and result rendering. */
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
  card.appendChild(title);

  if(explanationText){
    const explanation=document.createElement('p');
    explanation.textContent=explanationText;
    card.appendChild(explanation);
  }

  if(badgeText){
    const badge=document.createElement('span');
    badge.className='severity';
    badge.textContent=badgeText;
    card.appendChild(badge);
  }

  if(quoteText){
    const quote=document.createElement('p');
    quote.className='quote';
    quote.textContent=`Dấu hiệu: “${quoteText}”`;
    card.appendChild(quote);
  }
  row.append(avatar,card);
  signalList.appendChild(row);
  return card;
}

function appendOriginalMessageCard(text,excerpts,shouldHighlight){
  const row=document.createElement('div');
  row.className='detective-message-row original-message-row';
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

function revealPostAnalysisQuestion(){
  if(postAnalysisQuestion.dataset.eligible!=='true')return;
  postAnalysisQuestion.hidden=false;
  revealResultMessage(postAnalysisQuestion);
}

function revealPsychologyMessages(){
  if(psychologyMessage.childElementCount===0)return;
  actionSection.hidden=false;
  psychologyBlock.hidden=false;
  revealRowsSequentially(
    psychologyMessage.querySelectorAll('.psychology-message-row'),
    {onComplete:revealPostAnalysisQuestion}
  );
}

function playMessageSequence(){
  clearMessageRevealTimers();
  revealRowsSequentially(
    signalList.querySelectorAll('.detective-message-row'),
    {onComplete:revealPsychologyMessages}
  );
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
    null,
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
        null,
        item.excerpt
      );
    });
  }else{
    const indicators=Array.isArray(detective.indicators)?detective.indicators:[];
    if(indicators.length){
      indicators.forEach(indicator=>{
        appendSignalCard(indicator,null);
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
  card.classList.add('recommendations-card');
  card.closest('.detective-message-row')?.classList.add('recommendations-message');
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

function psychologyEmojiFor(message){
  return psychologyEmojiRules.find(rule=>rule.pattern.test(message))?.emoji||'💜';
}

function appendPsychologyMessage(message){
  const row=document.createElement('div');
  row.className='psychology-message-row';
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
  emoji.textContent=psychologyEmojiFor(message);
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
  postAnalysisQuestion.hidden=true;
  postAnalysisQuestion.dataset.eligible=String(shouldShow);
  postAnalysisQuestion.dataset.riskLevel=riskLevel||'suspicious';
  responderBlock.hidden=true;
  responderSteps.replaceChildren();
  postAnalysisOptions.forEach(option=>{
    option.disabled=false;
    option.classList.remove('selected');
    option.setAttribute('aria-pressed','false');
  });
  actionSection.hidden=true;
  psychologyBlock.hidden=true;
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

function renderResponderGuidance(choice,riskLevel){
  const normalizedRisk=riskLevel==='dangerous'?'dangerous':'suspicious';
  const steps=rescuePlans[choice]?.[normalizedRisk]||rescuePlans.none[normalizedRisk];
  const items=steps.map(step=>{
    const row=document.createElement('li');
    row.className='responder-message-row';
    const avatar=document.createElement('img');
    avatar.className='responder-message-avatar';
    avatar.src='/responder-avatar.png';
    avatar.alt='';
    avatar.width=40;
    avatar.height=40;
    avatar.setAttribute('aria-hidden','true');
    const bubble=document.createElement('article');
    bubble.className='responder-message-bubble';
    const text=document.createElement('span');
    text.textContent=step;
    bubble.appendChild(text);
    row.append(avatar,bubble);
    return row;
  });
  responderSteps.replaceChildren(...items);
  responderBlock.hidden=false;
  revealRowsSequentially(items);
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
