/* ScamCheck browser client data and shared page state.
   This file holds constants, cached DOM refs, local datasets, and top-level
   mutable state so the behavior files can stay smaller. */
const byId=id=>document.getElementById(id),query=(selector,root=document)=>root.querySelector(selector),queryAll=(selector,root=document)=>root.querySelectorAll(selector);
const MIN_LENGTH=10,MAX_LENGTH=10000,ANALYSIS_LIMIT=10,DRAFT_KEY='scamcheck-message-draft',ONLINE_HISTORY_KEY='scamcheck-online-history-v1',OFFLINE_HISTORY_KEY='scamcheck-offline-history-v1',PENDING_ANALYSIS_KEY='scamcheck-pending-analysis-v1',DISPLAY_PREFERENCES_KEY='scamcheck-display-preferences-v1',ANALYSIS_REMAINING_KEY='scamcheck-analysis-remaining-v1',MAX_OFFLINE_HISTORY=10,MAX_ONLINE_HISTORY=10,SHARE_PRODUCT_URL='https://fctsc-hackathon-2026.vercel.app/';
// Cache the DOM once so the rest of the code can stay shorter.
const messageInput=byId('message'),checkButton=byId('check-button'),processingFrame=byId('processing-frame'),characterCount=byId('character-count'),feedback=byId('message-feedback'),usage=byId('usage'),connectivityStatus=byId('connectivity-status'),connectivityMessage=byId('connectivity-message'),voiceButton=byId('voice-button'),voiceButtonLabel=byId('voice-button-label'),voiceStatus=byId('voice-status'),inputFrame=byId('input-frame'),resultFrame=byId('result-frame'),riskCard=byId('risk-card'),riskLabel=byId('risk-label'),riskDescription=byId('risk-description'),signalList=byId('signal-list'),resultContextLabel=byId('result-context-label'),resultScrollButton=byId('result-scroll-button'),historyReturnButton=byId('history-return-button'),sampleButtons=queryAll('.sample-button'),historyList=byId('history-list'),historySelectedCount=byId('history-selected-count'),historyDeleteButton=byId('history-delete-button'),deleteConfirmModal=byId('delete-confirm-modal'),deleteConfirmText=byId('delete-confirm-text'),deletePreview=byId('delete-preview'),deleteCancelButton=byId('delete-cancel-button'),deleteConfirmButton=byId('delete-confirm-button'),contrastToggle=byId('contrast-toggle'),fontSizeToggle=byId('font-size-toggle'),displayPreferenceStatus=byId('display-preference-status');
const psychologyBlock=byId('psychology-block'),psychologyMessage=byId('psychology-message'),actionSection=byId('action-section'),postAnalysisQuestion=byId('post-analysis-question'),postAnalysisOptions=queryAll('.post-analysis-option'),bankQuestion=byId('bank-question'),bankOptions=byId('bank-options'),responderBlock=byId('responder-block'),responderSteps=byId('responder-steps'),downloadResultImageButton=byId('download-result-image-button'),resultImageStatus=byId('result-image-status');
const practiceContent=byId('practice-content'),practiceMessage=byId('practice-message'),practiceProgress=byId('practice-progress'),practiceScore=byId('practice-score'),practiceAnswerButtons=queryAll('.practice-answer-button'),practiceFeedback=byId('practice-feedback'),practiceNextButton=byId('practice-next-button');
const libraryListFrame=byId('library-list-frame'),libraryDetailFrame=byId('library-detail-frame'),librarySearch=byId('library-search'),libraryFilters=queryAll('.library-filter'),libraryResultCount=byId('library-result-count'),libraryLoadError=byId('library-load-error'),libraryRetryButton=byId('library-retry-button'),scamTypeList=byId('scam-type-list'),libraryEmpty=byId('library-empty'),libraryResetButton=byId('library-reset-button'),libraryDetailBack=byId('library-detail-back'),libraryDetailError=byId('library-detail-error'),libraryDetailContent=byId('library-detail-content'),libraryDetailIcon=byId('library-detail-icon'),libraryDetailGroup=byId('library-detail-group'),libraryDetailTitle=byId('library-detail-title'),libraryDetailDescription=byId('library-detail-description'),libraryDetailSigns=byId('library-detail-signs'),libraryDetailExample=byId('library-detail-example'),libraryDetailDo=byId('library-detail-do'),libraryDetailDont=byId('library-detail-dont');
const navLinks=queryAll('.nav-link[data-view]'),pageViews=queryAll('[data-view-panel]');
const toolsColumn=query('.tools-column'),mobileQuickCards=queryAll('.sample-card'),mobileLayoutQuery=window.matchMedia('(max-width: 620px)');
let recognition=null,isRecording=false,selectedHistoryIds=new Set(),isAnalyzing=false,sessionAtLimit=false,remainingAnalyses=ANALYSIS_LIMIT,isOffline=!navigator.onLine,historyCache=[];
let autoFollowResult=true,latestResultMessage=null,lastResultScrollY=window.scrollY,resultScrollGuardUntil=0,resultTouchY=null,currentShareSummary=null;
let practiceIndex=0,practiceCorrect=0,practiceAnswered=0,practiceLocked=false;
let scamTypes=[],scamTypesPromise=null,telephoneCatalog=null,selectedScamGroup='all',libraryQuery='',libraryScrollPosition=0;
const samples={
  'safe-balance':'Tài khoản thanh toán vừa nhận 1.250.000 đồng lúc 09:12. Nếu không nhận ra giao dịch, bác tự mở ứng dụng ngân hàng chính thức để kiểm tra.',
  'safe-appointment':'Hồ sơ cấp căn cước của bác đã có lịch trả vào thứ Sáu. Vui lòng mang giấy hẹn đến đúng trụ sở đã đăng ký để nhận kết quả.',
  'safe-delivery':'Bưu tá dự kiến giao đơn vào sáng thứ Hai. Bác có thể xem trạng thái bằng mã đơn trong ứng dụng nơi đã mua hàng.',
  'safe-pickup':'Chiều nay con đón bác ở cổng bệnh viện lúc 16 giờ như đã hẹn. Xe vẫn mang biển số quen thuộc nên bác cứ chờ ở sảnh chính.',
  'safe-payment':'Bác vui lòng thanh toán hóa đơn điện tháng này qua ứng dụng chính thức hoặc quầy thu quen thuộc. Không cần bấm vào liên kết lạ.',
  'danger-bank':'NGÂN HÀNG THÔNG BÁO: Tài khoản của quý khách đang bị tạm khóa. Vui lòng truy cập đường link bên dưới và nhập mã OTP để xác minh ngay.',
  'danger-delivery':'Đơn hàng của bạn chưa thể giao vì thiếu phí vận chuyển 25.000 đồng. Hãy bấm vào liên kết và thanh toán trong hôm nay để tránh hoàn hàng.',
  'danger-prize':'Chúc mừng bạn đã trúng giải thưởng 100 triệu đồng. Vui lòng chuyển trước 2 triệu đồng phí hồ sơ vào tài khoản cá nhân để nhận thưởng.',
  'danger-police':'Công an thông báo bác liên quan đến đường dây rửa tiền. Bác phải giữ bí mật cuộc gọi và chuyển tiền ngay để chứng minh trong sạch.',
  'danger-remote':'Nhân viên kỹ thuật ngân hàng cần bác cài AnyDesk để hỗ trợ khôi phục tài khoản và nhận lại số dư đang bị treo trong hệ thống.'
};
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
const viewTitles={analyze:'Kiểm tra',result:'Kết quả kiểm tra',library:'Thư viện lừa đảo',history:'Lịch sử',practice:'Luyện tập'};
const psychologyEmojiRules=[
  {pattern:/dừng|không làm theo|không chuyển|đừng vội/i,emoji:'🛑'},
  {pattern:/xác minh|kiểm tra|đối chiếu|nguồn chính thức/i,emoji:'🔎'},
  {pattern:/liên hệ|gọi|ngân hàng|người thân/i,emoji:'📞'},
  {pattern:/bình tĩnh|chậm lại|hít thở|thở sâu/i,emoji:'🌿'},
  {pattern:/lo lắng|sợ hãi|hoang mang|áp lực|thúc giục/i,emoji:'🫶'},
  {pattern:/an toàn|bảo vệ|giữ mình/i,emoji:'🛡️'}
];
const rescuePlans={
  none:{
    suspicious:[
      'Dừng trả lời người gửi và không làm theo yêu cầu trong tin nhắn.',
      'Không bấm liên kết, mở tệp hoặc gọi số điện thoại do người gửi cung cấp.',
      'Xác minh sự việc qua ứng dụng, trang web hoặc số điện thoại chính thức của đơn vị liên quan.',
      'Chụp màn hình, lưu thông tin người gửi rồi chặn và báo cáo tài khoản.'
    ],
    dangerous:[
      'Dừng toàn bộ liên lạc với người gửi ngay.',
      'Không bấm liên kết, mở tệp, chuyển tiền hoặc cung cấp bất kỳ mã xác thực nào.',
      'Chụp màn hình và lưu lại tin nhắn, số điện thoại, tài khoản cùng thời điểm nhận.',
      'Liên hệ đơn vị bị mạo danh bằng kênh chính thức để xác minh.',
      'Chặn và báo cáo tài khoản gửi tin nhắn.'
    ]
  },
  'opened-link':{
    suspicious:[
      'Đóng trang vừa mở và dừng mọi lượt tải xuống.',
      'Kiểm tra thư mục tải xuống và xóa tệp lạ khi chưa mở tệp.',
      'Quét bảo mật thiết bị và kiểm tra ứng dụng hoặc cấu hình lạ vừa được thêm.',
      'Đổi ngay mật khẩu liên quan bằng một thiết bị an toàn nếu bác đã nhập thông tin đăng nhập.',
      'Theo dõi đăng nhập và giao dịch bất thường trên các tài khoản liên quan.'
    ],
    dangerous:[
      'Đóng trang, ngắt lượt tải xuống và không mở bất kỳ tệp nào từ liên kết.',
      'Ngắt kết nối mạng nếu thiết bị vừa cài ứng dụng, cấu hình hoặc cấp quyền điều khiển.',
      'Gỡ ứng dụng hoặc cấu hình lạ rồi quét toàn bộ thiết bị bằng công cụ bảo mật tin cậy.',
      'Đổi mật khẩu từ một thiết bị an toàn và đăng xuất tất cả phiên đang hoạt động.',
      'Liên hệ ngay ngân hàng bằng số chính thức nếu bác đã nhập thông tin tài chính.'
    ]
  },
  'shared-info':{
    suspicious:[
      'Đổi ngay mật khẩu của tài khoản đã cung cấp và bật xác thực hai lớp.',
      'Đăng xuất tất cả phiên đang hoạt động và thu hồi quyền truy cập lạ.',
      'Liên hệ đơn vị quản lý tài khoản bằng kênh chính thức để báo lộ thông tin.',
      'Theo dõi cảnh báo đăng nhập, thay đổi hồ sơ và giao dịch bất thường.',
      'Lưu lại tin nhắn cùng thông tin người gửi để báo cáo khi cần.'
    ],
    dangerous:[
      'Khóa tạm thời tài khoản, thẻ hoặc dịch vụ có thông tin đã bị lộ.',
      'Đổi toàn bộ mật khẩu liên quan từ một thiết bị an toàn và bật xác thực hai lớp.',
      'Đăng xuất mọi phiên đang hoạt động và thu hồi thiết bị hoặc ứng dụng không nhận ra.',
      'Liên hệ ngay ngân hàng hoặc đơn vị quản lý bằng số chính thức để lập cảnh báo gian lận.',
      'Lưu bằng chứng và báo cáo sự việc cho cơ quan chức năng.'
    ]
  },
  'sent-money':{
    suspicious:[
      'Gọi ngay ngân hàng hoặc dịch vụ chuyển tiền bằng số chính thức để yêu cầu chặn hoặc thu hồi giao dịch.',
      'Khóa tạm thời tài khoản thanh toán và đổi mật khẩu đăng nhập.',
      'Lưu biên lai, mã giao dịch, tin nhắn và thông tin tài khoản nhận tiền.',
      'Báo cáo giao dịch gian lận cho ngân hàng và cơ quan chức năng.',
      'Không chuyển thêm tiền cho bất kỳ lời hứa hoàn tiền hoặc hỗ trợ thu hồi nào.'
    ],
    dangerous:[
      'Gọi ngay ngân hàng hoặc dịch vụ chuyển tiền bằng số chính thức để yêu cầu phong tỏa và thu hồi giao dịch.',
      'Khóa thẻ, tài khoản thanh toán và đổi mật khẩu từ một thiết bị an toàn.',
      'Lưu đầy đủ biên lai, mã giao dịch, nội dung trao đổi và thông tin tài khoản nhận tiền.',
      'Trình báo ngay với cơ quan chức năng và cung cấp toàn bộ bằng chứng.',
      'Dừng mọi khoản chuyển tiếp theo và không trả phí cho người tự nhận có thể lấy lại tiền.'
    ]
  }
};
