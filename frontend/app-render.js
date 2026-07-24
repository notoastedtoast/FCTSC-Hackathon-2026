/* ScamCheck browser rendering helpers.
   This file only handles presentation and result rendering. */
// --- Risk labels and descriptions shown in the result header ---------------------
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

// --- QR code generator used by the share-image feature ---------------------------
function qrAppendBits(value,length,bits){
  for(let shift=length-1;shift>=0;shift--)bits.push((value>>>shift)&1);
}

function qrMultiply(left,right){
  let result=0;
  for(let bit=7;bit>=0;bit--){
    result=(result<<1)^(((result>>>7)&1)*0x11d);
    result^=((right>>>bit)&1)*left;
  }
  return result;
}

function qrReedSolomonDivisor(degree){
  const result=new Array(degree).fill(0);
  result[degree-1]=1;
  let root=1;
  for(let index=0;index<degree;index++){
    for(let position=0;position<result.length;position++){
      result[position]=qrMultiply(result[position],root);
      if(position+1<result.length)result[position]^=result[position+1];
    }
    root=qrMultiply(root,2);
  }
  return result;
}

function qrReedSolomonRemainder(data,divisor){
  const result=new Array(divisor.length).fill(0);
  data.forEach(byte=>{
    const factor=byte^result.shift();
    result.push(0);
    divisor.forEach((coefficient,index)=>{
      result[index]^=qrMultiply(coefficient,factor);
    });
  });
  return result;
}

function createQrMatrix(value=SHARE_PRODUCT_URL){
  // Version 5-L accommodates a public result URL with its 36-character UUID.
  const version=5,size=version*4+17,dataCodewords=108,errorCodewords=26;
  if(value.length>106)throw new Error('QR value is too long');
  const bits=[];
  qrAppendBits(0x4,4,bits);
  qrAppendBits(value.length,8,bits);
  Array.from(value).forEach(character=>qrAppendBits(character.charCodeAt(0),8,bits));
  const capacity=dataCodewords*8;
  qrAppendBits(0,Math.min(4,capacity-bits.length),bits);
  while(bits.length%8!==0)bits.push(0);
  const data=[];
  for(let index=0;index<bits.length;index+=8){
    let byte=0;
    for(let offset=0;offset<8;offset++)byte=(byte<<1)|bits[index+offset];
    data.push(byte);
  }
  for(let padIndex=0;data.length<dataCodewords;padIndex++){
    data.push(padIndex%2===0?0xec:0x11);
  }
  const codewords=data.concat(
    qrReedSolomonRemainder(data,qrReedSolomonDivisor(errorCodewords))
  );
  const modules=Array.from({length:size},()=>new Array(size).fill(false));
  const functions=Array.from({length:size},()=>new Array(size).fill(false));
  const setFunction=(x,y,dark)=>{
    if(x<0||y<0||x>=size||y>=size)return;
    modules[y][x]=dark;
    functions[y][x]=true;
  };
  for(let index=0;index<size;index++){
    setFunction(6,index,index%2===0);
    setFunction(index,6,index%2===0);
  }
  [[3,3],[size-4,3],[3,size-4]].forEach(([centerX,centerY])=>{
    for(let deltaY=-4;deltaY<=4;deltaY++){
      for(let deltaX=-4;deltaX<=4;deltaX++){
        const distance=Math.max(Math.abs(deltaX),Math.abs(deltaY));
        setFunction(centerX+deltaX,centerY+deltaY,distance!==2&&distance!==4);
      }
    }
  });
  for(let deltaY=-2;deltaY<=2;deltaY++)for(let deltaX=-2;deltaX<=2;deltaX++){
    const distance=Math.max(Math.abs(deltaX),Math.abs(deltaY));
    setFunction(30+deltaX,30+deltaY,distance!==1);
  }
  const formatData=(1<<3)|0;
  let formatRemainder=formatData;
  for(let index=0;index<10;index++){
    formatRemainder=(formatRemainder<<1)^(((formatRemainder>>>9)&1)*0x537);
  }
  const formatBits=((formatData<<10)|formatRemainder)^0x5412;
  const formatBit=index=>((formatBits>>>index)&1)!==0;
  for(let index=0;index<=5;index++)setFunction(8,index,formatBit(index));
  setFunction(8,7,formatBit(6));
  setFunction(8,8,formatBit(7));
  setFunction(7,8,formatBit(8));
  for(let index=9;index<15;index++)setFunction(14-index,8,formatBit(index));
  for(let index=0;index<8;index++)setFunction(size-1-index,8,formatBit(index));
  for(let index=8;index<15;index++)setFunction(8,size-15+index,formatBit(index));
  setFunction(8,size-8,true);

  let dataBitIndex=0;
  for(let right=size-1;right>=1;right-=2){
    if(right===6)right=5;
    for(let vertical=0;vertical<size;vertical++){
      for(let column=0;column<2;column++){
        const x=right-column;
        const upward=((right+1)&2)===0;
        const y=upward?size-1-vertical:vertical;
        if(functions[y][x])continue;
        let dark=false;
        if(dataBitIndex<codewords.length*8){
          dark=((codewords[dataBitIndex>>>3]>>>(7-(dataBitIndex&7)))&1)!==0;
          dataBitIndex++;
        }
        modules[y][x]=dark!==((x+y)%2===0);
      }
    }
  }
  return modules;
}

