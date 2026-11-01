export type LangCode = "vi" | "en" | "ko" | "ja" | "zh";

export type LanguageOption = {
  code: LangCode;
  label: string;
  flag: string;
};

export const LANGUAGES: LanguageOption[] = [
  { code: "vi", label: "Tiếng Việt", flag: "🇻🇳" },
  { code: "en", label: "English", flag: "🇺🇸" },
  { code: "ko", label: "한국어", flag: "🇰🇷" },
  { code: "ja", label: "日本語", flag: "🇯🇵" },
  { code: "zh", label: "中文", flag: "🇨🇳" },
];

export type Translations = {
  locale: string;

  // Navigation
  navHome: string;
  navPlay: string;
  navTeam: string;
  navAreas: string;
  navNews: string;
  navLogin: string;
  navLogout: string;
  navAccount: string;

  // Hero
  heroEyebrow: string;
  heroTitle1: string;
  heroTitle2: string;
  heroDesc: string;
  heroCta: string;
  heroDate: string;

  // Mega Menu
  megaPublisher: string;
  megaAllPublishers: string;
  megaGames: string;
  megaEsports: string;
  megaSystem: string;
  megaAllTournaments: string;
  megaOngoing: string;
  megaUpcoming: string;
  megaCompleted: string;
  megaManageTeams: string;
  megaAreas: string;
  megaNews: string;
  megaCatalog: string;
  megaRules: string;
  megaNewBadge: string;
  megaLiveBadge: string;
  megaExploreNow: string;

  // Game Picker
  pickerHeaderEyebrow: string;
  pickerTitle: string;
  pickerSub: string;
  pickerPublisherLabel: string;
  pickerAllPubOption: string;
  pickerViewTournaments: string;
  pickerActiveDiscipline: string;
  pickerShowingTournamentsFor: string;
  pickerResetBtn: string;

  // Tournaments Main
  tournamentsEyebrowAll: string;
  tournamentsEyebrowGame: string;
  tournamentsHeadingOngoing: string;
  tournamentsHeadingGame: string;
  tournamentsSubAll: string;
  tournamentsSubGame: string;
  tournamentCountBadge: string;
  allGamesFilter: string;
  allStatusesFilter: string;
  allAreasFilter: string;
  statusUpcoming: string;
  statusOngoing: string;
  statusCompleted: string;
  statusCancelled: string;
  statusCardUpcoming: string;
  statusCardOngoing: string;
  statusCardCompleted: string;
  statusCardCancelled: string;
  btnRefresh: string;
  btnCreateTournament: string;
  btnDetails: string;
  btnRegister: string;
  cardViewDetails: string;
  cardOpenEnd: string;
  cardDatePrefix: string;
  noTournaments: string;
  noTournamentsSub: string;
  loadingTournaments: string;
  retry: string;
  pagePrev: string;
  pageNext: string;
  pageLabel: string;

  // Tournament Create Form
  tcTitle: string;
  tcNameLabel: string;
  tcNamePlaceholder: string;
  tcGameLabel: string;
  tcGameSelect: string;
  tcFormatLabel: string;
  tcStartLabel: string;
  tcEndLabel: string;
  tcAreaLabel: string;
  tcAreaGlobal: string;
  tcDescLabel: string;
  tcDescPlaceholder: string;
  tcSubmitBtn: string;

  // Tournament Detail Profile
  detailTitle: string;
  detailClose: string;
  detailStatus: string;
  detailRoster: string;
  detailRosterLocked: string;
  detailRosterUnlocked: string;
  detailStartDate: string;
  detailArea: string;
  detailGlobalArea: string;
  detailOpsTitle: string;
  detailLockRosterBtn: string;
  detailLockingRoster: string;
  detailRosterLockedNotice: string;
  detailConditionsTitle: string;
  detailConditionsDesc: string;
  detailNoApprovedTeams: string;
  detailMissingPlayersWarning: string;
  detailRosterReady: string;
  detailActionStart: string;
  detailActionComplete: string;
  detailActionCancel: string;
  detailActionReopen: string;

  // Stages
  stagesTitle: string;
  stagesAddBtn: string;
  stagesEmpty: string;
  stageNamePlaceholder: string;
  stageOrderPlaceholder: string;
  stageSaveBtn: string;
  stageCancelBtn: string;
  stageEditBtn: string;
  stageDeleteBtn: string;

  // Registrations
  regTitle: string;
  regEmpty: string;
  regSubmittedPrefix: string;
  regReasonPrefix: string;
  regApproveBtn: string;
  regRejectBtn: string;
  regCancelBtn: string;
  regFilterAll: string;

  // Areas Section
  areasTitle: string;
  areasSub: string;
  areasBadge: string;
  areasCountSuffix: string;
  areasTournamentCountSuffix: string;
  areasViewTournaments: string;
  areasSelectedAction: string;

  // News Section
  newsTitle: string;
  newsSub: string;
  newsBadge: string;
  newsLiveUpdates: string;
  newsReadMore: string;
  newsClose: string;
  newsBy: string;

  // Teams Section
  teamsTitle: string;
  teamsCount: string;
  teamNameLabel: string;
  teamTagLabel: string;
  teamGameLabel: string;
  teamGameSelectPlaceholder: string;
  teamCreateBtn: string;
  teamLoginRequired: string;
  teamEmpty: string;
  teamViewBtn: string;
  teamMembersTitle: string;
  teamAddMemberBtn: string;
  teamUsernamePlaceholder: string;
  teamRoleLabel: string;
  teamActiveStatus: string;
  teamLeftStatus: string;
  teamLeaveBtn: string;

  // User Profile
  profileTitle: string;
  profileRole: string;
  profileVerifiedEmail: string;
  profileSessionNote: string;
  profileWorkflowTitle: string;
  profileWorkflowItem1: string;
  profileWorkflowItem2: string;
  profileWorkflowItem3: string;
  profileWorkflowItem4: string;

  // Catalog
  catalogTitle: string;
  catalogAddPub: string;
  catalogAddGame: string;
  catalogAddArea: string;
  catalogReload: string;
  catalogSubtext: string;

  // Auth Dialog
  authWelcomeBack: string;
  authJoinArena: string;
  authLoginTitle: string;
  authRegisterTitle: string;
  authLoginDesc: string;
  authRegisterDesc: string;
  authFullName: string;
  authFullNamePlaceholder: string;
  authEmail: string;
  authUsername: string;
  authUsernamePlaceholder: string;
  authPassword: string;
  authPasswordHint: string;
  authSecureConnection: string;
  authProcessing: string;
  authBtnLogin: string;
  authBtnRegister: string;
  authSwitchToRegister: string;
  authSwitchToLogin: string;
  authCloseAria: string;
  regFormTitle: string;
  regSelectTeam: string;
  regSubmitBtn: string;
  regRosterLockedNotice: string;
  regRosterLockedReviewNotice: string;
  regListTitle: string;
  regTotalSuffix: string;
  regStatusPending: string;
  regStatusApproved: string;
  regStatusRejected: string;
  regStatusCancelled: string;
  teamJoinedPrefix: string;
  teamLeftPrefix: string;
  teamCloseBtn: string;
  teamNoMembers: string;
  megaAllGamesCount: string;
  megaGamesSuffix: string;
  emptyTournamentsTitle: string;
  emptyTournamentsSub: string;
  statusChangeTo: string;
  circuitHeaderTitle: string;
  circuitHeaderDesc: string;
  circuitAllTabs: string;
  circuitToggleShow: string;
  circuitToggleHide: string;
  circuitGameDescTemplate: string;
  detailConditionsHelp: string;
  detailNoApprovedTeamsWarning: string;
  detailDraftStatus: string;
  detailLockedStatus: string;
  detailRosterPlayerEmpty: string;
  detailRosterNoPlayers: string;
  detailSelectMemberToAdd: string;
  detailHasPlayer: string;
  detailMissingPlayer: string;
  navAdmin: string;
};

