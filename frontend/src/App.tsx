import { LangCode, LANGUAGES, TRANSLATIONS, getLocalizedGameName, getLocalizedRegionCountry, getLocalizedAreaDesc, getLocalizedNews } from "./i18n";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import "./styles.css";

type User = { id: number; username: string; email?: string; role: string };
type Game = { game_id: number; name: string; slug: string; publisher_id: number };
type Publisher = { publisher_id: number; name: string };
export type Area = {
  area_id: number;
  code: string;
  name: string;
  country?: string;
  gameSlug?: string;
  flag?: string;
  parent_id?: number | null;
};

export const AREA_METAS: Record<string, { country: string; flag: string; gameSlug: string; name?: string }> = {
  GLOBAL: { country: "Toàn cầu", flag: "🌐", gameSlug: "all" },
  APAC: { country: "Châu Á – Thái Bình Dương", flag: "🌏", gameSlug: "all" },
  VN: { country: "Việt Nam", flag: "🇻🇳", gameSlug: "all" },
  "VN-HCM": { country: "TP. Hồ Chí Minh", flag: "🇻🇳", gameSlug: "all" },
  LCK: { country: "Hàn Quốc", flag: "🇰🇷", gameSlug: "league-of-legends" },
  LPL: { country: "Trung Quốc", flag: "🇨🇳", gameSlug: "league-of-legends" },
  LEC: { country: "Châu Âu (EMEA)", flag: "🇪🇺", gameSlug: "league-of-legends" },
  LCS: { country: "Bắc Mỹ", flag: "🇺🇸", gameSlug: "league-of-legends" },
  CBLOL: { country: "Brazil", flag: "🇧🇷", gameSlug: "league-of-legends" },
  LCP: { country: "Châu Á – Thái Bình Dương", flag: "🌏", gameSlug: "league-of-legends" },
  "TFT AMER": { country: "Châu Mỹ", flag: "🌎", gameSlug: "teamfight-tactics" },
  "TFT EMEA": { country: "Châu Âu, Trung Đông và châu Phi", flag: "🌍", gameSlug: "teamfight-tactics" },
  "TFT APAC": { country: "Châu Á – Thái Bình Dương", flag: "🌏", gameSlug: "teamfight-tactics" },
  "TFT CN": { country: "Trung Quốc", flag: "🇨🇳", gameSlug: "teamfight-tactics" },
  "VCT Americas": { country: "Châu Mỹ", flag: "🌎", gameSlug: "valorant" },
  "VCT EMEA": { country: "Châu Âu, Trung Đông và châu Phi", flag: "🌍", gameSlug: "valorant" },
  "VCT Pacific": { country: "Châu Á – Thái Bình Dương", flag: "🌏", gameSlug: "valorant" },
  "VCT CN": { country: "Trung Quốc", flag: "🇨🇳", gameSlug: "valorant" },
  RPL: { country: "Thái Lan", flag: "🇹🇭", gameSlug: "arena-of-valor" },
  AOG: { country: "Việt Nam", flag: "🇻🇳", gameSlug: "arena-of-valor" },
  GCS: { country: "Đài Bắc Trung Hoa", flag: "🇹🇼", gameSlug: "arena-of-valor" },
  ASL: { country: "Indonesia", flag: "🇮🇩", gameSlug: "arena-of-valor" },
  "FFWS SEA": { country: "Đông Nam Á", flag: "🌏", gameSlug: "free-fire" },
  "FFWS BR": { country: "Brazil", flag: "🇧🇷", gameSlug: "free-fire" },
  "FFWS LATAM": { country: "Mỹ Latinh", flag: "🌎", gameSlug: "free-fire" },
  "FFWS MEA": { country: "Trung Đông & Châu Phi", flag: "🌍", gameSlug: "free-fire" },
  AVC: { country: "Châu Á – Quốc tế", flag: "🌏", gameSlug: "arena-of-valor", name: "AoV International Championship" },
  "FFWS NA": { country: "Bắc Mỹ", flag: "🇺🇸", gameSlug: "free-fire", name: "FFWS North America" },
  "FFWS PK": { country: "Pakistan", flag: "🇵🇰", gameSlug: "free-fire", name: "FFWS Pakistan" },
  "FFWS IN": { country: "Ấn Độ", flag: "🇮🇳", gameSlug: "free-fire", name: "FFWS India" },
  "FFWS BD": { country: "Bangladesh", flag: "🇧🇩", gameSlug: "free-fire", name: "FFWS Bangladesh" },
};
type Team = { team_id: number; name: string; tag: string; game_id: number };
type TeamMember = { membership_id: number; user_id: number; username: string; role: string; status: string; joined_date: string; left_date: string | null };
type TeamDetail = Team & { members: TeamMember[] };
type Tournament = {
  tournament_id: number; name: string; game_id: number; area_id: number | null;
  format: "SINGLE_ELIM" | "DOUBLE_ELIM" | "ROUND_ROBIN"; start_date: string;
  end_date: string | null; status: "UPCOMING" | "ONGOING" | "COMPLETED" | "CANCELLED";
  description: string | null; created_by: number | null; created_at: string;
};
type TournamentCapabilities = {
  tournament_id: number; can_manage: boolean; can_update: boolean;
  can_change_status: boolean; can_review_registrations: boolean;
  can_approve_registrations: boolean; roster_locked: boolean;
  can_lock_roster: boolean; can_manage_stages?: boolean;
  editable_fields: string[]; allowed_status_transitions: string[];
};
type RosterRole = "PLAYER" | "SUBSTITUTE";
type RosterMember = {
  user_id: number;
  display_name: string | null;
  role_in_team: RosterRole;
};
type RosterRead = {
  tournament_id: number;
  team_id: number;
  locked: boolean;
  members: RosterMember[];
};
type RosterLockRead = {
  tournament_id: number;
  locked: boolean;
  locked_at: string | null;
};
type RosterCapabilities = {
  tournament_id: number;
  team_id: number;
  can_view_roster: boolean;
  can_edit_roster: boolean;
};
type RosterDraftItem = {
  user_id: number;
  role_in_team: RosterRole;
  username?: string;
  display_name?: string;
};
type RegistrationStatus = "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED";
type TournamentRegistrationItem = {
  registration_id: number; tournament_id: number; team_id: number;
  status: RegistrationStatus; submitted_by: number | null; submitted_at: string;
  reviewed_by: number | null; reviewed_at: string | null; rejection_reason: string | null;
  cancelled_by: number | null; cancelled_at: string | null;
};
type ApprovedTeam = { team_id: number; name: string; tag: string; game_id: number };
type Stage = {
  stage_id: number;
  tournament_id: number;
  name: string;
  sequence_order: number;
};
const APPROVED_TEAMS_PER_PAGE = 10;
const REGISTRATIONS_PER_PAGE = 10;
type GlobalCapabilities = { can_manage_catalog: boolean; can_create_tournament: boolean };
type TeamCapabilities = { team_id: number; can_manage_members: boolean; can_register_for_tournament: boolean };
type AuthMode = "login" | "register";

const API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1";
const TOKEN_KEY = "esports_access_token";

class RequestError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
  }
}

type ValidationError = { msg?: string };

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string | ValidationError[] } | null;
    const detail = body?.detail;
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((item) => item.msg ?? "Dữ liệu không hợp lệ").join("; ")
        : "Yêu cầu không thành công";
    throw new RequestError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function getGameBadge(name: string): string {
  const lower = name.toLowerCase().replace(/[-_]/g, " ");
  if (lower.includes("liên quân") || lower.includes("lien quan") || lower.includes("arena of valor") || lower.includes("arena") || lower.includes("aov") || lower === "lq") return "AOV";
  if (lower.includes("teamfight") || lower.includes("tft") || lower.includes("chân lý") || lower.includes("chan ly")) return "TFT";
  if (lower.includes("league") || lower.includes("huyền thoại") || lower.includes("huyen thoai") || lower.includes("lol")) return "LoL";
  if (lower.includes("valorant") || lower === "vlr" || lower.startsWith("val ")) return "VAL";
  if (lower.includes("free fire") || lower.includes("freefire") || lower === "ff") return "FF";
  return name.slice(0, 3).toUpperCase();
}

function gameMatchesPublisher(game: Game, publisherId: number | null, publisherList: Publisher[]): boolean {
  if (publisherId === null) return true;
  return game.publisher_id === publisherId;
}

export type CircuitItem = {
  area_id: number;
  code: string;
  name: string;
  country: string;
  flag: string;
};

export const GAME_CIRCUITS_MAP: Record<string, { code: string; name: string; country: string; flag: string; dbCodes: string[] }[]> = {
  "league-of-legends": [
    { code: "LCK", name: "Korea (LCK)", country: "Hàn Quốc", flag: "🇰🇷", dbCodes: ["LCK"] },
    { code: "LPL", name: "China (LPL)", country: "Trung Quốc", flag: "🇨🇳", dbCodes: ["LPL"] },
    { code: "LEC", name: "EMEA (LEC)", country: "Châu Âu (EMEA)", flag: "🇪🇺", dbCodes: ["LEC"] },
    { code: "LCS", name: "North America (LCS)", country: "Bắc Mỹ", flag: "🇺🇸", dbCodes: ["LCS"] },
    { code: "CBLOL", name: "Brazil (CBLOL)", country: "Brazil", flag: "🇧🇷", dbCodes: ["CBLOL"] },
    { code: "LCP", name: "Asia-Pacific (LCP)", country: "Châu Á – Thái Bình Dương", flag: "🌏", dbCodes: ["LCP"] },
  ],
  "teamfight-tactics": [
    { code: "AMER", name: "TFT Americas", country: "Châu Mỹ", flag: "🌎", dbCodes: ["TFT AMER"] },
    { code: "EMEA", name: "TFT EMEA", country: "Châu Âu, Trung Đông & Châu Phi", flag: "🌍", dbCodes: ["TFT EMEA"] },
    { code: "APAC", name: "TFT APAC", country: "Châu Á – Thái Bình Dương", flag: "🌏", dbCodes: ["TFT APAC"] },
    { code: "CN", name: "TFT China", country: "Trung Quốc", flag: "🇨🇳", dbCodes: ["TFT CN"] },
  ],
  "valorant": [
    { code: "AMER", name: "VCT Americas", country: "Châu Mỹ", flag: "🌎", dbCodes: ["VCT Americas", "VCT AMER"] },
    { code: "EMEA", name: "VCT EMEA", country: "Châu Âu, Trung Đông & Châu Phi", flag: "🌍", dbCodes: ["VCT EMEA"] },
    { code: "PACIFIC", name: "VCT Pacific", country: "Châu Á – Thái Bình Dương", flag: "🌏", dbCodes: ["VCT Pacific", "VCT PACIFIC"] },
    { code: "CN", name: "VCT China", country: "Trung Quốc", flag: "🇨🇳", dbCodes: ["VCT CN"] },
  ],
  "arena-of-valor": [
    { code: "RPL", name: "Thailand (RPL)", country: "Thái Lan", flag: "🇹🇭", dbCodes: ["RPL"] },
    { code: "AOG", name: "Vietnam (AOG)", country: "Việt Nam", flag: "🇻🇳", dbCodes: ["AOG"] },
    { code: "GCS", name: "Chinese Taipei (GCS)", country: "Đài Bắc Trung Hoa", flag: "🇹🇼", dbCodes: ["GCS"] },
    { code: "ASL", name: "Indonesia (ASL)", country: "Indonesia", flag: "🇮🇩", dbCodes: ["ASL"] },
    { code: "AVC", name: "AoV International Championship", country: "Châu Á – Quốc tế", flag: "🌏", dbCodes: ["AVC"] },
  ],
  "free-fire": [
    { code: "BR", name: "FFWS Brazil", country: "Brazil", flag: "🇧🇷", dbCodes: ["FFWS BR"] },
    { code: "LATAM", name: "FFWS Latin America", country: "Mỹ Latinh", flag: "🌎", dbCodes: ["FFWS LATAM"] },
    { code: "NA", name: "FFWS North America", country: "Bắc Mỹ", flag: "🇺🇸", dbCodes: ["FFWS NA"] },
    { code: "SEA", name: "FFWS Southeast Asia", country: "Đông Nam Á", flag: "🌏", dbCodes: ["FFWS SEA"] },
    { code: "MEA", name: "FFWS Middle East & Africa", country: "Trung Đông & Châu Phi", flag: "🌍", dbCodes: ["FFWS MEA"] },
    { code: "PK", name: "FFWS Pakistan", country: "Pakistan", flag: "🇵🇰", dbCodes: ["FFWS PK"] },
    { code: "IN", name: "FFWS India", country: "Ấn Độ", flag: "🇮🇳", dbCodes: ["FFWS IN"] },
    { code: "BD", name: "FFWS Bangladesh", country: "Bangladesh", flag: "🇧🇩", dbCodes: ["FFWS BD"] },
  ],
};

function getGameCanonicalSlug(game: Game | null): string | null {
  if (!game) return null;
  const s = (game.slug || "").toLowerCase().trim();
  if (s === "league-of-legends" || s === "lol") return "league-of-legends";
  if (s === "teamfight-tactics" || s === "tft") return "teamfight-tactics";
  if (s === "valorant" || s === "vlr") return "valorant";
  if (s === "arena-of-valor" || s === "lien-quan-mobile" || s === "lqm" || s === "aov") return "arena-of-valor";
  if (s === "free-fire" || s === "ff") return "free-fire";
  return game.slug;
}

function isAreaMatchingGame(area: Area, game: Game | null): boolean {
  if (!game) return true;
  const slug = getGameCanonicalSlug(game);
  if (!slug || !GAME_CIRCUITS_MAP[slug]) return true;
  const circuits = GAME_CIRCUITS_MAP[slug];
  return circuits.some((c) => c.dbCodes.includes(area.code));
}

function getPublisherLogo(nameOrId?: string | number | null): string | null {
  if (nameOrId === null || nameOrId === undefined) return null;
  const str = String(nameOrId).toLowerCase();
  if (str.includes("riot") || str === "1") return "/publishers/riot-games.png";
  if (str.includes("garena") || str === "2") return "/publishers/garena.png";
  return null;
}

function getGameLogo(slugOrName?: string | null): string | null {
  if (!slugOrName) return null;
  const lower = slugOrName.toLowerCase().replace(/[-_]/g, " ");

  // 1. Liên Quân Mobile / Arena of Valor
  if (
    lower.includes("liên quân") ||
    lower.includes("lien quan") ||
    lower.includes("arena of valor") ||
    lower.includes("arena") ||
    lower.includes("aov") ||
    lower.includes("lqmb") ||
    lower.split(" ").includes("lq") ||
    lower === "lq"
  ) {
    return "/game-logos/lien-quan-mobile.png?v=2";
  }

  // 2. Teamfight Tactics / ĐTCL
  if (
    lower.includes("teamfight") ||
    lower.includes("chân lý") ||
    lower.includes("chan ly") ||
    lower.split(" ").includes("tft") ||
    lower === "tft"
  ) {
    return "/game-logos/teamfight-tactics.png";
  }

  // 3. League of Legends / LMHT
  if (
    lower.includes("league") ||
    lower.includes("huyền thoại") ||
    lower.includes("huyen thoai") ||
    lower.split(" ").includes("lol") ||
    lower === "lol"
  ) {
    return "/game-logos/league-of-legends.png";
  }

  // 4. VALORANT (careful: do NOT use substring "val" which matches "valor" in Arena of Valor!)
  if (
    lower.includes("valorant") ||
    lower.split(" ").includes("val") ||
    lower === "val"
  ) {
    return "/game-logos/valorant.png";
  }

  // 5. Free Fire
  if (
    lower.includes("free fire") ||
    lower.includes("freefire") ||
    lower.split(" ").includes("ff") ||
    lower === "ff"
  ) {
    return "/game-logos/free-fire.png?v=3";
  }

  return null;
}