// --- Canvas drawing helpers -----------------------------------------------------
function drawRoundedRectangle(context,x,y,width,height,radius,fill,stroke=null,lineWidth=1){
  const safeRadius=Math.min(radius,width/2,height/2);
  context.beginPath();
  context.moveTo(x+safeRadius,y);
  context.lineTo(x+width-safeRadius,y);
  context.quadraticCurveTo(x+width,y,x+width,y+safeRadius);
  context.lineTo(x+width,y+height-safeRadius);
  context.quadraticCurveTo(x+width,y+height,x+width-safeRadius,y+height);
  context.lineTo(x+safeRadius,y+height);
  context.quadraticCurveTo(x,y+height,x,y+height-safeRadius);
  context.lineTo(x,y+safeRadius);
  context.quadraticCurveTo(x,y,x+safeRadius,y);
  context.closePath();
  context.fillStyle=fill;
  context.fill();
  if(stroke){
    context.strokeStyle=stroke;
    context.lineWidth=lineWidth;
    context.stroke();
  }
}

const SHARE_CANVAS_FONT='system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

function normalizeShareText(value){
  return String(value||'').normalize('NFC').replace(/\r\n?/g,'\n').trim();
}

function setShareCanvasFont(context,weight,size){
  context.font=`${weight} ${size}px ${SHARE_CANVAS_FONT}`;
}

function fitCanvasLines(context,value,maxWidth,maxLines){
  const words=normalizeShareText(value).replace(/\s+/g,' ').split(' ').filter(Boolean);
  if(words.length===0)return [];
  const allLines=[];
  let line='';
  words.forEach(word=>{
    const candidate=line?`${line} ${word}`:word;
    if(context.measureText(candidate).width<=maxWidth){
      line=candidate;
      return;
    }
    if(line){
      allLines.push(line);
      line='';
    }
    if(context.measureText(word).width<=maxWidth){
      line=word;
      return;
    }
    let chunk='';
    Array.from(word).forEach(character=>{
      const next=`${chunk}${character}`;
      if(chunk&&context.measureText(next).width>maxWidth){
        allLines.push(chunk);
        chunk=character;
      }else{
        chunk=next;
      }
    });
    line=chunk;
  });
  if(line)allLines.push(line);
  if(allLines.length<=maxLines)return allLines;
  const lines=allLines.slice(0,maxLines);
  let last=lines[maxLines-1];
  while(last.length>1&&context.measureText(`${last}…`).width>maxWidth){
    last=last.slice(0,-1);
  }
  lines[maxLines-1]=`${last.trimEnd()}…`;
  return lines;
}