export const TRANSLATIONS: Record<LangCode, Translations> = {
  vi: {
    locale: "vi-VN",
    navHome: "Trang chủ",
    navPlay: "Giải đấu",
    navTeam: "Đội tuyển",
    navAreas: "Khu vực",
    navNews: "Tin tức",
    navLogin: "Đăng nhập",
    navLogout: "Đăng xuất",
    navAccount: "Tài khoản",

    heroEyebrow: "THẾ HỆ TRANH TÀI TIẾP THEO",
    heroTitle1: "Khẳng định bản lĩnh.",
    heroTitle2: "Thống trị đấu trường.",
    heroDesc: "Quản lý đội tuyển, khám phá giải đấu và đưa đội của bạn lên đỉnh vinh quang bảng xếp hạng.",
    heroCta: "Khám phá giải đấu",
    heroDate: "THÁNG 7 — THÁNG 8, 2027",

    megaPublisher: "NHÀ PHÁT HÀNH:",
    megaAllPublishers: "Tất cả Nhà phát hành",
    megaGames: "TRÒ CHƠI",
    megaEsports: "ESPORTS & GIẢI ĐẤU",
    megaSystem: "HỆ THỐNG",
    megaAllTournaments: "Tất cả giải đấu",
    megaOngoing: "Đang diễn ra",
    megaUpcoming: "Sắp diễn ra",
    megaCompleted: "Đã kết thúc",
    megaManageTeams: "Quản lý đội tuyển",
    megaAreas: "Khu vực thi đấu",
    megaNews: "Tin tức & Sự kiện",
    megaCatalog: "Dữ liệu & Catalog",
    megaRules: "Luật & Quy định",
    megaNewBadge: "MỚI",
    megaLiveBadge: "LIVE",
    megaExploreNow: "Khám phá giải đấu ngay",

    pickerHeaderEyebrow: "CHỌN TỰA GAME ĐỂ THAM GIA TRANH TÀI",
    pickerTitle: "Đấu trường trò chơi",
    pickerSub: "Chọn nhà phát hành (Riot Games, Garena) hoặc bấm vào tựa game để xem giải đấu tương ứng.",
    pickerPublisherLabel: "Nhà phát hành:",
    pickerAllPubOption: "Tất cả Nhà phát hành",
    pickerViewTournaments: "Khám phá giải đấu ↗",
    pickerActiveDiscipline: "BỘ MÔN THI ĐẤU ESPORTS",
    pickerShowingTournamentsFor: "Đang hiển thị danh sách các giải đấu và bảng đấu cho tựa game này",
    pickerResetBtn: "✕ Xem tất cả tựa game",

    tournamentsEyebrowAll: "HỆ THỐNG GIẢI ĐẤU",
    tournamentsEyebrowGame: "HỆ THỐNG GIẢI ĐẤU —",
    tournamentsHeadingOngoing: "Giải đấu đang diễn ra",
    tournamentsHeadingGame: "Giải đấu",
    tournamentsSubAll: "Khám phá lịch thi đấu, theo dõi trạng thái và vận hành giải từ một command center.",
    tournamentsSubGame: "Khám phá các giải đấu, lịch thi đấu và bảng đấu cho tựa game này.",
    tournamentCountBadge: "giải",
    allGamesFilter: "Tất cả tựa game",
    allStatusesFilter: "Tất cả trạng thái",
    allAreasFilter: "Tất cả khu vực",
    statusUpcoming: "Sắp diễn ra",
    statusOngoing: "Đang diễn ra",
    statusCompleted: "Đã kết thúc",
    statusCancelled: "Đã hủy",
    statusCardUpcoming: "SẮP DIỄN RA",
    statusCardOngoing: "LIVE NOW",
    statusCardCompleted: "ĐÃ KẾT THÚC",
    statusCardCancelled: "ĐÃ HỦY",
    btnRefresh: "Làm mới",
    btnCreateTournament: "Tạo giải đấu mới",
    btnDetails: "Xem chi tiết",
    btnRegister: "Đăng ký",
    cardViewDetails: "Xem chi tiết ↗",
    cardOpenEnd: "Chưa xác định",
    cardDatePrefix: "◷",
    noTournaments: "Không tìm thấy giải đấu phù hợp",
    noTournamentsSub: "Hãy thử thay đổi bộ lọc tựa game, trạng thái hoặc khu vực thi đấu.",
    loadingTournaments: "Đang đồng bộ dữ liệu giải đấu...",
    retry: "Thử lại",
    pagePrev: "Trước",
    pageNext: "Sau",
    pageLabel: "Trang",

    tcTitle: "Tạo giải đấu mới",
    tcNameLabel: "Tên giải đấu",
    tcNamePlaceholder: "VCT Vietnam — Stage 1",
    tcGameLabel: "Tựa game",
    tcGameSelect: "Chọn tựa game",
    tcFormatLabel: "Thể thức",
    tcStartLabel: "Bắt đầu",
    tcEndLabel: "Kết thúc",
    tcAreaLabel: "Khu vực",
    tcAreaGlobal: "Toàn cầu",
    tcDescLabel: "Mô tả",
    tcDescPlaceholder: "Thông tin giải, luật thi đấu, phần thưởng...",
    tcSubmitBtn: "Tạo giải đấu",

    detailTitle: "HỒ SƠ GIẢI ĐẤU",
    detailClose: "Đóng ×",
    detailStatus: "Trạng thái",
    detailRoster: "Đội hình",
    detailRosterLocked: "Đã khóa",
    detailRosterUnlocked: "Chưa khóa",
    detailStartDate: "Ngày bắt đầu",
    detailArea: "Khu vực",
    detailGlobalArea: "Toàn cầu",
    detailOpsTitle: "Điều hành giải",
    detailLockRosterBtn: "🔒 Khóa đội hình giải đấu",
    detailLockingRoster: "Đang khóa đội hình...",
    detailRosterLockedNotice: "Đội hình giải đấu đã được khóa",
    detailConditionsTitle: "Điều kiện bắt đầu giải đấu (chuyển sang ONGOING):",
    detailConditionsDesc: "Giải đấu cần phải khóa đội hình và mỗi đội đã duyệt phải có ít nhất một tuyển thủ (PLAYER).",
    detailNoApprovedTeams: "Chưa có đội tuyển nào được duyệt (APPROVED) vào giải đấu này.",
    detailMissingPlayersWarning: "Đội chưa có tuyển thủ PLAYER",
    detailRosterReady: "Tất cả các đội đã có PLAYER. Sẵn sàng để khóa đội hình!",
    detailActionStart: "▶ Bắt đầu giải (ONGOING)",
    detailActionComplete: "✓ Hoàn thành (COMPLETED)",
    detailActionCancel: "✕ Hủy giải (CANCELLED)",
    detailActionReopen: "↺ Mở lại đăng ký (UPCOMING)",

    stagesTitle: "Giai đoạn thi đấu",
    stagesAddBtn: "+ Thêm giai đoạn",
    stagesEmpty: "Chưa có giai đoạn nào cho giải đấu này.",
    stageNamePlaceholder: "Vòng bảng, Tứ kết, Chung kết...",
    stageOrderPlaceholder: "Thứ tự (1, 2, 3...)",
    stageSaveBtn: "Lưu",
    stageCancelBtn: "Hủy",
    stageEditBtn: "Sửa",
    stageDeleteBtn: "Xóa",

    regTitle: "Danh sách đăng ký",
    regEmpty: "Không có đơn đăng ký nào.",
    regSubmittedPrefix: "Gửi lúc",
    regReasonPrefix: "Lý do",
    regApproveBtn: "Duyệt",
    regRejectBtn: "Từ chối",
    regCancelBtn: "Hủy đơn",
    regFilterAll: "Tất cả đơn đăng ký",

    areasTitle: "Khu vực thi đấu",
    areasSub: "Khám phá các khu vực tranh tài chính thức từ cấp độ Toàn Cầu, Châu Á - Thái Bình Dương cho đến các giải đấu quốc nội và thành phố. Bấm vào khu vực để xem các giải đấu tương ứng.",
    areasBadge: "HỆ THỐNG GIẢI TOÀN CẦU",
    areasCountSuffix: "KHU VỰC",
    areasTournamentCountSuffix: "giải đấu",
    areasViewTournaments: "Xem giải đấu khu vực này →",
    areasSelectedAction: "Đang chọn • Bấm để xem tất cả",

    newsTitle: "Tin tức & Sự kiện",
    newsSub: "Cập nhật tin tức nóng hổi về lịch thi đấu, bảng xếp hạng, thị trường chuyển nhượng và những diễn biến hấp dẫn nhất từ các giải đấu.",
    newsBadge: "TIN TỨC & TIÊU ĐIỂM ESPORTS",
    newsLiveUpdates: "CẬP NHẬT 24/7",
    newsReadMore: "Đọc chi tiết ↗",
    newsClose: "Đóng bài viết",
    newsBy: "Bởi",

    teamsTitle: "Đội tuyển",
    teamsCount: "đội",
    teamNameLabel: "Tên đội",
    teamTagLabel: "Tag",
    teamGameLabel: "Game",
    teamGameSelectPlaceholder: "Chọn game",
    teamCreateBtn: "Tạo đội",
    teamLoginRequired: "Đăng nhập để tạo đội mới. Danh sách đội vẫn được xem công khai.",
    teamEmpty: "Chưa có đội tuyển.",
    teamViewBtn: "Xem đội",
    teamMembersTitle: "Thành viên và lịch sử",
    teamAddMemberBtn: "Thêm thành viên",
    teamUsernamePlaceholder: "Nhập username",
    teamRoleLabel: "Vị trí",
    teamActiveStatus: "Đang hoạt động",
    teamLeftStatus: "Đã rời đội",
    teamLeaveBtn: "Rời đội",

    profileTitle: "Tài khoản đã xác thực",
    profileRole: "Vai trò",
    profileVerifiedEmail: "Email đã được xác thực",
    profileSessionNote: "JWT đang được lưu trong trình duyệt và dùng cho các request cần xác thực.",
    profileWorkflowTitle: "Luồng quản lý đội",
    profileWorkflowItem1: "Tải danh sách game qua GET /catalog/games",
    profileWorkflowItem2: "Tải đội tuyển qua GET /teams",
    profileWorkflowItem3: "Tạo đội tuyển mới qua POST /teams",
    profileWorkflowItem4: "Người tạo đội tự động là MANAGER",

    catalogTitle: "Quản trị catalog",
    catalogAddPub: "Thêm publisher",
    catalogAddGame: "Thêm game",
    catalogAddArea: "Thêm khu vực",
    catalogReload: "Thử tải lại",
    catalogSubtext: "Danh sách catalog có thể chưa phản ánh thao tác gần nhất.",

    authWelcomeBack: "CHÀO MỪNG TRỞ LẠI",
    authJoinArena: "GIA NHẬP ĐẤU TRƯỜNG",
    authLoginTitle: "Đăng nhập",
    authRegisterTitle: "Đăng ký",
    authLoginDesc: "Đăng nhập để tiếp tục hành trình thi đấu của bạn.",
    authRegisterDesc: "Tạo tài khoản và bước vào đấu trường cạnh tranh.",
    authFullName: "Họ và tên",
    authFullNamePlaceholder: "Nhập tên hiển thị",
    authEmail: "Email",
    authUsername: "Tên đăng nhập",
    authUsernamePlaceholder: "Nhập username",
    authPassword: "Mật khẩu",
    authPasswordHint: "Tối thiểu 8 ký tự",
    authSecureConnection: "Kết nối bảo mật",
    authProcessing: "Đang xử lý...",
    authBtnLogin: "Đăng nhập",
    authBtnRegister: "Tạo tài khoản",
    authSwitchToRegister: "Chưa có tài khoản? Đăng ký",
    authSwitchToLogin: "Đã có tài khoản? Đăng nhập",
    authCloseAria: "Đóng giao diện đăng nhập",
    regFormTitle: "Đăng ký đội tham gia giải",
    regSelectTeam: "Chọn đội tuyển",
    regSubmitBtn: "Gửi đơn đăng ký",
    regRosterLockedNotice: "🔒 Đội hình giải đấu đã khóa — Không thể gửi đơn đăng ký mới.",
    regRosterLockedReviewNotice: "🔒 Đội hình giải đấu đã khóa — Thao tác duyệt đơn mới bị tạm dừng.",
    regListTitle: "Đơn đăng ký giải",
    regTotalSuffix: "đơn",
    regStatusPending: "Chờ duyệt",
    regStatusApproved: "Đã duyệt",
    regStatusRejected: "Từ chối",
    regStatusCancelled: "Đã hủy",
    teamJoinedPrefix: "Tham gia",
    teamLeftPrefix: "Rời đội",
    teamCloseBtn: "Đóng",
    teamNoMembers: "Chưa có thành viên.",
    megaAllGamesCount: "Hiển thị tất cả tựa game",
    megaGamesSuffix: "tựa game",
    emptyTournamentsTitle: "Chưa có giải đấu phù hợp",
    emptyTournamentsSub: "Thử thay đổi bộ lọc hoặc tạo giải đấu đầu tiên.",
    statusChangeTo: "Chuyển sang",
    circuitHeaderTitle: "Khu vực & Giải đấu chuyên nghiệp",
    circuitHeaderDesc: "Các khu vực thi đấu và hệ thống giải đấu chuyên nghiệp chính thức tương ứng với từng bộ môn.",
    circuitAllTabs: "Tất cả bộ môn",
    circuitToggleShow: "Xem 26 khu vực chuyên nghiệp theo game",
    circuitToggleHide: "Thu gọn khu vực thi đấu",
    circuitGameDescTemplate: "Hệ thống khu vực và giải đấu chuyên nghiệp chính thức của bộ môn {game}.",
    detailConditionsHelp: "Giải đấu cần phải khóa đội hình và mỗi đội đã duyệt phải có ít nhất một tuyển thủ (PLAYER). Nút \"Chuyển sang ONGOING\" sẽ tự động hiển thị sau khi khóa thành công.",
    detailNoApprovedTeamsWarning: "Chưa có đội tuyển nào được duyệt (APPROVED) vào giải.",
    detailDraftStatus: "📝 Bản nháp (Chưa khóa)",
    detailLockedStatus: "🔒 Đã khóa (Snapshot)",
    detailRosterPlayerEmpty: "Chưa có tuyển thủ nào trong đội hình tham dự.",
    detailRosterNoPlayers: "Đội tuyển chưa có danh sách tuyển thủ.",
    detailSelectMemberToAdd: "-- Chọn thành viên để thêm --",
    detailHasPlayer: "Đã có PLAYER",
    detailMissingPlayer: "Chưa có PLAYER",
    navAdmin: "Quản trị",
  },

  en: {
    locale: "en-US",
    navHome: "Home",
    navPlay: "Tournaments",
    navTeam: "Teams",
    navAreas: "Regions",
    navNews: "News",
    navLogin: "Sign In",
    navLogout: "Sign Out",
    navAccount: "Account",

    heroEyebrow: "THE NEXT GENERATION OF COMPETITION",
    heroTitle1: "Build your legacy.",
    heroTitle2: "Own the arena.",
    heroDesc: "Manage teams, discover premier tournaments, and lead your squad to the top of the leaderboards.",
    heroCta: "Explore Tournaments",
    heroDate: "JULY — AUGUST, 2027",

    megaPublisher: "PUBLISHER:",
    megaAllPublishers: "All Publishers",
    megaGames: "GAMES",
    megaEsports: "ESPORTS & TOURNAMENTS",
    megaSystem: "SYSTEM",
    megaAllTournaments: "All Tournaments",
    megaOngoing: "Ongoing",
    megaUpcoming: "Upcoming",
    megaCompleted: "Completed",
    megaManageTeams: "Manage Teams",
    megaAreas: "Competition Regions",
    megaNews: "News & Events",
    megaCatalog: "Data & Catalog",
    megaRules: "Rules & Guidelines",
    megaNewBadge: "NEW",
    megaLiveBadge: "LIVE",
    megaExploreNow: "Explore Tournaments Now",

    pickerHeaderEyebrow: "SELECT A GAME TO COMPETE",
    pickerTitle: "Game Arena",
    pickerSub: "Select a publisher (Riot Games, Garena) or click on any title to view corresponding tournaments.",
    pickerPublisherLabel: "Publisher:",
    pickerAllPubOption: "All Publishers",
    pickerViewTournaments: "Explore Tournaments ↗",
    pickerActiveDiscipline: "ESPORTS DISCIPLINE",
    pickerShowingTournamentsFor: "Displaying all active tournaments and brackets for this discipline",
    pickerResetBtn: "✕ View all games",

    tournamentsEyebrowAll: "ARENA CONTROL",
    tournamentsEyebrowGame: "ARENA CONTROL —",
    tournamentsHeadingOngoing: "Active Tournaments",
    tournamentsHeadingGame: "Tournaments",
    tournamentsSubAll: "Discover schedules, track live bracket status, and manage events from a unified command center.",
    tournamentsSubGame: "Discover active tournaments, live matches, and brackets for this discipline.",
    tournamentCountBadge: "tournaments",
    allGamesFilter: "All Games",
    allStatusesFilter: "All Statuses",
    allAreasFilter: "All Regions",
    statusUpcoming: "Upcoming",
    statusOngoing: "Live Now",
    statusCompleted: "Completed",
    statusCancelled: "Cancelled",
    statusCardUpcoming: "UPCOMING",
    statusCardOngoing: "LIVE NOW",
    statusCardCompleted: "COMPLETED",
    statusCardCancelled: "CANCELLED",
    btnRefresh: "Refresh",
    btnCreateTournament: "Create Tournament",
    btnDetails: "Details",
    btnRegister: "Register",
    cardViewDetails: "View Details ↗",
    cardOpenEnd: "Open end",
    cardDatePrefix: "◷",
    noTournaments: "No tournaments found",
    noTournamentsSub: "Try adjusting your game, status, or competition region filter.",
    loadingTournaments: "Syncing tournament data...",
    retry: "Retry",
    pagePrev: "Previous",
    pageNext: "Next",
    pageLabel: "Page",

    tcTitle: "Create New Tournament",
    tcNameLabel: "Tournament Name",
    tcNamePlaceholder: "VCT Regional — Stage 1",
    tcGameLabel: "Game",
    tcGameSelect: "Select a game",
    tcFormatLabel: "Format",
    tcStartLabel: "Start Date",
    tcEndLabel: "End Date",
    tcAreaLabel: "Region",
    tcAreaGlobal: "Global",
    tcDescLabel: "Description",
    tcDescPlaceholder: "Tournament rules, format, prize pool...",
    tcSubmitBtn: "Create Tournament",

    detailTitle: "TOURNAMENT PROFILE",
    detailClose: "Close ×",
    detailStatus: "Status",
    detailRoster: "Roster",
    detailRosterLocked: "Locked",
    detailRosterUnlocked: "Unlocked",
    detailStartDate: "Start Date",
    detailArea: "Region",
    detailGlobalArea: "Global",
    detailOpsTitle: "Tournament Ops",
    detailLockRosterBtn: "🔒 Lock Tournament Roster",
    detailLockingRoster: "Locking roster...",
    detailRosterLockedNotice: "Tournament roster is officially locked",
    detailConditionsTitle: "Tournament Start Conditions (switch to ONGOING):",
    detailConditionsDesc: "The tournament roster must be locked and each approved team must have at least one PLAYER.",
    detailNoApprovedTeams: "No teams have been APPROVED for this tournament yet.",
    detailMissingPlayersWarning: "Teams without any PLAYER",
    detailRosterReady: "All approved teams have PLAYER members. Ready to lock rosters!",
    detailActionStart: "▶ Start Tournament (ONGOING)",
    detailActionComplete: "✓ Mark Completed (COMPLETED)",
    detailActionCancel: "✕ Cancel Tournament (CANCELLED)",
    detailActionReopen: "↺ Reopen Registrations (UPCOMING)",

    stagesTitle: "Tournament Stages",
    stagesAddBtn: "+ Add Stage",
    stagesEmpty: "No stages defined for this tournament yet.",
    stageNamePlaceholder: "Group Stage, Quarterfinals, Finals...",
    stageOrderPlaceholder: "Order (1, 2, 3...)",
    stageSaveBtn: "Save",
    stageCancelBtn: "Cancel",
    stageEditBtn: "Edit",
    stageDeleteBtn: "Delete",

    regTitle: "Registrations",
    regEmpty: "No registrations found.",
    regSubmittedPrefix: "Submitted",
    regReasonPrefix: "Reason",
    regApproveBtn: "Approve",
    regRejectBtn: "Reject",
    regCancelBtn: "Cancel",
    regFilterAll: "All Registrations",

    areasTitle: "Competition Regions",
    areasSub: "Explore official competitive circuits from Global and Asia-Pacific to national leagues and metropolitan circuits. Click any region to filter corresponding tournaments.",
    areasBadge: "GLOBAL CIRCUIT SYSTEM",
    areasCountSuffix: "REGIONS",
    areasTournamentCountSuffix: "tournaments",
    areasViewTournaments: "View tournaments in this region →",
    areasSelectedAction: "Currently selected • Click to view all",

    newsTitle: "News & Highlights",
    newsSub: "Stay updated with breaking tournament news, official standings, roster transfers, and competitive esports highlights.",
    newsBadge: "ESPORTS DISPATCH & HIGHLIGHTS",
    newsLiveUpdates: "UPDATES 24/7",
    newsReadMore: "Read Full Story ↗",
    newsClose: "Close Article",
    newsBy: "By",

    teamsTitle: "Teams",
    teamsCount: "teams",
    teamNameLabel: "Team Name",
    teamTagLabel: "Team Tag",
    teamGameLabel: "Game",
    teamGameSelectPlaceholder: "Select Game",
    teamCreateBtn: "Create Team",
    teamLoginRequired: "Sign in to create a new squad. Team rosters are publicly viewable.",
    teamEmpty: "No teams registered yet.",
    teamViewBtn: "View Team",
    teamMembersTitle: "Members & History",
    teamAddMemberBtn: "Add Member",
    teamUsernamePlaceholder: "Enter username",
    teamRoleLabel: "Role",
    teamActiveStatus: "Active",
    teamLeftStatus: "Left Team",
    teamLeaveBtn: "Leave Team",

    profileTitle: "Authenticated Profile",
    profileRole: "Role",
    profileVerifiedEmail: "Verified Email",
    profileSessionNote: "JWT securely stored in browser for authenticated requests.",
    profileWorkflowTitle: "Team Workflow",
    profileWorkflowItem1: "Load games via GET /catalog/games",
    profileWorkflowItem2: "Load teams via GET /teams",
    profileWorkflowItem3: "Create new team via POST /teams",
    profileWorkflowItem4: "Creator is automatically assigned as MANAGER",

    catalogTitle: "Catalog Administration",
    catalogAddPub: "Add Publisher",
    catalogAddGame: "Add Game",
    catalogAddArea: "Add Region",
    catalogReload: "Reload Catalog",
    catalogSubtext: "Catalog listing may not reflect recent mutations yet.",

    authWelcomeBack: "WELCOME BACK",
    authJoinArena: "JOIN THE ARENA",
    authLoginTitle: "Sign In",
    authRegisterTitle: "Create Account",
    authLoginDesc: "Sign in to continue your competitive journey.",
    authRegisterDesc: "Create your account and step into the arena.",
    authFullName: "Full Name",
    authFullNamePlaceholder: "Enter display name",
    authEmail: "Email",
    authUsername: "Username",
    authUsernamePlaceholder: "Enter username",
    authPassword: "Password",
    authPasswordHint: "Minimum 8 characters",
    authSecureConnection: "Secure Connection",
    authProcessing: "Processing...",
    authBtnLogin: "Sign In",
    authBtnRegister: "Create Account",
    authSwitchToRegister: "Don't have an account? Sign Up",
    authSwitchToLogin: "Already have an account? Sign In",
    authCloseAria: "Close authentication modal",
    regFormTitle: "Register Team for Tournament",
    regSelectTeam: "Select Team",
    regSubmitBtn: "Submit Registration",
    regRosterLockedNotice: "🔒 Tournament roster is locked — New registrations are closed.",
    regRosterLockedReviewNotice: "🔒 Tournament roster is locked — New approvals are paused.",
    regListTitle: "Tournament Registrations",
    regTotalSuffix: "entries",
    regStatusPending: "Pending",
    regStatusApproved: "Approved",
    regStatusRejected: "Rejected",
    regStatusCancelled: "Cancelled",
    teamJoinedPrefix: "Joined",
    teamLeftPrefix: "Left",
    teamCloseBtn: "Close",
    teamNoMembers: "No members yet.",
    megaAllGamesCount: "Display all games",
    megaGamesSuffix: "games",
    emptyTournamentsTitle: "No matching tournaments",
    emptyTournamentsSub: "Try adjusting filters or create the first tournament.",
    statusChangeTo: "Switch to",
    circuitHeaderTitle: "Official Regional Circuits",
    circuitHeaderDesc: "Official competitive regions and premier professional league circuits for each discipline.",
    circuitAllTabs: "All Disciplines",
    circuitToggleShow: "View 26 official circuits by game",
    circuitToggleHide: "Collapse regional circuits",
    circuitGameDescTemplate: "Official regional circuits and premier leagues for {game}.",
    detailConditionsHelp: "Tournament roster must be locked and each approved team must have at least one PLAYER. 'Move to ONGOING' will be enabled once locked.",
    detailNoApprovedTeamsWarning: "No teams have been approved into this tournament yet.",
    detailDraftStatus: "📝 Draft (Unlocked)",
    detailLockedStatus: "🔒 Locked (Snapshot)",
    detailRosterPlayerEmpty: "No players in this roster yet.",
    detailRosterNoPlayers: "Team has no member roster.",
    detailSelectMemberToAdd: "-- Select member to add --",
    detailHasPlayer: "Has PLAYER",
    detailMissingPlayer: "Missing PLAYER",
    navAdmin: "Admin",
  },

  ko: {
    locale: "ko-KR",
    navHome: "홈",
    navPlay: "토너먼트",
    navTeam: "팀",
    navAreas: "지역",
    navNews: "뉴스",
    navLogin: "로그인",
    navLogout: "로그아웃",
    navAccount: "계정",

    heroEyebrow: "차세대 e스포츠 경쟁",
    heroTitle1: "당신의 전설을 쓰다.",
    heroTitle2: "전장을 지배하라.",
    heroDesc: "팀을 관리하고, 최고의 대회를 탐색하여 팀을 순위표 정상으로 이끄세요.",
    heroCta: "토너먼트 탐색",
    heroDate: "2027년 7월 — 8월",

    megaPublisher: "퍼블리셔:",
    megaAllPublishers: "모든 퍼블리셔",
    megaGames: "게임 종목",
    megaEsports: "e스포츠 및 토너먼트",
    megaSystem: "시스템",
    megaAllTournaments: "모든 토너먼트",
    megaOngoing: "진행 중",
    megaUpcoming: "개최 예정",
    megaCompleted: "종료됨",
    megaManageTeams: "팀 관리",
    megaAreas: "경기 지역",
    megaNews: "뉴스 및 이벤트",
    megaCatalog: "데이터 및 카탈로그",
    megaRules: "규정 및 규칙",
    megaNewBadge: "신규",
    megaLiveBadge: "LIVE",
    megaExploreNow: "지금 토너먼트 둘러보기",

    pickerHeaderEyebrow: "참가할 게임 종목을 선택하세요",
    pickerTitle: "게임 아레나",
    pickerSub: "퍼블리셔(Riot Games, Garena)를 선택하거나 게임을 클릭하여 관련 대회를 확인하세요.",
    pickerPublisherLabel: "퍼블리셔:",
    pickerAllPubOption: "모든 퍼블리셔",
    pickerViewTournaments: "토너먼트 탐색 ↗",
    pickerActiveDiscipline: "e스포츠 공식 종목",
    pickerShowingTournamentsFor: "이 종목에 등록된 모든 토너먼트 및 대진표를 표시합니다",
    pickerResetBtn: "✕ 모든 게임 보기",

    tournamentsEyebrowAll: "아레나 컨트롤",
    tournamentsEyebrowGame: "아레나 컨트롤 —",
    tournamentsHeadingOngoing: "진행 중인 토너먼트",
    tournamentsHeadingGame: "토너먼트",
    tournamentsSubAll: "통합 사령부에서 경기 일정을 확인하고, 실시간 상태를 추적하며 대회를 운영하세요.",
    tournamentsSubGame: "이 종목의 공식 토너먼트, 경기 일정 및 대진표를 확인하세요.",
    tournamentCountBadge: "개 대회",
    allGamesFilter: "모든 게임",
    allStatusesFilter: "모든 상태",
    allAreasFilter: "모든 지역",
    statusUpcoming: "예정됨",
    statusOngoing: "진행 중",
    statusCompleted: "종료됨",
    statusCancelled: "취소됨",
    statusCardUpcoming: "개최 예정",
    statusCardOngoing: "LIVE NOW",
    statusCardCompleted: "종료됨",
    statusCardCancelled: "취소됨",
    btnRefresh: "새로고침",
    btnCreateTournament: "새 대회 생성",
    btnDetails: "상세보기",
    btnRegister: "참가 신청",
    cardViewDetails: "상세보기 ↗",
    cardOpenEnd: "미정",
    cardDatePrefix: "◷",
    noTournaments: "조건에 맞는 대회가 없습니다",
    noTournamentsSub: "게임 종목, 상태 또는 지역 필터를 변경해 보세요.",
    loadingTournaments: "토너먼트 데이터를 동기화 중...",
    retry: "다시 시도",
    pagePrev: "이전",
    pageNext: "다음",
    pageLabel: "페이지",

    tcTitle: "새 토너먼트 만들기",
    tcNameLabel: "대회명",
    tcNamePlaceholder: "VCT 코리아 — 스테이지 1",
    tcGameLabel: "게임 종목",
    tcGameSelect: "게임 선택",
    tcFormatLabel: "대회 포맷",
    tcStartLabel: "시작일",
    tcEndLabel: "종료일",
    tcAreaLabel: "지역",
    tcAreaGlobal: "글로벌",
    tcDescLabel: "대회 설명",
    tcDescPlaceholder: "대회 규정, 상금, 세부 사항...",
    tcSubmitBtn: "토너먼트 생성",

    detailTitle: "토너먼트 프로필",
    detailClose: "닫기 ×",
    detailStatus: "상태",
    detailRoster: "로스터",
    detailRosterLocked: "잠김",
    detailRosterUnlocked: "미잠금",
    detailStartDate: "시작일",
    detailArea: "지역",
    detailGlobalArea: "글로벌",
    detailOpsTitle: "대회 운영",
    detailLockRosterBtn: "🔒 토너먼트 로스터 잠금",
    detailLockingRoster: "로스터 잠금 중...",
    detailRosterLockedNotice: "토너먼트 로스터가 공식적으로 잠겼습니다",
    detailConditionsTitle: "대회 시작 조건 (ONGOING 전환):",
    detailConditionsDesc: "로스터가 잠겨 있어야 하며, 승인된 각 팀에 최소 1명의 선수(PLAYER)가 있어야 합니다.",
    detailNoApprovedTeams: "이 대회에 아직 승인(APPROVED)된 팀이 없습니다.",
    detailMissingPlayersWarning: "선수가 없는 팀",
    detailRosterReady: "모든 승인 팀에 선수가 등록되었습니다. 로스터 잠금 준비 완료!",
    detailActionStart: "▶ 대회 시작 (ONGOING)",
    detailActionComplete: "✓ 완료 처리 (COMPLETED)",
    detailActionCancel: "✕ 대회 취소 (CANCELLED)",
    detailActionReopen: "↺ 참가 재개 (UPCOMING)",

    stagesTitle: "대회 스테이지",
    stagesAddBtn: "+ 스테이지 추가",
    stagesEmpty: "아직 등록된 스테이지가 없습니다.",
    stageNamePlaceholder: "그룹 스테이지, 8강, 결승전...",
    stageOrderPlaceholder: "순서 (1, 2, 3...)",
    stageSaveBtn: "저장",
    stageCancelBtn: "취소",
    stageEditBtn: "수정",
    stageDeleteBtn: "삭제",

    regTitle: "참가 신청 목록",
    regEmpty: "신청 내역이 없습니다.",
    regSubmittedPrefix: "신청일",
    regReasonPrefix: "사유",
    regApproveBtn: "승인",
    regRejectBtn: "거절",
    regCancelBtn: "취소",
    regFilterAll: "모든 참가 신청",

    areasTitle: "경기 지역",
    areasSub: "글로벌 및 아시아 태평양 서킷부터 국가별 리그 및 도시 대항전까지 공식 경쟁 지역을 탐색하세요. 지역을 클릭하면 관련 대회를 볼 수 있습니다.",
    areasBadge: "글로벌 서킷 시스템",
    areasCountSuffix: "개 지역",
    areasTournamentCountSuffix: "개 대회",
    areasViewTournaments: "이 지역의 대회 보기 →",
    areasSelectedAction: "선택됨 • 전체 보려면 클릭",

    newsTitle: "뉴스 및 이벤트",
    newsSub: "경기 일정, 공식 순위, 이적 시장 소식 및 흥미진진한 e스포츠 하이라이트를 실시간으로 확인하세요.",
    newsBadge: "e스포츠 속보 및 하이라이트",
    newsLiveUpdates: "24/7 실시간 업데이트",
    newsReadMore: "자세히 보기 ↗",
    newsClose: "기사 닫기",
    newsBy: "작성자:",

    teamsTitle: "팀",
    teamsCount: "개 팀",
    teamNameLabel: "팀 이름",
    teamTagLabel: "팀 태그",
    teamGameLabel: "종목",
    teamGameSelectPlaceholder: "게임 선택",
    teamCreateBtn: "팀 생성",
    teamLoginRequired: "새 팀을 만들려면 로그인하세요. 팀 목록은 누구나 볼 수 있습니다.",
    teamEmpty: "등록된 팀이 없습니다.",
    teamViewBtn: "팀 보기",
    teamMembersTitle: "팀원 및 이력",
    teamAddMemberBtn: "멤버 추가",
    teamUsernamePlaceholder: "사용자명 입력",
    teamRoleLabel: "역할",
    teamActiveStatus: "활동 중",
    teamLeftStatus: "팀 탈퇴",
    teamLeaveBtn: "팀 탈퇴",

    profileTitle: "인증된 프로필",
    profileRole: "역할",
    profileVerifiedEmail: "인증된 이메일",
    profileSessionNote: "인증 요청을 위해 브라우저에 JWT가 안전하게 보관됩니다.",
    profileWorkflowTitle: "팀 관리 프로세스",
    profileWorkflowItem1: "GET /catalog/games로 게임 목록 조회",
    profileWorkflowItem2: "GET /teams로 팀 목록 조회",
    profileWorkflowItem3: "POST /teams로 새 팀 창단",
    profileWorkflowItem4: "창단자는 자동으로 MANAGER 권한을 부여받습니다",

    catalogTitle: "카탈로그 관리",
    catalogAddPub: "퍼블리셔 추가",
    catalogAddGame: "게임 추가",
    catalogAddArea: "지역 추가",
    catalogReload: "다시 불러오기",
    catalogSubtext: "카탈로그 목록에 최근 변경 사항이 즉시 반영되지 않을 수 있습니다.",

    authWelcomeBack: "다시 오신 것을 환영합니다",
    authJoinArena: "아레나에 합류하세요",
    authLoginTitle: "로그인",
    authRegisterTitle: "회원가입",
    authLoginDesc: "경쟁 여정을 계속하려면 로그인하세요.",
    authRegisterDesc: "계정을 생성하고 전장에 참여하세요.",
    authFullName: "성명",
    authFullNamePlaceholder: "표시 이름 입력",
    authEmail: "이메일",
    authUsername: "아이디",
    authUsernamePlaceholder: "아이디 입력",
    authPassword: "비밀번호",
    authPasswordHint: "최소 8자 이상",
    authSecureConnection: "보안 연결",
    authProcessing: "처리 중...",
    authBtnLogin: "로그인",
    authBtnRegister: "계정 생성",
    authSwitchToRegister: "계정이 없으신가요? 회원가입",
    authSwitchToLogin: "이미 계정이 있으신가요? 로그인",
    authCloseAria: "로그인 창 닫기",
    regFormTitle: "대회 참가 신청",
    regSelectTeam: "팀 선택",
    regSubmitBtn: "참가 신청서 제출",
    regRosterLockedNotice: "🔒 로스터가 잠겼습니다 — 신규 참가 신청이 마감되었습니다.",
    regRosterLockedReviewNotice: "🔒 로스터가 잠겼습니다 — 신규 승인 처리가 일시 중단되었습니다.",
    regListTitle: "대회 참가 신청 내역",
    regTotalSuffix: "건",
    regStatusPending: "승인 대기",
    regStatusApproved: "승인됨",
    regStatusRejected: "거절됨",
    regStatusCancelled: "취소됨",
    teamJoinedPrefix: "가입일",
    teamLeftPrefix: "탈퇴일",
    teamCloseBtn: "닫기",
    teamNoMembers: "등록된 멤버가 없습니다.",
    megaAllGamesCount: "모든 게임 표시",
    megaGamesSuffix: "개 게임",
    emptyTournamentsTitle: "조건에 맞는 대회가 없습니다",
    emptyTournamentsSub: "필터를 변경하거나 첫 번째 대회를 만들어 보세요.",
    statusChangeTo: "상태 변경:",
    circuitHeaderTitle: "공식 지역 리그 및 서킷",
    circuitHeaderDesc: "각 종목별 공식 프로 리그 및 지역별 챔피언십 서킷입니다.",
    circuitAllTabs: "모든 종목",
    circuitToggleShow: "종목별 26개 공식 리그 보기",
    circuitToggleHide: "지역 리그 접기",
    circuitGameDescTemplate: "{game}의 공식 지역 리그 및 서킷 시스템.",
    detailConditionsHelp: "토너먼트 로스터를 잠가야 하며 각 승인된 팀에는 최소 한 명의 선수(PLAYER)가 있어야 합니다. 잠금 후 '진행 중으로 변경' 버튼이 활성화됩니다.",
    detailNoApprovedTeamsWarning: "이 토너먼트에 승인된 팀이 아직 없습니다.",
    detailDraftStatus: "📝 임시 명단 (미잠금)",
    detailLockedStatus: "🔒 잠김 (스냅샷)",
    detailRosterPlayerEmpty: "참가 로스터에 선수가 없습니다.",
    detailRosterNoPlayers: "팀에 멤버 로스터가 없습니다.",
    detailSelectMemberToAdd: "-- 추가할 멤버 선택 --",
    detailHasPlayer: "선수 등록됨",
    detailMissingPlayer: "선수 없음",
    navAdmin: "관리",
  },

  ja: {
    locale: "ja-JP",
    navHome: "ホーム",
    navPlay: "大会",
    navTeam: "チーム",
    navAreas: "地域",
    navNews: "ニュース",
    navLogin: "ログイン",
    navLogout: "ログアウト",
    navAccount: "アカウント",

    heroEyebrow: "次世代のeスポーツ競技",
    heroTitle1: "伝説を築け。",
    heroTitle2: "アリーナを支配せよ。",
    heroDesc: "チームを管理し、公式トーナメントに挑み、ランキングの頂点を目指しましょう。",
    heroCta: "大会を探す",
    heroDate: "2027年7月 — 8月",

    megaPublisher: "パブリッシャー:",
    megaAllPublishers: "すべてのパブリッシャー",
    megaGames: "ゲームタイトル",
    megaEsports: "eスポーツ＆大会",
    megaSystem: "システム",
    megaAllTournaments: "すべての大会",
    megaOngoing: "開催中",
    megaUpcoming: "開催予定",
    megaCompleted: "終了済み",
    megaManageTeams: "チーム管理",
    megaAreas: "競技地域",
    megaNews: "ニュース＆イベント",
    megaCatalog: "データ＆カタログ",
    megaRules: "規約＆ルール",
    megaNewBadge: "NEW",
    megaLiveBadge: "LIVE",
    megaExploreNow: "大会を今すぐチェック",

    pickerHeaderEyebrow: "参戦するゲームタイトルを選択",
    pickerTitle: "ゲームアリーナ",
    pickerSub: "パブリッシャー(Riot Games, Garena)を選択するか、タイトルをクリックして大会を確認してください。",
    pickerPublisherLabel: "パブリッシャー:",
    pickerAllPubOption: "すべてのパブリッシャー",
    pickerViewTournaments: "大会を見る ↗",
    pickerActiveDiscipline: "eスポーツ公式競技",
    pickerShowingTournamentsFor: "このタイトルの公式大会およびトーナメント表を表示中",
    pickerResetBtn: "✕ すべてのゲームを表示",

    tournamentsEyebrowAll: "アリーナコントロール",
    tournamentsEyebrowGame: "アリーナコントロール —",
    tournamentsHeadingOngoing: "開催中のトーナメント",
    tournamentsHeadingGame: "大会",
    tournamentsSubAll: "統一コマンドセンターから日程を確認し、進行状況を追跡・運営します。",
    tournamentsSubGame: "このタイトルの公式大会、試合日程、対戦表をご覧ください。",
    tournamentCountBadge: "大会",
    allGamesFilter: "すべてのゲーム",
    allStatusesFilter: "すべてのステータス",
    allAreasFilter: "すべての地域",
    statusUpcoming: "開催予定",
    statusOngoing: "進行中",
    statusCompleted: "終了",
    statusCancelled: "中止",
    statusCardUpcoming: "開催予定",
    statusCardOngoing: "LIVE NOW",
    statusCardCompleted: "終了",
    statusCardCancelled: "中止",
    btnRefresh: "更新",
    btnCreateTournament: "大会を作成",
    btnDetails: "詳細",
    btnRegister: "エントリー",
    cardViewDetails: "詳細を見る ↗",
    cardOpenEnd: "未定",
    cardDatePrefix: "◷",
    noTournaments: "該当する大会がありません",
    noTournamentsSub: "ゲームタイトルや地域、ステータスのフィルターを変更してみてください。",
    loadingTournaments: "大会データを同期中...",
    retry: "再試行",
    pagePrev: "前へ",
    pageNext: "次へ",
    pageLabel: "ページ",

    tcTitle: "新規大会の作成",
    tcNameLabel: "大会名",
    tcNamePlaceholder: "VCT Japan — Stage 1",
    tcGameLabel: "タイトル",
    tcGameSelect: "タイトルを選択",
    tcFormatLabel: "形式",
    tcStartLabel: "開始日",
    tcEndLabel: "終了日",
    tcAreaLabel: "地域",
    tcAreaGlobal: "グローバル",
    tcDescLabel: "説明",
    tcDescPlaceholder: "大会ルール、賞金、詳細...",
    tcSubmitBtn: "大会を作成する",

    detailTitle: "トーナメント概要",
    detailClose: "閉じる ×",
    detailStatus: "ステータス",
    detailRoster: "ロスター",
    detailRosterLocked: "確定済み",
    detailRosterUnlocked: "未確定",
    detailStartDate: "開始日",
    detailArea: "地域",
    detailGlobalArea: "グローバル",
    detailOpsTitle: "大会運営",
    detailLockRosterBtn: "🔒 ロスターを確定する",
    detailLockingRoster: "ロスター確定中...",
    detailRosterLockedNotice: "ロスターが確定されました",
    detailConditionsTitle: "大会開始要件 (ONGOINGへ移行):",
    detailConditionsDesc: "ロスターが確定しており、承認された各チームに最低1名の選手(PLAYER)が必要です。",
    detailNoApprovedTeams: "この大会で承認されたチームがまだありません。",
    detailMissingPlayersWarning: "選手が不足しているチーム",
    detailRosterReady: "すべての承認チームに選手が登録されました。確定可能です！",
    detailActionStart: "▶ 大会開始 (ONGOING)",
    detailActionComplete: "✓ 完了にする (COMPLETED)",
    detailActionCancel: "✕ 中止する (CANCELLED)",
    detailActionReopen: "↺ エントリー再開 (UPCOMING)",

    stagesTitle: "大会ステージ",
    stagesAddBtn: "+ ステージを追加",
    stagesEmpty: "この大会にはステージがまだ登録されていません。",
    stageNamePlaceholder: "グループステージ、準々決勝、決勝...",
    stageOrderPlaceholder: "順序 (1, 2, 3...)",
    stageSaveBtn: "保存",
    stageCancelBtn: "キャンセル",
    stageEditBtn: "編集",
    stageDeleteBtn: "削除",

    regTitle: "エントリー一覧",
    regEmpty: "エントリーはありません。",
    regSubmittedPrefix: "申請日時",
    regReasonPrefix: "理由",
    regApproveBtn: "承認",
    regRejectBtn: "却下",
    regCancelBtn: "取消",
    regFilterAll: "すべてのエントリー",

    areasTitle: "競技地域",
    areasSub: "グローバルからアジア太平洋、国内トップリーグ、地域サーキットまで、公式競技エリアを探索できます。地域を選択すると該当大会を表示します。",
    areasBadge: "公式サーキットシステム",
    areasCountSuffix: "地域",
    areasTournamentCountSuffix: "大会",
    areasViewTournaments: "この地域の大会を見る →",
    areasSelectedAction: "選択中 • すべて見るにはクリック",

    newsTitle: "ニュース＆イベント",
    newsSub: "大会日程、公式順位、移籍情報、注目のeスポーツハイライトを随時お届けします。",
    newsBadge: "eスポーツ速報＆ハイライト",
    newsLiveUpdates: "24時間更新",
    newsReadMore: "記事を読む ↗",
    newsClose: "閉じる",
    newsBy: "著者:",

    teamsTitle: "チーム",
    teamsCount: "チーム",
    teamNameLabel: "チーム名",
    teamTagLabel: "タグ",
    teamGameLabel: "タイトル",
    teamGameSelectPlaceholder: "ゲームを選択",
    teamCreateBtn: "チーム作成",
    teamLoginRequired: "チームを作成するにはログインしてください。チーム一覧は公開されています。",
    teamEmpty: "チームが登録されていません。",
    teamViewBtn: "チームを見る",
    teamMembersTitle: "メンバーと履歴",
    teamAddMemberBtn: "メンバー追加",
    teamUsernamePlaceholder: "ユーザー名",
    teamRoleLabel: "役割",
    teamActiveStatus: "所属中",
    teamLeftStatus: "脱退済み",
    teamLeaveBtn: "脱退する",

    profileTitle: "認証済みプロフィール",
    profileRole: "権限",
    profileVerifiedEmail: "認証済みメール",
    profileSessionNote: "認証リクエスト用のJWTがブラウザに安全に保存されています。",
    profileWorkflowTitle: "チーム運営の流れ",
    profileWorkflowItem1: "GET /catalog/games でタイトル取得",
    profileWorkflowItem2: "GET /teams でチーム一覧取得",
    profileWorkflowItem3: "POST /teams で新チームを作成",
    profileWorkflowItem4: "作成者には自動的にMANAGER権限が付与されます",

    catalogTitle: "カタログ管理",
    catalogAddPub: "パブリッシャー追加",
    catalogAddGame: "ゲーム追加",
    catalogAddArea: "地域追加",
    catalogReload: "再読み込み",
    catalogSubtext: "カタログ一覧に最新の変更が即時反映されない場合があります。",

    authWelcomeBack: "おかえりなさい",
    authJoinArena: "アリーナに参加",
    authLoginTitle: "ログイン",
    authRegisterTitle: "新規登録",
    authLoginDesc: "ログインして対戦を続けましょう。",
    authRegisterDesc: "アカウントを作成してアリーナへ参戦しよう。",
    authFullName: "氏名",
    authFullNamePlaceholder: "表示名を入力",
    authEmail: "メールアドレス",
    authUsername: "ユーザー名",
    authUsernamePlaceholder: "ユーザー名を入力",
    authPassword: "パスワード",
    authPasswordHint: "8文字以上",
    authSecureConnection: "暗号化接続",
    authProcessing: "処理中...",
    authBtnLogin: "ログイン",
    authBtnRegister: "アカウント作成",
    authSwitchToRegister: "アカウントをお持ちでない方 新規登録",
    authSwitchToLogin: "すでにアカウントをお持ちの方 ログイン",
    authCloseAria: "ログイン画面を閉じる",
    regFormTitle: "大会エントリー",
    regSelectTeam: "チームを選択",
    regSubmitBtn: "エントリーを送信",
    regRosterLockedNotice: "🔒 ロスター確定済み — 新規エントリーは締め切られました。",
    regRosterLockedReviewNotice: "🔒 ロスター確定済み — 新規承認は停止されています。",
    regListTitle: "エントリー一覧",
    regTotalSuffix: "件",
    regStatusPending: "承認待ち",
    regStatusApproved: "承認済み",
    regStatusRejected: "却下",
    regStatusCancelled: "取消",
    teamJoinedPrefix: "加入",
    teamLeftPrefix: "脱退",
    teamCloseBtn: "閉じる",
    teamNoMembers: "メンバーはいません。",
    megaAllGamesCount: "すべてのゲームを表示",
    megaGamesSuffix: "タイトル",
    emptyTournamentsTitle: "該当する大会がありません",
    emptyTournamentsSub: "フィルターを変更するか、最初の大会を作成してください。",
    statusChangeTo: "ステータス変更:",
    circuitHeaderTitle: "公式地域リーグ＆サーキット",
    circuitHeaderDesc: "各競技タイトルごとの公式プロリーグおよび地域別チャンピオンシップです。",
    circuitAllTabs: "すべての種目",
    circuitToggleShow: "ゲーム別公式26地域サーキットを表示",
    circuitToggleHide: "地域サーキットを折りたたむ",
    circuitGameDescTemplate: "{game}の公式地域リーグ＆サーキット体系。",
    detailConditionsHelp: "トーナメントのロスターをロックする必要があり、各承認済みチームには少なくとも1名の選手（PLAYER）が必要です。ロック後に「進行中に変更」が有効になります。",
    detailNoApprovedTeamsWarning: "このトーナメントに承認されたチームはまだありません。",
    detailDraftStatus: "📝 下書き（未ロック）",
    detailLockedStatus: "🔒 ロック済み（スナップショット）",
    detailRosterPlayerEmpty: "参加ロスターに選手がいません。",
    detailRosterNoPlayers: "チームにメンバーロスターがありません。",
    detailSelectMemberToAdd: "-- 追加するメンバーを選択 --",
    detailHasPlayer: "PLAYER登録済み",
    detailMissingPlayer: "PLAYER未登録",
    navAdmin: "管理",
  },

  zh: {
    locale: "zh-CN",
    navHome: "首页",
    navPlay: "赛事",
    navTeam: "战队",
    navAreas: "赛区",
    navNews: "资讯",
    navLogin: "登录",
    navLogout: "退出",
    navAccount: "账户",

    heroEyebrow: "次世代电竞赛事",
    heroTitle1: "铸就传奇。",
    heroTitle2: "主宰赛场。",
    heroDesc: "管理战队、探索顶尖锦标赛，带领你的队伍登上积分榜巅峰。",
    heroCta: "探索赛事",
    heroDate: "2027年7月 — 8月",

    megaPublisher: "游戏厂商:",
    megaAllPublishers: "全部游戏厂商",
    megaGames: "游戏项目",
    megaEsports: "电竞赛事",
    megaSystem: "系统管理",
    megaAllTournaments: "全部锦标赛",
    megaOngoing: "进行中",
    megaUpcoming: "即将开始",
    megaCompleted: "已完赛",
    megaManageTeams: "战队管理",
    megaAreas: "竞赛赛区",
    megaNews: "资讯动态",
    megaCatalog: "数据与目录",
    megaRules: "规则与章程",
    megaNewBadge: "最新",
    megaLiveBadge: "LIVE",
    megaExploreNow: "立即探索赛事",

    pickerHeaderEyebrow: "选择竞技项目开启征程",
    pickerTitle: "游戏竞技场",
    pickerSub: "选择游戏厂商（Riot Games、Garena）或点击游戏图标查看专属锦标赛与对阵图。",
    pickerPublisherLabel: "厂商:",
    pickerAllPubOption: "全部游戏厂商",
    pickerViewTournaments: "探索赛事 ↗",
    pickerActiveDiscipline: "电竞官方项目",
    pickerShowingTournamentsFor: "正在展示该项目的全部锦标赛与赛程安排",
    pickerResetBtn: "✕ 查看所有游戏",

    tournamentsEyebrowAll: "赛场控制中心",
    tournamentsEyebrowGame: "赛场控制中心 —",
    tournamentsHeadingOngoing: "正在进行的锦标赛",
    tournamentsHeadingGame: "锦标赛",
    tournamentsSubAll: "从统一控制台查看赛程日历、追踪实时对阵与赛事运转。",
    tournamentsSubGame: "探索该项目的官方锦标赛、赛程安排与淘汰赛对阵图。",
    tournamentCountBadge: "个赛事",
    allGamesFilter: "所有游戏",
    allStatusesFilter: "所有状态",
    allAreasFilter: "所有赛区",
    statusUpcoming: "即将开始",
    statusOngoing: "进行中",
    statusCompleted: "已结束",
    statusCancelled: "已取消",
    statusCardUpcoming: "即将开赛",
    statusCardOngoing: "LIVE NOW",
    statusCardCompleted: "已完赛",
    statusCardCancelled: "已取消",
    btnRefresh: "刷新",
    btnCreateTournament: "创建新赛事",
    btnDetails: "详情",
    btnRegister: "报名",
    cardViewDetails: "查看详情 ↗",
    cardOpenEnd: "未定",
    cardDatePrefix: "◷",
    noTournaments: "未找到符合条件的赛事",
    noTournamentsSub: "请尝试更改游戏、状态或竞赛赛区筛选条件。",
    loadingTournaments: "正在同步赛事数据...",
    retry: "重试",
    pagePrev: "上一页",
    pageNext: "下一页",
    pageLabel: "第",

    tcTitle: "创建新锦标赛",
    tcNameLabel: "赛事名称",
    tcNamePlaceholder: "VCT 赛区邀请赛 — 第一阶段",
    tcGameLabel: "游戏项目",
    tcGameSelect: "选择游戏",
    tcFormatLabel: "赛制",
    tcStartLabel: "开始日期",
    tcEndLabel: "结束日期",
    tcAreaLabel: "赛区",
    tcAreaGlobal: "全球赛区",
    tcDescLabel: "赛事说明",
    tcDescPlaceholder: "比赛规则、奖金池、赛制详情...",
    tcSubmitBtn: "创建赛事",

    detailTitle: "赛事档案",
    detailClose: "关闭 ×",
    detailStatus: "状态",
    detailRoster: "阵容",
    detailRosterLocked: "已锁定",
    detailRosterUnlocked: "未锁定",
    detailStartDate: "开赛日期",
    detailArea: "赛区",
    detailGlobalArea: "全球赛区",
    detailOpsTitle: "赛事运营",
    detailLockRosterBtn: "🔒 锁定赛事阵容",
    detailLockingRoster: "正在锁定阵容...",
    detailRosterLockedNotice: "本赛事阵容已被正式锁定",
    detailConditionsTitle: "开赛前置条件 (转为 ONGOING):",
    detailConditionsDesc: "赛事必须先锁定阵容，且每支已通过审核的战队必须至少拥有一名选手 (PLAYER)。",
    detailNoApprovedTeams: "本赛事暂无审核通过 (APPROVED) 的战队。",
    detailMissingPlayersWarning: "缺少选手的战队",
    detailRosterReady: "所有战队均已配备选手。可以执行锁定阵容！",
    detailActionStart: "▶ 开赛 (ONGOING)",
    detailActionComplete: "✓ 完赛 (COMPLETED)",
    detailActionCancel: "✕ 取消赛事 (CANCELLED)",
    detailActionReopen: "↺ 重新开放报名 (UPCOMING)",

    stagesTitle: "赛程阶段",
    stagesAddBtn: "+ 添加阶段",
    stagesEmpty: "该赛事暂未划分赛程阶段。",
    stageNamePlaceholder: "小组赛、八强赛、总决赛...",
    stageOrderPlaceholder: "排序 (1, 2, 3...)",
    stageSaveBtn: "保存",
    stageCancelBtn: "取消",
    stageEditBtn: "编辑",
    stageDeleteBtn: "删除",

    regTitle: "报名名单",
    regEmpty: "暂无报名记录。",
    regSubmittedPrefix: "提交于",
    regReasonPrefix: "原因",
    regApproveBtn: "通过",
    regRejectBtn: "拒绝",
    regCancelBtn: "取消",
    regFilterAll: "所有报名",

    areasTitle: "竞赛赛区",
    areasSub: "探索涵盖全球、亚太、国家职业联赛以及城市巡回赛的官方电竞赛区。点击任意赛区即可筛选相关锦标赛。",
    areasBadge: "全球官方赛区体系",
    areasCountSuffix: "大赛区",
    areasTournamentCountSuffix: "个赛事",
    areasViewTournaments: "查看该赛区锦标赛 →",
    areasSelectedAction: "已选中 • 点击查看全部",

    newsTitle: "资讯与动态",
    newsSub: "实时掌握电竞赛程、官方积分榜、选手转会动态以及各大联赛精彩看点。",
    newsBadge: "电竞资讯精选",
    newsLiveUpdates: "24/7 全天候更新",
    newsReadMore: "阅读全文 ↗",
    newsClose: "关闭文章",
    newsBy: "作者:",

    teamsTitle: "战队",
    teamsCount: "支战队",
    teamNameLabel: "战队名称",
    teamTagLabel: "战队缩写",
    teamGameLabel: "参赛项目",
    teamGameSelectPlaceholder: "选择游戏",
    teamCreateBtn: "创建战队",
    teamLoginRequired: "登录后即可创建新战队。战队花名册公开可见。",
    teamEmpty: "暂无注册战队。",
    teamViewBtn: "查看战队",
    teamMembersTitle: "成员与历史",
    teamAddMemberBtn: "添加成员",
    teamUsernamePlaceholder: "输入用户名",
    teamRoleLabel: "队内职位",
    teamActiveStatus: "现役中",
    teamLeftStatus: "已离队",
    teamLeaveBtn: "退出战队",

    profileTitle: "已认证档案",
    profileRole: "身份角色",
    profileVerifiedEmail: "已认证邮箱",
    profileSessionNote: "JWT 安全储存在浏览器中，用于身份认证接口调用。",
    profileWorkflowTitle: "战队管理流程",
    profileWorkflowItem1: "通过 GET /catalog/games 获取游戏列表",
    profileWorkflowItem2: "通过 GET /teams 获取战队名册",
    profileWorkflowItem3: "通过 POST /teams 创建新战队",
    profileWorkflowItem4: "创建者自动获得 MANAGER 战队经理权限",

    catalogTitle: "目录管理后台",
    catalogAddPub: "添加厂商",
    catalogAddGame: "添加游戏",
    catalogAddArea: "添加赛区",
    catalogReload: "重新加载",
    catalogSubtext: "目录数据可能需要稍后刷新才能反映最新更改。",

    authWelcomeBack: "欢迎回来",
    authJoinArena: "进入竞技场",
    authLoginTitle: "登录",
    authRegisterTitle: "注册账号",
    authLoginDesc: "登录以继续你的电竞赛事征程。",
    authRegisterDesc: "创建账号，步入巅峰对决舞台。",
    authFullName: "姓名",
    authFullNamePlaceholder: "输入显示昵称",
    authEmail: "电子邮箱",
    authUsername: "用户名",
    authUsernamePlaceholder: "输入用户名",
    authPassword: "密码",
    authPasswordHint: "至少 8 位字符",
    authSecureConnection: "安全加密连接",
    authProcessing: "正在处理...",
    authBtnLogin: "立即登录",
    authBtnRegister: "创建账号",
    authSwitchToRegister: "还没有账号？立即注册",
    authSwitchToLogin: "已有账号？直接登录",
    authCloseAria: "关闭登录对话框",
    regFormTitle: "战队报名参赛",
    regSelectTeam: "选择战队",
    regSubmitBtn: "提交报名申请",
    regRosterLockedNotice: "🔒 赛事阵容已锁定 — 现已截止提交新报名申请。",
    regRosterLockedReviewNotice: "🔒 赛事阵容已锁定 — 新报名审核已暂停。",
    regListTitle: "赛事报名名单",
    regTotalSuffix: "份",
    regStatusPending: "待审核",
    regStatusApproved: "已审核通过",
    regStatusRejected: "已拒绝",
    regStatusCancelled: "已取消",
    teamJoinedPrefix: "加入于",
    teamLeftPrefix: "离队于",
    teamCloseBtn: "关闭",
    teamNoMembers: "暂无战队成员。",
    megaAllGamesCount: "显示所有游戏",
    megaGamesSuffix: "款游戏",
    emptyTournamentsTitle: "暂无符合条件的赛事",
    emptyTournamentsSub: "请尝试更改筛选条件或创建首个锦标赛。",
    statusChangeTo: "变更状态为",
    circuitHeaderTitle: "官方职业赛区与联赛体系",
    circuitHeaderDesc: "各电竞项目专属的官方职业赛区与顶级联赛体系。",
    circuitAllTabs: "全部竞技项目",
    circuitToggleShow: "按项目查看26个职业赛区体系",
    circuitToggleHide: "折叠赛区体系",
    circuitGameDescTemplate: "{game}官方职业赛区与顶级联赛体系。",
    detailConditionsHelp: "赛事必须锁定大名单，且每个获批战队至少拥有一名选手（PLAYER）。锁定后“变更为进行中”按钮可用。",
    detailNoApprovedTeamsWarning: "该赛事暂无已获批战队。",
    detailDraftStatus: "📝 草稿名单（未锁定）",
    detailLockedStatus: "🔒 已锁定（快照）",
    detailRosterPlayerEmpty: "参赛名单中暂无选手。",
    detailRosterNoPlayers: "战队暂无成员名单。",
    detailSelectMemberToAdd: "-- 选择要添加的成员 --",
    detailHasPlayer: "已有PLAYER",
    detailMissingPlayer: "缺少PLAYER",
    navAdmin: "管理",
  },
};

