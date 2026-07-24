/* Browser-only fallback analyzer used when the device is offline.
   It is intentionally conservative and returns a preliminary result. */
const ScamCheckOffline=(()=>{
  const URL_PATTERN=/(?:https?:\/\/[^\s]+|www\.[^\s]+|(?:bit\.ly|tinyurl\.com|t\.co|shorturl\.at)\/[^\s]+|[a-z0-9][a-z0-9-]{2,}\.[a-z]{2,63}(?:\/[^\s]*)?)/giu;
  const TRUSTED_URL_PATTERN=/^(?:https?:\/\/)?accounts\.google\.com(?:[/:?#]|$)/iu;

  function findUntrustedUrl(text){
    // Treat unknown URLs as caution signals without contacting the network.
    const matches=[...text.matchAll(URL_PATTERN)];
    for(const match of matches){
      const value=match[0];
      const index=match.index||0;
      if(index>0&&text[index-1]==='@')continue;
      const normalized=value.replace(/[.,;:!?]+$/u,'');
      if(!TRUSTED_URL_PATTERN.test(normalized))return normalized;
    }
    return null;
  }

  function foldText(text){
    // Fold accents so simpler regex rules can still match Vietnamese text.
    return text.normalize('NFD').replace(/[\u0300-\u036f]/gu,'').replace(/đ/giu,'d');
  }

  function hasApplicableIgnore(text,pattern){
    if(!pattern)return false;
    const match=text.match(pattern);
    if(!match)return false;
    const prefix=text.slice(Math.max(0,(match.index||0)-16),match.index||0);
    return !/\b(?:nếu|neu)\s+(?:(?:bạn|bác|ban|bac)\s+)?$/iu.test(prefix);
  }

  function findAccountAccessPrompt(text){
    if(!/(?:tài\s+khoản|ngân\s+hàng|bank\s+account)/iu.test(text))return null;
    const prompt=text.match(/(?:(?:quét|scan).{0,15}(?:mã\s+)?qr|(?:bấm|nhấn|click).{0,25}(?:nút|liên\s+kết|link)).{0,60}(?:đăng\s+nhập|xác\s+minh|kiểm\s+tra)|(?:đăng\s+nhập|xác\s+minh).{0,60}(?:(?:quét|scan).{0,15}(?:mã\s+)?qr|(?:bấm|nhấn|click).{0,25}(?:nút|liên\s+kết|link))/iu);
    return prompt?.[0]||null;
  }

  // Catch direct payment requests with amounts even when accents are missing.
  function findMoneyRequest(text){
    const folded=foldText(text);
    if(/\b(?:da|vua)\s+chuyen\b/iu.test(folded))return null;
    const match=folded.match(/(?:hay|vui\s+long|xin\s+hay|can|phai).{0,24}chuyen.{0,24}(?:\d[\d.\s]{2,}|k|nghin|trieu|usd|usdt|vnd|dong)|chuyen.{0,20}(?:\d[\d.\s]{2,}|k|nghin|trieu|usd|usdt|vnd|dong).{0,20}(?:de|cho|ngay)/iu);
    return match?text.slice(match.index,match.index+match[0].length):null;
  }

  const RULES=[
    {
      label:'Yêu cầu mã xác thực hoặc thông tin đăng nhập',
      weight:4,
      pattern:/(?:gửi|cung cấp|nhập|đọc|chia sẻ|tiết lộ|send|share|provide|enter).{0,35}(?:mã\s+otp|otp|mã\s+xác\s+(?:thực|nhận)|mật\s+khẩu|password|passcode|mã\s+pin)|(?:mã\s+otp|otp|mật\s+khẩu|password).{0,35}(?:cho\s+(?:tôi|chúng tôi)|vào\s+(?:link|liên kết)|để\s+xác\s+minh|to\s+me)/iu,
      foldedPattern:/(?:gui|cung cap|nhap|doc|chia se|tiet lo).{0,35}(?:ma\s+otp|otp|ma\s+xac\s+(?:thuc|nhan)|mat\s+khau|ma\s+pin)/iu,
      ignorePattern:/(?:(?:không\s+bao\s+giờ|tuyệt\s+đối\s+không|không\s+(?:nên|được)|đừng|không).{0,12}(?:gửi|cung cấp|nhập|đọc|chia sẻ|tiết lộ).{0,35}(?:mã\s+otp|otp|mã\s+xác\s+(?:thực|nhận)|mật\s+khẩu|password|passcode|mã\s+pin)|(?:mã\s+otp|otp|mật\s+khẩu|password).{0,50}(?:không\s+bao\s+giờ|tuyệt\s+đối\s+không|không\s+(?:nên|được)|đừng|không).{0,12}(?:gửi|chia sẻ|tiết lộ).{0,20}(?:cho|với)\s+(?:ai|bất\s+kỳ\s+ai|người\s+khác))/iu,
      foldedIgnorePattern:/(?:(?:khong\s+bao\s+gio|tuyet\s+doi\s+khong|khong\s+(?:nen|duoc)|dung|khong).{0,12}(?:gui|cung cap|nhap|doc|chia se|tiet lo).{0,35}(?:ma\s+otp|otp|ma\s+xac\s+(?:thuc|nhan)|mat\s+khau|password|passcode|ma\s+pin)|(?:ma\s+otp|otp|mat\s+khau|password).{0,50}(?:khong\s+bao\s+gio|tuyet\s+doi\s+khong|khong\s+(?:nen|duoc)|dung|khong).{0,12}(?:gui|chia se|tiet lo).{0,20}(?:cho|voi)\s+(?:ai|bat\s+ky\s+ai|nguoi\s+khac))/iu
    },
    {
      label:'Người gửi xin mã xác thực cá nhân',
      weight:2,
      pattern:/(?:cho\s+(?:tôi|mình|chúng\s+tôi)\s+xin|gửi\s+cho\s+(?:tôi|mình)).{0,30}(?:mã\s+otp|otp|mã\s+xác\s+(?:thực|nhận))/iu
    },
    {
      label:'Yêu cầu cài phần mềm hoặc điều khiển thiết bị từ xa',
      weight:4,
      pattern:/(?:anydesk|teamviewer|ultraviewer|quicksupport|chia\s+sẻ\s+màn\s+hình|điều\s+khiển\s+từ\s+xa|cài\s+(?:ứng\s+dụng|phần\s+mềm).{0,30}(?:hỗ\s+trợ|xử\s+lý|khôi\s+phục))/iu,
      ignorePattern:/(?:không\s+bao\s+giờ|tuyệt\s+đối\s+không|không\s+(?:nên|được)|đừng|không).{0,35}(?:cài|dùng|sử\s+dụng|mở|chia\s+sẻ).{0,25}(?:anydesk|teamviewer|ultraviewer|quicksupport|ứng\s+dụng|phần\s+mềm|màn\s+hình)/iu,
      foldedIgnorePattern:/(?:khong\s+bao\s+gio|tuyet\s+doi\s+khong|khong\s+(?:nen|duoc)|dung|khong).{0,35}(?:cai|dung|su\s+dung|mo|chia\s+se).{0,25}(?:anydesk|teamviewer|ultraviewer|quicksupport|ung\s+dung|phan\s+mem|man\s+hinh)/iu
    },
    {
      label:'Yêu cầu chuyển tiền hoặc đóng phí',
      weight:3,
      pattern:/(?:chuyển\s+(?:khoản|tiền)|thanh\s+toán|đóng\s+phí|nộp\s+phí|phí\s+(?:hồ\s+sơ|kích\s+hoạt|vận\s+chuyển)|mua\s+thẻ\s+(?:quà\s+tặng|gift)|gift\s*card|send\s+(?:money|payment)|wire\s+transfer|chuyển.{0,20}(?:bitcoin|usdt))/iu,
      foldedPattern:/(?:chuyen\s+(?:khoan|tien)|thanh\s+toan|dong\s+phi|nop\s+phi|phi\s+(?:ho\s+so|kich\s+hoat|van\s+chuyen)|mua\s+the\s+qua\s+tang)/iu,
      ignorePattern:/(?:(?:đã|vừa)\s+chuyển\s+(?:khoản|tiền)|(?:hóa\s+đơn\s+(?:điện|nước|internet)|cước\s+(?:điện\s+thoại|internet)).{0,60}(?:ứng\s+dụng|kênh|trang\s+web)\s+chính\s+thức|(?:không\s+bao\s+giờ|tuyệt\s+đối\s+không|không\s+(?:nên|được)|đừng).{0,20}(?:yêu\s+cầu.{0,35})?(?:chuyển\s+(?:khoản|tiền)|thanh\s+toán|đóng\s+phí|nộp\s+phí))/iu,
      foldedIgnorePattern:/(?:(?:da|vua)\s+chuyen\s+(?:khoan|tien)|(?:hoa\s+don\s+(?:dien|nuoc|internet)|cuoc\s+(?:dien\s+thoai|internet)).{0,60}(?:ung\s+dung|kenh|trang\s+web)\s+chinh\s+thuc|(?:khong\s+bao\s+gio|tuyet\s+doi\s+khong|khong\s+(?:nen|duoc)|dung).{0,20}(?:yeu\s+cau.{0,35})?(?:chuyen\s+(?:khoan|tien)|thanh\s+toan|dong\s+phi|nop\s+phi))/iu
    },
    {
      label:'Dẫn tới đăng nhập hoặc xác minh bằng mã QR hay nút bấm',
      weight:4,
      find:findAccountAccessPrompt
    },
    {
      label:'Đường dẫn cần được xác minh độc lập',
      weight:2,
      find:findUntrustedUrl
    },
    {
      label:'Yêu cầu chuyển tiền trực tiếp',
      weight:3,
      find:findMoneyRequest
    },
    {
      label:'Mạo danh tổ chức hoặc người có thẩm quyền',
      weight:2,
      pattern:/(?:(?:tôi|chúng\s+tôi|đây\s+là).{0,25}(?:nhân\s+viên\s+ngân\s+hàng|công\s+an|cảnh\s+sát|tòa\s+án|viện\s+kiểm\s+sát|cơ\s+quan\s+thuế|nhân\s+viên\s+kỹ\s+thuật)|(?:ngân\s+hàng|công\s+an|cảnh\s+sát|tòa\s+án|viện\s+kiểm\s+sát|cơ\s+quan\s+thuế|bank\s+(?:security|support)|police|government\s+agency).{0,35}(?:thông\s+báo|yêu\s+cầu|điều\s+tra|triệu\s+tập|tài\s+khoản\s+(?:của\s+)?(?:bạn|bác)))/iu,
      ignorePattern:/(?:ngân\s+hàng|công\s+an|cảnh\s+sát|cơ\s+quan).{0,25}(?:không\s+bao\s+giờ|sẽ\s+không|không).{0,20}yêu\s+cầu/iu,
      foldedIgnorePattern:/(?:ngan\s+hang|cong\s+an|canh\s+sat|co\s+quan).{0,25}(?:khong\s+bao\s+gio|se\s+khong|khong).{0,20}yeu\s+cau/iu
    },
    {
      label:'Tạo áp lực phải hành động gấp',
      weight:1,
      pattern:/(?:ngay\s+lập\s+tức|trong\s+\d+\s*(?:phút|giờ)|trước\s+\d+\s*giờ|khẩn\s+cấp|sắp\s+(?:hết\s+hạn|bị\s+khóa)|nếu\s+không|immediately|urgent|within\s+\d+)/iu,
      foldedPattern:/(?:ngay\s+lap\s+tuc|trong\s+\d+\s*(?:phut|gio)|truoc\s+\d+\s*gio|khan\s+cap|sap\s+(?:het\s+han|bi\s+khoa)|neu\s+khong)/iu
    },
    {
      label:'Đe dọa hậu quả để gây hoảng sợ',
      weight:3,
      pattern:/(?:bị\s+(?:khóa|bắt|khởi\s+tố|phạt)|ngừng\s+hoạt\s+động|truy\s+nã|lệnh\s+bắt|phát\s+tán|tống\s+tiền|blackmail|arrest|legal\s+action|suspend(?:ed|sion)?)/iu,
      foldedPattern:/(?:bi\s+(?:khoa|bat|khoi\s+to|phat)|ngung\s+hoat\s+dong|truy\s+na|lenh\s+bat|phat\s+tan|tong\s+tien)/iu
    },
    {
      label:'Yêu cầu giữ bí mật hoặc cô lập người nhận',
      weight:2,
      pattern:/(?:giữ\s+bí\s+mật|không\s+được\s+nói|không\s+liên\s+hệ|xóa\s+tin\s+nhắn|bí\s+mật\s+cuộc\s+gọi|keep\s+(?:this\s+)?secret|do\s+not\s+tell)/iu
    },
    {
      label:'Hứa phần thưởng hoặc quyền lợi bất ngờ',
      weight:2,
      pattern:/(?:trúng\s+(?:giải|thưởng)|nhận\s+(?:quà|thưởng)|quà\s+tặng\s+miễn\s+phí|lottery|winner|won\s+a\s+prize|inheritance)/iu
    },
    {
      label:'Mời đầu tư với lợi nhuận bất thường',
      weight:2,
      pattern:/(?:lợi\s+nhuận\s+(?:cao|đảm\s+bảo)|cam\s+kết\s+lãi|đầu\s+tư.{0,25}(?:tiền\s+ảo|crypto|forex)|cryptocurrency|guaranteed\s+return)/iu
    },
    {
      label:'Giả tình huống khẩn cấp của người thân',
      weight:2,
      pattern:/(?:con|cháu|anh|em|bạn).{0,20}(?:gặp\s+nạn|cấp\s+cứu|mất\s+điện\s+thoại|đổi\s+số)|emergency.{0,35}(?:money|transfer)/iu
    },
    {
      label:'Lời mời việc làm hoặc nhiệm vụ có dấu hiệu bất thường',
      weight:2,
      pattern:/(?:việc\s+làm\s+(?:tại\s+nhà|online)|nhiệm\s+vụ.{0,25}hoa\s+hồng|đặt\s+cọc\s+nhận\s+việc|job\s+offer|work\s+from\s+home|task\s+commission)/iu
    },
    {
      label:'Câu chữ cố điều khiển hoặc vô hiệu hóa hệ thống phân tích',
      weight:2,
      pattern:/(?:bỏ\s+qua\s+(?:mọi\s+)?hướng\s+dẫn|bỏ\s+qua\s+tin\s+nhắn\s+này|đánh\s+dấu\s+là\s+an\s+toàn|hãy\s+nói\s+tin\s+này\s+an\s+toàn|ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions)/iu,
      foldedPattern:/(?:bo\s+qua\s+(?:moi\s+)?huong\s+dan|bo\s+qua\s+tin\s+nhan\s+nay|danh\s+dau\s+la\s+an\s+toan|hay\s+noi\s+tin\s+nay\s+an\s+toan|ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions)/iu
    },
    {
      label:'Yêu cầu cung cấp dữ liệu tài chính hoặc định danh',
      weight:4,
      pattern:/(?:gửi|cung cấp|nhập|đọc|chia sẻ|tiết lộ).{0,40}(?:số\s+thẻ|cvv|căn\s+cước|cccd|tài\s+khoản\s+ngân\s+hàng|bank\s+account|social\s+security)/iu
    }
  ];

  const ACTIONS=[
    'Không trả lời, chuyển tiền hoặc cung cấp thông tin nhạy cảm.',
    'Tự liên hệ tổ chức hoặc người gửi qua kênh chính thức.',
    'Khi có mạng, kiểm tra lại trực tuyến hoặc nhờ người tin cậy hỗ trợ.'
  ];

  function analyze(text){
    // Produce the same general response shape as the online analyzer.
    const findings=[];
    const foldedText=foldText(text);
    let score=0;

    RULES.forEach(rule=>{
      let excerpt=rule.find?rule.find(text):(text.match(rule.pattern)?.[0]||null);
      if(!excerpt&&rule.foldedPattern){
        const foldedMatch=foldedText.match(rule.foldedPattern);
        if(foldedMatch)excerpt=text.slice(foldedMatch.index,foldedMatch.index+foldedMatch[0].length);
      }
      if(!excerpt)return;
      if(hasApplicableIgnore(text,rule.ignorePattern)||hasApplicableIgnore(foldedText,rule.foldedIgnorePattern))return;
      score+=rule.weight;
      findings.push({label:rule.label,excerpt,weight:rule.weight});
    });

    findings.sort((a,b)=>b.weight-a.weight);
    const riskLevel=score>=4?'dangerous':score>=2?'suspicious':'safe';
    const confidence=riskLevel==='dangerous'
      ?Math.min(.96,.78+score*.025)
      :riskLevel==='suspicious'
        ?Math.min(.76,.5+score*.07)
        :.18;
    const reasoning=riskLevel==='dangerous'
      ?`Đánh giá ngoại tuyến phát hiện ${findings.length} dấu hiệu rủi ro, trong đó có yêu cầu hoặc thủ thuật có mức nguy hiểm cao. Đây là kết quả sơ bộ từ các quy tắc lưu trên thiết bị.`
      :riskLevel==='suspicious'
        ?`Đánh giá ngoại tuyến phát hiện ${findings.length} dấu hiệu cần xác minh thêm. Đây là kết quả sơ bộ từ các quy tắc lưu trên thiết bị.`
        :findings.length
          ?`Đánh giá ngoại tuyến nhận ra ${findings.length} chi tiết có thể xuất hiện trong giao tiếp thông thường nhưng chưa đủ để kết luận có dấu hiệu lừa đảo. Kết quả sơ bộ này không thể khẳng định tin nhắn an toàn.`
          :'Đánh giá ngoại tuyến chưa nhận ra dấu hiệu lừa đảo phổ biến. Kết quả sơ bộ này không thể khẳng định tin nhắn an toàn; bác vẫn nên xác minh người gửi.';

    return {
      offline:true,
      detective:{
        title:'Thám tử ngoại tuyến',
        analysis_mode:'offline',
        risk_level:riskLevel,
        confidence,
        reasoning,
        indicators:findings.slice(0,4).map(item=>item.label),
        indicator_evidence:findings.slice(0,4).map(({label,excerpt})=>({label,excerpt})),
        actions:[...ACTIONS]
      },
      character:riskLevel==='safe'?null:{
        character_id:'calming-guide',
        title:'Cô tâm lý',
        message:riskLevel==='dangerous'
          ?'Cô thấy tin nhắn đang dùng áp lực hoặc yêu cầu nhạy cảm để bác hành động vội. Bác hãy dừng lại, không chuyển tiền hay cung cấp mã, rồi tự liên hệ nơi liên quan qua kênh chính thức.'
          :'Cô thấy tin nhắn có chi tiết dễ làm bác vội hoặc phân vân. Bác cứ tạm dừng và xác minh qua một kênh chính thức trước khi làm theo.'
      },
      character_notice:null
    };
  }

  return {analyze};
})();

if(typeof module!=='undefined'&&module.exports)module.exports=ScamCheckOffline;