function drawPreparedCanvasLines(context,lines,x,y,lineHeight){
  lines.forEach((line,index)=>context.fillText(line,x,y+index*lineHeight));
}

// --- Share-image asset loading and summary shaping -------------------------------
function drawCanvasLines(context,value,x,y,maxWidth,lineHeight,maxLines){
  const lines=fitCanvasLines(context,value,maxWidth,maxLines);
  drawPreparedCanvasLines(context,lines,x,y,lineHeight);
  return lines.length;
}

const shareImagePromises=new Map();
function loadShareImage(source){
  if(shareImagePromises.has(source))return shareImagePromises.get(source);
  const promise=new Promise(resolve=>{
    const image=new Image();
    image.onload=()=>resolve(image);
    image.onerror=()=>resolve(null);
    image.src=source;
  });
  shareImagePromises.set(source,promise);
  return promise;
}

function loadShareLogo(){
  return loadShareImage('/scamcheck-logo.png');
}

function loadShareDetectiveAvatar(){
  return loadShareImage('/detective-avatar.png');
}

async function waitForShareCanvasFonts(){
  try{
    if(document.fonts?.ready)await document.fonts.ready;
  }catch(error){
    // System-font fallbacks below still preserve Vietnamese glyphs.
  }
}

function drawShareAvatar(context,image,x,y,size){
  context.save();
  context.fillStyle='#eaf4ff';
  context.beginPath();
  context.arc(x+size/2,y+size/2,size/2,0,Math.PI*2);
  context.fill();
  if(image){
    context.beginPath();
    context.arc(x+size/2,y+size/2,size/2-3,0,Math.PI*2);
    context.clip();
    context.drawImage(image,x+4,y+4,size-8,size-8);
  }
  context.restore();
  context.strokeStyle='#9fc7ea';
  context.lineWidth=3;
  context.beginPath();
  context.arc(x+size/2,y+size/2,size/2-1.5,0,Math.PI*2);
  context.stroke();
}

function drawQr(context,x,y,pixelSize,value){
  const matrix=createQrMatrix(value);
  const quietZone=4;
  const moduleSize=Math.floor(pixelSize/(matrix.length+quietZone*2));
  const qrSize=moduleSize*(matrix.length+quietZone*2);
  const offsetX=x+Math.floor((pixelSize-qrSize)/2);
  const offsetY=y+Math.floor((pixelSize-qrSize)/2);
  context.fillStyle='#ffffff';
  context.fillRect(offsetX,offsetY,qrSize,qrSize);
  context.fillStyle='#071b2e';
  matrix.forEach((row,rowIndex)=>{
    row.forEach((dark,columnIndex)=>{
      if(dark){
        context.fillRect(
          offsetX+(columnIndex+quietZone)*moduleSize,
          offsetY+(rowIndex+quietZone)*moduleSize,
          moduleSize,
          moduleSize
        );
      }
    });
  });
}

function resultShareUrl(id){
  return /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(String(id||''))
    ?new URL(`#result/${id}`,SHARE_PRODUCT_URL).href
    :SHARE_PRODUCT_URL;
}