// Localized Game Name Resolver
export function getLocalizedGameName(rawNameOrSlug: string, lang: LangCode): string {
  const lower = (rawNameOrSlug || "").toLowerCase();
  if (lower.includes("teamfight") || lower.includes("tft") || lower.includes("chân lý") || lower.includes("chan ly")) {
    if (lang === "vi") return "Đấu Trường Chân Lý";
    if (lang === "en") return "Teamfight Tactics";
    if (lang === "ko") return "전략적 팀 전투";
    if (lang === "ja") return "チームファイト タクティクス";
    if (lang === "zh") return "云顶之弈";
  }
  if (lower.includes("league") || lower.includes("lol") || lower.includes("huyền thoại") || lower.includes("huyen thoai")) {
    if (lang === "vi") return "Liên Minh Huyền Thoại";
    if (lang === "en") return "League of Legends";
    if (lang === "ko") return "리그 오브 레전드";
    if (lang === "ja") return "リーグ・オブ・レジェンド";
    if (lang === "zh") return "英雄联盟";
  }
  if (lower.includes("liên quân") || lower.includes("lien quan") || lower.includes("arena of valor") || lower.includes("aov")) {
    if (lang === "vi") return "Liên Quân Mobile";
    if (lang === "en") return "Arena of Valor";
    if (lang === "ko") return "아레나 오브 발러";
    if (lang === "ja") return "伝説対決 -Arena of Valor-";
    if (lang === "zh") return "传说对决";
  }
  if (lower.includes("valorant") || lower.includes("val")) {
    return "VALORANT";
  }
  if (lower.includes("free fire") || lower.includes("ff")) {
    return "Free Fire";
  }
  return rawNameOrSlug;
}

