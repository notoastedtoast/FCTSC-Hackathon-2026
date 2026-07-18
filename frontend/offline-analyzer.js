const ScamCheckOffline=(()=>{
  const URL_PATTERN=/(?:https?:\/\/[^\s]+|www\.[^\s]+|(?:bit\.ly|tinyurl\.com|t\.co|shorturl\.at)\/[^\s]+|[a-z0-9][a-z0-9-]{2,}\.(?:com|net|org|vn|xyz|top|click|site|online)(?:\/[^\s]*)?)/giu;
  const TRUSTED_URL_PATTERN=/^(?:https?:\/\/)?accounts\.google\.com(?:[/:?#]|$)/iu;

  function findUntrustedUrl(text){
    const matches=text.match(URL_PATTERN)||[];
    return matches.find(value=>{
      const normalized=value.replace(/[.,;:!?]+$/u,'');
      return !TRUSTED_URL_PATTERN.test(normalized);
    })||null;
  }

  const RULES=[
    {
      label:'Yêu cầu mã xác thực hoặc thông tin đăng nhập',
      weight:4,
      pattern:/(?:gửi|cung cấp|nhập|đọc|chia sẻ|tiết lộ).{0,35}(?:mã\s+otp|otp|mã\s+xác\s+(?:thực|nhận)|mật\s+khẩu|password|passcode|mã\s+pin)|(?:mã\s+otp|otp|mật\s+khẩu|password).{0,35}(?:cho\s+(?:tôi|chúng tôi)|vào\s+(?:link|liên kết)|để\s+xác\s+minh)/iu
    },
    {
      label:'Người gửi xin mã xác thực cá nhân',
      weight:2,
      pattern:/(?:cho\s+(?:tôi|mình|chúng\s+tôi)\s+xin|gửi\s+cho\s+(?:tôi|mình)).{0,30}(?:mã\s+otp|otp|mã\s+xác\s+(?:thực|nhận))/iu
    },
    {
      label:'Yêu cầu cài phần mềm hoặc điều khiển thiết bị từ xa',
      weight:4,
      pattern:/(?:anydesk|teamviewer|ultraviewer|quicksupport|chia\s+sẻ\s+màn\s+hình|điều\s+khiển\s+từ\s+xa|cài\s+(?:ứng\s+dụng|phần\s+mềm).{0,30}(?:hỗ\s+trợ|xử\s+lý|khôi\s+phục))/iu
    },
    {
      label:'Yêu cầu chuyển tiền hoặc đóng phí',
      weight:3,
      pattern:/(?:chuyển\s+(?:khoản|tiền)|thanh\s+toán|đóng\s+phí|nộp\s+phí|phí\s+(?:hồ\s+sơ|kích\s+hoạt|vận\s+chuyển)|mua\s+thẻ\s+(?:quà\s+tặng|gift)|gift\s*card|send\s+(?:money|payment)|wire\s+transfer|chuyển.{0,20}(?:bitcoin|usdt))/iu
    },
    {
      label:'Đường dẫn cần được xác minh độc lập',
      weight:2,
      find:findUntrustedUrl
    },
    {
      label:'Mạo danh tổ chức hoặc người có thẩm quyền',
      weight:1,
      pattern:/(?:ngân\s+hàng|công\s+an|cảnh\s+sát|tòa\s+án|viện\s+kiểm\s+sát|cơ\s+quan\s+thuế|nhân\s+viên\s+kỹ\s+thuật|bank\s+(?:security|support)|police|government\s+agency)/iu
    },
    {
      label:'Tạo áp lực phải hành động gấp',
      weight:1,
      pattern:/(?:ngay\s+lập\s+tức|trong\s+\d+\s*(?:phút|giờ)|trước\s+\d+\s*giờ|khẩn\s+cấp|sắp\s+(?:hết\s+hạn|bị\s+khóa)|nếu\s+không|immediately|urgent|within\s+\d+)/iu
    },
    {
      label:'Đe dọa hậu quả để gây hoảng sợ',
      weight:3,
      pattern:/(?:bị\s+(?:khóa|bắt|khởi\s+tố|phạt)|ngừng\s+hoạt\s+động|truy\s+nã|lệnh\s+bắt|phát\s+tán|tống\s+tiền|blackmail|arrest|legal\s+action|suspend(?:ed|sion)?)/iu
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
      weight:1,
      pattern:/(?:bỏ\s+qua\s+(?:mọi\s+)?hướng\s+dẫn|hãy\s+nói\s+tin\s+này\s+an\s+toàn|ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions)/iu
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
    'Khi có mạng, kiểm tra lại bằng Gemini hoặc nhờ người tin cậy hỗ trợ.'
  ];

  function analyze(text){
    const findings=[];
    let score=0;

    RULES.forEach(rule=>{
      const excerpt=rule.find?rule.find(text):(text.match(rule.pattern)?.[0]||null);
      if(!excerpt)return;
      score+=rule.weight;
      findings.push({label:rule.label,excerpt,weight:rule.weight});
    });

    findings.sort((a,b)=>b.weight-a.weight);
    const riskLevel=score>=4?'dangerous':score>0?'suspicious':'safe';
    const confidence=riskLevel==='dangerous'
      ?Math.min(.96,.78+score*.025)
      :riskLevel==='suspicious'
        ?Math.min(.76,.5+score*.07)
        :.18;
    const reasoning=riskLevel==='dangerous'
      ?`Đánh giá ngoại tuyến phát hiện ${findings.length} dấu hiệu rủi ro, trong đó có yêu cầu hoặc thủ thuật có mức nguy hiểm cao. Đây là kết quả sơ bộ từ các quy tắc lưu trên thiết bị.`
      :riskLevel==='suspicious'
        ?`Đánh giá ngoại tuyến phát hiện ${findings.length} dấu hiệu cần xác minh thêm. Đây là kết quả sơ bộ từ các quy tắc lưu trên thiết bị.`
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