function resultShareSummary(originalText,payload){
  const detective=payload?.detective||{};
  const riskLevel=detective.risk_level||'suspicious';
  const risk=riskPresentations[riskLevel]||riskPresentations.suspicious;
  const signs=[];
  (Array.isArray(detective.indicator_evidence)?detective.indicator_evidence:[]).forEach(item=>{
    const label=typeof item==='string'?item:item?.label;
    const excerpt=typeof item==='string'?'':item?.excerpt;
    if(label)signs.push({label:normalizeShareText(label),excerpt:normalizeShareText(excerpt)});
  });
  (Array.isArray(payload?.deterministic_findings)?payload.deterministic_findings:[]).forEach(item=>{
    const label=deterministicRuleLabels[item?.kind]||item?.kind;
    if(label)signs.push({label:normalizeShareText(label),excerpt:normalizeShareText(item?.excerpt)});
  });
  if(signs.length===0){
    (Array.isArray(detective.indicators)?detective.indicators:[]).forEach(item=>{
      const label=typeof item==='string'?item:item?.label||item?.description;
      if(label)signs.push({label:normalizeShareText(label),excerpt:''});
    });
  }
  const uniqueSigns=signs
    .filter(item=>item.label)
    .filter((item,index,all)=>all.findIndex(candidate=>
      candidate.label===item.label&&candidate.excerpt===item.excerpt
    )===index)
    .slice(0,3);
  if(uniqueSigns.length===0){
    uniqueSigns.push({
      label:riskLevel==='safe'
        ?'Chưa phát hiện dấu hiệu lừa đảo rõ ràng'
        :'Nội dung cần được xác minh thêm',
      excerpt:''
    });
  }
  const defaultActions=[
    'Không bấm vào đường dẫn trong tin nhắn.',
    'Không cung cấp mật khẩu hoặc mã OTP.',
    'Liên hệ tổ chức qua số điện thoại hoặc ứng dụng chính thức.'
  ];
  return {
    riskLevel,
    riskLabel:payload?.offline&&riskLevel==='safe'
      ?(detective.indicators?.length?'Rủi ro thấp':'Chưa thấy dấu hiệu')
      :risk.label,
    reasoning:normalizeShareText(detective.reasoning||risk.description),
    confidence:Number.isFinite(detective.confidence)?detective.confidence:0,
    analysisMode:detective.analysis_mode,
    originalText:normalizeShareText(originalText)||'Không có nội dung tin nhắn.',
    signs:uniqueSigns,
    actions:defaultActions.map((fallback,index)=>
      normalizeShareText(detective.actions?.[index]||fallback)
    ),
    resultUrl:resultShareUrl(payload?.id)
  };
}