// Localized Area Description
export function getLocalizedAreaDesc(code: string, lang: LangCode): string {
  const DESCS: Record<LangCode, Record<string, string>> = {
    vi: {
      GLOBAL: "Các giải đấu thế giới, nơi hội tụ những đội tuyển xuất sắc nhất từ tất cả các châu lục.",
      APAC: "Đấu trường Châu Á - Thái Bình Dương với các giải đấu quy mô liên khu vực hấp dẫn.",
      VN: "Đấu trường Thể thao Điện tử Quốc gia Việt Nam với tinh thần thi đấu bùng nổ và khốc liệt.",
      "VN-HCM": "Đấu trường Esports TP. Hồ Chí Minh với các giải đấu bán chuyên và sự kiện LAN sôi động.",
    },
    en: {
      GLOBAL: "World championship tournaments featuring elite teams across all continents.",
      APAC: "Asia-Pacific battlegrounds hosting thrilling cross-regional premier leagues.",
      VN: "Vietnam National Esports League marked by explosive gameplay and intense competition.",
      "VN-HCM": "Ho Chi Minh City Esports Arena featuring semi-pro cups and electric LAN events.",
    },
    ko: {
      GLOBAL: "전 대륙 최고의 팀들이 모여 겨루는 세계 선수권 대회입니다.",
      APAC: "치열한 다지역 경쟁이 펼쳐지는 아시아 태평양 공식 리그입니다.",
      VN: "폭발적인 에너지와 치열한 경쟁이 펼쳐지는 베트남 공식 e스포츠 리그입니다.",
      "VN-HCM": "세미프로 대회와 열정적인 오프라인 LAN 이벤트가 열리는 호치민시 아레나입니다.",
    },
    ja: {
      GLOBAL: "全大陸から集まったトップチームが世界一を競う最高峰の国際大会です。",
      APAC: "白熱のクロス地域リーグが展開されるアジア太平洋公式ステージです。",
      VN: "熱気と激闘が繰り広げられるベトナム全国公式eスポーツリーグです。",
      "VN-HCM": "セミプロトーナメントや熱気あふれるオフラインLANイベントが開催されるホーチミン市アリーナです。",
    },
    zh: {
      GLOBAL: "汇聚全球各大洲顶尖战队的最高级别世界锦标赛舞台。",
      APAC: "充满激烈竞争的亚太跨赛区官方顶级职业联赛。",
      VN: "对抗激烈、激情四射的越南国家级官方电竞职业联赛。",
      "VN-HCM": "举办半职业巡回赛与火爆线下LAN盛会的胡志明市电竞竞技场。",
    },
  };

  const map = DESCS[lang] || DESCS.vi;
  return map[code] || (
    lang === "en" ? `Official tournament region under code ${code}.` :
    lang === "ko" ? `지역 코드 ${code}에 등록된 공식 대회 지역입니다.` :
    lang === "ja" ? `地域コード ${code} に登録された公式競技エリアです。` :
    lang === "zh" ? `代码为 ${code} 的官方竞赛赛区。` :
    `Khu vực thi đấu chính thức thuộc hệ thống giải đấu mã vùng ${code}.`
  );
}