type NewsArticle = {
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

const NEWS_ARTICLES: NewsArticle[] = [
  {
    id: 1,
    category: "ĐẤU TRƯỜNG CHÂN LÝ",
    categorySlug: "tft",
    title: "Chính thức khởi tranh Vòng loại Cúp Thế Giới ĐTCL Mùa 18: 32 cờ thủ tranh tài",
    summary: "Khu vực APAC và Việt Nam sẵn sàng bước vào vòng chung kết nảy lửa với tổng giải thưởng kỷ lục cùng 4 tấm vé trực tiếp tới giải Vô Địch Thế Giới.",
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

type GameMeta = {
  title: string;
  subtitle: string;
  tagline: string;
  coverImage: string;
  badge: string;
  publisherName: string;
};

const GAME_METAS: Record<string, GameMeta> = {
  "teamfight-tactics": {
    title: "ĐẤU TRƯỜNG CHÂN LÝ",
    subtitle: "TEAMFIGHT TACTICS",
    tagline: "Chiến đấu để vươn lên dẫn đầu trong khu rừng tràn ngập ma thuật hoang dã trong ĐTCL Mùa 18. Dự đoán kết quả và chinh phục bảng xếp hạng.",
    coverImage: "/games/teamfight-tactics.png",
    badge: "TFT",
    publisherName: "Riot Games",
  },
  "league-of-legends": {
    title: "LIÊN MINH HUYỀN THOẠI",
    subtitle: "LEAGUE OF LEGENDS",
    tagline: "Những cuộc đối đầu nảy lửa trong đấu trường 5v5 đỉnh cao. Tham gia các giải đấu chuyên nghiệp và ghi dấu ấn lịch sử.",
    coverImage: "/games/league-of-legends.png",
    badge: "LoL",
    publisherName: "Riot Games",
  },
  "valorant": {
    title: "VALORANT",
    subtitle: "BẮN SÚNG CHIẾN THUẬT 5V5",
    tagline: "Lấn át đối thủ trong trò chơi bắn súng chiến thuật 5v5 này. Viết lại luật chơi trên chiến trường cùng các Đặc Vụ Đối Đầu.",
    coverImage: "/games/valorant.png",
    badge: "VAL",
    publisherName: "Riot Games",
  },
  "arena-of-valor": {
    title: "LIÊN QUÂN MOBILE",
    subtitle: "ARENA OF VALOR",
    tagline: "Thao tác tay đỉnh cao, so tài 5v5 đỉnh cao di động. Khám phá các giải đấu thể thao điện tử quy mô hàng đầu khu vực.",
    coverImage: "/games/arena-of-valor.png",
    badge: "AOV",
    publisherName: "Garena",
  },
  "lien-quan-mobile": {
    title: "LIÊN QUÂN MOBILE",
    subtitle: "ARENA OF VALOR",
    tagline: "Thao tác tay đỉnh cao, so tài 5v5 đỉnh cao di động. Khám phá các giải đấu thể thao điện tử quy mô hàng đầu khu vực.",
    coverImage: "/games/arena-of-valor.png",
    badge: "AOV",
    publisherName: "Garena",
  },
  "lien-quan": {
    title: "LIÊN QUÂN MOBILE",
    subtitle: "ARENA OF VALOR",
    tagline: "Thao tác tay đỉnh cao, so tài 5v5 đỉnh cao di động. Khám phá các giải đấu thể thao điện tử quy mô hàng đầu khu vực.",
    coverImage: "/games/arena-of-valor.png",
    badge: "AOV",
    publisherName: "Garena",
  },
  "free-fire": {
    title: "FREE FIRE MAX",
    subtitle: "BATTLE ROYALE ĐỈNH CAO",
    tagline: "Đấu trường sinh tồn tốc độ cao. Sẵn sàng so tài và giành vị trí Top 1 danh giá cùng các chiến đội hàng đầu thế giới.",
    coverImage: "/games/free-fire.png?v=3",
    badge: "FF",
    publisherName: "Garena",
  },
};

function getGameMeta(game: Game, publisherList: Publisher[]): GameMeta {
  if (GAME_METAS[game.slug]) return GAME_METAS[game.slug];
  // check by name
  for (const [key, meta] of Object.entries(GAME_METAS)) {
    if (game.slug.includes(key) || game.name.toLowerCase().includes(meta.title.toLowerCase()) || game.name.toLowerCase().includes(meta.subtitle.toLowerCase())) {
      return meta;
    }
  }
  const pub = publisherList.find((p) => p.publisher_id === game.publisher_id);
  return {
    title: game.name.toUpperCase(),
    subtitle: game.name,
    tagline: `Khám phá đấu trường giải đấu chuyên nghiệp và bảng xếp hạng chính thức cho ${game.name}.`,
    coverImage: "/games/teamfight-tactics.png",
    badge: getGameBadge(game.name),
    publisherName: pub?.name ?? "Esports",
  };
}

export default function App() {
  const [lang, setLang] = useState<LangCode>(() => {
    const saved = localStorage.getItem("app_lang");
    if (saved && (saved === "vi" || saved === "en" || saved === "ko" || saved === "ja" || saved === "zh")) {
      return saved as LangCode;
    }
    return "vi";
  });
  const [langDropdownOpen, setLangDropdownOpen] = useState(false);
  const t = TRANSLATIONS[lang] || TRANSLATIONS.vi;
  const currentLang = LANGUAGES.find((l) => l.code === lang) || LANGUAGES[0];
  const newsArticles = getLocalizedNews(lang);


  const handleSelectLang = (code: LangCode) => {
    setLang(code);
    localStorage.setItem("app_lang", code);
    setLangDropdownOpen(false);
  };

  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? "");
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [activeNav, setActiveNav] = useState<"home" | "play" | "team" | "areas" | "news">("home");
  const [selectedNewsArticle, setSelectedNewsArticle] = useState<NewsArticle | null>(null);
  const [showGamesBar, setShowGamesBar] = useState(false);
  const [selectedPublisherId, setSelectedPublisherId] = useState<number | null>(null);
  const [publisherMenuOpen, setPublisherMenuOpen] = useState(false);
  const [selectedGameId, setSelectedGameId] = useState<number | null>(null);
  const [hoveredGameSlug, setHoveredGameSlug] = useState<string>("teamfight-tactics");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [authCheckAttempt, setAuthCheckAttempt] = useState(0);
  const [games, setGames] = useState<Game[]>([]);
  const [publishers, setPublishers] = useState<Publisher[]>([]);
  const [areas, setAreas] = useState<Area[]>([]);

  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<TeamDetail | null>(null);
  const [teamCapabilities, setTeamCapabilities] = useState<TeamCapabilities | null>(null);
  const [teamCapabilityError, setTeamCapabilityError] = useState("");
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [selectedTournament, setSelectedTournament] = useState<Tournament | null>(null);
  const [tournamentCapabilities, setTournamentCapabilities] = useState<TournamentCapabilities | null>(null);
  const [tournamentLoading, setTournamentLoading] = useState(false);
  const [capabilityError, setCapabilityError] = useState("");
  const [approvedTeams, setApprovedTeams] = useState<ApprovedTeam[]>([]);
  const [managedTeamsForTournament, setManagedTeamsForTournament] = useState<Team[]>([]);
  const [registrations, setRegistrations] = useState<TournamentRegistrationItem[]>([]);
  const [allTournamentRegistrations, setAllTournamentRegistrations] = useState<TournamentRegistrationItem[]>([]);
  const [registrationLoading, setRegistrationLoading] = useState(false);
  const [registrationError, setRegistrationError] = useState("");
  const [registrationNotice, setRegistrationNotice] = useState("");
  const [registrationStatusFilter, setRegistrationStatusFilter] = useState<string>("");
  const [tournamentError, setTournamentError] = useState("");
  const [tournamentTotal, setTournamentTotal] = useState(0);
  const [tournamentPage, setTournamentPage] = useState(0);
  const [tournamentGameFilter, setTournamentGameFilter] = useState("");
  const [tournamentStatusFilter, setTournamentStatusFilter] = useState("");
  const [tournamentAreaFilter, setTournamentAreaFilter] = useState("");
  const [createTournamentGameId, setCreateTournamentGameId] = useState("");

  const activeFilterGame = tournamentGameFilter
    ? games.find((g) => String(g.game_id) === tournamentGameFilter)
    : selectedGameId !== null
      ? games.find((g) => g.game_id === selectedGameId)
      : null;

  const tournamentAvailableAreas = useMemo(() => {
    const slug = getGameCanonicalSlug(activeFilterGame ?? null);
    if (!slug || !GAME_CIRCUITS_MAP[slug]) {
      return areas.map((a) => ({
        area_id: a.area_id,
        code: a.code,
        name: a.name,
        country: a.country ?? a.name,
        flag: a.flag ?? "🌐",
      }));
    }

    const circuits = GAME_CIRCUITS_MAP[slug];
    return circuits
      .map((circuit) => {
        const matched = areas.find((a) => circuit.dbCodes.includes(a.code));
        if (!matched) return null;
        return {
          area_id: matched.area_id,
          code: circuit.code,
          name: matched.name || circuit.name,
          country: circuit.country,
          flag: circuit.flag,
        };
      })
      .filter((item): item is CircuitItem => item !== null);
  }, [areas, activeFilterGame]);

  const createFormActiveGame = games.find((g) => String(g.game_id) === createTournamentGameId);
  const createFormAreas = useMemo(() => {
    const slug = getGameCanonicalSlug(createFormActiveGame ?? null);
    if (!slug || !GAME_CIRCUITS_MAP[slug]) {
      return areas.map((a) => ({
        area_id: a.area_id,
        code: a.code,
        name: a.name,
        country: a.country ?? a.name,
        flag: a.flag ?? "🌐",
      }));
    }

    const circuits = GAME_CIRCUITS_MAP[slug];
    return circuits
      .map((circuit) => {
        const matched = areas.find((a) => circuit.dbCodes.includes(a.code));
        if (!matched) return null;
        return {
          area_id: matched.area_id,
          code: circuit.code,
          name: matched.name || circuit.name,
          country: circuit.country,
          flag: circuit.flag,
        };
      })
      .filter((item): item is CircuitItem => item !== null);
  }, [areas, createFormActiveGame]);
  const [globalCapabilities, setGlobalCapabilities] = useState<GlobalCapabilities | null>(null);
  const [globalCapabilityError, setGlobalCapabilityError] = useState("");
  const [memberLoading, setMemberLoading] = useState(false);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogReloadError, setCatalogReloadError] = useState("");
  const [selectedRosterTeam, setSelectedRosterTeam] = useState<{ team_id: number; name: string; tag?: string } | null>(null);
  const [rosterLock, setRosterLock] = useState<RosterLockRead | null>(null);
  const [rosterData, setRosterData] = useState<RosterRead | null>(null);
  const [rosterCapabilities, setRosterCapabilities] = useState<RosterCapabilities | null>(null);
  const [rosterLoading, setRosterLoading] = useState(false);
  const [rosterError, setRosterError] = useState("");
  const [rosterNotice, setRosterNotice] = useState("");
  const [rosterSaving, setRosterSaving] = useState(false);
  const [teamEligibleMembers, setTeamEligibleMembers] = useState<TeamMember[]>([]);
  const [rosterDraftMembers, setRosterDraftMembers] = useState<RosterDraftItem[]>([]);
  const [lockLoading, setLockLoading] = useState(false);
  const [lockError, setLockError] = useState("");
  const [lockNotice, setLockNotice] = useState("");
  const [approvedRosterStatuses, setApprovedRosterStatuses] = useState<Record<number, { loaded: boolean; hasPlayer: boolean }>>({});
  const [rosterStatusWarning, setRosterStatusWarning] = useState("");

  const [stages, setStages] = useState<Stage[]>([]);
  const [stagesLoading, setStagesLoading] = useState(false);
  const [stagesError, setStagesError] = useState("");
  const [stagesNotice, setStagesNotice] = useState("");
  const [stageActionLoading, setStageActionLoading] = useState(false);
  const [isCreatingStage, setIsCreatingStage] = useState(false);
  const [newStageName, setNewStageName] = useState("");
  const [newStageOrder, setNewStageOrder] = useState("");
  const [stageFormError, setStageFormError] = useState("");
  const [editingStageId, setEditingStageId] = useState<number | null>(null);
  const [editingStageName, setEditingStageName] = useState("");
  const [editingStageOrder, setEditingStageOrder] = useState("");

  const [approvedTeamsTotal, setApprovedTeamsTotal] = useState(0);
  const [approvedTeamsPage, setApprovedTeamsPage] = useState(0);

  const [registrationTotal, setRegistrationTotal] = useState(0);
  const [registrationPage, setRegistrationPage] = useState(0);

  const sessionVersion = useRef(0);
  const tournamentViewVersion = useRef(0);
  const rosterTeamVersion = useRef(0);
  const activeRosterTeamIdRef = useRef<number | null>(null);

  const resetStagesState = () => {
    setStages([]);
    setStagesLoading(false);
    setStagesError("");
    setStagesNotice("");
    setStageActionLoading(false);
    setIsCreatingStage(false);
    setNewStageName("");
    setNewStageOrder("");
    setStageFormError("");
    setEditingStageId(null);
    setEditingStageName("");
    setEditingStageOrder("");
  };

  const resetRosterState = () => {
    activeRosterTeamIdRef.current = null;
    rosterTeamVersion.current += 1;
    setSelectedRosterTeam(null);
    setRosterData(null);
    setRosterCapabilities(null);
    setRosterLoading(false);
    setRosterSaving(false);
    setLockLoading(false);
    setRosterError("");
    setRosterNotice("");
    setTeamEligibleMembers([]);
    setRosterDraftMembers([]);
    setRosterStatusWarning("");
  };

  const handleAuthExpired = (customMessage?: string) => {
    sessionVersion.current += 1;
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUser(null);
    setTeamCapabilities(null);
    setTeamCapabilityError("");
    setGlobalCapabilities(null);
    setGlobalCapabilityError("");
    setTournamentCapabilities(null);
    setCapabilityError("");
    setRegistrations([]);
    setAllTournamentRegistrations([]);
    setRegistrationTotal(0);
    setRegistrationPage(0);
    setApprovedTeamsTotal(0);
    setApprovedTeamsPage(0);
    setManagedTeamsForTournament([]);
    setRegistrationError("");
    setRegistrationNotice("");
    resetRosterState();
    resetStagesState();
    setRosterLock(null);
    setLockError("");
    setLockNotice("");
    setApprovedRosterStatuses({});
    setError(customMessage || "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
  };

  const handleSelectPublisher = (pubId: number | null) => {
    setSelectedPublisherId(pubId);
    if (selectedGameId !== null && pubId !== null) {
      const currentGame = games.find((g) => g.game_id === selectedGameId);
      if (currentGame && !gameMatchesPublisher(currentGame, pubId, publishers)) {
        setSelectedGameId(null);
        setTournamentGameFilter("");
        setTournamentPage(0);
      }
    }
    const matching = games.filter(
      (g) => gameMatchesPublisher(g, pubId, publishers)
    );
    if (matching.length > 0 && !matching.some((g) => g.slug === hoveredGameSlug)) {
      setHoveredGameSlug(matching[0].slug);
    }
  };

  const displayedGames = games.filter(
    (g) => gameMatchesPublisher(g, selectedPublisherId, publishers)
  );
  const activePreviewGame = displayedGames.find((g) => g.slug === hoveredGameSlug) ?? displayedGames[0];
  const activePreviewMeta = activePreviewGame
    ? getGameMeta(activePreviewGame, publishers)
    : {
        title: "NEXUS ARENA",
        subtitle: "ĐẤU TRƯỜNG ESPORTS",
        tagline: "Chọn tựa game để khám phá các giải đấu và bảng đấu tương ứng.",
        coverImage: "/games/league-of-legends.png",
        badge: "NEXUS",
        publisherName: "ESPORTS",
      };

  const loadTeams = async () => {
    try {
      const [loadedGames, loadedTeams] = await Promise.all([
        request<Game[]>("/catalog/games"),
        request<Team[]>("/teams"),
      ]);
      setGames(loadedGames || []);
      setTeams(loadedTeams || []);
    } catch (reason) {
      setError((reason as Error).message);
    }
  };

  const loadCatalog = async () => {
    setCatalogLoading(true);
    setCatalogReloadError("");
    try {
      const [loadedPublishers, loadedGames, loadedAreas] = await Promise.all([
        request<Publisher[]>("/catalog/publishers"),
        request<Game[]>("/catalog/games"),
        request<Area[]>("/catalog/areas"),
      ]);
      setPublishers(loadedPublishers || []);
      setGames(loadedGames || []);

      const enrichedAreas: Area[] = (loadedAreas || []).map((la) => {
        const meta = AREA_METAS[la.code] || AREA_METAS[la.code.toUpperCase()];
        return {
          ...la,
          country: la.country || meta?.country || la.name,
          flag: la.flag || meta?.flag || "🌐",
          gameSlug: la.gameSlug || meta?.gameSlug || "all",
        };
      });
      setAreas(enrichedAreas);
    } catch (reason) {
      setCatalogReloadError((reason as Error).message);
      throw reason;
    } finally {
      setCatalogLoading(false);
    }
  };

  const loadTournaments = async (page = tournamentPage, gameId = tournamentGameFilter, status = tournamentStatusFilter, areaId = tournamentAreaFilter) => {
    if (gameId === "0") {
      setTournaments([]);
      setTournamentTotal(0);
      setTournamentLoading(false);
      setTournamentError("");
      return;
    }
    setTournamentLoading(true);
    setTournamentError("");
    try {
      const params = new URLSearchParams({ offset: String(page * 6), limit: "6" });
      if (gameId) params.set("game_id", gameId);
      if (status) params.set("status", status);
      if (areaId) params.set("area_id", areaId);
      const response = await fetch(`${API}/tournaments?${params}`);
      if (!response.ok) throw new RequestError("Không thể tải danh sách giải đấu", response.status);
      const totalHeader = response.headers.get("x-total-count");
      const parsedTotal = totalHeader !== null ? parseInt(totalHeader, 10) : NaN;
      const allTournaments = (await response.json()) as Tournament[];
      setTournaments(allTournaments);
      setTournamentTotal(!isNaN(parsedTotal) ? parsedTotal : allTournaments.length);
    } catch (reason) {
      setTournamentError((reason as Error).message);
    } finally {
      setTournamentLoading(false);
    }
  };

  useEffect(() => {
    loadTeams();
    loadCatalog().catch((reason) => {
      setError(`Không thể tải catalog: ${(reason as Error).message}`);
    });
  }, []);

  useEffect(() => {
    void loadTournaments();
  }, [tournamentPage, tournamentGameFilter, tournamentStatusFilter, tournamentAreaFilter]);

  useEffect(() => {
    if (!tournamentAreaFilter || !activeFilterGame) return;
    const isValid = tournamentAvailableAreas.some(
      (a) => String(a.area_id) === tournamentAreaFilter || a.code === tournamentAreaFilter
    );
    if (!isValid) {
      setTournamentAreaFilter("");
      setTournamentPage(0);
    }
  }, [activeFilterGame, tournamentAreaFilter, tournamentAvailableAreas]);

  useEffect(() => {
    if (!token) return;
    const version = sessionVersion.current;
    const controller = new AbortController();
    let active = true;

    request<User>("/auth/me", { signal: controller.signal }, token)
      .then((currentUser) => {
        if (active && sessionVersion.current === version) setUser(currentUser);
      })
      .catch((reason: unknown) => {
        if (!active || controller.signal.aborted) return;
        if (reason instanceof RequestError && (reason.status === 401 || reason.status === 403)) {
          handleAuthExpired();
          return;
        }
        setError("Không thể kiểm tra phiên đăng nhập. Hãy thử lại.");
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [token, authCheckAttempt]);

  useEffect(() => {
    const handleHash = () => {
      const hash = (window.location.hash || "").toLowerCase();
      if (hash === "#login") {
        setError("");
        setNotice("");
        setAuthMode("login");
        setIsAuthModalOpen(true);
      } else if (hash === "#tournaments") {
        setActiveNav("play");
      } else if (hash === "#teams") {
        setActiveNav("team");
      } else if (hash === "#areas") {
        setActiveNav("play");
        const el = document.getElementById("tournaments");
        if (el) el.scrollIntoView({ behavior: "smooth" });
      } else if (hash === "#news") {
        setActiveNav("news");
      } else if (hash === "#home" || hash === "#top" || hash === "") {
        setActiveNav("home");
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsAuthModalOpen(false);
        setUserMenuOpen(false);
        setShowGamesBar(false);
        setPublisherMenuOpen(false);
      }
    };
    handleHash();
    window.addEventListener("hashchange", handleHash);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("hashchange", handleHash);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  
  const loadGlobalCapabilities = async () => {
    if (!token) {
      setGlobalCapabilities(null);
      setGlobalCapabilityError("");
      return;
    }
    try {
      setGlobalCapabilityError("");
      const caps = await request<GlobalCapabilities>("/auth/capabilities", {}, token);
      setGlobalCapabilities(caps);
    } catch (reason) {
      setGlobalCapabilities(null);
      setGlobalCapabilityError((reason as Error).message || "Không thể tải quyền tài khoản.");
    }
  };

  useEffect(() => {
    void loadGlobalCapabilities();
  }, [token]);

  const submitAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setNotice("");
    setLoading(true);
    const form = new FormData(event.currentTarget);
    try {
      if (authMode === "register") {
        await request("/auth/register", {
          method: "POST",
          body: JSON.stringify({
            username: form.get("username"),
            email: form.get("email"),
            password: form.get("password"),
            real_name: form.get("real_name") ?? "",
          }),
        });
        setNotice("Đăng ký thành công. Hãy đăng nhập để tiếp tục.");
        setAuthMode("login");
      } else {
        const result = await request<{ access_token: string; user: User }>("/auth/login", {
          method: "POST",
          body: JSON.stringify({ username: form.get("username"), password: form.get("password") }),
        });
        sessionVersion.current += 1;
        localStorage.setItem(TOKEN_KEY, result.access_token);
        setToken(result.access_token);
        setUser(result.user);
        setNotice("Đăng nhập thành công.");
        setIsAuthModalOpen(false);
      }
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    sessionVersion.current += 1;
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUser(null);
    setAuthMode("login");
    setIsAuthModalOpen(true);
    setUserMenuOpen(false);
    setTeamCapabilities(null);
    setTeamCapabilityError("");
    setGlobalCapabilities(null);
    setGlobalCapabilityError("");
    setTournamentCapabilities(null);
    setCapabilityError("");
    setRegistrations([]);
    setAllTournamentRegistrations([]);
    setRegistrationTotal(0);
    setRegistrationPage(0);
    setApprovedTeamsTotal(0);
    setApprovedTeamsPage(0);
    setManagedTeamsForTournament([]);
    setRegistrationError("");
    setRegistrationNotice("");
    resetRosterState();
    resetStagesState();
    setRosterLock(null);
    setLockError("");
    setLockNotice("");
    setApprovedRosterStatuses({});
    setNotice("Bạn đã đăng xuất.");
  };

  const createTeam = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) return;
    setError("");
    setNotice("");
    setLoading(true);
    const formElement = event.currentTarget;
    const form = new FormData(event.currentTarget);
    try {
      await request<Team>("/teams", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          tag: form.get("tag"),
          game_id: Number(form.get("game_id")),
        }),
      }, token);
      formElement.reset();
      await loadTeams();
      setNotice("Tạo đội thành công. Bạn đã trở thành MANAGER của đội.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadTeamCapabilities = async (teamId: number) => {
    if (!token) {
      setTeamCapabilities(null);
      setTeamCapabilityError("");
      return;
    }
    try {
      setTeamCapabilityError("");
      const capabilities = await request<TeamCapabilities>(`/teams/${teamId}/capabilities`, {}, token);
      setTeamCapabilities(capabilities);
    } catch (reason) {
      setTeamCapabilities(null);
      setTeamCapabilityError((reason as Error).message || "Không thể tải quyền quản lý đội tuyển.");
    }
  };

  const viewTeam = async (teamId: number) => {
    setError("");
    setNotice("");
    setTeamCapabilityError("");
    try {
      const team = await request<TeamDetail>(`/teams/${teamId}`);
      setSelectedTeam(team);
      await loadTeamCapabilities(teamId);
    } catch (reason) {
      setError((reason as Error).message);
    }
  };

  const refreshSelectedTeam = async () => {
    if (!selectedTeam) return;
    try {
      const team = await request<TeamDetail>(`/teams/${selectedTeam.team_id}`);
      setSelectedTeam(team);
      await loadTeamCapabilities(selectedTeam.team_id);
    } catch (reason) {
      setError((reason as Error).message);
    }
  };

  const addMember = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !selectedTeam) return;
    setError("");
    setNotice("");
    setMemberLoading(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await request<TeamMember>(`/teams/${selectedTeam.team_id}/members`, {
        method: "POST",
        body: JSON.stringify({
          username: form.get("username"),
          role_in_team: form.get("role_in_team"),
        }),
      }, token);
      formElement.reset();
      await refreshSelectedTeam();
      setNotice("Đã thêm thành viên vào đội.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setMemberLoading(false);
    }
  };

  const updateMemberRole = async (membershipId: number, role: string) => {
    if (!token || !selectedTeam) return;
    setError("");
    setNotice("");
    setMemberLoading(true);
    try {
      await request<TeamMember>(`/teams/${selectedTeam.team_id}/members/${membershipId}`, {
        method: "PATCH",
        body: JSON.stringify({ role_in_team: role }),
      }, token);
      await refreshSelectedTeam();
      setNotice("Đã cập nhật vị trí thành viên.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setMemberLoading(false);
    }
  };

  const endMembership = async (membership: TeamMember) => {
    if (!token || !selectedTeam) return;
    const action = membership.user_id === user?.id ? "rời đội" : "kết thúc membership của thành viên này";
    if (!window.confirm(`Bạn có chắc muốn ${action}? Thao tác này không thể hoàn tác ngay.`)) return;
    setError("");
    setNotice("");
    setMemberLoading(true);
    try {
      await request<TeamMember>(`/teams/${selectedTeam.team_id}/members/${membership.membership_id}/end`, {
        method: "POST",
      }, token);
      await refreshSelectedTeam();
      setNotice(membership.user_id === user?.id ? "Bạn đã rời đội." : "Đã kết thúc membership.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setMemberLoading(false);
    }
  };

  const canManageSelectedTeam = teamCapabilities?.can_manage_members === true;

  const catalogRequest = async (path: string, method: "POST" | "PATCH" | "DELETE", body?: object): Promise<boolean> => {
    if (!token || !globalCapabilities?.can_manage_catalog) return false;
    setError("");
    setNotice("");
    setCatalogLoading(true);
    try {
      await request(path, { method, ...(body ? { body: JSON.stringify(body) } : {}) }, token);
    } catch (reason) {
      setError((reason as Error).message);
      setCatalogLoading(false);
      return false;
    }
    try {
      await loadCatalog();
      setNotice(t.catalogUpdatedNotice);
      return true;
    } catch (reason) {
      const message = (reason as Error).message;
      setError(`Đã ghi thành công nhưng không thể tải lại danh sách: ${message}. Không gửi lại thao tác; hãy thử tải lại.`);
      return false;
    }
  };

  const retryCatalogLoad = async () => {
    setError("");
    setNotice("");
    try {
      await loadCatalog();
      setNotice(t.catalogReloadedNotice);
    } catch (reason) {
      const message = (reason as Error).message;
      setError(`Không thể tải lại catalog: ${message}`);
    }
  };

  const submitPublisher = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    if (await catalogRequest("/catalog/publishers", "POST", { name: form.get("name") })) formElement.reset();
  };

  const submitGame = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    if (await catalogRequest("/catalog/games", "POST", {
      name: form.get("name"),
      slug: form.get("slug"),
      publisher_id: Number(form.get("publisher_id")),
    })) formElement.reset();
  };

  const submitArea = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const parent = form.get("parent_id");
    if (await catalogRequest("/catalog/areas", "POST", {
      name: form.get("name"),
      code: form.get("code"),
      parent_id: parent ? Number(parent) : null,
    })) formElement.reset();
  };

  const editCatalogItem = async (kind: "publishers" | "games" | "areas", item: Publisher | Game | Area) => {
    const name = window.prompt("Tên mới:", "name" in item ? item.name : "");
    if (!name?.trim()) return;
    if (kind === "publishers") {
      await catalogRequest(`/catalog/publishers/${(item as Publisher).publisher_id}`, "PATCH", { name: name.trim() });
    } else if (kind === "games") {
      const game = item as Game;
      const slug = window.prompt("Slug mới:", game.slug);
      if (!slug?.trim()) return;
      const publisherId = window.prompt(
        `Publisher ID mới (${publishers.map((publisher) => `${publisher.publisher_id}: ${publisher.name}`).join(", ")}):`,
        String(game.publisher_id),
      );
      if (!publisherId?.trim() || !Number.isInteger(Number(publisherId))) return;
      await catalogRequest(`/catalog/games/${game.game_id}`, "PATCH", {
        name: name.trim(), slug: slug.trim(), publisher_id: Number(publisherId),
      });
    } else {
      const area = item as Area;
      const code = window.prompt("Mã khu vực mới:", area.code);
      if (!code?.trim()) return;
      const parentId = window.prompt(
        `Khu vực cha ID mới (để trống để bỏ cấp cha; ${areas.map((candidate) => `${candidate.area_id}: ${candidate.code}`).join(", ")}):`,
        area.parent_id ? String(area.parent_id) : "",
      );
      if (parentId === null) return;
      if (parentId && !Number.isInteger(Number(parentId))) return;
      await catalogRequest(`/catalog/areas/${area.area_id}`, "PATCH", {
        name: name.trim(), code: code.trim(), parent_id: parentId ? Number(parentId) : null,
      });
    }
  };

  const deleteCatalogItem = async (kind: "publishers" | "games" | "areas", id: number, label: string) => {
    if (!window.confirm(`Bạn có chắc muốn xóa ${label}?`)) return;
    await catalogRequest(`/catalog/${kind}/${id}`, "DELETE");
  };

  const closeTournamentDetail = () => {
    tournamentViewVersion.current += 1;
    setSelectedTournament(null);
    setTournamentCapabilities(null);
    setCapabilityError("");
    setApprovedTeams([]);
    setApprovedTeamsTotal(0);
    setApprovedTeamsPage(0);
    setManagedTeamsForTournament([]);
    setRegistrations([]);
    setAllTournamentRegistrations([]);
    setRegistrationTotal(0);
    setRegistrationPage(0);
    setRegistrationError("");
    setRegistrationNotice("");
    setRegistrationStatusFilter("");
    resetRosterState();
    resetStagesState();
    setRosterLock(null);
    setLockLoading(false);
    setLockError("");
    setLockNotice("");
    setApprovedRosterStatuses({});
    setRosterStatusWarning("");
  };

  const loadTournamentCapabilities = async (
    tournamentId: number,
    authToken = token,
    expectedVersion?: number,
    expectedSessionVersion?: number
  ): Promise<TournamentCapabilities | null> => {
    const sessionV = expectedSessionVersion ?? sessionVersion.current;
    if (!authToken) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return null;
      if (sessionVersion.current !== sessionV) return null;
      setTournamentCapabilities(null);
      setCapabilityError("");
      return null;
    }
    try {
      setCapabilityError("");
      const caps = await request<TournamentCapabilities>(`/tournaments/${tournamentId}/capabilities`, {}, authToken);
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return null;
      if (sessionVersion.current !== sessionV) return null;
      setTournamentCapabilities(caps);
      return caps;
    } catch (reason) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return null;
      if (sessionVersion.current !== sessionV) return null;
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return null;
      }
      setTournamentCapabilities(null);
      setCapabilityError((reason as Error).message || "Không thể tải quyền quản lý giải đấu.");
      return null;
    }
  };

  const loadApprovedTeams = async (
    tournamentId: number,
    page = approvedTeamsPage,
    expectedVersion?: number
  ): Promise<{ list: ApprovedTeam[]; total: number }> => {
    try {
      const offset = page * APPROVED_TEAMS_PER_PAGE;
      const res = await fetch(`${API}/tournaments/${tournamentId}/teams?offset=${offset}&limit=${APPROVED_TEAMS_PER_PAGE}`);
      if (!res.ok) throw new RequestError("Không thể tải danh sách đội đã duyệt", res.status);
      const total = Number(res.headers.get("X-Total-Count") ?? 0);
      const list = (await res.json()) as ApprovedTeam[];
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return { list, total };
      setApprovedTeams(list);
      setApprovedTeamsTotal(total);
      return { list, total };
    } catch (reason) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return { list: [], total: 0 };
      setApprovedTeams([]);
      setApprovedTeamsTotal(0);
      setRegistrationError((reason as Error).message);
      return { list: [], total: 0 };
    }
  };

  const handleApprovedTeamsPageChange = async (newPage: number) => {
    if (!selectedTournament) return;
    setApprovedTeamsPage(newPage);
    const version = tournamentViewVersion.current;
    const sessionV = sessionVersion.current;
    const { list } = await loadApprovedTeams(selectedTournament.tournament_id, newPage, version);
    if (tournamentViewVersion.current !== version || sessionVersion.current !== sessionV) return;
    if (token && list && (tournamentCapabilities?.can_manage || tournamentCapabilities?.can_lock_roster)) {
      void loadApprovedTeamRosterStatuses(selectedTournament.tournament_id, list, token, version, sessionV);
    }
  };

  const loadApprovedTeamRosterStatuses = async (
    tournamentId: number,
    teams: ApprovedTeam[],
    authToken: string,
    expectedVersion?: number,
    expectedSessionVersion?: number
  ) => {
    const sessionV = expectedSessionVersion ?? sessionVersion.current;
    if (!authToken || teams.length === 0) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      if (sessionVersion.current !== sessionV) return;
      setApprovedRosterStatuses({});
      setRosterStatusWarning("");
      return;
    }
    try {
      let hasFetchFailure = false;
      const results = await Promise.all(
        teams.map(async (t) => {
          try {
            const r = await request<RosterRead>(`/tournaments/${tournamentId}/teams/${t.team_id}/roster`, {}, authToken);
            const hasPlayer = r.members.some((m) => m.role_in_team === "PLAYER");
            return { teamId: t.team_id, loaded: true, hasPlayer };
          } catch {
            hasFetchFailure = true;
            return { teamId: t.team_id, loaded: false, hasPlayer: false };
          }
        })
      );
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      if (sessionVersion.current !== sessionV) return;
      const statusMap: Record<number, { loaded: boolean; hasPlayer: boolean }> = {};
      for (const res of results) {
        statusMap[res.teamId] = { loaded: res.loaded, hasPlayer: res.hasPlayer };
      }
      setApprovedRosterStatuses(statusMap);
      if (hasFetchFailure) {
        setRosterStatusWarning("Không thể tải trạng thái đội hình của một số đội đã duyệt.");
      } else {
        setRosterStatusWarning("");
      }
    } catch {
      // ignore status check error
    }
  };

  // Lưu ý: Endpoint /teams/managed mặc định limit 50; trong phạm vi demo W44 danh sách hiển thị tối đa 50 đội.
  const loadManagedTeamsForTournament = async (
    gameId: number,
    authToken = token,
    expectedVersion?: number,
    expectedSessionVersion?: number
  ): Promise<Team[]> => {
    const sessionV = expectedSessionVersion ?? sessionVersion.current;
    if (!authToken) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return [];
      if (sessionVersion.current !== sessionV) return [];
      setManagedTeamsForTournament([]);
      return [];
    }
    try {
      const list = await request<Team[]>(`/teams/managed?game_id=${gameId}`, {}, authToken);
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return [];
      if (sessionVersion.current !== sessionV) return [];
      setManagedTeamsForTournament(list);
      return list;
    } catch (reason) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return [];
      if (sessionVersion.current !== sessionV) return [];
      setManagedTeamsForTournament([]);
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return [];
      }
      setRegistrationError((reason as Error).message);
      return [];
    }
  };

  const loadTournamentRegistrations = async (
    tournamentId: number,
    statusFilter = registrationStatusFilter,
    authToken = token,
    expectedVersion?: number,
    managedTeams?: Team[],
    page = registrationPage,
    expectedSessionVersion?: number
  ) => {
    const sessionV = expectedSessionVersion ?? sessionVersion.current;
    setRegistrationError("");
    if (!authToken) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      if (sessionVersion.current !== sessionV) return;
      setRegistrations([]);
      setAllTournamentRegistrations([]);
      setRegistrationTotal(0);
      return;
    }
    try {
      const offset = page * REGISTRATIONS_PER_PAGE;
      const params = new URLSearchParams({ offset: String(offset), limit: String(REGISTRATIONS_PER_PAGE) });
      if (statusFilter) params.set("status", statusFilter);

      const paginatedResPromise = fetch(`${API}/tournaments/${tournamentId}/registrations?${params}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });

      const teamsToCheck = managedTeams ?? managedTeamsForTournament;
      const managedRegistrationsPromise = teamsToCheck.length > 0
        ? Promise.all(
            teamsToCheck.map(async (t) => {
              try {
                const res = await request<TournamentRegistrationItem[]>(
                  `/tournaments/${tournamentId}/registrations?team_id=${t.team_id}`,
                  {},
                  authToken
                );
                return res;
              } catch {
                return [];
              }
            })
          )
        : Promise.resolve([]);

      const [paginatedRes, managedRegArrays] = await Promise.all([
        paginatedResPromise,
        managedRegistrationsPromise,
      ]);

      if (!paginatedRes.ok) {
        if (paginatedRes.status === 401) {
          handleAuthExpired();
          return;
        }
        if (paginatedRes.status === 403) {
          if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
          if (sessionVersion.current !== sessionV) return;
          setRegistrations([]);
          setAllTournamentRegistrations([]);
          setRegistrationTotal(0);
          return;
        }
        throw new RequestError("Không thể tải danh sách đơn đăng ký", paginatedRes.status);
      }

      const total = Number(paginatedRes.headers.get("X-Total-Count") ?? 0);
      const paginatedList = (await paginatedRes.json()) as TournamentRegistrationItem[];
      const allManagedRegs = (managedRegArrays as TournamentRegistrationItem[][]).flat();

      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      if (sessionVersion.current !== sessionV) return;
      setRegistrations(paginatedList);
      setRegistrationTotal(total);
      setAllTournamentRegistrations(allManagedRegs);
    } catch (reason) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      if (sessionVersion.current !== sessionV) return;
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setRegistrationError((reason as Error).message);
    }
  };

  const handleRegistrationPageChange = async (newPage: number) => {
    if (!selectedTournament || !token) return;
    setRegistrationPage(newPage);
    const version = tournamentViewVersion.current;
    const sessionV = sessionVersion.current;
    await loadTournamentRegistrations(
      selectedTournament.tournament_id,
      registrationStatusFilter,
      token,
      version,
      undefined,
      newPage,
      sessionV
    );
  };

  const fetchAllStages = async (tournamentId: number): Promise<Stage[]> => {
    let all: Stage[] = [];
    let offset = 0;
    const limit = 100;
    while (true) {
      const res = await fetch(`${API}/tournaments/${tournamentId}/stages?offset=${offset}&limit=${limit}`);
      if (!res.ok) {
        throw new RequestError("Không thể tải danh sách vòng đấu", res.status);
      }
      const total = Number(res.headers.get("X-Total-Count") ?? 0);
      const data = (await res.json()) as Stage[];
      all = all.concat(data);
      if (all.length >= total || data.length < limit) break;
      offset += limit;
    }
    return all;
  };

  const loadTournamentStages = async (
    tournamentId: number,
    expectedVersion?: number,
    expectedSessionVersion?: number
  ): Promise<Stage[]> => {
    setStagesLoading(true);
    setStagesError("");
    try {
      const list = await fetchAllStages(tournamentId);
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return list;
      if (expectedSessionVersion !== undefined && sessionVersion.current !== expectedSessionVersion) return list;
      setStages(list);
      return list;
    } catch (reason) {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return [];
      if (expectedSessionVersion !== undefined && sessionVersion.current !== expectedSessionVersion) return [];
      setStages([]);
      setStagesError((reason as Error).message || "Không thể tải danh sách vòng đấu.");
      return [];
    } finally {
      if (
        (expectedVersion === undefined || tournamentViewVersion.current === expectedVersion) &&
        (expectedSessionVersion === undefined || sessionVersion.current === expectedSessionVersion)
      ) {
        setStagesLoading(false);
      }
    }
  };

  const handleCreateStage = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!token || !selectedTournament) return;
    const startingSession = sessionVersion.current;
    const startingToken = token;
    const currentTournamentId = selectedTournament.tournament_id;
    const currentTournamentVersion = tournamentViewVersion.current;
    const trimmedName = newStageName.trim();
    const orderNum = Number(newStageOrder);

    if (!trimmedName) {
      setStageFormError("Tên vòng đấu không được để trống.");
      return;
    }
    if (!Number.isInteger(orderNum) || orderNum <= 0) {
      setStageFormError("Thứ tự vòng đấu phải là số nguyên dương.");
      return;
    }

    setStageActionLoading(true);
    setStageFormError("");
    setStagesNotice("");
    try {
      await request<Stage>(`/tournaments/${currentTournamentId}/stages`, {
        method: "POST",
        body: JSON.stringify({ name: trimmedName, sequence_order: orderNum }),
      }, startingToken);
      if (
        tournamentViewVersion.current !== currentTournamentVersion ||
        sessionVersion.current !== startingSession ||
        token !== startingToken
      ) {
        return;
      }
      setNewStageName("");
      setNewStageOrder("");
      setIsCreatingStage(false);
      setStagesNotice("Đã thêm vòng đấu thành công.");
      await loadTournamentStages(currentTournamentId, currentTournamentVersion, startingSession);
      if (
        tournamentViewVersion.current !== currentTournamentVersion ||
        sessionVersion.current !== startingSession ||
        token !== startingToken
      ) {
        return;
      }
    } catch (reason) {
      if (
        tournamentViewVersion.current !== currentTournamentVersion ||
        sessionVersion.current !== startingSession ||
        token !== startingToken
      ) {
        return;
      }
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setStageFormError((reason as Error).message || "Không thể tạo vòng đấu.");
    } finally {
      if (
        tournamentViewVersion.current === currentTournamentVersion &&
        sessionVersion.current === startingSession
      ) {
        setStageActionLoading(false);
      }
    }
  };

  const handleUpdateStage = async (stageId: number, e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!token || !selectedTournament) return;
    const startingSession = sessionVersion.current;
    const startingToken = token;
    const currentTournamentId = selectedTournament.tournament_id;
    const currentTournamentVersion = tournamentViewVersion.current;
    const trimmedName = editingStageName.trim();
    const orderNum = Number(editingStageOrder);

    if (!trimmedName) {
      setStageFormError("Tên vòng đấu không được để trống.");
      return;
    }
    if (!Number.isInteger(orderNum) || orderNum <= 0) {
      setStageFormError("Thứ tự vòng đấu phải là số nguyên dương.");
      return;
    }

    setStageActionLoading(true);
    setStageFormError("");
    setStagesNotice("");
    try {
      await request<Stage>(`/tournaments/${currentTournamentId}/stages/${stageId}`, {
        method: "PATCH",
        body: JSON.stringify({ name: trimmedName, sequence_order: orderNum }),
      }, startingToken);
      if (
        tournamentViewVersion.current !== currentTournamentVersion ||
        sessionVersion.current !== startingSession ||
        token !== startingToken
      ) {
        return;
      }
      setEditingStageId(null);
      setStagesNotice("Đã cập nhật vòng đấu.");
      await loadTournamentStages(currentTournamentId, currentTournamentVersion, startingSession);
      if (
        tournamentViewVersion.current !== currentTournamentVersion ||
        sessionVersion.current !== startingSession ||
        token !== startingToken
      ) {
        return;
      }
    } catch (reason) {
      if (
        tournamentViewVersion.current !== currentTournamentVersion ||
        sessionVersion.current !== startingSession ||
        token !== startingToken
      ) {
        return;
      }
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setStageFormError((reason as Error).message || "Không thể cập nhật vòng đấu.");
    } finally {
      if (
        tournamentViewVersion.current === currentTournamentVersion &&
        sessionVersion.current === startingSession
      ) {
        setStageActionLoading(false);
      }
    }
  };

  const handleDeleteStage = async (stage: Stage) => {
    if (!token || !selectedTournament) return;
    const startingSession = sessionVersion.current;
    const startingToken = token;
    const currentTournamentId = selectedTournament.tournament_id;
    const currentTournamentVersion = tournamentViewVersion.current;
    if (!window.confirm(`Bạn có chắc chắn muốn xóa vòng đấu "${stage.name}"?`)) return;

    setStageActionLoading(true);
    setStagesError("");
    setStagesNotice("");
    try {
      await request(`/tournaments/${currentTournamentId}/stages/${stage.stage_id}`, {
        method: "DELETE",
      }, startingToken);
      if (
        tournamentViewVersion.current !== currentTournamentVersion ||
        sessionVersion.current !== startingSession ||
        token !== startingToken
      ) {
        return;
      }
      setStagesNotice("Đã xóa vòng đấu.");
      await loadTournamentStages(currentTournamentId, currentTournamentVersion, startingSession);
      if (
        tournamentViewVersion.current !== currentTournamentVersion ||
        sessionVersion.current !== startingSession ||
        token !== startingToken
      ) {
        return;
      }
    } catch (reason) {
      if (
        tournamentViewVersion.current !== currentTournamentVersion ||
        sessionVersion.current !== startingSession ||
        token !== startingToken
      ) {
        return;
      }
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setStagesError((reason as Error).message || "Không thể xóa vòng đấu.");
    } finally {
      if (
        tournamentViewVersion.current === currentTournamentVersion &&
        sessionVersion.current === startingSession
      ) {
        setStageActionLoading(false);
      }
    }
  };

  const handleMoveStage = async (stageIndex: number, direction: "up" | "down") => {
    if (!token || !selectedTournament || stageActionLoading) return;
    const targetIndex = direction === "up" ? stageIndex - 1 : stageIndex + 1;
    if (targetIndex < 0 || targetIndex >= stages.length) return;

    const startingSession = sessionVersion.current;
    const startingToken = token;
    const currentTournamentId = selectedTournament.tournament_id;
    const currentTournamentVersion = tournamentViewVersion.current;
    setStageActionLoading(true);
    setStagesError("");
    setStagesNotice("");

    try {
      const allStages = await fetchAllStages(currentTournamentId);
      if (
        tournamentViewVersion.current !== currentTournamentVersion ||
        sessionVersion.current !== startingSession ||
        token !== startingToken
      ) {
        return;
      }

      const currentStageId = stages[stageIndex]?.stage_id;
      if (!currentStageId) return;
      const allIdx = allStages.findIndex((s) => s.stage_id === currentStageId);
      if (allIdx === -1) {
        throw new Error("Không tìm thấy vòng đấu để sắp xếp.");
      }
      const allTargetIdx = direction === "up" ? allIdx - 1 : allIdx + 1;
      if (allTargetIdx < 0 || allTargetIdx >= allStages.length) return;

      const updated = [...allStages];
      const temp = updated[allIdx];
      updated[allIdx] = updated[allTargetIdx];
      updated[allTargetIdx] = temp;

      const stageIds = updated.map((s) => s.stage_id);
      const reordered = await request<Stage[]>(`/tournaments/${currentTournamentId}/stages/order`, {
        method: "PUT",
        body: JSON.stringify({ stage_ids: stageIds }),
      }, startingToken);

      if (
        tournamentViewVersion.current !== currentTournamentVersion ||
        sessionVersion.current !== startingSession ||
        token !== startingToken
      ) {
        return;
      }
      setStages(reordered);
      setStagesNotice("Đã cập nhật thứ tự vòng đấu.");
    } catch (reason) {
      if (
        tournamentViewVersion.current !== currentTournamentVersion ||
        sessionVersion.current !== startingSession ||
        token !== startingToken
      ) {
        return;
      }
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setStagesError((reason as Error).message || "Không thể sắp xếp thứ tự vòng đấu.");
      await loadTournamentStages(currentTournamentId, currentTournamentVersion, startingSession);
      if (
        tournamentViewVersion.current !== currentTournamentVersion ||
        sessionVersion.current !== startingSession ||
        token !== startingToken
      ) {
        return;
      }
    } finally {
      if (
        tournamentViewVersion.current === currentTournamentVersion &&
        sessionVersion.current === startingSession
      ) {
        setStageActionLoading(false);
      }
    }
  };

  const loadRosterLock = async (tournamentId: number, expectedVersion?: number) => {
    try {
      const res = await request<RosterLockRead>(`/tournaments/${tournamentId}/roster-lock`);
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      setRosterLock(res);
    } catch {
      if (expectedVersion !== undefined && tournamentViewVersion.current !== expectedVersion) return;
      setRosterLock(null);
    }
  };

  const loadTeamRosterData = async (
    teamId: number,
    expectedTournamentVersion?: number,
    expectedTeamVersion?: number,
    preserveError = false,
    expectedSessionVersion?: number
  ) => {
    const sessionV = expectedSessionVersion ?? sessionVersion.current;
    if (!selectedTournament) return;
    const currentTournamentId = selectedTournament.tournament_id;
    setRosterLoading(true);
    if (!preserveError) {
      setRosterError("");
    }
    setRosterNotice("");
    try {
      let caps: RosterCapabilities | null = null;
      if (token) {
        try {
          caps = await request<RosterCapabilities>(
            `/tournaments/${currentTournamentId}/teams/${teamId}/roster/capabilities`,
            {},
            token
          );
        } catch (reason) {
          if (expectedTournamentVersion !== undefined && tournamentViewVersion.current !== expectedTournamentVersion) return;
          if (expectedTeamVersion !== undefined && rosterTeamVersion.current !== expectedTeamVersion) return;
          if (sessionVersion.current !== sessionV) return;
          if (activeRosterTeamIdRef.current !== teamId) return;

          if (reason instanceof RequestError && reason.status === 401) {
            handleAuthExpired();
            return;
          }
          throw reason;
        }
      }

      if (expectedTournamentVersion !== undefined && tournamentViewVersion.current !== expectedTournamentVersion) return;
      if (expectedTeamVersion !== undefined && rosterTeamVersion.current !== expectedTeamVersion) return;
      if (sessionVersion.current !== sessionV) return;
      if (activeRosterTeamIdRef.current !== teamId) return;

      setRosterCapabilities(caps);

      const roster = await request<RosterRead>(
        `/tournaments/${currentTournamentId}/teams/${teamId}/roster`,
        {},
        token || undefined
      );

      if (expectedTournamentVersion !== undefined && tournamentViewVersion.current !== expectedTournamentVersion) return;
      if (expectedTeamVersion !== undefined && rosterTeamVersion.current !== expectedTeamVersion) return;
      if (sessionVersion.current !== sessionV) return;
      if (activeRosterTeamIdRef.current !== teamId) return;

      setRosterData(roster);
      setRosterDraftMembers(
        roster.members.map((m) => ({
          user_id: m.user_id,
          role_in_team: m.role_in_team,
          display_name: m.display_name ?? undefined,
        }))
      );

      if (caps?.can_edit_roster && token) {
        try {
          const members = await request<TeamMember[]>(
            `/teams/${teamId}/members?include_history=false`,
            {},
            token
          );
          if (expectedTournamentVersion !== undefined && tournamentViewVersion.current !== expectedTournamentVersion) return;
          if (expectedTeamVersion !== undefined && rosterTeamVersion.current !== expectedTeamVersion) return;
          if (sessionVersion.current !== sessionV) return;
          if (activeRosterTeamIdRef.current !== teamId) return;

          const eligible = members.filter(
            (m) => m.status === "ACTIVE" && (m.role === "PLAYER" || m.role === "SUBSTITUTE")
          );
          setTeamEligibleMembers(eligible);
        } catch (reason) {
          if (expectedTournamentVersion !== undefined && tournamentViewVersion.current !== expectedTournamentVersion) return;
          if (expectedTeamVersion !== undefined && rosterTeamVersion.current !== expectedTeamVersion) return;
          if (sessionVersion.current !== sessionV) return;
          if (activeRosterTeamIdRef.current !== teamId) return;

          if (reason instanceof RequestError && reason.status === 401) {
            handleAuthExpired();
            return;
          }
          setTeamEligibleMembers([]);
          setRosterError((reason as Error).message || "Không thể tải danh sách thành viên đội để chọn đội hình.");
          return;
        }
      } else {
        setTeamEligibleMembers([]);
      }
    } catch (reason) {
      if (expectedTournamentVersion !== undefined && tournamentViewVersion.current !== expectedTournamentVersion) return;
      if (expectedTeamVersion !== undefined && rosterTeamVersion.current !== expectedTeamVersion) return;
      if (sessionVersion.current !== sessionV) return;
      if (activeRosterTeamIdRef.current !== teamId) return;

      setRosterData(null);
      if (reason instanceof RequestError) {
        if (reason.status === 401) {
          if (token) {
            handleAuthExpired();
          } else {
            setRosterError("Đội hình đang là bản nháp riêng tư. Cần đăng nhập để xem.");
          }
          return;
        }
        if (reason.status === 403) {
          setRosterError("Bạn không có quyền xem đội hình nháp này (chỉ quản lý đội hoặc quản lý giải).");
          return;
        }
      }
      setRosterError((reason as Error).message || "Không thể tải thông tin đội hình.");
    } finally {
      if (
        (expectedTournamentVersion === undefined || tournamentViewVersion.current === expectedTournamentVersion) &&
        (expectedTeamVersion === undefined || rosterTeamVersion.current === expectedTeamVersion) &&
        sessionVersion.current === sessionV &&
        activeRosterTeamIdRef.current === teamId
      ) {
        setRosterLoading(false);
      }
    }
  };

  const openTeamRoster = async (teamId: number, teamName: string, teamTag?: string) => {
    if (selectedRosterTeam?.team_id === teamId) {
      resetRosterState();
      return;
    }
    const currentTeamVersion = ++rosterTeamVersion.current;
    activeRosterTeamIdRef.current = teamId;
    setSelectedRosterTeam({ team_id: teamId, name: teamName, tag: teamTag });
    setRosterData(null);
    setRosterCapabilities(null);
    setTeamEligibleMembers([]);
    setRosterDraftMembers([]);
    setRosterError("");
    setRosterNotice("");
    await loadTeamRosterData(teamId, tournamentViewVersion.current, currentTeamVersion, false, sessionVersion.current);
  };

  const addMemberToRosterDraft = (userId: number) => {
    const member = teamEligibleMembers.find((m) => m.user_id === userId);
    if (!member) return;
    if (rosterDraftMembers.some((m) => m.user_id === userId)) return;
    setRosterNotice("");
    setRosterError("");
    setRosterDraftMembers((prev) => [
      ...prev,
      {
        user_id: member.user_id,
        role_in_team: member.role as RosterRole,
        username: member.username,
      },
    ]);
  };

  const removeMemberFromRosterDraft = (userId: number) => {
    setRosterNotice("");
    setRosterError("");
    setRosterDraftMembers((prev) => prev.filter((m) => m.user_id !== userId));
  };

  const saveRoster = async () => {
    if (!token || !selectedTournament || !selectedRosterTeam) return;
    const startingSession = sessionVersion.current;
    const startingToken = token;
    const currentTournamentId = selectedTournament.tournament_id;
    const currentTournamentVersion = tournamentViewVersion.current;
    const currentTeamId = selectedRosterTeam.team_id;
    const currentTeamVersion = rosterTeamVersion.current;

    setRosterSaving(true);
    setRosterError("");
    setRosterNotice("");
    try {
      const payload = {
        members: rosterDraftMembers.map((m) => ({
          user_id: m.user_id,
          role_in_team: m.role_in_team,
        })),
      };
      const updated = await request<RosterRead>(
        `/tournaments/${currentTournamentId}/teams/${currentTeamId}/roster`,
        {
          method: "PUT",
          body: JSON.stringify(payload),
        },
        startingToken
      );

      if (
        tournamentViewVersion.current !== currentTournamentVersion ||
        sessionVersion.current !== startingSession ||
        token !== startingToken
      ) {
        return;
      }
      if (rosterTeamVersion.current !== currentTeamVersion || activeRosterTeamIdRef.current !== currentTeamId) return;

      setRosterData(updated);
      setRosterDraftMembers(
        updated.members.map((m) => ({
          user_id: m.user_id,
          role_in_team: m.role_in_team,
          display_name: m.display_name ?? undefined,
        }))
      );
      setRosterNotice("Đã lưu đội hình tham dự thành công!");

      setApprovedRosterStatuses((prev) => ({
        ...prev,
        [currentTeamId]: {
          loaded: true,
          hasPlayer: updated.members.some((m) => m.role_in_team === "PLAYER"),
        },
      }));
    } catch (reason) {
      if (tournamentViewVersion.current !== currentTournamentVersion) return;
      if (rosterTeamVersion.current !== currentTeamVersion || activeRosterTeamIdRef.current !== currentTeamId) return;

      if (reason instanceof RequestError) {
        if (reason.status === 401) {
          handleAuthExpired();
          return;
        }
        if (reason.status === 409) {
          const conflictMsg =
            reason.message || "Xung đột: Giải đấu đã bị khóa hoặc trạng thái đội hình đã thay đổi.";
          const currentSession = sessionVersion.current;
          const [caps, , approvedData] = await Promise.all([
            loadTournamentCapabilities(currentTournamentId, token, currentTournamentVersion, currentSession),
            loadRosterLock(currentTournamentId, currentTournamentVersion),
            loadApprovedTeams(currentTournamentId, approvedTeamsPage, currentTournamentVersion),
            loadTeamRosterData(currentTeamId, currentTournamentVersion, currentTeamVersion, true, currentSession),
          ]);
          if (
            tournamentViewVersion.current === currentTournamentVersion &&
            sessionVersion.current === currentSession &&
            token && approvedData?.list && (caps?.can_manage || caps?.can_lock_roster)
          ) {
            void loadApprovedTeamRosterStatuses(currentTournamentId, approvedData.list, token, currentTournamentVersion, currentSession);
          }
          if (
            tournamentViewVersion.current === currentTournamentVersion &&
            sessionVersion.current === currentSession &&
            rosterTeamVersion.current === currentTeamVersion
          ) {
            setRosterError(conflictMsg);
          }
          return;
        }
      }
      setRosterError((reason as Error).message || "Không thể lưu đội hình.");
    } finally {
      if (
        tournamentViewVersion.current === currentTournamentVersion &&
        rosterTeamVersion.current === currentTeamVersion &&
        activeRosterTeamIdRef.current === currentTeamId
      ) {
        setRosterSaving(false);
      }
    }
  };

  const handleLockRoster = async () => {
    if (!token || !selectedTournament) return;
    const startingSession = sessionVersion.current;
    const startingToken = token;
    const currentTournamentId = selectedTournament.tournament_id;
    const currentTournamentVersion = tournamentViewVersion.current;

    const confirmed = window.confirm(
      "Xác nhận khóa đội hình cho giải đấu này?\n\nSau khi khóa:\n- Không thể chỉnh sửa đội hình của các đội.\n- Không thể nhận thêm đơn đăng ký mới.\n- Snapshot đội hình sẽ được cố định để chuẩn bị thi đấu."
    );
    if (!confirmed) return;

    setLockLoading(true);
    setLockError("");
    setLockNotice("");
    try {
      const res = await request<RosterLockRead>(
        `/tournaments/${currentTournamentId}/roster-lock`,
        { method: "POST" },
        startingToken
      );

      if (
        tournamentViewVersion.current !== currentTournamentVersion ||
        sessionVersion.current !== startingSession ||
        token !== startingToken
      ) {
        return;
      }

      setRosterLock(res);
      setLockNotice("Đã khóa đội hình giải đấu thành công! Snapshot đội hình đã được cố định.");

      const currentSession = sessionVersion.current;
      const [caps, approvedData] = await Promise.all([
        loadTournamentCapabilities(currentTournamentId, token, currentTournamentVersion, currentSession),
        loadApprovedTeams(currentTournamentId, approvedTeamsPage, currentTournamentVersion),
        loadTournaments(),
      ]);

      if (tournamentViewVersion.current !== currentTournamentVersion || sessionVersion.current !== currentSession) return;

      if (token && approvedData?.list && (caps?.can_manage || caps?.can_lock_roster)) {
        void loadApprovedTeamRosterStatuses(currentTournamentId, approvedData.list, token, currentTournamentVersion, currentSession);
      }

      if (activeRosterTeamIdRef.current) {
        await loadTeamRosterData(activeRosterTeamIdRef.current, currentTournamentVersion, rosterTeamVersion.current, false, currentSession);
      }
    } catch (reason) {
      if (tournamentViewVersion.current !== currentTournamentVersion) return;

      if (reason instanceof RequestError) {
        if (reason.status === 401) {
          handleAuthExpired();
          return;
        }
        if (reason.status === 409) {
          const conflictMsg =
            reason.message || "Xung đột khi khóa đội hình: Trạng thái giải đấu hoặc đội hình đã thay đổi.";
          const currentSession = sessionVersion.current;
          const [caps, , approvedData] = await Promise.all([
            loadTournamentCapabilities(currentTournamentId, token, currentTournamentVersion, currentSession),
            loadRosterLock(currentTournamentId, currentTournamentVersion),
            loadApprovedTeams(currentTournamentId, approvedTeamsPage, currentTournamentVersion),
          ]);
          if (
            tournamentViewVersion.current === currentTournamentVersion &&
            sessionVersion.current === currentSession &&
            token && approvedData?.list && (caps?.can_manage || caps?.can_lock_roster)
          ) {
            void loadApprovedTeamRosterStatuses(currentTournamentId, approvedData.list, token, currentTournamentVersion, currentSession);
          }
          if (activeRosterTeamIdRef.current) {
            await loadTeamRosterData(activeRosterTeamIdRef.current, currentTournamentVersion, rosterTeamVersion.current, false, currentSession);
          }
          if (tournamentViewVersion.current === currentTournamentVersion && sessionVersion.current === currentSession) {
            setLockError(conflictMsg);
          }
          return;
        }
      }
      setLockError((reason as Error).message || "Không thể khóa đội hình.");
    } finally {
      if (tournamentViewVersion.current === currentTournamentVersion) {
        setLockLoading(false);
      }
    }
  };
  const reloadTournamentDetailsData = async (tournament: Tournament) => {
    const version = tournamentViewVersion.current;
    const currentSession = sessionVersion.current;
    setRegistrationError("");
    const managedTeams = await loadManagedTeamsForTournament(tournament.game_id, token, version, currentSession);
    if (tournamentViewVersion.current !== version || sessionVersion.current !== currentSession) return;
    const [, approvedData] = await Promise.all([
      loadTournamentCapabilities(tournament.tournament_id, token, version, currentSession),
      loadApprovedTeams(tournament.tournament_id, approvedTeamsPage, version),
      loadTournamentRegistrations(tournament.tournament_id, registrationStatusFilter, token, version, managedTeams, registrationPage, currentSession),
      loadRosterLock(tournament.tournament_id, version),
      loadTournamentStages(tournament.tournament_id, version, currentSession),
    ]);
    if (tournamentViewVersion.current !== version || sessionVersion.current !== currentSession) return;
    if (token && approvedData?.list && (tournamentCapabilities?.can_manage || tournamentCapabilities?.can_lock_roster)) {
      void loadApprovedTeamRosterStatuses(tournament.tournament_id, approvedData.list, token, version, currentSession);
    }
    if (activeRosterTeamIdRef.current) {
      await loadTeamRosterData(activeRosterTeamIdRef.current, version, rosterTeamVersion.current, false, currentSession);
    }
  };

  useEffect(() => {
    if (!selectedTournament) return;
    if (!token) {
      setTournamentCapabilities(null);
      setCapabilityError("");
      setRegistrations([]);
      setAllTournamentRegistrations([]);
      setRegistrationTotal(0);
      setRegistrationPage(0);
      setApprovedTeamsTotal(0);
      setApprovedTeamsPage(0);
      setManagedTeamsForTournament([]);
      setRegistrationError("");
      setRegistrationNotice("");
      resetRosterState();
      resetStagesState();
      setRosterLock(null);
      setLockError("");
      setLockNotice("");
      setApprovedRosterStatuses({});
      return;
    }
    const version = tournamentViewVersion.current;
    const sessionV = sessionVersion.current;
    void (async () => {
      const managedTeams = await loadManagedTeamsForTournament(selectedTournament.game_id, token, version, sessionV);
      if (tournamentViewVersion.current !== version || sessionVersion.current !== sessionV) return;
      const [, caps, approvedData] = await Promise.all([
        loadTournamentRegistrations(selectedTournament.tournament_id, registrationStatusFilter, token, version, managedTeams, registrationPage, sessionV),
        loadTournamentCapabilities(selectedTournament.tournament_id, token, version, sessionV),
        loadApprovedTeams(selectedTournament.tournament_id, approvedTeamsPage, version),
        loadRosterLock(selectedTournament.tournament_id, version),
        loadTournamentStages(selectedTournament.tournament_id, version, sessionV),
      ]);
      if (tournamentViewVersion.current !== version || sessionVersion.current !== sessionV) return;
      if (token && approvedData?.list && (caps?.can_manage || caps?.can_lock_roster)) {
        void loadApprovedTeamRosterStatuses(selectedTournament.tournament_id, approvedData.list, token, version, sessionV);
      }
      if (activeRosterTeamIdRef.current) {
        await loadTeamRosterData(activeRosterTeamIdRef.current, version, rosterTeamVersion.current, false, sessionV);
      }
    })();
  }, [token]);

  const submitRegistration = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !selectedTournament) return;
    const startingSession = sessionVersion.current;
    const startingToken = token;
    const currentTourneyId = selectedTournament.tournament_id;
    const currentGameId = selectedTournament.game_id;
    const currentTourneyVersion = tournamentViewVersion.current;

    setRegistrationLoading(true);
    setRegistrationError("");
    setRegistrationNotice("");
    const form = new FormData(event.currentTarget);
    const teamId = Number(form.get("team_id"));
    if (!teamId) {
      setRegistrationLoading(false);
      return;
    }
    try {
      await request<TournamentRegistrationItem>(`/tournaments/${currentTourneyId}/registrations`, {
        method: "POST",
        body: JSON.stringify({ team_id: teamId }),
      }, startingToken);

      if (
        sessionVersion.current !== startingSession ||
        token !== startingToken ||
        tournamentViewVersion.current !== currentTourneyVersion
      ) {
        return;
      }

      setRegistrationNotice("Đã gửi đơn đăng ký thành công.");
      await Promise.all([
        loadTournamentRegistrations(currentTourneyId, registrationStatusFilter, startingToken, currentTourneyVersion, undefined, registrationPage, startingSession),
        loadManagedTeamsForTournament(currentGameId, startingToken, currentTourneyVersion, startingSession),
      ]);
    } catch (reason) {
      if (
        sessionVersion.current !== startingSession ||
        token !== startingToken ||
        tournamentViewVersion.current !== currentTourneyVersion
      ) {
        return;
      }
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setRegistrationError((reason as Error).message);
    } finally {
      if (
        sessionVersion.current === startingSession &&
        tournamentViewVersion.current === currentTourneyVersion
      ) {
        setRegistrationLoading(false);
      }
    }
  };

  const cancelRegistration = async (registrationId: number) => {
    if (!token || !selectedTournament) return;
    if (!window.confirm("Bạn có chắc chắn muốn hủy đơn đăng ký này?")) return;
    const startingSession = sessionVersion.current;
    const startingToken = token;
    const currentTourneyId = selectedTournament.tournament_id;
    const currentGameId = selectedTournament.game_id;
    const currentTourneyVersion = tournamentViewVersion.current;

    setRegistrationLoading(true);
    setRegistrationError("");
    setRegistrationNotice("");
    try {
      await request<TournamentRegistrationItem>(`/tournaments/${currentTourneyId}/registrations/${registrationId}/cancel`, {
        method: "POST",
      }, startingToken);

      if (
        sessionVersion.current !== startingSession ||
        token !== startingToken ||
        tournamentViewVersion.current !== currentTourneyVersion
      ) {
        return;
      }

      setRegistrationNotice("Đã hủy đơn đăng ký.");
      await Promise.all([
        loadTournamentRegistrations(currentTourneyId, registrationStatusFilter, startingToken, currentTourneyVersion, undefined, registrationPage, startingSession),
        loadManagedTeamsForTournament(currentGameId, startingToken, currentTourneyVersion, startingSession),
      ]);
    } catch (reason) {
      if (
        sessionVersion.current !== startingSession ||
        token !== startingToken ||
        tournamentViewVersion.current !== currentTourneyVersion
      ) {
        return;
      }
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setRegistrationError((reason as Error).message);
    } finally {
      if (
        sessionVersion.current === startingSession &&
        tournamentViewVersion.current === currentTourneyVersion
      ) {
        setRegistrationLoading(false);
      }
    }
  };

  const decideRegistration = async (registrationId: number, status: "APPROVED" | "REJECTED") => {
    if (!token || !selectedTournament) return;
    let rejectionReason: string | undefined = undefined;
    if (status === "REJECTED") {
      const reason = window.prompt("Nhập lý do từ chối (tùy chọn, tối đa 500 ký tự):");
      if (reason === null) return;
      if (reason.trim()) rejectionReason = reason.trim().slice(0, 500);
    }
    const startingSession = sessionVersion.current;
    const startingToken = token;
    const currentTourneyId = selectedTournament.tournament_id;
    const currentTourneyVersion = tournamentViewVersion.current;

    setRegistrationLoading(true);
    setRegistrationError("");
    setRegistrationNotice("");
    try {
      const body: { status: "APPROVED" | "REJECTED"; rejection_reason?: string } = { status };
      if (rejectionReason) body.rejection_reason = rejectionReason;
      await request<TournamentRegistrationItem>(`/tournaments/${currentTourneyId}/registrations/${registrationId}/decision`, {
        method: "POST",
        body: JSON.stringify(body),
      }, startingToken);

      if (
        sessionVersion.current !== startingSession ||
        token !== startingToken ||
        tournamentViewVersion.current !== currentTourneyVersion
      ) {
        return;
      }

      setRegistrationNotice(status === "APPROVED" ? "Đã duyệt đơn đăng ký." : "Đã từ chối đơn đăng ký.");
      const [, approvedData, caps] = await Promise.all([
        loadTournamentRegistrations(currentTourneyId, registrationStatusFilter, startingToken, currentTourneyVersion, undefined, registrationPage, startingSession),
        loadApprovedTeams(currentTourneyId, approvedTeamsPage, currentTourneyVersion),
        loadTournamentCapabilities(currentTourneyId, startingToken, currentTourneyVersion, startingSession),
      ]);
      if (
        sessionVersion.current === startingSession &&
        token === startingToken &&
        tournamentViewVersion.current === currentTourneyVersion &&
        approvedData?.list &&
        (caps?.can_manage || caps?.can_lock_roster)
      ) {
        void loadApprovedTeamRosterStatuses(currentTourneyId, approvedData.list, startingToken, currentTourneyVersion, startingSession);
      }
    } catch (reason) {
      if (
        sessionVersion.current !== startingSession ||
        token !== startingToken ||
        tournamentViewVersion.current !== currentTourneyVersion
      ) {
        return;
      }
      if (reason instanceof RequestError && reason.status === 401) {
        handleAuthExpired();
        return;
      }
      setRegistrationError((reason as Error).message);
    } finally {
      if (
        sessionVersion.current === startingSession &&
        tournamentViewVersion.current === currentTourneyVersion
      ) {
        setRegistrationLoading(false);
      }
    }
  };

  const handleRegistrationFilterChange = async (status: string) => {
    setRegistrationStatusFilter(status);
    setRegistrationPage(0);
    if (!selectedTournament || !token) return;
    const version = tournamentViewVersion.current;
    const sessionV = sessionVersion.current;
    await loadTournamentRegistrations(
      selectedTournament.tournament_id,
      status,
      token,
      version,
      undefined,
      0,
      sessionV
    );
  };

  const viewTournament = async (tournamentId: number) => {
    const version = ++tournamentViewVersion.current;
    const sessionV = sessionVersion.current;
    setError("");
    setNotice("");
    setRegistrationError("");
    setRegistrationNotice("");
    resetRosterState();
    resetStagesState();
    setTournamentCapabilities(null);
    setCapabilityError("");
    setRosterLock(null);
    setLockLoading(false);
    setLockError("");
    setLockNotice("");
    setApprovedRosterStatuses({});
    setRosterStatusWarning("");
    setApprovedTeamsPage(0);
    setApprovedTeamsTotal(0);
    setRegistrationPage(0);
    setRegistrationTotal(0);
    try {
      const tournament = await request<Tournament>(`/tournaments/${tournamentId}`);
      if (tournamentViewVersion.current !== version || sessionVersion.current !== sessionV) return;
      setSelectedTournament(tournament);

      const managedTeamsPromise = loadManagedTeamsForTournament(tournament.game_id, token, version, sessionV);
      const capsPromise = loadTournamentCapabilities(tournamentId, token, version, sessionV);
      const approvedPromise = loadApprovedTeams(tournamentId, 0, version);
      const lockPromise = loadRosterLock(tournamentId, version);
      const stagesPromise = loadTournamentStages(tournamentId, version, sessionV);

      const [managedTeams, caps, approvedData] = await Promise.all([
        managedTeamsPromise,
        capsPromise,
        approvedPromise,
        lockPromise,
        stagesPromise,
      ]);
      if (tournamentViewVersion.current !== version || sessionVersion.current !== sessionV) return;

      if (token && approvedData?.list && (caps?.can_manage || caps?.can_lock_roster)) {
        void loadApprovedTeamRosterStatuses(tournamentId, approvedData.list, token, version, sessionV);
      }

      await loadTournamentRegistrations(tournamentId, registrationStatusFilter, token, version, managedTeams, 0, sessionV);
    } catch (reason) {
      if (tournamentViewVersion.current !== version || sessionVersion.current !== sessionV) return;
      setError((reason as Error).message);
    }
  };

  const submitTournament = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) return;
    setError("");
    setNotice("");
    setTournamentLoading(true);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const body = {
      name: form.get("name"), game_id: Number(form.get("game_id")),
      area_id: form.get("area_id") ? Number(form.get("area_id")) : null,
      format: form.get("format"), start_date: form.get("start_date"),
      end_date: form.get("end_date") || null, description: form.get("description") || null,
    };
    try {
      await request<Tournament>("/tournaments", { method: "POST", body: JSON.stringify(body) }, token);
      formElement.reset();
      await loadTournaments();
      setNotice("Đã tạo giải đấu mới.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setTournamentLoading(false);
    }
  };

  const changeTournamentStatus = async (status: string) => {
    if (!token || !selectedTournament) return;
    setTournamentLoading(true);
    setError("");
    try {
      const updated = await request<Tournament>(`/tournaments/${selectedTournament.tournament_id}/status`, {
        method: "POST", body: JSON.stringify({ status }),
      }, token);
      setSelectedTournament(updated);
      await loadTournamentCapabilities(updated.tournament_id, token, tournamentViewVersion.current, sessionVersion.current);
      await loadRosterLock(updated.tournament_id);
      await loadTournaments();
      setNotice(`Đã chuyển trạng thái giải sang ${status}.`);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setTournamentLoading(false);
    }
  };

  const updateTournament = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token || !selectedTournament) return;
    setTournamentLoading(true);
    const form = new FormData(event.currentTarget);
    const nullableFields = ["end_date", "description", "area_id"];
    const editable = tournamentCapabilities?.editable_fields ?? [];
    const body: Record<string, string | number | null> = {};
    for (const [key, value] of form.entries()) {
      if (!editable.includes(key)) continue;
      if (value !== "") {
        body[key] = key === "game_id" || key === "area_id" ? Number(value) : String(value);
      } else if (nullableFields.includes(key)) {
        body[key] = null;
      }
    }
    try {
      const updated = await request<Tournament>(`/tournaments/${selectedTournament.tournament_id}`, {
        method: "PATCH", body: JSON.stringify(body),
      }, token);
      setSelectedTournament(updated);
      await loadTournamentCapabilities(updated.tournament_id, token, tournamentViewVersion.current, sessionVersion.current);
      await loadTournaments();
      setNotice("Đã cập nhật thông tin giải đấu.");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setTournamentLoading(false);
    }
  };

  return (
    <>
      {/* Horizontal Top Navigation Bar */}
      <header className="ewc-navbar" aria-label="Thanh điều hướng chính">
        <div className="ewc-nav-left">
          <a className="ewc-logo-wrap navbar-brand-logo" href="#top" title="Nexus Arena">
            <span className="brand-mark">N</span>
            <span className="brand-text">
              <strong>NEXUS</strong>
              <span>ARENA</span>
            </span>
          </a>
        </div>

        <nav className="ewc-nav-center">
          <button
            type="button"
            className={`ewc-item ${activeNav === "home" ? "active" : ""}`}
            onClick={() => {
              setActiveNav("home");
              setShowGamesBar(false);
              setSelectedGameId(null);
              setTournamentGameFilter("");
              setTournamentPage(0);
              const el = document.getElementById("top");
              if (el) el.scrollIntoView({ behavior: "smooth" });
            }}
            title="Trang chủ"
          >
            <span className="ewc-icon"><img src="/ewc/icon-home.png" alt="Home" /></span>
            <strong>{t.navHome}</strong>
          </button>

          <button
            type="button"
            className={`ewc-item ${activeNav === "play" || showGamesBar ? "active" : ""}`}
            onClick={() => {
              setActiveNav("play");
              setShowGamesBar((prev) => !prev);
            }}
            title="Play / Giải đấu"
          >
            <span className="ewc-icon"><img src="/ewc/icon-play.png" alt="Play" /></span>
            <strong>{t.navPlay}</strong>
            <span className="nav-chevron">{showGamesBar || activeNav === "play" ? "▴" : "▾"}</span>
          </button>

          <button
            type="button"
            className={`ewc-item ${activeNav === "team" ? "active" : ""}`}
            onClick={() => {
              setActiveNav("team");
              setShowGamesBar(false);
              const el = document.getElementById("teams");
              if (el) el.scrollIntoView({ behavior: "smooth" });
            }}
            title="Team / Đội tuyển"
          >
            <span className="ewc-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </span>
            <strong>{t.navTeam}</strong>
          </button>

          <button
            type="button"
            className={`ewc-item ${activeNav === "news" ? "active" : ""}`}
            onClick={() => {
              setActiveNav("news");
              setShowGamesBar(false);
              const el = document.getElementById("news");
              if (el) el.scrollIntoView({ behavior: "smooth" });
            }}
            title="News / Tin tức"
          >
            <span className="ewc-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2" />
                <path d="M18 14h-8" />
                <path d="M15 18h-5" />
                <path d="M10 6h8v4h-8V6Z" />
              </svg>
            </span>
            <strong>{t.navNews}</strong>
          </button>
        </nav>

        <div className="ewc-nav-right">
          <div className="ewc-lang-dropdown-wrapper">
            <button
              className="ewc-lang-block"
              type="button"
              title="Chọn ngôn ngữ / Select Language"
              onClick={() => setLangDropdownOpen((prev) => !prev)}
            >
              <span className="ewc-lang-flag">{currentLang.flag}</span>
              <strong>{currentLang.label}</strong>
              <span className="ewc-lang-caret">▾</span>
            </button>
            {langDropdownOpen && (
              <div className="ewc-lang-menu">
                {LANGUAGES.map((item) => (
                  <button
                    key={item.code}
                    type="button"
                    className={`ewc-lang-item ${lang === item.code ? "is-active" : ""}`}
                    onClick={() => handleSelectLang(item.code)}
                  >
                    <span className="ewc-lang-flag">{item.flag}</span>
                    <span className="ewc-lang-label">{item.label}</span>
                    {lang === item.code && <span className="ewc-lang-check">✓</span>}
                  </button>
                ))}
              </div>
            )}
          </div>

          {user ? (
            <div
              className="ewc-user-block is-authenticated"
              title={`Tài khoản: ${user.username}`}
              onClick={() => setUserMenuOpen((prev) => !prev)}
              tabIndex={0}
              role="button"
              aria-label="Tài khoản người dùng"
            >
              <span className="ewc-avatar-wrap">
                <img src="/ewc/avatar.png" alt={user.username} className="ewc-avatar-img" />
              </span>
              <strong className="ewc-username">{user.username}</strong>

              {userMenuOpen && (
                <div className="ewc-user-dropdown" onClick={(e) => e.stopPropagation()}>
                  <div className="dropdown-user-info">
                    <strong>{user.username}</strong>
                    <span className="dropdown-role">{user.role}</span>
                    {user.email && <span className="dropdown-email">{user.email}</span>}
                  </div>
                  {globalCapabilities?.can_manage_catalog && (
                    <>
                      <hr className="dropdown-divider" />
                      <button
                        type="button"
                        className="dropdown-logout-btn dropdown-admin-btn"
                        onClick={() => {
                          setUserMenuOpen(false);
                          const el = document.getElementById("catalog");
                          if (el) el.scrollIntoView({ behavior: "smooth" });
                        }}
                      >
                        ⚙ {t.catalogAdminBtn}
                      </button>
                    </>
                  )}
                  <hr className="dropdown-divider" />
                  <button
                    type="button"
                    className="dropdown-logout-btn"
                    onClick={() => {
                      setUserMenuOpen(false);
                      logout();
                    }}
                  >
                    {t.navLogout}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <a
              href="#login"
              className="ewc-user-block sidebar-login"
              data-testid="sidebar-login"
              role="link"
              title={t.navAccount}
              onClick={(e) => {
                e.preventDefault();
                setError("");
                setNotice("");
                setAuthMode("login");
                setIsAuthModalOpen(true);
              }}
            >
              <span className="ewc-avatar-wrap">
                <img src="/ewc/avatar.png" alt="" className="ewc-avatar-img" />
              </span>
              <strong>{t.navLogin}</strong>
            </a>
          )}
        </div>
      </header>

      {/* Backdrop for Play Mega Menu */}
      {showGamesBar && (
        <div
          className="mega-menu-backdrop"
          onClick={() => {
            setShowGamesBar(false);
            setPublisherMenuOpen(false);
          }}
          aria-hidden="true"
        />
      )}

      {/* Play Mega Menu (As shown in the video) */}
      {showGamesBar && (
        <aside className="play-mega-menu" aria-label="Mega menu tựa game và nhà phát hành">
          {/* Top Bar: Publisher Switcher & Close button */}
          <div className="mega-menu-top">
            <div className="mega-publisher-select-box">
              <span className="mega-pub-label">{t.megaPublisher}</span>
              <div className="mega-pub-dropdown-wrapper">
                <button
                  type="button"
                  className={`mega-pub-btn-trigger ${publisherMenuOpen ? "active" : ""}`}
                  onClick={() => setPublisherMenuOpen((prev) => !prev)}
                  aria-haspopup="listbox"
                  aria-expanded={publisherMenuOpen}
                  aria-label="Chọn nhà phát hành"
                >
                  <span className="mega-pub-current-icon">
                    {selectedPublisherId === null ? (
                      <span className="mega-pub-globe">🌐</span>
                    ) : getPublisherLogo(selectedPublisherId) ? (
                      <img
                        src={getPublisherLogo(selectedPublisherId)!}
                        alt="Logo"
                        className="mega-pub-logo-img"
                      />
                    ) : (
                      "🎮"
                    )}
                  </span>
                  <span className="mega-pub-current-name">
                    {selectedPublisherId === null
                      ? t.megaAllPublishers
                      : publishers.find((p) => p.publisher_id === selectedPublisherId)?.name ?? "Chọn NPH"}
                  </span>
                  <span className="mega-pub-caret">{publisherMenuOpen ? "▲" : "▼"}</span>
                </button>

                {publisherMenuOpen && (
                  <div className="mega-pub-dropdown-popover" role="listbox">
                    <button
                      type="button"
                      className={`mega-pub-option ${selectedPublisherId === null ? "selected" : ""}`}
                      onClick={() => {
                        handleSelectPublisher(null);
                        setPublisherMenuOpen(false);
                      }}
                      role="option"
                      aria-selected={selectedPublisherId === null}
                    >
                      <span className="option-icon">🌐</span>
                      <div className="option-body">
                        <strong>Tất cả Nhà phát hành</strong>
                        <small>{t.megaAllGamesCount} ({games.length})</small>
                      </div>
                      {selectedPublisherId === null && <span className="option-check">✓</span>}
                    </button>

                    {publishers.map((pub) => {
                      const isSelected = selectedPublisherId === pub.publisher_id;
                      const count = games.filter((g) => gameMatchesPublisher(g, pub.publisher_id, publishers)).length;
                      const logo = getPublisherLogo(pub.name);
                      return (
                        <button
                          key={pub.publisher_id}
                          type="button"
                          className={`mega-pub-option ${isSelected ? "selected" : ""}`}
                          onClick={() => {
                            handleSelectPublisher(pub.publisher_id);
                            setPublisherMenuOpen(false);
                          }}
                          role="option"
                          aria-selected={isSelected}
                        >
                          <span className="option-icon">
                            {logo ? (
                              <img src={logo} alt={pub.name} className="mega-pub-popover-logo" />
                            ) : (
                              "🎮"
                            )}
                          </span>
                          <div className="option-body">
                            <strong>{pub.name}</strong>
                            <small>{count} {t.megaGamesSuffix}</small>
                          </div>
                          {isSelected && <span className="option-check">✓</span>}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            <button
              type="button"
              className="mega-menu-close"
              onClick={() => {
            setShowGamesBar(false);
            setPublisherMenuOpen(false);
          }}
              aria-label="Đóng menu"
            >
              ✕
            </button>
          </div>

          {/* Body: Multi-column navigation + Right showcase card */}
          <div className="mega-menu-body">
            {/* Column 1: TRÒ CHƠI */}
            <div className="mega-col mega-col-games">
              <span className="mega-col-title">{t.megaGames}</span>
              <div className="mega-items-list">
                {catalogLoading && displayedGames.length === 0 && (
                  <p className="muted catalog-loading-text">{t.catalogLoadingText}</p>
                )}
                {!catalogLoading && catalogReloadError && displayedGames.length === 0 && (
                  <div className="catalog-reload">
                    <p className="muted">{t.catalogSubtext}</p>
                    <button type="button" className="button secondary small" onClick={retryCatalogLoad} disabled={catalogLoading}>
                      {t.catalogReload}
                    </button>
                  </div>
                )}
                {displayedGames.map((game) => {
                  const isHovered = activePreviewGame?.slug === game.slug;
                  const isSelected = selectedGameId === game.game_id;
                  return (
                    <button
                      key={game.game_id}
                      type="button"
                      className={`mega-game-item ${isHovered ? "is-hovered" : ""} ${isSelected ? "is-selected" : ""}`}
                      onMouseEnter={() => setHoveredGameSlug(game.slug)}
                      onClick={() => {
                        if (game.publisher_id) {
                          handleSelectPublisher(game.publisher_id);
                        }
                        setSelectedGameId(game.game_id);
                        setTournamentGameFilter(String(game.game_id));
                        setTournamentPage(0);
                        setShowGamesBar(false);
                        const el = document.getElementById("tournaments");
                        if (el) el.scrollIntoView({ behavior: "smooth" });
                      }}
                    >
                      <span className="mega-game-item-left">
                        {(getGameLogo(game.slug) || getGameLogo(game.name)) ? (
                          <span className="mega-game-logo-wrap">
                            <img
                              src={(getGameLogo(game.slug) || getGameLogo(game.name))!}
                              alt={game.name}
                              className="mega-game-logo"
                            />
                          </span>
                        ) : (
                          <span className="mega-item-badge">{getGameBadge(game.name)}</span>
                        )}
                        <span className="mega-item-name">{game.name}</span>
                      </span>
                      <span className="mega-item-arrow">→</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Column 2: ESPORTS & GIẢI ĐẤU */}
            <div className="mega-col mega-col-esports">
              <span className="mega-col-title">{t.megaEsports}</span>
              <div className="mega-items-list">
                <button
                  type="button"
                  className="mega-link-item"
                  onClick={() => {
                    setSelectedGameId(null);
                    setTournamentGameFilter("");
                    setTournamentPage(0);
                    setShowGamesBar(false);
                    const el = document.getElementById("tournaments");
                    if (el) el.scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  <span>{t.megaAllTournaments}</span>
                  <span className="mega-tag-mini">LIVE</span>
                </button>
                <button
                  type="button"
                  className="mega-link-item"
                  onClick={() => {
                    setTournamentStatusFilter("ONGOING");
                    setShowGamesBar(false);
                    const el = document.getElementById("tournaments");
                    if (el) el.scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  <span>{t.megaOngoing}</span>
                </button>
                <button
                  type="button"
                  className="mega-link-item"
                  onClick={() => {
                    setTournamentStatusFilter("UPCOMING");
                    setShowGamesBar(false);
                    const el = document.getElementById("tournaments");
                    if (el) el.scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  <span>{t.megaUpcoming}</span>
                </button>
                <button
                  type="button"
                  className="mega-link-item"
                  onClick={() => {
                    setTournamentStatusFilter("COMPLETED");
                    setShowGamesBar(false);
                    const el = document.getElementById("tournaments");
                    if (el) el.scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  <span>{t.megaCompleted}</span>
                </button>
              </div>
            </div>

            {/* Column 3: HỆ THỐNG / VẬN HÀNH */}
            <div className="mega-col mega-col-system">
              <span className="mega-col-title">{t.megaSystem}</span>
              <div className="mega-items-list">
                <button
                  type="button"
                  className="mega-link-item"
                  onClick={() => {
                    setShowGamesBar(false);
                    setActiveNav("team");
                    const el = document.getElementById("teams");
                    if (el) el.scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  <span>{t.megaManageTeams}</span>
                </button>
                <button
                  type="button"
                  className="mega-link-item"
                  onClick={() => {
                    setShowGamesBar(false);
                    setActiveNav("news");
                    const el = document.getElementById("news");
                    if (el) el.scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  <span>{t.megaNews}</span>
                  <span className="mega-tag-mini" style={{ background: "rgba(34, 197, 94, 0.2)", color: "#4ade80", borderColor: "rgba(34, 197, 94, 0.4)" }}>MỚI</span>
                </button>
                {globalCapabilities?.can_manage_catalog && (
                  <button
                    type="button"
                    className="mega-link-item"
                    onClick={() => {
                      setShowGamesBar(false);
                      const el = document.getElementById("catalog");
                      if (el) el.scrollIntoView({ behavior: "smooth" });
                    }}
                  >
                    <span>{t.megaCatalog}</span>
                  </button>
                )}
                <button
                  type="button"
                  className="mega-link-item"
                  onClick={() => {
                    setShowGamesBar(false);
                    setNotice("Hệ thống giải đấu Nexus Arena phiên bản 2.0.");
                  }}
                >
                  <span>{t.megaRules}</span>
                </button>
              </div>
            </div>

            {/* Column 4: Dynamic Showcase Card (Video Reference) */}
            <div className="mega-col-preview">
              <div
                className="mega-preview-card"
                onClick={() => {
                  if (activePreviewGame) {
                    if (activePreviewGame.publisher_id) {
                      handleSelectPublisher(activePreviewGame.publisher_id);
                    }
                    setSelectedGameId(activePreviewGame.game_id);
                    setTournamentGameFilter(String(activePreviewGame.game_id));
                    setTournamentPage(0);
                  }
                  setShowGamesBar(false);
                  const el = document.getElementById("tournaments");
                  if (el) el.scrollIntoView({ behavior: "smooth" });
                }}
                role="button"
                tabIndex={0}
                aria-label={`${t.megaExploreNow} ${getLocalizedGameName(activePreviewMeta.title, lang)}`}
              >
                <img
                  src={activePreviewMeta.coverImage}
                  alt={activePreviewMeta.title}
                  className="mega-preview-img"
                />
                <div className="mega-preview-card-overlay">
                  <div className="mega-preview-top">
                    <span className="mega-preview-pub">
                      {getPublisherLogo(activePreviewMeta.publisherName) && (
                        <img
                          src={getPublisherLogo(activePreviewMeta.publisherName)!}
                          alt={activePreviewMeta.publisherName}
                          className="preview-pub-logo"
                        />
                      )}
                      {activePreviewMeta.publisherName}
                    </span>
                    <span className="mega-preview-badge">{activePreviewMeta.badge}</span>
                  </div>
                  <div className="mega-preview-bottom">
                    <button
                      type="button"
                      className="button hero-cta mega-preview-cta"
                    >
                      {t.megaExploreNow} <span>↗</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </aside>
      )}

      <main className="shell">
        <header className="hero" id="top">
          <div className="hero-content">
            <span className="eyebrow">{t.heroEyebrow}</span>
            <h1>{t.heroTitle1}<br /><em>{t.heroTitle2}</em></h1>
            <p>{t.heroDesc}</p>
            <div className="hero-actions">
              <a className="button hero-cta" href="#tournaments">
                {t.heroCta} <span>↗</span>
              </a>
              <span className="hero-date">{t.heroDate}</span>
            </div>
          </div>
        </header>

        {!isAuthModalOpen && (error || notice) && <div className={`${error ? "message error" : "message success"}${error?.startsWith("Không thể tải catalog") ? " catalog-error" : ""}`}>
          <p>{error || notice}</p>
          {error === "Không thể kiểm tra phiên đăng nhập. Hãy thử lại." && <button className="link-button" onClick={() => {
            setError("");
            setAuthCheckAttempt((attempt) => attempt + 1);
          }}>{t.retry}</button>}
        </div>}

        {user && (
          <section className="auth-layout user-profile-layout" id="auth-section">
            <section className="panel auth-panel">
              <div className="panel-title">
                <h2>{t.profileTitle}</h2>
              </div>
              <div className="profile">
                <p><strong>{user.username}</strong></p>
                <p>{user.email ?? t.profileVerifiedEmail} · {t.profileRole}: {user.role}</p>
                <p className="muted">{t.profileSessionNote}</p>
                <div style={{ marginTop: "14px" }}>
                  <button type="button" className="button secondary small" onClick={logout}>{t.navLogout}</button>
                </div>
              </div>
            </section>
          </section>
        )}
    <section id="tournaments" className="tournament-zone">
      <div className="section-heading">
        <div>
          <span className="eyebrow">
            {selectedGameId
              ? `${t.tournamentsEyebrowGame} ${getLocalizedGameName(games.find((g) => g.game_id === selectedGameId)?.name ?? "", lang).toUpperCase()}`
              : t.tournamentsEyebrowAll}
          </span>
          <h2>
            {selectedGameId
              ? `${t.tournamentsHeadingGame} ${getLocalizedGameName(games.find((g) => g.game_id === selectedGameId)?.name ?? "", lang)}`
              : t.tournamentsHeadingOngoing}
          </h2>
          <p>
            {selectedGameId
              ? `${t.tournamentsSubGame} (${getLocalizedGameName(games.find((g) => g.game_id === selectedGameId)?.name ?? "", lang)})`
              : t.tournamentsSubAll}
          </p>
        </div>
        <span className="section-count">{tournamentTotal} {t.tournamentCountBadge}</span>
      </div>

      {/* When in Play and no game is selected yet, show Game Picker Cards */}
      {activeNav === "play" && selectedGameId === null && (
        <div className="play-game-picker">
          <div className="picker-header">
            <div className="picker-header-text">
              <span className="eyebrow">{t.pickerHeaderEyebrow}</span>
              <h3>{t.pickerTitle}</h3>
              <p>
                {selectedPublisherId !== null
                  ? `Đang hiển thị các tựa game của nhà phát hành: ${publishers.find((p) => p.publisher_id === selectedPublisherId)?.name}`
                  : t.pickerSub}
              </p>
            </div>

            {/* Publisher Filter in Picker */}
            <div className="picker-publisher-filter">
              <span className="picker-filter-label">{t.pickerPublisherLabel}</span>
              <div className="picker-pub-select-wrapper">
                {selectedPublisherId !== null && getPublisherLogo(selectedPublisherId) && (
                  <img
                    src={getPublisherLogo(selectedPublisherId)!}
                    alt="Logo NPH"
                    className="picker-select-current-logo"
                  />
                )}
                <select
                  className="picker-pub-select"
                  aria-label="Lọc theo nhà phát hành"
                  value={selectedPublisherId ?? ""}
                  onChange={(e) => handleSelectPublisher(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">{t.pickerAllPubOption} ({games.length} game)</option>
                  {publishers.map((pub) => {
                    const count = games.filter((g) => gameMatchesPublisher(g, pub.publisher_id, publishers)).length;
                    return (
                      <option key={pub.publisher_id} value={pub.publisher_id}>
                        {pub.name} ({count} game)
                      </option>
                    );
                  })}
                </select>
              </div>
            </div>
          </div>

          {catalogLoading && displayedGames.length === 0 && (
            <p className="muted catalog-loading-text">{t.catalogLoadingText}</p>
          )}
          {!catalogLoading && catalogReloadError && displayedGames.length === 0 && (
            <div className="catalog-reload">
              <p className="muted">{t.catalogSubtext}</p>
              <button type="button" className="button secondary small" onClick={retryCatalogLoad} disabled={catalogLoading}>
                {t.catalogReload}
              </button>
            </div>
          )}
          <div className="picker-grid">
            {displayedGames.map((g) => {
              const pub = publishers.find((p) => p.publisher_id === g.publisher_id);
              return (
                <button
                  key={g.game_id}
                  type="button"
                  className="picker-card"
                  onClick={() => {
                    if (g.publisher_id) {
                      setSelectedPublisherId(g.publisher_id);
                    }
                    setSelectedGameId(g.game_id);
                    setTournamentGameFilter(String(g.game_id));
                    setTournamentPage(0);
                    const el = document.getElementById("tournaments");
                    if (el) el.scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  <div className="picker-badge">
                    {(getGameLogo(g.slug) || getGameLogo(g.name)) ? (
                      <span className="picker-game-logo-wrap">
                        <img
                          src={(getGameLogo(g.slug) || getGameLogo(g.name))!}
                          alt={g.name}
                          className="picker-game-logo"
                        />
                      </span>
                    ) : (
                      getGameBadge(g.name)
                    )}
                  </div>
                  <div className="picker-info">
                    <strong>
                      {(getGameLogo(g.slug) || getGameLogo(g.name)) && (
                        <img
                          src={(getGameLogo(g.slug) || getGameLogo(g.name))!}
                          alt=""
                          className="picker-title-logo"
                        />
                      )}
                      {g.name}
                    </strong>
                    <span className="picker-pub-tag">
                      {getPublisherLogo(pub?.name) && (
                        <img
                          src={getPublisherLogo(pub?.name)!}
                          alt={pub?.name}
                          className="picker-pub-tag-logo"
                        />
                      )}
                      NPH: {pub?.name ?? "Esports"}
                    </span>
                    <span className="picker-action-link">{t.pickerViewTournaments}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Selected Game Banner */}
      {selectedGameId !== null && (
        <div className="active-game-banner">
          <div className="active-game-badge">
            {(getGameLogo(games.find((g) => g.game_id === selectedGameId)?.slug) || getGameLogo(games.find((g) => g.game_id === selectedGameId)?.name)) ? (
              <span className="active-game-logo-wrap">
                <img
                  src={(getGameLogo(games.find((g) => g.game_id === selectedGameId)?.slug) || getGameLogo(games.find((g) => g.game_id === selectedGameId)?.name))!}
                  alt="Active game logo"
                  className="active-game-banner-logo"
                />
              </span>
            ) : (
              getGameBadge(games.find((g) => g.game_id === selectedGameId)?.name ?? "")
            )}
          </div>
          <div className="active-game-meta">
            <span className="active-game-label">
              {getPublisherLogo(games.find((g) => g.game_id === selectedGameId)?.publisher_id) && (
                <img
                  src={getPublisherLogo(games.find((g) => g.game_id === selectedGameId)?.publisher_id)!}
                  alt="Publisher logo"
                  className="active-game-pub-logo"
                />
              )}
              {t.pickerActiveDiscipline} · {publishers.find((p) => p.publisher_id === games.find((g) => g.game_id === selectedGameId)?.publisher_id)?.name?.toUpperCase() ?? "PLAY ARENA"}
            </span>
            <h3>
              {(getGameLogo(games.find((g) => g.game_id === selectedGameId)?.slug) || getGameLogo(games.find((g) => g.game_id === selectedGameId)?.name)) && (
                <img
                  src={(getGameLogo(games.find((g) => g.game_id === selectedGameId)?.slug) || getGameLogo(games.find((g) => g.game_id === selectedGameId)?.name))!}
                  alt=""
                  className="active-game-heading-logo"
                />
              )}
              {getLocalizedGameName(games.find((g) => g.game_id === selectedGameId)?.name ?? "", lang)}
            </h3>
            <p>
              {t.pickerShowingTournamentsFor} ({publishers.find((p) => p.publisher_id === games.find((g) => g.game_id === selectedGameId)?.publisher_id)?.name ?? "NPH"}).
            </p>
          </div>
          <button
            type="button"
            className="button secondary small active-game-reset"
            onClick={() => {
              setSelectedGameId(null);
              setTournamentGameFilter("");
              setTournamentAreaFilter("");
              setTournamentPage(0);
            }}
          >
            {t.pickerResetBtn}
          </button>
        </div>
      )}
            <div className="tournament-toolbar">
        <label>{t.allGamesFilter}<select
            aria-label="Bộ lọc giải đấu"
            value={tournamentGameFilter}
            onChange={(event) => {
              setTournamentPage(0);
              const val = event.target.value;
              setTournamentGameFilter(val);
              let nextArea = tournamentAreaFilter;
              if (val) {
                const found = games.find((g) => String(g.game_id) === val);
                setSelectedGameId(found ? found.game_id : null);
                if (found && found.publisher_id) {
                  setSelectedPublisherId(found.publisher_id);
                }
                if (tournamentAreaFilter && found) {
                  const currentAreaObj = areas.find(
                    (a) => String(a.area_id) === tournamentAreaFilter || a.code === tournamentAreaFilter
                  );
                  if (currentAreaObj && !isAreaMatchingGame(currentAreaObj, found)) {
                    nextArea = "";
                    setTournamentAreaFilter("");
                  }
                }
              } else {
                setSelectedGameId(null);
              }
              void loadTournaments(0, val, tournamentStatusFilter, nextArea);
            }}
          ><option value="">{t.allGamesFilter}</option>{games.map((game) => <option key={game.game_id} value={game.game_id}>{getLocalizedGameName(game.name, lang)}</option>)}</select></label>
        <label>{t.allStatusesFilter}<select value={tournamentStatusFilter} onChange={(event) => { setTournamentPage(0); setTournamentStatusFilter(event.target.value); void loadTournaments(0, tournamentGameFilter, event.target.value, tournamentAreaFilter); }}><option value="">{t.allStatusesFilter}</option><option value="UPCOMING">{t.statusUpcoming}</option><option value="ONGOING">{t.statusOngoing}</option><option value="COMPLETED">{t.statusCompleted}</option><option value="CANCELLED">{t.statusCancelled}</option></select></label>
        <label>{t.allAreasFilter}<select value={tournamentAreaFilter} onChange={(event) => { setTournamentPage(0); setTournamentAreaFilter(event.target.value); void loadTournaments(0, tournamentGameFilter, tournamentStatusFilter, event.target.value); }}><option value="">{t.allAreasFilter}</option>{tournamentAvailableAreas.map((area) => <option key={area.area_id} value={area.area_id}>{area.flag ? `${area.flag} ` : ""}{area.code} — {getLocalizedRegionCountry(area.code, area.country ?? area.name, lang)}</option>)}</select></label>
        <button className="button secondary" onClick={() => void loadTournaments()} disabled={tournamentLoading}>↻ {t.btnRefresh}</button>
      </div>
      {tournamentError && <div className="inline-error"><span>{tournamentError}</span><button className="link-button" onClick={() => void loadTournaments()}>{t.retry}</button></div>}
      {tournamentLoading && <div className="loading-state"><span className="spinner" /> {t.loadingTournaments}</div>}
      {!tournamentLoading && !tournamentError && tournaments.length === 0 && <div className="empty-state"><strong>{t.emptyTournamentsTitle}</strong><span>{t.emptyTournamentsSub}</span></div>}
      <div className="tournament-grid">{tournaments.map((tournament) => {
        const game = games.find((item) => item.game_id === tournament.game_id);
        const cardGameSlug = getGameCanonicalSlug(game ?? null) || "default";
        const cardGameLogo = getGameLogo(game?.slug || game?.name);
        return <article className={`tournament-card card-game-${cardGameSlug}`} data-tournament-id={tournament.tournament_id} key={tournament.tournament_id} onClick={() => void viewTournament(tournament.tournament_id)}>
          <div className="card-topline"><span className={`status status-${tournament.status.toLowerCase()}`}>{tournament.status === "UPCOMING" ? t.statusCardUpcoming : tournament.status === "ONGOING" ? t.statusCardOngoing : tournament.status === "COMPLETED" ? t.statusCardCompleted : t.statusCardCancelled}</span><span className="tournament-id">#T{String(tournament.tournament_id).padStart(3, "0")}</span></div>
          <h3>{tournament.name}</h3><p className="game-label">{cardGameLogo && <img src={cardGameLogo} alt="" className="card-game-icon" />}{game ? getLocalizedGameName(game.name, lang) : "Esports"} <span>·</span> {tournament.format.replace("_", " ")}</p>
          <div className="card-meta"><span>{t.cardDatePrefix} {new Date(tournament.start_date).toLocaleDateString(t.locale)}</span><span>{tournament.end_date ? `→ ${new Date(tournament.end_date).toLocaleDateString(t.locale)}` : t.cardOpenEnd}</span></div>
          <button className="card-link" onClick={(event) => { event.stopPropagation(); void viewTournament(tournament.tournament_id); }}>{t.cardViewDetails}</button>
        </article>;
      })}</div>
      {tournamentTotal > 6 && <div className="pagination"><button className="button secondary" disabled={tournamentPage === 0 || tournamentLoading} onClick={() => setTournamentPage((page) => page - 1)}>← {t.pagePrev}</button><span>{t.pageLabel} {tournamentPage + 1} / {Math.ceil(tournamentTotal / 6)}</span><button className="button secondary" disabled={(tournamentPage + 1) * 6 >= tournamentTotal || tournamentLoading} onClick={() => setTournamentPage((page) => page + 1)}>{t.pageNext} →</button></div>}
      {globalCapabilityError && <div className="error-banner"><span>{globalCapabilityError}</span><button className="button secondary" onClick={() => void loadGlobalCapabilities()}>{t.retry}</button></div>}

            {globalCapabilities?.can_create_tournament && <details className="tournament-create"><summary><span>+</span> {t.btnCreateTournament}</summary><form onSubmit={submitTournament} className="tournament-form">
        <label>{t.tcNameLabel}<input name="name" placeholder={t.tcNamePlaceholder} minLength={3} maxLength={150} required /></label><label>{t.tcGameLabel}<select name="game_id" defaultValue="" required onChange={(e) => setCreateTournamentGameId(e.target.value)}><option value="" disabled>{t.tcGameSelect}</option>{games.filter((game) => game.game_id > 0).map((game) => <option key={game.game_id} value={game.game_id}>{getLocalizedGameName(game.name, lang)}</option>)}</select></label><label>{t.tcFormatLabel}<select name="format" defaultValue="SINGLE_ELIM"><option value="SINGLE_ELIM">Single Elimination</option><option value="DOUBLE_ELIM">Double Elimination</option><option value="ROUND_ROBIN">Round Robin</option></select></label><label>{t.tcStartLabel}<input name="start_date" type="date" required /></label><label>{t.tcEndLabel}<input name="end_date" type="date" /></label><label>{t.tcAreaLabel}<select name="area_id" defaultValue=""><option value="">{t.tcAreaGlobal}</option>{createFormAreas.map((area) => <option key={area.area_id} value={area.area_id}>{area.name}</option>)}</select></label><label className="wide-field">{t.tcDescLabel}<textarea name="description" maxLength={2000} placeholder={t.tcDescPlaceholder} /></label><button className="button" disabled={tournamentLoading}>{t.tcSubmitBtn}</button>
      </form></details>}
      {selectedTournament && <div className="tournament-detail">
        <div className="detail-header"><div><span className="eyebrow">{t.detailTitle}</span><h3>{selectedTournament.name}</h3><p>{games.find((game) => game.game_id === selectedTournament.game_id)?.name ?? "Game"} · {selectedTournament.format.replace("_", " ")}</p></div><button className="link-button" onClick={closeTournamentDetail}>{t.detailClose}</button></div>
                <div className="detail-stats">
          <div><span>{t.detailStatus}</span><strong className={`status status-${selectedTournament.status.toLowerCase()}`}>{selectedTournament.status}</strong></div>
          <div><span>{t.detailRoster}</span><strong className={tournamentCapabilities?.roster_locked || rosterLock?.locked ? "status status-completed" : "status status-upcoming"}>{tournamentCapabilities?.roster_locked || rosterLock?.locked ? t.detailRosterLocked : t.detailRosterUnlocked}</strong></div>
          <div><span>{t.detailStartDate}</span><strong>{new Date(selectedTournament.start_date).toLocaleDateString(t.locale)}</strong></div>
          <div><span>{t.detailArea}</span><strong>{areas.find((area) => area.area_id === selectedTournament.area_id)?.name ?? t.detailGlobalArea}</strong></div>
        </div>
        {selectedTournament.description && <p className="detail-description">{selectedTournament.description}</p>}
        {capabilityError && <div className="error-banner"><span>{capabilityError}</span><button className="button secondary" onClick={() => void loadTournamentCapabilities(selectedTournament.tournament_id, token, tournamentViewVersion.current, sessionVersion.current)}>{t.retry}</button></div>}
                {tournamentCapabilities?.can_manage && <div className="manage-panel">
          <div className="panel-title"><h4>{t.detailOpsTitle}</h4></div>
          {selectedTournament.status === "UPCOMING" && (
            <div className="start-conditions-box">
              {tournamentCapabilities.roster_locked || rosterLock?.locked ? (
                <div className="condition-item met">
                  <span className="condition-icon">✓</span>
                  <span>{t.detailRosterLockedNotice}{rosterLock?.locked_at ? ` (${new Date(rosterLock.locked_at).toLocaleString(t.locale)})` : ""}. Đã đủ điều kiện khóa để bắt đầu giải đấu.</span>
                </div>
              ) : (
                <div className="condition-item unmet">
                  <span className="condition-icon">⚠️</span>
                  <div>
                    <strong>{t.detailConditionsTitle}</strong>
                    <p>{t.detailConditionsHelp}</p>
                    {rosterStatusWarning && (
                      <p className="condition-warning-detail text-warning">⚠️ {rosterStatusWarning}</p>
                    )}
                    {approvedTeams.length === 0 ? (
                      <p className="condition-warning-detail text-warning">{t.detailNoApprovedTeamsWarning}</p>
                    ) : (
                      (() => {
                        const missing = approvedTeams.filter(
                          (t) => approvedRosterStatuses[t.team_id]?.loaded && !approvedRosterStatuses[t.team_id]?.hasPlayer
                        );
                        if (missing.length > 0) {
                          return (
                            <p className="condition-warning-detail text-warning">
                              ⚠️ {t.detailMissingPlayersWarning}: <strong>{missing.map((t) => t.name).join(", ")}</strong>. Cần bổ sung PLAYER trước khi khóa.
                            </p>
                          );
                        }
                        const allLoaded = approvedTeams.every((t) => approvedRosterStatuses[t.team_id]?.loaded);
                        if (allLoaded && approvedTeams.length > 0) {
                          return (
                            <p className="condition-warning-detail text-success">
                              {t.detailRosterReady}
                            </p>
                          );
                        }
                        return null;
                      })()
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
          {selectedTournament.status === "UPCOMING" && (
            <div className="roster-lock-controls">
              {tournamentCapabilities.can_lock_roster && !(tournamentCapabilities.roster_locked || rosterLock?.locked) && (
                <div className="lock-prompt">
                  <button
                    type="button"
                    className="button warning"
                    disabled={lockLoading || tournamentLoading}
                    onClick={() => void handleLockRoster()}
                  >
                    {lockLoading ? <><span className="spinner" /> {t.detailLockingRoster}</> : t.detailLockRosterBtn}
                  </button>
                </div>
              )}
              {lockError && (
                <div className="error-banner">
                  <span>{lockError}</span>
                  <button type="button" className="button secondary" onClick={() => void handleLockRoster()}>{t.retry}</button>
                </div>
              )}
              {lockNotice && <div className="notice-banner">{lockNotice}</div>}
            </div>
          )}
          <div className="status-actions">{tournamentCapabilities.allowed_status_transitions.map((status) => <button className="button secondary" key={status} disabled={tournamentLoading} onClick={() => void changeTournamentStatus(status)}>{t.statusChangeTo} {status}</button>)}</div>{tournamentCapabilities.can_update && tournamentCapabilities.editable_fields.length > 0 && (
          <form className="tournament-form edit-form" onSubmit={updateTournament}>
            {tournamentCapabilities.editable_fields.includes("name") && (
              <label>Tên giải đấu<input name="name" defaultValue={selectedTournament.name} minLength={3} maxLength={150} required /></label>
            )}
            {tournamentCapabilities.editable_fields.includes("game_id") && (
              <label>Tựa game<select name="game_id" defaultValue={selectedTournament.game_id} required>
                {games.filter((game) => game.game_id > 0).map((game) => <option key={game.game_id} value={game.game_id}>{getLocalizedGameName(game.name, lang)}</option>)}
              </select></label>
            )}
            {tournamentCapabilities.editable_fields.includes("format") && (
              <label>Thể thức<select name="format" defaultValue={selectedTournament.format}>
                <option value="SINGLE_ELIM">Single Elimination</option>
                <option value="DOUBLE_ELIM">Double Elimination</option>
                <option value="ROUND_ROBIN">Round Robin</option>
              </select></label>
            )}
            {tournamentCapabilities.editable_fields.includes("start_date") && (
              <label>Bắt đầu<input name="start_date" type="date" defaultValue={selectedTournament.start_date.slice(0, 10)} required /></label>
            )}
            {tournamentCapabilities.editable_fields.includes("end_date") && (
              <label>Kết thúc<input name="end_date" type="date" defaultValue={selectedTournament.end_date ? selectedTournament.end_date.slice(0, 10) : ""} /></label>
            )}
            {tournamentCapabilities.editable_fields.includes("area_id") && (
              <label>Khu vực<select name="area_id" defaultValue={selectedTournament.area_id ?? ""}>
                <option value="">Toàn cầu</option>
                {areas.map((area) => <option key={area.area_id} value={area.area_id}>{area.name}</option>)}
              </select></label>
            )}
            {tournamentCapabilities.editable_fields.includes("description") && (
              <label className="wide-field">Mô tả<textarea name="description" maxLength={2000} defaultValue={selectedTournament.description ?? ""} /></label>
            )}
            <button className="button" disabled={tournamentLoading}>Lưu thay đổi</button>
          </form>
        )}</div>}

        <div className="stages-section" data-testid="tournament-stages-section">
          <div className="section-header">
            <div>
              <h4>Vòng đấu / Giai đoạn ({stages.length})</h4>
              <p className="muted small-text">Các vòng đấu theo thứ tự diễn ra trong giải.</p>
            </div>
            {tournamentCapabilities?.can_manage_stages && !isCreatingStage && (
              <button
                type="button"
                className="button small"
                onClick={() => {
                  setIsCreatingStage(true);
                  setNewStageName("");
                  setNewStageOrder(String(stages.length > 0 ? Math.max(...stages.map((s) => s.sequence_order)) + 1 : 1));
                  setStageFormError("");
                }}
              >
                + Thêm vòng đấu
              </button>
            )}
          </div>

          {stagesNotice && <div className="notice-banner">{stagesNotice}</div>}
          {stagesError && (
            <div className="error-banner">
              <span>{stagesError}</span>
              <button
                type="button"
                className="button secondary small"
                onClick={() => void loadTournamentStages(selectedTournament.tournament_id, tournamentViewVersion.current, sessionVersion.current)}
              >
                Thử lại
              </button>
            </div>
          )}

          {isCreatingStage && (
            <form className="stage-form create-form" onSubmit={(e) => void handleCreateStage(e)} data-testid="stage-create-form">
              <h5>Thêm vòng đấu mới</h5>
              {stageFormError && <div className="error-banner">{stageFormError}</div>}
              <div className="form-grid">
                <label>
                  Tên vòng đấu <span className="required">*</span>
                  <input
                    type="text"
                    required
                    maxLength={80}
                    placeholder="Ví dụ: Vòng bảng, Tứ kết, Chung kết..."
                    value={newStageName}
                    onChange={(e) => setNewStageName(e.target.value)}
                    disabled={stageActionLoading}
                  />
                </label>
                <label>
                  Thứ tự (#) <span className="required">*</span>
                  <input
                    type="number"
                    required
                    min="1"
                    value={newStageOrder}
                    onChange={(e) => setNewStageOrder(e.target.value)}
                    disabled={stageActionLoading}
                  />
                </label>
              </div>
              <div className="form-actions">
                <button type="submit" className="button small" disabled={stageActionLoading}>
                  {stageActionLoading ? <><span className="spinner" /> Đang thêm...</> : "Lưu vòng đấu"}
                </button>
                <button
                  type="button"
                  className="button secondary small"
                  disabled={stageActionLoading}
                  onClick={() => {
                    setIsCreatingStage(false);
                    setStageFormError("");
                  }}
                >
                  Hủy
                </button>
              </div>
            </form>
          )}

          {stagesLoading ? (
            <div className="loading-state">
              <span className="spinner" /> Đang tải danh sách vòng đấu...
            </div>
          ) : stages.length === 0 ? (
            <p className="muted">Giải đấu chưa có vòng đấu nào được thiết lập.</p>
          ) : (
            <div className="stage-list" data-testid="stage-list">
              {stages.map((stage, index) => {
                const isEditing = editingStageId === stage.stage_id;
                return (
                  <div
                    className={`stage-card ${isEditing ? "editing" : ""}`}
                    key={stage.stage_id}
                    data-stage-id={stage.stage_id}
                    data-sequence-order={stage.sequence_order}
                  >
                    {isEditing ? (
                      <form
                        className="stage-inline-edit"
                        onSubmit={(e) => void handleUpdateStage(stage.stage_id, e)}
                        data-testid={`stage-edit-form-${stage.stage_id}`}
                      >
                        {stageFormError && <div className="error-banner">{stageFormError}</div>}
                        <div className="form-grid">
                          <label>
                            Tên vòng đấu
                            <input
                              type="text"
                              required
                              maxLength={80}
                              value={editingStageName}
                              onChange={(e) => setEditingStageName(e.target.value)}
                              disabled={stageActionLoading}
                            />
                          </label>
                          <label>
                            Thứ tự (#)
                            <input
                              type="number"
                              required
                              min="1"
                              value={editingStageOrder}
                              onChange={(e) => setEditingStageOrder(e.target.value)}
                              disabled={stageActionLoading}
                            />
                          </label>
                        </div>
                        <div className="form-actions">
                          <button type="submit" className="button small" disabled={stageActionLoading}>
                            {stageActionLoading ? "Đang lưu..." : "Lưu"}
                          </button>
                          <button
                            type="button"
                            className="button secondary small"
                            disabled={stageActionLoading}
                            onClick={() => {
                              setEditingStageId(null);
                              setStageFormError("");
                            }}
                          >
                            Hủy
                          </button>
                        </div>
                      </form>
                    ) : (
                      <div className="stage-row">
                        <div className="stage-info">
                          <span className="stage-badge">#{stage.sequence_order}</span>
                          <strong className="stage-name">{stage.name}</strong>
                        </div>
                        {tournamentCapabilities?.can_manage_stages && (
                          <div className="stage-actions">
                            <button
                              type="button"
                              className="button secondary small"
                              title="Chuyển lên"
                              disabled={index === 0 || stageActionLoading}
                              onClick={() => void handleMoveStage(index, "up")}
                            >
                              ▲ Lên
                            </button>
                            <button
                              type="button"
                              className="button secondary small"
                              title="Chuyển xuống"
                              disabled={index === stages.length - 1 || stageActionLoading}
                              onClick={() => void handleMoveStage(index, "down")}
                            >
                              ▼ Xuống
                            </button>
                            <button
                              type="button"
                              className="button secondary small"
                              disabled={stageActionLoading}
                              onClick={() => {
                                setEditingStageId(stage.stage_id);
                                setNewStageName("");
                                setNewStageOrder("");
                                setEditingStageName(stage.name);
                                setEditingStageOrder(String(stage.sequence_order));
                                setStageFormError("");
                              }}
                            >
                              Sửa
                            </button>
                            <button
                              type="button"
                              className="button secondary small danger-link"
                              disabled={stageActionLoading}
                              onClick={() => void handleDeleteStage(stage)}
                            >
                              Xóa
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="approved-teams-section">
          <h4>Đội tuyển tham gia ({approvedTeamsTotal})</h4>
          {approvedTeams.length === 0 ? (
            <p className="muted">Chưa có đội tuyển nào được nhận vào giải.</p>
          ) : (
            <>
              <div className="approved-teams-grid">
                {approvedTeams.map((team) => (
                  <div className="approved-team-card" data-team-id={team.team_id} key={team.team_id}>
                    <div className="team-basic-info">
                      <strong>{team.name}</strong>
                      <span className="tag">#{team.tag}</span>
                      {approvedRosterStatuses[team.team_id]?.loaded &&
                        !(tournamentCapabilities?.roster_locked || rosterLock?.locked) && (
                          approvedRosterStatuses[team.team_id]?.hasPlayer ? (
                            <span className="status-badge ready">Đã có PLAYER</span>
                          ) : (
                            <span className="status-badge missing-player">Chưa có PLAYER</span>
                          )
                        )}
                    </div>
                    <button
                      type="button"
                      className="link-button roster-btn"
                      onClick={() => void openTeamRoster(team.team_id, team.name, team.tag)}
                    >
                      {selectedRosterTeam?.team_id === team.team_id ? "Đóng đội hình ▲" : "Đội hình ▼"}
                    </button>
                  </div>
                ))}
              </div>

              {approvedTeamsTotal > APPROVED_TEAMS_PER_PAGE && (
                <div className="pagination-controls" data-testid="approved-teams-pagination">
                  <button
                    type="button"
                    className="button secondary small"
                    disabled={approvedTeamsPage === 0}
                    onClick={() => void handleApprovedTeamsPageChange(approvedTeamsPage - 1)}
                  >
                    ‹ {t.pagePrev}
                  </button>
                  <span className="pagination-info">
                    Trang {approvedTeamsPage + 1} / {Math.max(1, Math.ceil(approvedTeamsTotal / APPROVED_TEAMS_PER_PAGE))} (Tổng {approvedTeamsTotal} đội)
                  </span>
                  <button
                    type="button"
                    className="button secondary small"
                    disabled={approvedTeamsPage >= Math.ceil(approvedTeamsTotal / APPROVED_TEAMS_PER_PAGE) - 1}
                    onClick={() => void handleApprovedTeamsPageChange(approvedTeamsPage + 1)}
                  >
                    {t.pageNext} ›
                  </button>
                </div>
              )}
            </>
          )}

          {selectedRosterTeam && (
            <div className="team-roster-panel" data-team-id={selectedRosterTeam.team_id}>
              <div className="panel-header">
                <div>
                  <span className="eyebrow">TOURNAMENT ROSTER</span>
                  <h5>
                    Đội hình: {selectedRosterTeam.name}
                    {selectedRosterTeam.tag && <span className="tag"> #{selectedRosterTeam.tag}</span>}
                  </h5>
                </div>
                <div className="header-badges">
                  {rosterData?.locked || rosterLock?.locked || tournamentCapabilities?.roster_locked ? (
                    <span className="status status-completed">{t.detailLockedStatus}</span>
                  ) : (
                    <span className="status status-upcoming">{t.detailDraftStatus}</span>
                  )}
                  <button
                    type="button"
                    className="link-button"
                    onClick={resetRosterState}
                  >
                    Đóng ×
                  </button>
                </div>
              </div>

              {rosterLoading && (
                <div className="loading-state">
                  <span className="spinner" /> Đang tải dữ liệu đội hình...
                </div>
              )}

              {rosterError && (
                <div className="error-banner">
                  <span>{rosterError}</span>
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() => void loadTeamRosterData(selectedRosterTeam.team_id, tournamentViewVersion.current)}
                  >
                    Thử lại
                  </button>
                </div>
              )}

              {rosterNotice && <div className="notice-banner">{rosterNotice}</div>}

              {!rosterLoading && (rosterData || !rosterError) && (
                <>
                  {!Boolean(rosterData?.locked || rosterLock?.locked || tournamentCapabilities?.roster_locked) &&
                  selectedTournament.status === "UPCOMING" &&
                  rosterCapabilities?.can_edit_roster ? (
                    <div className="roster-editor">
                      <div className="editor-heading">
                        <strong>Danh sách tuyển thủ tham gia giải đấu:</strong>
                        <span className="muted">
                          (Yêu cầu tối thiểu 1 tuyển thủ PLAYER để đủ điều kiện khóa giải)
                        </span>
                      </div>

                      {rosterDraftMembers.length === 0 ? (
                        <p className="muted empty-roster-msg">Chưa có tuyển thủ nào trong đội hình tham dự.</p>
                      ) : (
                        <div className="roster-members-list">
                          {rosterDraftMembers.map((m) => {
                            const displayName =
                              m.display_name ??
                              m.username ??
                              teamEligibleMembers.find((em) => em.user_id === m.user_id)?.username ??
                              `User #${m.user_id}`;
                            return (
                              <div className="roster-member-row" key={m.user_id}>
                                <div className="member-name-role">
                                  <strong>{displayName}</strong>
                                  <span className={`role-badge role-${m.role_in_team.toLowerCase()}`}>
                                    {m.role_in_team === "PLAYER" ? "Chính thức (PLAYER)" : "Dự bị (SUBSTITUTE)"}
                                  </span>
                                </div>
                                <button
                                  type="button"
                                  className="link-button danger-link"
                                  disabled={rosterSaving}
                                  onClick={() => removeMemberFromRosterDraft(m.user_id)}
                                >
                                  Gỡ khỏi đội hình
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {teamEligibleMembers.filter((em) => !rosterDraftMembers.some((m) => m.user_id === em.user_id)).length > 0 && (
                        <div className="add-member-form">
                          <label>
                            Thêm tuyển thủ từ danh sách đội:
                            <select
                              value=""
                              onChange={(e) => {
                                const uid = Number(e.target.value);
                                if (uid) {
                                  addMemberToRosterDraft(uid);
                                }
                              }}
                            >
                              <option value="" disabled>-- Chọn thành viên để thêm --</option>
                              {teamEligibleMembers
                                .filter((em) => !rosterDraftMembers.some((m) => m.user_id === em.user_id))
                                .map((em) => (
                                  <option key={em.user_id} value={em.user_id}>
                                    {em.username} ({em.role})
                                  </option>
                                ))}
                            </select>
                          </label>
                        </div>
                      )}

                      {teamEligibleMembers.length === 0 && (
                        <p className="muted small-text">
                          Đội chưa có thành viên PLAYER hoặc SUBSTITUTE đang hoạt động nào. Hãy thêm tuyển thủ vào đội tuyển trước.
                        </p>
                      )}

                      <div className="roster-save-actions">
                        <button
                          type="button"
                          className="button"
                          disabled={rosterSaving}
                          onClick={() => void saveRoster()}
                        >
                          {rosterSaving ? <><span className="spinner" /> Đang lưu...</> : "Lưu đội hình"}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="roster-viewer">
                      {(!rosterData?.members || rosterData.members.length === 0) ? (
                        <p className="muted">{t.detailRosterNoPlayers}</p>
                      ) : (
                        <div className="roster-members-grid">
                          {rosterData.members.map((m) => (
                            <div className="roster-member-card" key={m.user_id}>
                              <strong>{m.display_name ?? `User #${m.user_id}`}</strong>
                              <span className={`role-badge role-${m.role_in_team.toLowerCase()}`}>
                                {m.role_in_team === "PLAYER" ? "Chính thức (PLAYER)" : "Dự bị (SUBSTITUTE)"}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </> 
              )}
            </div>
          )}
        </div>

        {selectedTournament.status === "UPCOMING" && tournamentCapabilities?.roster_locked === false && token && (
          (() => {
            const availableTeams = managedTeamsForTournament.filter(
              (team) => !allTournamentRegistrations.some((r) => r.team_id === team.team_id)
            );
            return availableTeams.length > 0 ? (
              <form className="registration-form" onSubmit={submitRegistration}>
                <h4>{t.regFormTitle}</h4>
                <div className="form-row">
                  <label>
                    Chọn đội tuyển
                    <select name="team_id" required defaultValue={availableTeams[0].team_id}>
                      {availableTeams.map((team) => (
                        <option key={team.team_id} value={team.team_id}>
                          {team.name} (#{team.tag})
                        </option>
                      ))}
                    </select>
                  </label>
                  <button className="button" disabled={registrationLoading}>{t.regSubmitBtn}</button>
                </div>
              </form>
            ) : null;
          })()
        )}

        {selectedTournament.status === "UPCOMING" && (tournamentCapabilities?.roster_locked || rosterLock?.locked) && token && (
          <div className="info-banner" style={{ marginTop: "16px" }}>
            {t.regRosterLockedNotice}
          </div>
        )}

        {(registrations.length > 0 || tournamentCapabilities?.can_review_registrations || registrationError) && (
          <div className="registrations-section">
            {(tournamentCapabilities?.roster_locked || rosterLock?.locked) && selectedTournament.status === "UPCOMING" && (
              <div className="info-banner">
                {t.regRosterLockedReviewNotice}
              </div>
            )}
            <div className="section-header">
              <h4>{t.regListTitle} ({registrationTotal})</h4>
              {tournamentCapabilities?.can_review_registrations && (
                <select
                  className="filter-select"
                  value={registrationStatusFilter}
                  onChange={(e) => handleRegistrationFilterChange(e.target.value)}
                >
                  <option value="">{t.allStatusesFilter}</option>
                  <option value="PENDING">{t.regStatusPending} (PENDING)</option>
                  <option value="APPROVED">{t.regStatusApproved} (APPROVED)</option>
                  <option value="REJECTED">{t.regStatusRejected} (REJECTED)</option>
                  <option value="CANCELLED">{t.regStatusCancelled} (CANCELLED)</option>
                </select>
              )}
            </div>

            {registrationError && (
              <div className="error-banner">
                <span>{registrationError}</span>
                <button className="button secondary" onClick={() => void reloadTournamentDetailsData(selectedTournament)}>{t.retry}</button>
              </div>
            )}
            {registrationNotice && <div className="notice-banner">{registrationNotice}</div>}

            {registrations.length === 0 ? (
              <p className="muted">{t.regEmpty}</p>
            ) : (
              <>
                <div className="registration-list">
                {registrations.map((reg) => {
                  const teamName = teams.find((t) => t.team_id === reg.team_id)?.name ??
                                   managedTeamsForTournament.find((t) => t.team_id === reg.team_id)?.name ??
                                   `Đội #${reg.team_id}`;
                  const teamTag = teams.find((t) => t.team_id === reg.team_id)?.tag ??
                                  managedTeamsForTournament.find((t) => t.team_id === reg.team_id)?.tag;
                  const isMyManagedTeam = managedTeamsForTournament.some((t) => t.team_id === reg.team_id);
                  const canReview = tournamentCapabilities?.can_review_registrations;

                  return (
                    <div className="registration-card" data-registration-id={reg.registration_id} data-team-id={reg.team_id} key={reg.registration_id}>
                      <div className="reg-info">
                        <strong>{teamName} {teamTag && <span className="tag">#{teamTag}</span>}</strong>
                        <span className={`reg-badge reg-badge-${reg.status.toLowerCase()}`}>{reg.status}</span>
                        <p className="reg-meta">
                          {t.regSubmittedPrefix}: {new Date(reg.submitted_at).toLocaleString(t.locale)}
                          {reg.rejection_reason && <span className="reg-reason"> · {t.regReasonPrefix}: {reg.rejection_reason}</span>}
                        </p>
                      </div>
                      <div className="reg-actions">
                        {canReview && reg.status === "PENDING" && selectedTournament.status === "UPCOMING" && (
                          <>
                            {tournamentCapabilities?.can_approve_registrations && (
                            <button
                              className="button small"
                              disabled={registrationLoading}
                              onClick={() => void decideRegistration(reg.registration_id, "APPROVED")}
                            >
                              Duyệt
                            </button>
                            )}
                            <button
                              className="button secondary small danger"
                              disabled={registrationLoading}
                              onClick={() => void decideRegistration(reg.registration_id, "REJECTED")}
                            >
                              Từ chối
                            </button>
                          </>
                        )}
                        {isMyManagedTeam && reg.status === "PENDING" && selectedTournament.status === "UPCOMING" && (
                          <button
                            className="button secondary small danger"
                            disabled={registrationLoading}
                            onClick={() => void cancelRegistration(reg.registration_id)}
                          >
                            Hủy đơn
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {registrationTotal > REGISTRATIONS_PER_PAGE && (
                <div className="pagination-controls" data-testid="registrations-pagination">
                  <button
                    type="button"
                    className="button secondary small"
                    disabled={registrationPage === 0 || registrationLoading}
                    onClick={() => void handleRegistrationPageChange(registrationPage - 1)}
                  >
                    ‹ {t.pagePrev}
                  </button>
                  <span className="pagination-info">
                    Trang {registrationPage + 1} / {Math.max(1, Math.ceil(registrationTotal / REGISTRATIONS_PER_PAGE))} (Tổng {registrationTotal} {t.regTotalSuffix})
                  </span>
                  <button
                    type="button"
                    className="button secondary small"
                    disabled={registrationPage >= Math.ceil(registrationTotal / REGISTRATIONS_PER_PAGE) - 1 || registrationLoading}
                    onClick={() => void handleRegistrationPageChange(registrationPage + 1)}
                  >
                    {t.pageNext} ›
                  </button>
                </div>
              )}
            </>
          )}
          </div>
        )}
      </div>}
    </section>

    {/* Competition Regions Section */}
    

    {/* News & Updates Section */}
    <section className="panel news-panel" id="news">
      <div className="panel-title">
        <div>
          <span className="auth-overline">{t.newsBadge}</span>
          <h2>{t.newsTitle}</h2>
        </div>
        <span>{t.newsLiveUpdates}</span>
      </div>
      <p className="section-subtext">
        {t.newsSub}
      </p>

      <div className="news-grid">
        {newsArticles.map((article) => (
          <article
            key={article.id}
            className="news-card"
            onClick={() => setSelectedNewsArticle(article)}
            role="button"
            tabIndex={0}
          >
            <div className="news-thumb-wrap">
              <img src={article.image} alt={article.title} className="news-thumb-img" />
              <span className={`news-category-badge tag-${article.categorySlug}`}>
                {article.category}
              </span>
              <span className="news-date-badge">{article.date}</span>
            </div>
            <div className="news-body">
              <h3 className="news-title">{article.title}</h3>
              <p className="news-summary">{article.summary}</p>
              <div className="news-footer">
                <span className="news-author">{t.newsBy} {article.author}</span>
                <span className="news-read-more">{t.newsReadMore}</span>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>

    {user && <section className="panel catalog-panel" id="catalog">
      <div className="panel-title"><h2>{t.catalogTitle}</h2></div>
      {globalCapabilityError && <div className="error-banner"><span>{globalCapabilityError}</span><button className="button secondary" onClick={() => void loadGlobalCapabilities()}>{t.retry}</button></div>}
      {!globalCapabilityError && !globalCapabilities?.can_manage_catalog && <p className="muted">Bạn chưa được cấp quyền quản lý publisher, game và khu vực.</p>}
      {globalCapabilities?.can_manage_catalog && <>
        <div className="catalog-forms">
          <form onSubmit={submitPublisher}>
            <h3>Publisher</h3>
            <label>Tên publisher<input name="name" minLength={2} maxLength={120} required /></label>
            <button className="button" disabled={catalogLoading}>{t.catalogAddPub}</button>
          </form>
          <form onSubmit={submitGame}>
            <h3>Game</h3>
            <label>Tên game<input name="name" maxLength={120} required /></label>
            <label>Slug<input name="slug" pattern="[a-z0-9]+(?:-[a-z0-9]+)*" maxLength={120} required /></label>
            <label>Publisher<select name="publisher_id" defaultValue="" required><option value="" disabled>Chọn publisher</option>{publishers.map((publisher) => <option key={publisher.publisher_id} value={publisher.publisher_id}>{publisher.name}</option>)}</select></label>
            <button className="button" disabled={catalogLoading}>{t.catalogAddGame}</button>
          </form>
          <form onSubmit={submitArea}>
            <h3>Khu vực</h3>
            <label>Tên khu vực<input name="name" minLength={2} maxLength={120} required /></label>
            <label>Mã<input name="code" minLength={2} pattern="[A-Z0-9]+(?:-[A-Z0-9]+)*" maxLength={30} required /></label>
            <label>Khu vực cha<select name="parent_id" defaultValue=""><option value="">Không có</option>{areas.map((area) => <option key={area.area_id} value={area.area_id}>{area.code} · {area.name}</option>)}</select></label>
            <button className="button" disabled={catalogLoading}>{t.catalogAddArea}</button>
          </form>
        </div>
        {catalogLoading && <p className="muted catalog-loading-text">{t.catalogLoadingText}</p>}
        {catalogReloadError && <div className="catalog-reload">
          <p>{t.catalogSubtext}</p>
          <button className="button secondary" onClick={retryCatalogLoad} disabled={catalogLoading}>{t.catalogReload}</button>
        </div>}
        <div className="catalog-lists">
          <div><h3>Publishers</h3>{publishers.map((publisher) => {
            const logo = getPublisherLogo(publisher.name);
            return (
              <p className="catalog-item" key={publisher.publisher_id}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
                  {logo && <img src={logo} alt={publisher.name} className="catalog-pub-logo" />}
                  {publisher.name}
                </span>
                <span><button className="link-button" onClick={() => editCatalogItem("publishers", publisher)}>{t.stageEditBtn}</button><button className="link-button danger-link" onClick={() => deleteCatalogItem("publishers", publisher.publisher_id, publisher.name)}>{t.stageDeleteBtn}</button></span>
              </p>
            );
          })}</div>
          <div><h3>Games</h3>{games.map((game) => {
            const gLogo = getGameLogo(game.slug || game.name);
            return (
              <p className="catalog-item" key={game.game_id}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  {gLogo && <img src={gLogo} alt="" className="catalog-game-logo" />}
                  {game.name} <small>({game.slug})</small>
                </span>
                <span><button className="link-button" onClick={() => editCatalogItem("games", game)}>{t.stageEditBtn}</button><button className="link-button danger-link" onClick={() => deleteCatalogItem("games", game.game_id, game.name)}>{t.stageDeleteBtn}</button></span>
              </p>
            );
          })}</div>
          <div><h3>Khu vực</h3>{areas.map((area) => <p className="catalog-item" key={area.area_id}><span>{area.name} <small>({area.code})</small></span><span><button className="link-button" onClick={() => editCatalogItem("areas", area)}>{t.stageEditBtn}</button><button className="link-button danger-link" onClick={() => deleteCatalogItem("areas", area.area_id, area.name)}>{t.stageDeleteBtn}</button></span></p>)}</div>
        </div>
      </>}
    </section>}
    <section className="panel teams-panel" id="teams">
      <div className="panel-title"><h2>{t.teamsTitle}</h2><span>{teams.length} {t.teamsCount}</span></div>
      {user ? <form className="team-form" onSubmit={createTeam}>
        <label>{t.teamNameLabel}<input name="name" placeholder="Phoenix Gaming" minLength={2} maxLength={100} required /></label>
        <label>{t.teamTagLabel}<input name="tag" placeholder="PHX" minLength={2} maxLength={10} pattern="[A-Za-z0-9]+" required /></label>
        <label>{t.teamGameLabel}<select name="game_id" defaultValue="" required><option value="" disabled>{t.teamGameSelectPlaceholder}</option>{games.filter((game) => game.game_id > 0).map((game) => <option key={game.game_id} value={game.game_id}>{getLocalizedGameName(game.name, lang)}</option>)}</select></label>
        <button className="button" disabled={loading}>{t.teamCreateBtn}</button>
      </form> : <p className="muted">{t.teamLoginRequired}</p>}
      {teams.length === 0 ? <p className="muted">{t.teamEmpty}</p> : <div className="team-list">{teams.map((team) => {
        const teamGame = games.find((game) => game.game_id === team.game_id);
        const teamGameLogo = getGameLogo(teamGame?.slug || teamGame?.name);
        const teamGameSlug = getGameCanonicalSlug(teamGame ?? null) || "default";
        return <article className={`team-card card-game-${teamGameSlug}`} data-team-id={team.team_id} key={team.team_id}>
          <div className="team-card-body">
            <div className="team-card-top">
              <span className="team-tag-pill">#{team.tag}</span>
              {teamGameLogo && <img src={teamGameLogo} alt="" className="team-card-logo" />}
            </div>
            <h3>{team.name}</h3>
            <p className="team-card-meta">#{team.tag} · {teamGame?.name ?? "Game"}</p>
          </div>
          <button className="link-button team-card-btn" onClick={() => viewTeam(team.team_id)}>{t.teamViewBtn}</button>
        </article>;
      })}</div>}
      {selectedTeam && <div className="team-detail">
      <div className="panel-title"><h3>{selectedTeam.name} <span>#{selectedTeam.tag}</span></h3><button className="link-button" onClick={() => { setSelectedTeam(null); setTeamCapabilities(null); setTeamCapabilityError(""); }}>{t.teamCloseBtn}</button></div>
        <p>{games.find((game) => game.game_id === selectedTeam.game_id)?.name ?? "Game"}</p>
        {teamCapabilityError && <div className="error-banner"><span>{teamCapabilityError}</span><button className="button secondary" onClick={() => void loadTeamCapabilities(selectedTeam.team_id)}>{t.retry}</button></div>}
        {canManageSelectedTeam && <form className="member-form" onSubmit={addMember}>
          <label>{t.authUsername}<input name="username" placeholder={t.teamUsernamePlaceholder} maxLength={50} required /></label>
          <label>{t.teamRoleLabel}<select name="role_in_team" defaultValue="PLAYER"><option value="MANAGER">MANAGER</option><option value="COACH">COACH</option><option value="PLAYER">PLAYER</option><option value="SUBSTITUTE">SUBSTITUTE</option></select></label>
          <button className="button" disabled={memberLoading}>{t.teamAddMemberBtn}</button>
        </form>}
        <h4>{t.teamMembersTitle} ({selectedTeam.members.length})</h4>
        {selectedTeam.members.length === 0 ? <p className="muted">{t.teamNoMembers}</p> : <div className="member-list">{selectedTeam.members.map((member) => <div className={`member-row ${member.status === "ENDED" ? "ended" : ""}`} key={member.membership_id}>
          <div>
            <strong>{member.username}</strong>
            <p>{member.role} · {member.status === "ACTIVE" ? t.teamActiveStatus : t.teamLeftStatus} · {t.teamJoinedPrefix} {member.joined_date}{member.left_date ? ` · Rời đội ${member.left_date}` : ""}</p>
          </div>
          {user && <div className="member-actions">
            {canManageSelectedTeam && member.status === "ACTIVE" && <select aria-label={`Vị trí của ${member.username}`} value={member.role} disabled={memberLoading} onChange={(event) => updateMemberRole(member.membership_id, event.target.value)}>
              <option value="MANAGER">MANAGER</option><option value="COACH">COACH</option><option value="PLAYER">PLAYER</option><option value="SUBSTITUTE">SUBSTITUTE</option>
            </select>}
            {member.status === "ACTIVE" && (canManageSelectedTeam || member.user_id === user.id) && <button className="link-button danger-link" disabled={memberLoading} onClick={() => endMembership(member)}>{member.user_id === user.id ? "Rời đội" : "Kết thúc"}</button>}
          </div>}
        </div>)}</div>}
      </div>}
    </section>
  </main>

  {/* Auth Modal (Sign In / Register Popup Dialog) */}
  {isAuthModalOpen && (
    <div
      className="auth-modal-overlay"
      onClick={() => setIsAuthModalOpen(false)}
    >
      <div
        className="auth-modal-card"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-modal-dialog-title"
      >
        <button
          type="button"
          className="auth-modal-close"
          onClick={() => setIsAuthModalOpen(false)}
          aria-label="Đóng"
        >
          ✕
        </button>
        <div className="auth-kicker">
          <span className="auth-status-dot" /> NEXUS IDENTITY <span>SECURE ACCESS</span>
        </div>
        <div className="panel-title" style={{ marginBottom: "16px" }}>
          <div>
            <span className="auth-overline">
              {authMode === "login" ? t.authWelcomeBack : t.authJoinArena}
            </span>
            <h2 id="auth-modal-dialog-title" style={{ margin: 0 }}>
              {authMode === "login" ? t.authLoginTitle : t.authRegisterTitle}
            </h2>
          </div>
          
        </div>

        {(error || notice) && (
          <div className={`message ${error ? "error" : "success"}`} style={{ marginBottom: "16px" }}>
            <p>{error || notice}</p>
          </div>
        )}

        <form onSubmit={submitAuth} className="auth-form" style={{ marginTop: 0 }}>
          {authMode === "register" && (
            <>
              <label>
                {t.authFullName}
                <input name="real_name" maxLength={100} placeholder={t.authFullNamePlaceholder} />
              </label>
              <label>
                {t.authEmail}
                <input name="email" type="email" required placeholder="you@arena.gg" />
              </label>
            </>
          )}
          <label>
            {t.authUsername}
            <input
              name="username"
              minLength={3}
              maxLength={50}
              required
              placeholder={t.authUsernamePlaceholder}
              autoComplete="username"
              autoFocus
            />
          </label>
          <label>
            {t.authPassword}
            <input
              name="password"
              type="password"
              minLength={8}
              maxLength={128}
              required
              placeholder={t.authPasswordHint}
              autoComplete={authMode === "login" ? "current-password" : "new-password"}
            />
          </label>
          <button className="button" disabled={loading} style={{ width: "100%", marginTop: "8px" }}>
            {loading ? t.authProcessing : authMode === "login" ? t.authBtnLogin : t.authBtnRegister}
          </button>
          <div style={{ textAlign: "center", marginTop: "12px" }}>
            <button
              type="button"
              className="link-button"
              onClick={() => {
                setError("");
                setNotice("");
                setAuthMode(authMode === "login" ? "register" : "login");
              }}
            >
              {authMode === "login" ? t.authSwitchToRegister : t.authSwitchToLogin}
            </button>
          </div>
        </form>
      </div>
    </div>
  )}

  {/* News Article Detail Modal */}
  {selectedNewsArticle && (
    <div
      className="auth-modal-overlay"
      onClick={() => setSelectedNewsArticle(null)}
    >
      <div
        className="auth-modal-card news-modal-card"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="news-modal-title"
      >
        <button
          type="button"
          className="auth-modal-close"
          onClick={() => setSelectedNewsArticle(null)}
          aria-label={t.newsClose || "Đóng"}
        >
          ✕
        </button>
        <div className="news-modal-header">
          <div className="news-modal-badges">
            <span className={`news-category-badge tag-${selectedNewsArticle.categorySlug}`}>
              {selectedNewsArticle.category}
            </span>
            <span className="news-modal-date">{selectedNewsArticle.date} · {selectedNewsArticle.author}</span>
          </div>
          <h2 id="news-modal-title" className="news-modal-title">
            {selectedNewsArticle.title}
          </h2>
        </div>
        <div className="news-modal-hero">
          <img
            src={selectedNewsArticle.image}
            alt={selectedNewsArticle.title}
            className="news-modal-img"
          />
        </div>
        <div className="news-modal-content">
          <p className="news-modal-lead">{selectedNewsArticle.summary}</p>
          <p className="news-modal-body">{selectedNewsArticle.content}</p>
        </div>
        <div className="news-modal-footer">
          <button
            type="button"
            className="button secondary"
            onClick={() => setSelectedNewsArticle(null)}
          >
            Đóng bài viết
          </button>
        </div>
      </div>
    </div>
  )}
  </>);
}