// Build the exported summary image shown when the user taps
// "Tải kết quả dạng ảnh".
async function createResultShareCanvas(summary){
  await waitForShareCanvasFonts();
  const canvas=document.createElement('canvas');
  canvas.width=1080;
  let context=canvas.getContext('2d');
  if(!context)throw new Error('Canvas is unavailable');
  const [logo,detectiveAvatar]=await Promise.all([
    loadShareLogo(),
    loadShareDetectiveAvatar()
  ]);

  const bubbleX=166,bubbleWidth=854,textX=bubbleX+34,textWidth=bubbleWidth-68;
  const prepareBubble=(title,body,{titleMax=2,bodyMax=6,quote='',quoteMax=3}={})=>{
    setShareCanvasFont(context,800,28);
    const titleLines=fitCanvasLines(context,title,textWidth,titleMax);
    setShareCanvasFont(context,500,27);
    const bodyLines=fitCanvasLines(context,body,textWidth,bodyMax);
    setShareCanvasFont(context,600,25);
    const quoteLines=fitCanvasLines(context,quote,textWidth-34,quoteMax);
    let height=31+titleLines.length*38;
    if(bodyLines.length)height+=12+bodyLines.length*38;
    if(quoteLines.length)height+=18+38+quoteLines.length*34;
    return {titleLines,bodyLines,quoteLines,height:height+27};
  };
  const reasoningBubble=prepareBubble(
    summary.analysisMode==='offline'?'Nhận định ngoại tuyến':'Nhận định của Thám tử',
    summary.reasoning,
    {bodyMax:7}
  );
  const originalBubble=prepareBubble(
    'Tin nhắn gốc',
    summary.originalText,
    {bodyMax:18}
  );
  const signBubbles=summary.signs.map(sign=>prepareBubble(
    sign.label,
    '',
    {quote:sign.excerpt,quoteMax:4}
  ));
  setShareCanvasFont(context,800,28);
  const recommendationTitle=fitCanvasLines(context,'Ba hành động nên làm ngay',textWidth,2);
  setShareCanvasFont(context,700,26);
  const actionLines=summary.actions.map(action=>fitCanvasLines(context,action,textWidth-68,3));
  const recommendationHeight=38+recommendationTitle.length*38
    +actionLines.reduce((total,lines)=>total+Math.max(48,lines.length*34)+14,0)+22;
  const bubbleGap=20;
  const bubblesHeight=reasoningBubble.height+originalBubble.height
    +signBubbles.reduce((total,bubble)=>total+bubble.height,0)
    +recommendationHeight
    +(signBubbles.length+2)*bubbleGap;
  const chatTop=175,chatHeaderHeight=130,bubblesTop=chatTop+chatHeaderHeight;
  const footerHeight=190;
  const footerTop=bubblesTop+bubblesHeight+32;
  canvas.height=Math.max(1350,footerTop+footerHeight+55);
  context=canvas.getContext('2d');
  if(!context)throw new Error('Canvas is unavailable');
  context.textBaseline='alphabetic';
  context.textAlign='left';
  context.fontKerning='normal';
  context.textRendering='optimizeLegibility';
  context.fillStyle='#edf3f8';
  context.fillRect(0,0,canvas.width,canvas.height);

  drawRoundedRectangle(context,38,30,1004,canvas.height-60,30,'#ffffff','#c8dce9',2);
  if(logo){
    context.drawImage(logo,66,43,300,107);
  }else{
    setShareCanvasFont(context,900,48);
    context.fillStyle='#1769c2';
    context.fillText('ScamCheck',68,110);
  }
  const riskThemes={
    safe:{background:'#e5f5ec',border:'#86c5a2',accent:'#146c3a'},
    suspicious:{background:'#fff3d7',border:'#dfbd69',accent:'#875300'},
    dangerous:{background:'#fde8e8',border:'#df9999',accent:'#9b1c1c'}
  };
  const theme=riskThemes[summary.riskLevel]||riskThemes.suspicious;
  drawRoundedRectangle(context,725,58,275,80,18,theme.background,theme.border,2);
  context.fillStyle=theme.accent;
  setShareCanvasFont(context,700,20);
  context.fillText('MỨC RỦI RO',750,87);
  setShareCanvasFont(context,900,34);
  context.fillText(summary.riskLabel,750,123);

  const chatGradient=context.createLinearGradient(60,chatTop,1020,chatTop+420);
  chatGradient.addColorStop(0,'#ffffff');
  chatGradient.addColorStop(1,'#eef7fd');
  drawRoundedRectangle(
    context,60,chatTop,960,footerTop-chatTop-12,26,chatGradient,'#bcd7ea',2
  );
  drawShareAvatar(context,detectiveAvatar,84,chatTop+25,76);
  context.fillStyle='#0d56a4';
  setShareCanvasFont(context,800,20);
  context.fillText('THÁM TỬ',184,chatTop+55);
  context.fillStyle='#102f4f';
  setShareCanvasFont(context,900,34);
  context.fillText('Phản hồi phân tích',184,chatTop+96);
  context.fillStyle='#526a80';
  setShareCanvasFont(context,600,21);
  context.fillText('Nội dung được trình bày như trên màn hình kết quả',505,chatTop+78);

  const drawBubbleFrame=(top,height,{fill='#ffffff',border='#cbdde9'}={})=>{
    context.save();
    context.shadowColor='rgba(26,61,95,.10)';
    context.shadowBlur=18;
    context.shadowOffsetY=7;
    drawRoundedRectangle(context,bubbleX,top,bubbleWidth,height,22,fill,border,2);
    context.restore();
    context.fillStyle=fill;
    context.beginPath();
    context.moveTo(bubbleX+1,top+30);
    context.lineTo(bubbleX-13,top+44);
    context.lineTo(bubbleX+1,top+55);
    context.closePath();
    context.fill();
    drawShareAvatar(context,detectiveAvatar,83,top+18,58);
  };
  const drawBubbleContent=(layout,top,{fill='#ffffff',border='#cbdde9',quoteFill='#fff4c7'}={})=>{
    drawBubbleFrame(top,layout.height,{fill,border});
    let cursor=top+49;
    context.fillStyle='#102f4f';
    setShareCanvasFont(context,800,28);
    drawPreparedCanvasLines(context,layout.titleLines,textX,cursor,38);
    cursor+=layout.titleLines.length*38;
    if(layout.bodyLines.length){
      cursor+=12;
      context.fillStyle='#29465f';
      setShareCanvasFont(context,500,27);
      drawPreparedCanvasLines(context,layout.bodyLines,textX,cursor,38);
      cursor+=layout.bodyLines.length*38;
    }
    if(layout.quoteLines.length){
      cursor+=18;
      const quoteHeight=38+layout.quoteLines.length*34;
      drawRoundedRectangle(
        context,textX,cursor-26,textWidth,quoteHeight,13,quoteFill,'#e2c466',1.5
      );
      context.fillStyle='#775000';
      setShareCanvasFont(context,700,21);
      context.fillText('DẤU HIỆU TRONG TIN NHẮN',textX+17,cursor);
      context.fillStyle='#17324d';
      setShareCanvasFont(context,600,25);
      drawPreparedCanvasLines(context,layout.quoteLines,textX+17,cursor+34,34);
    }
  };

  let top=bubblesTop;
  drawBubbleContent(reasoningBubble,top,{fill:'#eef7ff',border:'#a9cde8'});
  const confidenceLabel=summary.analysisMode==='offline'
    ?`Ước lượng rủi ro sơ bộ: ${Math.round(summary.confidence*100)}%`
    :`Khả năng lừa đảo: ${Math.round(summary.confidence*100)}%`;
  context.fillStyle='#0d56a4';
  setShareCanvasFont(context,700,21);
  context.fillText(confidenceLabel,textX,top+reasoningBubble.height-23);
  top+=reasoningBubble.height+bubbleGap;

  drawBubbleContent(originalBubble,top,{
    fill:summary.riskLevel==='safe'?'#ffffff':'#fffdf5',
    border:summary.riskLevel==='safe'?'#cbdde9':'#e2c466'
  });
  top+=originalBubble.height+bubbleGap;

  signBubbles.forEach(layout=>{
    drawBubbleContent(layout,top);
    top+=layout.height+bubbleGap;
  });

  drawBubbleFrame(top,recommendationHeight,{fill:'#eaf4ff',border:'#8ebce7'});
  let recommendationCursor=top+51;
  context.fillStyle='#0e4f91';
  setShareCanvasFont(context,800,28);
  drawPreparedCanvasLines(
    context,recommendationTitle,textX,recommendationCursor,38
  );
  recommendationCursor+=recommendationTitle.length*38+17;
  actionLines.forEach((lines,index)=>{
    context.fillStyle='#1769c2';
    context.beginPath();
    context.arc(textX+22,recommendationCursor+8,22,0,Math.PI*2);
    context.fill();
    context.fillStyle='#ffffff';
    setShareCanvasFont(context,900,21);
    context.textAlign='center';
    context.fillText(String(index+1),textX+22,recommendationCursor+16);
    context.textAlign='left';
    context.fillStyle='#17324d';
    setShareCanvasFont(context,700,26);
    drawPreparedCanvasLines(context,lines,textX+62,recommendationCursor+10,34);
    recommendationCursor+=Math.max(48,lines.length*34)+14;
  });

  drawRoundedRectangle(context,60,footerTop,960,footerHeight,24,'#0f3558');
  context.fillStyle='#ffffff';
  setShareCanvasFont(context,800,29);
  context.fillText('Chia sẻ để người thân cùng kiểm tra',92,footerTop+60);
  context.fillStyle='#d9eaf7';
  setShareCanvasFont(context,500,22);
  drawCanvasLines(
    context,
    'Quét mã ở góc để mở kết quả này.',
    92,footerTop+101,600,30,2
  );
  context.fillStyle='#ffffff';
  setShareCanvasFont(context,700,20);
  context.fillText('fctsc-hackathon-2026.vercel.app',92,footerTop+145);
  drawRoundedRectangle(context,846,footerTop+17,154,154,13,'#ffffff');
  drawQr(context,850,footerTop+21,146,summary.resultUrl);

  context.fillStyle='#526a80';
  setShareCanvasFont(context,600,18);
  context.textAlign='center';
  context.fillText(
    'Ảnh chia sẻ từ ScamCheck · Không thay thế cảnh báo chính thức',
    540,canvas.height-24
  );
  context.textAlign='left';
  return canvas;
}