export type NewsArticle = {
  id: number;
  category: string;
  categorySlug: string;
  title: string;
  summary: string;
  content: string;
  date: string;
  author: string;
  image: string;
};

export function getLocalizedNews(lang: LangCode): NewsArticle[] {
  if (lang === "en") {
    return [
      {
        id: 1,
        category: "TEAMFIGHT TACTICS",
        categorySlug: "tft",
        title: "TFT Set 18 World Championship Qualifiers Officially Underway: 32 Tacticians Clash",
        summary: "APAC and Western regions enter intense finals with a record $500,000 prize pool and exclusive global slots.",
        content: "After weeks of rigorous Swiss-stage competition, 32 elite tacticians have secured their spots in the Set 18 Grand Finals. The tournament will feature the pulse-pounding 18-point Checkpoint format. Players will need deep meta mastery, adaptive pivoting, and ironclad composure to lift the trophy and represent their region at Worlds.",
        date: "Nov 01, 2026",
        author: "Nexus Newsroom",
        image: "/games/teamfight-tactics.png",
      },
      {
        id: 2,
        category: "LEAGUE OF LEGENDS",
        categorySlug: "lol",
        title: "VCS & LCK Rosters Reshuffle Ahead of the 2027 Season",
        summary: "Blockbuster signings announced as top contenders rebuild their lineups in pursuit of the Summoner's Cup.",
        content: "The 2027 preseason transfer window is experiencing unprecedented blockbuster moves. Marquee players are seeking new challenges on championship-caliber rosters. Tournament organizers also announced the adoption of Fearless Draft across all regional leagues, delivering unmatched strategic depth.",
        date: "Oct 31, 2026",
        author: "Esports Insider",
        image: "/games/league-of-legends.png",
      },
      {
        id: 3,
        category: "VALORANT",
        categorySlug: "valorant",
        title: "VALORANT Champions Tour 2027 Roadmap: Masters & Champions Format Update",
        summary: "Riot Games reveals an upgraded Championship Points system and new international Masters venues.",
        content: "The VCT 2027 season introduces major overhauls to qualification mechanics with refined Championship Points. Teams across the four international leagues will compete year-round to secure their direct slots to VALORANT Champions, with two high-stakes Masters tournaments setting the stage.",
        date: "Oct 30, 2026",
        author: "Tactical Reporter",
        image: "/games/valorant.png",
      },
      {
        id: 4,
        category: "ARENA OF VALOR",
        categorySlug: "aov",
        title: "Arena of Glory Spring 2027 Official Schedule Announced",
        summary: "Top 8 teams battle through a Bo5 double round-robin leading into a relentless Bo7 Playoffs bracket.",
        content: "AOG Spring 2027 promises to be the most competitive split to date, with seasoned legends clashing against rising prodigies. All matches will be broadcast in crisp 4K HDR featuring premier analyst desks. The champion earns the coveted seed at the APL World Cup.",
        date: "Oct 29, 2026",
        author: "Garena Arena",
        image: "/games/arena-of-valor.png",
      },
    ];
  }

  if (lang === "ko") {
    return [
      {
        id: 1,
        category: "전략적 팀 전투",
        categorySlug: "tft",
        title: "TFT 세트 18 월드 챔피언십 예선 개막: 32인의 전략가 격돌",
        summary: "APAC 및 글로벌 지역이 총상금 50만 달러와 세계대회 직행 티켓을 두고 치열한 결선에 돌입합니다.",
        content: "치열했던 스위스 스테이지를 거쳐 32명의 최정예 전략가들이 세트 18 결승전 진출을 확정지었습니다. 이번 대회는 18점 체크포인트 룰로 진행되며, 깊은 메타 이해도와 유연한 덱 전환 능력이 승패를 결정지을 예정입니다.",
        date: "2026. 11. 01",
        author: "넥서스 뉴스룸",
        image: "/games/teamfight-tactics.png",
      },
      {
        id: 2,
        category: "리그 오브 레전드",
        categorySlug: "lol",
        title: "2027 시즌 대비 LCK 및 글로벌 이적 시장 개막",
        summary: "소환사의 컵 탈환을 위해 각 팀이 파격적인 라인업 리빌딩을 단행하고 있습니다.",
        content: "2027 시즌을 앞두고 대규모 선수 이적이 이어지고 있습니다. 새로운 도전을 선언한 스타 플레이어들의 합류와 함께, 전면 도입되는 피어리스 드래프트 규정으로 인해 밴픽 심리전이 극대화될 전망입니다.",
        date: "2026. 10. 31",
        author: "e스포츠 인사이드",
        image: "/games/league-of-legends.png",
      },
      {
        id: 3,
        category: "발로란트",
        categorySlug: "valorant",
        title: "발로란트 챔피언스 투어 2027 로드맵 및 마스터스 규정 발표",
        summary: "새로운 챔피언십 포인트 시스템과 국제 마스터스 개최지가 공개되었습니다.",
        content: "VCT 2027 시즌은 개편된 챔피언십 포인트 제도를 통해 한층 공정한 진출 구조를 제공합니다. 4개 국제 리그 팀들은 연중 꾸준한 성적을 바탕으로 연말 최고 권위의 발로란트 챔피언스 직행을 노리게 됩니다.",
        date: "2026. 10. 30",
        author: "택티컬 리포터",
        image: "/games/valorant.png",
      },
      {
        id: 4,
        category: "아레나 오브 발러",
        categorySlug: "aov",
        title: "아레나 오브 발러 2027 스프링 정규 시즌 일정 공개",
        summary: "최상위 8개 팀이 참가하는 5전 3선승제 풀리그와 7전 4선승제 플레이오프가 시작됩니다.",
        content: "베테랑의 관록과 신예의 패기가 맞붙는 역대급 시즌이 개막합니다. 전 경기 4K 초고화질 중계와 전문 해설진이 함께하며, 우승팀은 APL 세계대회 진출권을 획득합니다.",
        date: "2026. 10. 29",
        author: "가레나 아레나",
        image: "/games/arena-of-valor.png",
      },
    ];
  }

  if (lang === "ja") {
    return [
      {
        id: 1,
        category: "チームファイト タクティクス",
        categorySlug: "tft",
        title: "TFT Set 18 世界選手権予選が開幕：32名のタクティシャンが集結",
        summary: "賞金総額50万ドルと世界大会出場枠を懸け、APACおよび世界の強豪が激突します。",
        content: "スイスステージを勝ち抜いた32名のエリートプレイヤーがSet 18決勝への切符を手にしました。18ポイントのチェックポイント方式が採用され、柔軟な構成判断と勝負強さが栄冠への鍵となります。",
        date: "2026年11月1日",
        author: "Nexus Newsroom",
        image: "/games/teamfight-tactics.png",
      },
      {
        id: 2,
        category: "リーグ・オブ・レジェンド",
        categorySlug: "lol",
        title: "2027新シーズンに向けたストーブリーグとロスター刷新",
        summary: "サモナーズカップを目指し、各チームが大幅な戦力補強と新体制を発表しています。",
        content: "2027シーズン開幕を控え、各リーグで大型移籍が次々と成立しています。新レギュレーションとしてフィアレスドラフトの導入も確定し、かつてない戦術の深みが生み出されます。",
        date: "2026年10月31日",
        author: "Esports Insider",
        image: "/games/league-of-legends.png",
      },
      {
        id: 3,
        category: "VALORANT",
        categorySlug: "valorant",
        title: "VALORANT Champions Tour 2027 ロードマップ＆Masters詳細公開",
        summary: "刷新されたチャンピオンシップポイント制度と国際Masters大会の日程が発表されました。",
        content: "VCT 2027では年間ポイントレースの公平性が一段と向上。4大インターナショナルリーグの代表チームが年間を通じて鎬を削り、世界最高峰の舞台『Champions』を目指します。",
        date: "2026年10月30日",
        author: "Tactical Reporter",
        image: "/games/valorant.png",
      },
      {
        id: 4,
        category: "伝説対決 -Arena of Valor-",
        categorySlug: "aov",
        title: "Arena of Glory 2027 Spring 公式日程発表",
        summary: "トップ8チームによるBo5総当たり戦と白熱のBo7プレーオフがまもなく開幕。",
        content: "歴戦のベテランと期待の若手が激突する今シーズン。全試合4K超高画質配信でお届けし、優勝チームには国際大会APLへの切符が授与されます。",
        date: "2026年10月29日",
        author: "Garena Arena",
        image: "/games/arena-of-valor.png",
      },
    ];
  }

  if (lang === "zh") {
    return [
      {
        id: 1,
        category: "云顶之弈",
        categorySlug: "tft",
        title: "云顶之弈 S18 全球总决赛预选赛打响：32强弈士同台争锋",
        summary: "亚太及全球赛区会师终极对决，争夺50万美元总奖金与全球直通席位。",
        content: "经过瑞士轮的激烈拼杀，32位顶尖弈士成功晋级第18赛季总决赛。本次赛事采用18分登顶制，极其考验选手对版本环境的理解、临场变阵速度与大心脏抗压能力。",
        date: "2026年11月01日",
        author: "Nexus 新闻室",
        image: "/games/teamfight-tactics.png",
      },
      {
        id: 2,
        category: "英雄联盟",
        categorySlug: "lol",
        title: "2027 赛季转会期重磅官宣：各大战队阵容全面升级",
        summary: "为了争夺召唤师奖杯，各大赛区强队纷纷公布明星选手加盟与阵容重组名单。",
        content: "2027赛季季前转会窗口风云变幻，多位王牌选手转投新阵营。赛事官方亦宣布在新赛季全面推行全局BP模式，战术多样性与观赏性将达到崭新高度。",
        date: "2026年10月31日",
        author: "电竞观察家",
        image: "/games/league-of-legends.png",
      },
      {
        id: 3,
        category: "无畏契约",
        categorySlug: "valorant",
        title: "VCT 2027 赛季路线图：大师赛与全球冠军赛赛制升级",
        summary: "拳头游戏公布全新冠军积分体系与国际大师赛举办城市。",
        content: "VCT 2027 赛季针对积分晋级机制进行了全方位革新。四大国际联赛的顶尖战队将在整年中持续征战累积积分，通过两届大师赛的试炼，争夺全球冠军赛的终极荣耀。",
        date: "2026年10月30日",
        author: "战术前线",
        image: "/games/valorant.png",
      },
      {
        id: 4,
        category: "传说对决",
        categorySlug: "aov",
        title: "职业联赛 2027 春季赛赛程正式出炉",
        summary: "8支顶尖战队展开Bo5双循环积分赛与Bo7巅峰淘汰赛。",
        content: "2027春季赛将见证老牌传奇与超新星势力的正面对决。赛事全场次采用4K HDR超高清直播并配备顶尖解说席，总冠军队伍将代表赛区出征国际大奖赛 APL。",
        date: "2026年10月29日",
        author: "Garena 竞技台",
        image: "/games/arena-of-valor.png",
      },
    ];
  }

  // Default: Vietnamese (vi)
  return [
    {
      id: 1,
      category: "ĐẤU TRƯỜNG CHÂN LÝ",
      categorySlug: "tft",
      title: "Chính thức khởi tranh Vòng loại Cúp Thế Giới ĐTCL Mùa 18: 32 cờ thủ tranh tài",
      summary: "Khu vực APAC và Việt Nam sẵn sàng bước vào vòng chung kết nảy lửa với tổng giải thưởng kỷ lục 500.000 USD cùng vé đi CKTG.",
      content: "Sau nhiều tuần thi đấu căng thẳng ở vòng bảng, 32 cờ thủ xuất sắc nhất đã chính thức ghi tên mình vào Vòng Chung Kết Đấu Trường Chân Lý Mùa 18. Giải đấu sẽ diễn ra theo thể thức tính điểm Checkpoint 18 điểm đầy kịch tính. Các kỳ thủ sẽ phải thể hiện sự am hiểu sâu sắc về meta, khả năng xoay bài linh hoạt và bản lĩnh thép để giành chức vô địch cùng tấm vé đại diện khu vực tham dự CKTG.",
      date: "01/11/2026",
      author: "Nexus Newsroom",
      image: "/games/teamfight-tactics.png",
    },
    {
      id: 2,
      category: "LIÊN MINH HUYỀN THOẠI",
      categorySlug: "lol",
      title: "Thị trường chuyển nhượng VCS & LCK nóng bỏng trước thềm mùa giải mới 2027",
      summary: "Hàng loạt bản hợp đồng bom tấn được kích hoạt khi các chiến đội tái cơ cấu đội hình nhằm chinh phục chiếc cúp danh giá.",
      content: "Kỳ chuyển nhượng trước thềm mùa giải 2027 đang chứng kiến những biến động lớn chưa từng có. Nhiều tuyển thủ ngôi sao đã quyết định tìm kiếm thử thách mới tại các đội tuyển cạnh tranh chức vô địch. Ban tổ chức cũng thông báo sẽ áp dụng thể thức Fearless Draft mới, hứa hẹn mang đến những trận đối đầu chiến thuật đỉnh cao và đa dạng tướng hơn bao giờ hết.",
      date: "31/10/2026",
      author: "Esports Insider",
      image: "/games/league-of-legends.png",
    },
    {
      id: 3,
      category: "VALORANT",
      categorySlug: "valorant",
      title: "Lộ trình VALORANT Champions Tour 2027: Cập nhật thể thức Masters & Champions",
      summary: "Riot Games công bố thể thức thi đấu mới với hệ thống điểm Championship Points cải tiến và các giải Masters quốc tế.",
      content: "Mùa giải VCT 2027 sẽ mang đến sự đột phá về cơ chế tranh vé với hệ thống điểm Championship Points hoàn toàn mới. Các đội tuyển thuộc 4 giải đấu quốc tế sẽ phải nỗ lực xuyên suốt cả năm để tích lũy điểm số, tránh việc bị loại sớm. Hai giải đấu Masters quốc tế sẽ là thước đo phong độ trước khi bước vào đấu trường đỉnh cao VALORANT Champions.",
      date: "30/10/2026",
      author: "Tactical Reporter",
      image: "/games/valorant.png",
    },
    {
      id: 4,
      category: "LIÊN QUÂN MOBILE",
      categorySlug: "aov",
      title: "Đấu Trường Danh Vọng Mùa Xuân 2027 công bố lịch thi đấu chính thức",
      summary: "8 đội tuyển hàng đầu Việt Nam sẽ chính thức tranh tài với thể thức vòng bảng Bo5 và Playoffs Bo7 nghẹt thở.",
      content: "ĐTDV Mùa Xuân 2027 hứa hẹn sẽ là mùa giải hấp dẫn nhất lịch sử với sự trở lại của các huyền thoại cùng làn sóng tài năng trẻ triển vọng. Tất cả các trận đấu sẽ được trực tiếp với công nghệ hình ảnh 4K HDR và sự tham gia bình luận của dàn Caster được yêu thích nhất. Đội vô địch sẽ đại diện Việt Nam tham dự giải đấu quốc tế APL danh giá.",
      date: "29/10/2026",
      author: "Garena Arena",
      image: "/games/arena-of-valor.png",
    },
  ];
}