// --- DOM capture helpers for result export --------------------------------------
function createCaptureQrCanvas(value){
  const canvas=document.createElement('canvas');
  canvas.width=90;
  canvas.height=90;
  const context=canvas.getContext('2d');
  if(!context)throw new Error('Canvas is unavailable');
  drawQr(context,0,0,90,value);
  return canvas;
}

function waitForCaptureImages(container){
  return Promise.all([...container.querySelectorAll('img')].map(image=>{
    if(image.complete)return Promise.resolve();
    return new Promise(resolve=>{
      image.addEventListener('load',resolve,{once:true});
      image.addEventListener('error',resolve,{once:true});
    });
  }));
}

function createDetectiveCaptureNode(){
  const source=query('.detective-section',resultFrame);
  if(!source)throw new Error('Detective result is unavailable');
  const shell=document.createElement('div');
  shell.className='result-image-capture-shell';
  shell.setAttribute('aria-hidden','true');

  const detective=source.cloneNode(true);
  detective.classList.add('result-image-capture');
  detective.querySelectorAll('[id]').forEach(element=>element.removeAttribute('id'));
  const messageList=query('.detective-message-list',detective);
  if(!messageList)throw new Error('Detective messages are unavailable');
  const rows=[...messageList.querySelectorAll('.detective-message-row')];
  const original=rows.find(row=>row.classList.contains('original-message-row'));
  const analysisRows=rows.filter(row=>
    row!==original&&!row.classList.contains('recommendations-message')
  );
  messageList.replaceChildren(...(original?[original,...analysisRows]:analysisRows));

  const footer=document.createElement('div');
  footer.className='result-image-capture-footer';
  const logo=document.createElement('img');
  logo.src='/scamcheck-logo.png';
  logo.alt='';
  logo.width=145;
  const qr=createCaptureQrCanvas(currentShareSummary?.resultUrl);
  qr.setAttribute('aria-hidden','true');
  footer.append(logo,qr);
  shell.append(detective,footer);
  document.body.appendChild(shell);
  return shell;
}

async function createDetectiveDomCaptureCanvas(){
  if(typeof window.html2canvas!=='function'){
    throw new Error('DOM capture is unavailable');
  }
  const capture=createDetectiveCaptureNode();
  try{
    if(document.fonts?.ready)await document.fonts.ready;
    await waitForCaptureImages(capture);
    await new Promise(resolve=>requestAnimationFrame(()=>
      requestAnimationFrame(resolve)
    ));
    return await window.html2canvas(capture,{
      backgroundColor:'#edf3f8',
      scale:3,
      useCORS:true,
      allowTaint:false,
      logging:false,
      width:capture.offsetWidth,
      height:capture.scrollHeight,
      windowWidth:390,
      windowHeight:capture.scrollHeight,
      scrollX:0,
      scrollY:0
    });
  }finally{
    capture.remove();
  }
}

function canvasToPngBlob(canvas){
  return new Promise((resolve,reject)=>{
    canvas.toBlob(blob=>{
      if(blob)resolve(blob);
      else reject(new Error('PNG export failed'));
    },'image/png',1);
  });
}

function isAppleMobileDevice(){
  return /iPad|iPhone|iPod/.test(navigator.userAgent)
    ||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
}

async function saveCurrentResultImage(){
  if(!currentShareSummary)throw new Error('No result to export');
  const isAppleMobile=isAppleMobileDevice();
  const canAttemptFileShare=isAppleMobile
    &&typeof File==='function'
    &&typeof navigator.share==='function'
    &&typeof navigator.canShare==='function';
  const previewWindow=isAppleMobile&&!canAttemptFileShare
    ?window.open('about:blank','_blank')
    :null;
  const canvas=await createDetectiveDomCaptureCanvas();
  const blob=await canvasToPngBlob(canvas);
  const date=new Date().toISOString().slice(0,10);
  const filename=`scamcheck-ket-qua-${date}.png`;
  const file=typeof File==='function'
    ?new File([blob],filename,{type:'image/png',lastModified:Date.now()})
    :null;
  if(canAttemptFileShare&&file){
    let canShareFile=false;
    try{
      canShareFile=navigator.canShare({files:[file]});
    }catch(error){
      canShareFile=false;
    }
    if(canShareFile){
      try{
        await navigator.share({
          files:[file],
          title:'Kết quả ScamCheck',
          text:'Ảnh tóm tắt kết quả kiểm tra từ ScamCheck'
        });
        return 'shared';
      }catch(error){
        if(error?.name==='AbortError')return 'cancelled';
      }
    }
  }
  const objectUrl=URL.createObjectURL(blob);
  if(previewWindow&&!previewWindow.closed){
    previewWindow.location.href=objectUrl;
    window.setTimeout(()=>URL.revokeObjectURL(objectUrl),60000);
    return 'preview';
  }
  const anchor=document.createElement('a');
  anchor.href=objectUrl;
  anchor.download=filename;
  if(isAppleMobile){
    anchor.target='_blank';
    anchor.rel='noopener';
  }
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(()=>URL.revokeObjectURL(objectUrl),60000);
  return isAppleMobile?'preview':'downloaded';
}