// Localized Region Country & Circuit Names
const REGION_COUNTRIES: Record<string, Record<LangCode, string>> = {
  LCK: { vi: "Hàn Quốc", en: "South Korea", ko: "대한민국", ja: "韓国", zh: "韩国" },
  LPL: { vi: "Trung Quốc", en: "China", ko: "중국", ja: "中国", zh: "中国" },
  LEC: { vi: "Châu Âu (EMEA)", en: "Europe (EMEA)", ko: "유럽 (EMEA)", ja: "欧州 (EMEA)", zh: "欧洲 (EMEA)" },
  LCS: { vi: "Bắc Mỹ", en: "North America", ko: "북미", ja: "北米", zh: "北美" },
  CBLOL: { vi: "Brazil", en: "Brazil", ko: "브라질", ja: "ブラジル", zh: "巴西" },
  LCP: { vi: "Châu Á – Thái Bình Dương", en: "Asia-Pacific (LCP)", ko: "아시아 태평양 (LCP)", ja: "アジア太平洋 (LCP)", zh: "亚太地区 (LCP)" },

  "TFT AMER": { vi: "Châu Mỹ", en: "Americas", ko: "아메리카", ja: "南北アメリカ", zh: "美洲赛区" },
  "TFT EMEA": { vi: "Châu Âu, Trung Đông và châu Phi", en: "Europe, Middle East & Africa", ko: "유럽, 중동 및 아프리카", ja: "欧州・中東・アフリカ", zh: "欧洲、中东与非洲" },
  "TFT APAC": { vi: "Châu Á – Thái Bình Dương", en: "Asia-Pacific", ko: "아시아 태평양", ja: "アジア太平洋", zh: "亚太地区" },
  "TFT CN": { vi: "Trung Quốc", en: "China", ko: "중국", ja: "中国", zh: "中国" },

  "VCT Americas": { vi: "Châu Mỹ", en: "Americas", ko: "아메리카", ja: "南北アメリカ", zh: "美洲赛区" },
  "VCT EMEA": { vi: "Châu Âu, Trung Đông và châu Phi", en: "Europe, Middle East & Africa", ko: "유럽, 중동 및 아프리카", ja: "欧州・中東・アフリカ", zh: "欧洲、中东与非洲" },
  "VCT Pacific": { vi: "Châu Á – Thái Bình Dương", en: "Asia-Pacific (Pacific)", ko: "아시아 태평양 (퍼시픽)", ja: "アジア太平洋 (Pacific)", zh: "亚太地区 (Pacific)" },
  "VCT CN": { vi: "Trung Quốc", en: "China", ko: "중국", ja: "中国", zh: "中国" },

  RPL: { vi: "Thái Lan", en: "Thailand", ko: "태국", ja: "タイ", zh: "泰国" },
  AOG: { vi: "Việt Nam (ĐTDV)", en: "Vietnam (AOG)", ko: "베트남 (AOG)", ja: "ベトナム (AOG)", zh: "越南赛区 (AOG)" },
  GCS: { vi: "Đài Bắc Trung Hoa", en: "Chinese Taipei", ko: "차이니즈 타이베이", ja: "チャイニーズタイペイ", zh: "中国港澳台" },
  ASL: { vi: "Indonesia", en: "Indonesia", ko: "인도네시아", ja: "インドネシア", zh: "印度尼西亚" },

  "FFWS SEA": { vi: "Đông Nam Á", en: "Southeast Asia", ko: "동남아시아", ja: "東南アジア", zh: "东南亚" },
  "FFWS BR": { vi: "Brazil", en: "Brazil", ko: "브라질", ja: "ブラジル", zh: "巴西" },
  "FFWS LATAM": { vi: "Mỹ Latinh", en: "Latin America", ko: "라틴 아메리카", ja: "ラテンアメリカ", zh: "拉丁美洲" },
  "FFWS MEA": { vi: "Trung Đông & Châu Phi", en: "Middle East & Africa", ko: "중동 및 아프리카", ja: "中東・アフリカ", zh: "中东与非洲" },

  GLOBAL: { vi: "Toàn cầu", en: "Global", ko: "글로벌", ja: "グローバル", zh: "全球赛区" },
};

export function getLocalizedRegionCountry(code: string, defaultCountry: string, lang: LangCode): string {
  return REGION_COUNTRIES[code]?.[lang] || defaultCountry;
}