// --- Safe text rendering for result messages ------------------------------------
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

// --- Detective / Psychology / Responder result blocks ----------------------------
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
  if(!psychologyMessage.childElementCount)return;
  actionSection.hidden=false;
  psychologyBlock.hidden=false;
  revealRows(psychologyMessage.querySelectorAll('.psychology-message-row'));
  revealPostAnalysisQuestion();
}

function renderResultBlocks(){
  revealRows(signalList.querySelectorAll('.detective-message-row'));
  downloadResultImageButton.disabled=false;
  resultImageStatus.textContent='';
  revealPsychologyMessages();
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
  bankQuestion.hidden=true;
  bankOptions.replaceChildren();
  postAnalysisQuestion.dataset.eligible=String(Boolean(shouldShow&&!payload.offline&&payload.id));
  postAnalysisQuestion.dataset.analysisId=String(payload.id||'');
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
  if(!shouldShow||payload.character_pending){
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

function renderResponderGuidance(steps){
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
  revealRows(items);
}

// Main renderer for the result page after online or offline analysis finishes.
function showResultFrame(text,payload,{fromHistory=false}={}){
  const detective=payload.detective;
  const risk=riskPresentations[detective.risk_level]||riskPresentations.suspicious;

  resultContextLabel.textContent=fromHistory?'Kết quả đã lưu':'Phân tích hoàn tất';
  postAnalysisQuestion.dataset.message=text;
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
  if(Array.isArray(payload.responder_output?.steps)&&!payload.responder_output.needs_bank){
    renderResponderGuidance(payload.responder_output.steps);
  }
  currentShareSummary=resultShareSummary(text,payload);
  void Promise.all([loadShareLogo(),loadShareDetectiveAvatar()]);
  downloadResultImageButton.disabled=true;
  resultImageStatus.textContent='Ảnh sẽ sẵn sàng khi Thám tử phản hồi xong.';

  inputFrame.style.display='none';
  hideProcessingFrame();
  resultFrame.classList.add('active');
  resetResultAutoFollow();
  window.scrollTo({top:0,behavior:'smooth'});
  renderResultBlocks();
}
