import streamlit as st
import streamlit.components.v1 as components
from streamlit_image_coordinates import streamlit_image_coordinates
from PIL import Image, ImageDraw, ImageFont
import math, requests, os, json, datetime
from functools import lru_cache

_KST = datetime.timezone(datetime.timedelta(hours=9))
BUILD_TIME = datetime.datetime.fromtimestamp(os.path.getmtime(__file__), tz=_KST).strftime("%m/%d %H:%M")

_COUNTER_NS = "yardbus-rogermostwanted"

def _hit_counter(key: str) -> int:
    """counterapi.dev 히트 → 카운트 반환. 실패 시 -1."""
    try:
        r = requests.get(f"https://api.counterapi.dev/v1/{_COUNTER_NS}/{key}/up", timeout=3)
        return r.json().get("count", -1) if r.ok else -1
    except Exception:
        return -1

def fetch_visitor_counts() -> tuple[int, int]:
    """오늘(KST) + 총 방문자 카운트를 각 1씩 증가 후 반환."""
    today_key = "today-" + datetime.datetime.now(tz=_KST).strftime("%Y-%m-%d")
    today = _hit_counter(today_key)
    total = _hit_counter("total")
    return today, total

st.set_page_config(page_title="야드 버스 시간표", page_icon="🚌", layout="wide",
                   initial_sidebar_state="collapsed")

# ── 상수 ──────────────────────────────────────────────────────────────────────
BASE_URL = "https://hse.samsungshi.com/hs/HSMB/0001/"
API_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}
LINE_DISPLAY = {
    "A": "A 노선", "C": "C 노선", "J1": "J1 노선",
    "J2": "J2 노선", "K": "K 노선", "NH": "신한내 노선",
}
LINE_COLORS = {
    "A": "#e50012", "C": "#1d2087", "J1": "#fdef01",
    "J2": "#e75699", "K": "#009843", "NH": "#00AADD",  # NH: 하늘색
}
LINE_TEXT_COLOR = {
    "J1": "#222222",  # 노란 배경엔 검정 글씨
}

# ── 다국어 텍스트 ──────────────────────────────────────────────────────────────
TEXTS = {
    "ko": {
        "title": "야드 버스 시간표",
        "spinner_lines": "노선 조회 중...",
        "spinner_timetable": "시간표 불러오는 중...",
        "no_lines": "운행 노선 정보를 불러올 수 없습니다.",
        "select_station": "지도 또는 사이드바에서 정류장을 선택하세요.",
        "dir_select": "**방향 선택**",
        "next_bus": "🚌 다음 버스",
        "last_bus": "막차",
        "next2": "그 다음",
        "next3": "그 다다음",
        "no_service": "🚫 오늘 운행 종료",
        "no_timetable": "시간표 없음",
        "full_timetable": "📋 전체 시간표",
        "refresh": "🔄 새로고침",
        "sidebar_hint": "노선을 선택하면 정류장 목록이 표시됩니다.",
        "route_stops": "{r} 정류장",
        "remind_title": "도착 알림 설정",
        "remind_3": "3분 전",
        "remind_5": "5분 전",
        "remind_cancel": "취소",
    },
    "en": {
        "title": "Yard Bus Timetable",
        "spinner_lines": "Loading routes...",
        "spinner_timetable": "Loading timetable...",
        "no_lines": "Could not load route information.",
        "select_station": "Select a stop on the map or sidebar.",
        "dir_select": "**Select direction**",
        "next_bus": "🚌 Next Bus",
        "last_bus": "Last",
        "next2": "2nd bus",
        "next3": "3rd bus",
        "no_service": "🚫 No more service today",
        "no_timetable": "No timetable available",
        "full_timetable": "📋 Full timetable",
        "refresh": "🔄 Refresh",
        "sidebar_hint": "Select a route to see stops.",
        "route_stops": "{r} Stops",
        "remind_title": "Set arrival reminder",
        "remind_3": "3 min",
        "remind_5": "5 min",
        "remind_cancel": "Cancel",
    },
    "ja": {
        "title": "ヤードバス時刻表",
        "spinner_lines": "路線を読み込み中...",
        "spinner_timetable": "時刻表を読み込み中...",
        "no_lines": "路線情報を取得できません。",
        "select_station": "地図またはサイドバーで停留所を選択してください。",
        "dir_select": "**方向選択**",
        "next_bus": "🚌 次のバス",
        "last_bus": "最終",
        "next2": "その次",
        "next3": "さらにその次",
        "no_service": "🚫 本日の運行終了",
        "no_timetable": "時刻表なし",
        "full_timetable": "📋 全時刻表",
        "refresh": "🔄 更新",
        "sidebar_hint": "路線を選択すると停留所一覧が表示されます。",
        "route_stops": "{r} 停留所",
        "remind_title": "到着通知を設定",
        "remind_3": "3分前",
        "remind_5": "5分前",
        "remind_cancel": "キャンセル",
    },
}

LINE_DISPLAY_EN = {
    "A": "Route A", "C": "Route C", "J1": "Route J1",
    "J2": "Route J2", "K": "Route K", "NH": "Route NH",
}
LINE_DISPLAY_JA = {
    "A": "A ルート", "C": "C ルート", "J1": "J1 ルート",
    "J2": "J2 ルート", "K": "K ルート", "NH": "NH ルート",
}

# 지도 이미지에 표기된 영문 정류장 명칭
STATION_NAMES_EN = {
    "가로지식당": "GAROJI Cafeteria",
    "여객선공장": "Ferry Factory",
    "회사정문":   "Main Gate",
    "공장정문":   "Factory Gate",
    "설계1관":    "Design 1 Office",
    "한마음관":   "Business Support Ctr",
    "3도크헤드":  "3 Dock Head",
    "D식당":      "Dining Hall D",
    "피솔관":     "PISOL Office",
    "G3도크입구": "G3 Dock Gate",
    "사곡공장":   "SAGOK Factory",
    "의장관":     "Hull Outfitting Office",
    "B식당":      "Dining Hall B",
    "1도크헤드":  "1 Dock Head",
    "선각공장":   "Hull Shop",
    "A식당":      "Dining Hall A",
    "LNG관":      "LNG Office",
    "K안벽":      "K QUAY",
    "6안벽관":    "6 QUAY",
    "J안벽":      "J QUAY",
    "해양삼거리": "Offshore 3-Way",
    "C2식당":     "Dining Hall C2",
    "해양관":     "Offshore Office",
}
STATION_NAMES_JA = {
    "가로지식당": "カロジ食堂",
    "여객선공장": "フェリー工場",
    "회사정문":   "正門",
    "공장정문":   "工場正門",
    "설계1관":    "設計1館",
    "한마음관":   "ハンマウム館",
    "3도크헤드":  "3ドックヘッド",
    "D식당":      "D食堂",
    "피솔관":     "ピソル館",
    "G3도크입구": "G3ドック入口",
    "사곡공장":   "サゴク工場",
    "의장관":     "艤装館",
    "B식당":      "B食堂",
    "1도크헤드":  "1ドックヘッド",
    "선각공장":   "船殻工場",
    "A식당":      "A食堂",
    "LNG관":      "LNG館",
    "K안벽":      "K岸壁",
    "6안벽관":    "6岸壁館",
    "J안벽":      "J岸壁",
    "해양삼거리": "海洋三叉路",
    "C2식당":     "C2食堂",
    "해양관":     "海洋館",
}


def stn(name: str, lang: str) -> str:
    """Return station display name for the given language."""
    if lang == "en":
        return STATION_NAMES_EN.get(name, name)
    if lang == "ja":
        return STATION_NAMES_JA.get(name, name)
    return name

# 환승 가능 정류장 (태극 마커 — 여러 노선 교차)
TRANSFER_STATIONS = {"여객선공장", "회사정문", "설계1관", "LNG관", "6안벽관", "C2식당", "해양관"}


# ── 정류장 데이터 (pixel x, y 기준: 1280×720 이미지) ──────────────────────────
STATIONS = {
    "가로지식당": {"code": "A01", "x": 1109, "y": 394},
    "여객선공장": {"code": "A02", "x": 1061, "y": 512},  # 태극 마커
    "회사정문":   {"code": "A03", "x": 1013, "y": 665},  # 태극 마커
    "공장정문":   {"code": "A04", "x":  885, "y": 633},
    "설계1관":    {"code": "A05", "x":  752, "y": 542},  # 태극 마커
    "한마음관":   {"code": "A06", "x":  507, "y": 494},
    "3도크헤드":  {"code": "A07", "x":  338, "y": 510},
    "D식당":      {"code": "A08", "x":  322, "y": 233},
    "피솔관":     {"code": "A09", "x":  300, "y": 112},
    "G3도크입구": {"code": "A10", "x":  236, "y":  86},
    "사곡공장":   {"code": "A11", "x":   46, "y": 166},
    "의장관":     {"code": "A12", "x":  912, "y": 397},
    "B식당":      {"code": "A13", "x":  881, "y": 318},
    "1도크헤드":  {"code": "A14", "x":  904, "y": 446},
    "선각공장":   {"code": "A15", "x":  830, "y": 512},
    "A식당":      {"code": "A16", "x":  758, "y": 456},
    "LNG관":      {"code": "A17", "x":  697, "y": 360},  # 태극 마커
    "K안벽":      {"code": "A18", "x":  688, "y": 215},
    "6안벽관":    {"code": "A19", "x":  477, "y": 246},  # 태극 마커
    "J안벽":      {"code": "A20", "x":  552, "y": 166},
    "해양삼거리": {"code": "A21", "x":  613, "y": 475},
    "C2식당":     {"code": "A22", "x":  594, "y": 399},  # 태극 마커
    "해양관":     {"code": "A23", "x":  478, "y": 356},  # 태극 마커
}

# ── 노선 데이터 ────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def load_routes():
    with open("data/routes.json", "r", encoding="utf-8") as f:
        return json.load(f)

def get_terminal_direction(station_name: str, route_id: str):
    """시·종점이면 유일한 방향 문자열 반환, 아니면 None"""
    routes = load_routes()
    stations = routes["routes"].get(route_id, {}).get("stations", [])
    if not stations:
        return None
    if stations[0] == station_name:
        return "1"   # 시점 → 종점 방향만 존재
    if stations[-1] == station_name:
        return "2"   # 종점 → 시점 방향만 존재
    return None

def get_direction_parts(station_name: str, route_id: str, direction: str):
    """방향 카드용 (종점, 이전, 다음) 반환"""
    routes = load_routes()
    base = routes["routes"].get(route_id, {}).get("stations", [])
    if not base or station_name not in base:
        return f"방향{direction}", None, None
    ordered = base if direction == "1" else list(reversed(base))
    idx = ordered.index(station_name)
    n   = len(ordered)
    return ordered[-1], (ordered[idx-1] if idx > 0 else None), (ordered[idx+1] if idx < n-1 else None)

# ── CSS / JS 주입 ─────────────────────────────────────────────────────────────
def inject_all_css(line_display, close_sidebar=False, visitor_today=-1, visitor_total=-1):
    st.markdown("""
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-title" content="야드버스">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <link rel="manifest" href="/app/static/manifest.json">
    <style>
    .block-container { padding-top: 3.5rem !important; }
    /* 타이틀과 지도 사이 여백 최소화 */
    .block-container h2 { margin-top: 0 !important; margin-bottom: 2px !important; white-space: nowrap !important; overflow: hidden !important; }
    hr { margin: 6px 0 !important; }
    /* 사이드바 공통 */
    section[data-testid="stSidebar"] {
        z-index: 999 !important;
        height: 100dvh !important;
    }
    /* 사이드바 토글 버튼 — 화면 중앙 왼쪽, 눈에 띄게 */
    button[data-testid="collapsedControl"] {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        position: fixed !important;
        left: 0px !important;
        top: 50dvh !important;
        transform: translateY(-50%) !important;
        width: 28px !important;
        height: 56px !important;
        background: #2a5298 !important;
        border-radius: 0 8px 8px 0 !important;
        border: none !important;
        z-index: 1000 !important;
        opacity: 0.85 !important;
    }
    button[data-testid="collapsedControl"]:hover {
        opacity: 1 !important;
        width: 32px !important;
    }
    button[data-testid="collapsedControl"] svg {
        fill: white !important;
    }
    section[data-testid='stSidebar'] .stButton { margin-bottom: 2px !important; }
    /* 사이드바 노선 버튼 높이 통일 */
    section[data-testid='stSidebar'] .stButton button {
        height: 40px !important;
        min-height: 40px !important;
        font-size: 0.76em !important;
        padding: 0 4px !important;
        line-height: 1.2 !important;
        white-space: normal !important;
        word-break: keep-all !important;
    }
    /* 터치 반응성 — 300ms 딜레이 제거 */
    button { touch-action: manipulation !important; }
    /* 버튼 래퍼 배경 투명 — 다크모드 흰 꼭짓점 방지 */
    div[data-testid="stButton"] {
        background: transparent !important;
        background-color: transparent !important;
    }
    /* 노선 버튼: CSS grid 레이아웃 — 열 수는 Python이 결정, auto-fit으로 자동 적용 */
    [data-testid="stColumn"] [data-testid="stHorizontalBlock"] {
        display: grid !important;
        grid-template-columns: repeat(auto-fit, minmax(0, 1fr)) !important;
        gap: 4px !important;
    }
    [data-testid="stColumn"] [data-testid="stColumn"] {
        min-width: 0 !important;
        max-width: 100% !important;
        width: 100% !important;
        flex: unset !important;
    }
    /* JS injection 요소 높이 최소화 (height=0 iframe 래퍼) */
    [data-testid="stCustomComponentV1"] {
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }
    /* 야드 지도 확대/축소 래퍼 */
    .ypf-map-wrap {
        position: relative !important;
        overflow: hidden !important;
        border-radius: 6px;
    }
    .ypf-map-wrap [data-testid="stCustomComponentV1"] {
        touch-action: none !important;
        will-change: transform;
    }
    /* 지도 iframe 위를 덮는 투명 오버레이 — 핀치/드래그/휠 제스처를 여기서 가로챈다 */
    .ypf-map-touch {
        position: absolute;
        inset: 0;
        z-index: 10;
        background: transparent;
        touch-action: none;
        cursor: grab;
    }
    /* 종 알림 버튼 — 시간 표시 옆에 절대 위치로 붙여서 시간 자체의 가운데 정렬에 영향 없게 함 */
    .ypf-bell-anchor { position: relative; display: inline-block; }
    .ypf-bell-wrap {
        position: absolute; left: 100%; top: 50%; transform: translateY(-50%);
        margin-left: 8px; display: inline-block;
    }
    .ypf-bell-btn {
        border: none; background: transparent; cursor: pointer;
        display: inline-flex; align-items: center; justify-content: center;
        padding: 4px; border-radius: 50%;
        color: #9ca3af;
        transition: color 0.15s ease, background-color 0.15s ease;
    }
    .ypf-bell-btn:hover { background: rgba(148, 163, 184, 0.18); }
    .ypf-bell-btn svg { width: 17px; height: 17px; display: block; }
    .ypf-bell-btn.ypf-bell-active { color: #f59e0b; }
    .ypf-bell-menu {
        position: absolute; top: 130%; left: 50%; transform: translateX(-50%);
        background: #fff; border: 1px solid #d1d5db; border-radius: 8px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.18); padding: 6px; z-index: 50;
        display: none; white-space: nowrap;
    }
    .ypf-bell-menu.ypf-open { display: flex; gap: 4px; }
    .ypf-bell-menu button {
        border: 1px solid #d1d5db; background: #f3f4f6; color: #374151;
        border-radius: 6px; padding: 5px 9px; font-size: 0.78em;
        cursor: pointer; white-space: nowrap;
    }
    .ypf-bell-menu button.ypf-cancel { color: #b91c1c; border-color: #fca5a5; background: #fef2f2; }
    @media (prefers-color-scheme: dark) {
        .ypf-bell-menu { background: #1f2937; border-color: #374151; }
        .ypf-bell-menu button { background: #374151; color: #e5e7eb; border-color: #4b5563; }
        .ypf-bell-menu button.ypf-cancel { background: #4c1d1d; color: #fca5a5; border-color: #7f1d1d; }
    }
    /* 도착 알림 인앱 토스트 */
    .ypf-toast {
        position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%);
        background: #1f2937; color: #fff; padding: 12px 18px; border-radius: 10px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.35); z-index: 9999;
        font-size: 0.92em; text-align: center; max-width: 90vw;
        animation: ypf-toast-in 0.25s ease-out;
    }
    .ypf-toast.ypf-toast-out { opacity: 0; transform: translateX(-50%) translateY(8px); transition: all 0.4s ease; }
    @keyframes ypf-toast-in {
        from { opacity: 0; transform: translateX(-50%) translateY(8px); }
        to { opacity: 1; transform: translateX(-50%) translateY(0); }
    }
    /* ── 모바일 반응형 (768px 이하) ───────────────────────────────────────── */
    @media (max-width: 768px) {
        /* 모바일: 사이드바 오버레이 (position:fixed) + 메인 폭 유지 → sticky 지도 작동 */
        section[data-testid="stSidebar"] {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
        }
        [data-testid="stAppViewContainer"] > .main {
            margin-left: 0 !important;
        }
        .block-container {
            padding-top: calc(env(safe-area-inset-top, 0px) + 3.5rem) !important;
            padding-left: 8px !important;
            padding-right: 8px !important;
        }
        /* 바깥 컬럼(지도/정보패널) 세로 배치 */
        [data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
            align-items: stretch !important;
        }
        [data-testid="stColumn"] {
            flex: none !important;
            width: 100% !important;
            min-width: 100% !important;
        }
        /* 지도 컬럼: 스크롤해도 상단 고정 */
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {
            position: sticky !important;
            top: 3.5rem !important;
            z-index: 10 !important;
            background: var(--background-color) !important;
        }
        /* 정보 패널 컬럼: 지도 뒤로 */
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {
            position: relative !important;
            z-index: 1 !important;
        }
        /* 사이드바 토글 버튼 — 모바일에서 크고 탭하기 쉽게 */
        button[data-testid="collapsedControl"] {
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            width: 52px !important;
            height: 110px !important;
            top: 50dvh !important;
            transform: translateY(-50%) !important;
            border-radius: 0 16px 16px 0 !important;
            gap: 4px !important;
            font-size: 11px !important;
            opacity: 1 !important;
        }
        /* 사이드바 노선 버튼 — 모바일 터치 크기 */
        section[data-testid='stSidebar'] .stButton button {
            height: 48px !important;
            min-height: 48px !important;
            font-size: 0.9em !important;
            padding: 0 8px !important;
        }
        /* 정보패널 버튼 — 터치 타겟 확보 */
        [data-testid="stButton"] button {
            min-height: 48px !important;
        }
        /* 종 알림 버튼 — 모바일 터치 타겟 확보 */
        .ypf-bell-btn {
            min-width: 44px !important;
            min-height: 40px !important;
        }
        .ypf-bell-btn svg {
            width: 22px !important;
            height: 22px !important;
        }
        .ypf-bell-menu button {
            padding: 10px 14px !important;
            font-size: 0.9em !important;
        }
        /* 헤더 행 언어선택 컬럼: 타이틀보다 위에 표시 */
        .block-container > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"]:first-child > [data-testid="stColumn"]:last-child,
        .block-container > div > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"]:first-child > [data-testid="stColumn"]:last-child {
            order: -1 !important;
            flex: 0 0 auto !important;
            width: auto !important;
            min-width: 100px !important;
            max-width: 150px !important;
            align-self: flex-end !important;
        }
        /* 헤더 행과 지도 사이 여백 최소화 */
        .block-container > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"]:first-child,
        .block-container > div > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"]:first-child {
            margin-bottom: 4px !important;
            padding-bottom: 0 !important;
        }
    }
    .ypf-footer {
        position: fixed !important;
        bottom: 4px !important;
        left: 8px !important;
        font-size: 0.68em !important;
        color: rgba(150, 150, 150, 0.45) !important;
        pointer-events: none !important;
        z-index: 1 !important;
        user-select: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

    today_disp  = str(visitor_today)  if visitor_today  >= 0 else "--"
    total_disp  = str(visitor_total)  if visitor_total  >= 0 else "--"
    st.markdown(
        f'<div class="ypf-footer">📧 rogermostwanted@gmail.com &nbsp;|&nbsp; Today {today_disp} &nbsp;Total {total_disp}</div>',
        unsafe_allow_html=True,
    )

    color_map = {
        line_display[k]: {"bg": v, "text": LINE_TEXT_COLOR.get(k, "white")}
        for k, v in LINE_COLORS.items()
    }
    color_map_json = json.dumps(color_map, ensure_ascii=False)

    components.html(f"""
    <script>
    const colorMap = {color_map_json};
    const routeNames = new Set(Object.keys(colorMap));

    function getState(id) {{
        const el = window.parent.document.getElementById(id);
        return el ? (el.dataset.val || '') : '';
    }}

    function applyStyles() {{
        const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
        // 파이썬이 주입한 hidden div에서 선택 상태 읽기
        const sbActive   = getState('ypf-sb');    // 사이드바 열린 노선
        const mainActive = getState('ypf-main');  // 메인패널 선택 노선

        const allBtns  = [...window.parent.document.querySelectorAll('[data-testid="stButton"] button')];
        const routeBtns = allBtns.filter(btn => colorMap[btn.innerText.trim()]);

        routeBtns.forEach(btn => {{
            const text       = btn.innerText.trim();
            const c          = colorMap[text];
            const isSbBtn    = sidebar && sidebar.contains(btn);
            const isSelected = isSbBtn ? (text === sbActive) : (text === mainActive);

            btn.style.setProperty('background-color', c.bg, 'important');
            btn.style.setProperty('color', c.text, 'important');
            btn.style.fontWeight = '700';

            // stButton·stColumn 래퍼 투명화 (다크모드 흰 꼭짓점 방지)
            const stBtn = btn.closest('[data-testid="stButton"]');
            if (stBtn) stBtn.style.setProperty('background', 'transparent', 'important');
            const stCol = btn.closest('[data-testid="stColumn"]');
            if (stCol) stCol.style.setProperty('background', 'transparent', 'important');

            // 메인패널: 선택이 있으면 나머지 흐리게
            if (!isSbBtn) {{
                btn.style.opacity = (!mainActive || isSelected) ? '1' : '0.35';
            }} else {{
                btn.style.opacity = '1';
            }}

            if (isSelected) {{
                // 선택됨: 흰색 굵은 테두리 + 그림자
                btn.style.setProperty('border', '3px solid rgba(255,255,255,0.92)', 'important');
                btn.style.setProperty('box-shadow', '0 0 0 2px rgba(0,0,0,0.25), 0 4px 14px rgba(0,0,0,0.35)', 'important');
                btn.style.filter = 'brightness(1.1)';
            }} else {{
                btn.style.setProperty('border', '1px solid transparent', 'important');
                btn.style.setProperty('box-shadow', 'none', 'important');
                btn.style.filter = '';
            }}
        }});

        // 방향 버튼: ypf-dir에 저장된 종점 이름으로 활성 감지
        const activeDirEnd = getState('ypf-dir');
        allBtns.forEach(btn => {{
            const text = btn.innerText.trim();
            if (routeNames.has(text)) return;
            if (!text.includes('→')) return;   // 방향 버튼은 → 포함
            if (sidebar && sidebar.contains(btn)) return;

            // 모바일(768px 이하)에서는 줄바꿈 허용
            const isMobile = window.parent.innerWidth <= 768;
            const ws = isMobile ? 'normal' : 'nowrap';

            // 레이아웃 스타일
            btn.style.setProperty('white-space', ws, 'important');
            btn.style.setProperty('text-align', 'center', 'important');
            btn.style.setProperty('min-height', isMobile ? '56px' : '0', 'important');
            btn.style.setProperty('padding', isMobile ? '10px 14px' : '6px 14px', 'important');
            btn.style.setProperty('line-height', '1.2', 'important');

            // p 태그 줄간격 및 마진 제거
            btn.querySelectorAll('p').forEach(p => {{
                p.style.setProperty('margin', '0', 'important');
                p.style.setProperty('padding', '0', 'important');
                p.style.setProperty('line-height', '1.2', 'important');
                p.style.setProperty('text-align', 'center', 'important');
                p.style.setProperty('white-space', ws, 'important');
            }});

            // strong 태그 스타일: 1번째=종점방면(2em), 2번째 이후=이전/다음 정류장(자동 크기)
            const strongs = btn.querySelectorAll('p strong, strong');
            if (strongs.length > 0) {{
                strongs[0].style.setProperty('font-size', '2em', 'important');
                strongs[0].style.setProperty('display', 'block', 'important');
                strongs[0].style.setProperty('margin', '0 0 2px 0', 'important');
                strongs[0].style.setProperty('line-height', '1', 'important');
            }}
            // 이전/다음 줄: 마지막 p태그를 한 줄 고정, 넘치면 폰트 자동 축소
            const dirStrongs = Array.from(strongs).slice(1);
            if (dirStrongs.length > 0) {{
                const pTags = btn.querySelectorAll('p');
                // p태그 3개 = 비한/영 언어: 중간 p(한국어 힌트) 소형화
                if (pTags.length >= 3) {{
                    const hintP = pTags[1];
                    hintP.style.setProperty('font-size', '0.7em', 'important');
                    hintP.style.setProperty('color', '#999', 'important');
                    hintP.style.setProperty('line-height', '1', 'important');
                }}
                const p2 = pTags.length >= 2 ? pTags[pTags.length - 1] : null;
                if (p2) p2.style.setProperty('white-space', 'nowrap', 'important');
                let fs = 1.4;
                dirStrongs.forEach(s => {{
                    s.style.setProperty('font-size', fs + 'em', 'important');
                    s.style.setProperty('line-height', '1', 'important');
                }});
                if (p2) {{
                    while (p2.scrollWidth > p2.offsetWidth + 1 && fs > 0.85) {{
                        fs = Math.round((fs - 0.05) * 100) / 100;
                        dirStrongs.forEach(s => s.style.setProperty('font-size', fs + 'em', 'important'));
                    }}
                }}
            }}

            // 버튼 간격 축소: stButton 래퍼 margin 줄이기
            const wrapper = btn.closest('[data-testid="stButton"]');
            if (wrapper) wrapper.style.setProperty('margin-bottom', '-8px', 'important');

            // 활성 감지: 첫 번째 p태그에 종점 이름 포함 여부 (한국어/영어 공통)
            const firstP = btn.querySelector('p');
            const isActive = activeDirEnd !== '' && firstP && firstP.innerText.trim().includes('[' + activeDirEnd + ']');
            if (isActive) {{
                btn.style.setProperty('background', '#dbeafe', 'important');
                btn.style.setProperty('background-color', '#dbeafe', 'important');
                btn.style.setProperty('border', '2px solid #3b82f6', 'important');
                btn.style.setProperty('color', '#1d4ed8', 'important');
                btn.style.setProperty('box-shadow', '0 0 0 2px #93c5fd', 'important');
                btn.style.fontWeight = '700';
            }} else {{
                btn.style.setProperty('background', '#f3f4f6', 'important');
                btn.style.setProperty('background-color', '#f3f4f6', 'important');
                btn.style.setProperty('border', '1px solid #d1d5db', 'important');
                btn.style.setProperty('color', '#374151', 'important');
                btn.style.setProperty('box-shadow', 'none', 'important');
                btn.style.fontWeight = '';
            }}
            btn.style.opacity = '1';
            btn.style.filter = '';
        }});

        // 헤더 행 컬럼 배경 강제 투명화 + 모바일 언어선택 컬럼 순서 조정
        // 사이드바 제외 후 첫 번째 stHorizontalBlock = 헤더 행
        const allHBlocksMain = [...window.parent.document.querySelectorAll('[data-testid="stHorizontalBlock"]')]
            .filter(el => !el.closest('[data-testid="stSidebar"]'));
        const hdrRow = allHBlocksMain.length > 0 ? allHBlocksMain[0] : null;
        if (hdrRow) {{
            const hdrCols = hdrRow.querySelectorAll(':scope > [data-testid="stColumn"]');
            hdrCols.forEach(col => {{
                col.style.setProperty('background', 'transparent', 'important');
                col.style.setProperty('background-color', 'transparent', 'important');
                col.style.setProperty('position', 'static', 'important');
                col.style.setProperty('top', 'auto', 'important');
            }});
            // 모바일: 언어선택(last) 컬럼을 타이틀 위로 이동 (CSS order 보완)
            const isMobile = window.parent.innerWidth <= 768;
            if (isMobile && hdrCols.length >= 2) {{
                hdrCols[hdrCols.length - 1].style.setProperty('order', '-1', 'important');
                hdrCols[0].style.setProperty('order', '0', 'important');
            }}
        }}

        // 사이드바 정류장 버튼
        if (!sidebar) return;
        sidebar.querySelectorAll('[data-testid="stButton"] button').forEach(btn => {{
            const text = btn.innerText.trim();
            if (routeNames.has(text)) return;
            const isSel = text.startsWith('◀');
            btn.style.setProperty('font-size', '0.82em', 'important');
            btn.style.setProperty('padding', '3px 10px', 'important');
            btn.style.setProperty('height', 'auto', 'important');
            btn.style.setProperty('min-height', 'unset', 'important');
            btn.style.setProperty('background', isSel ? '#dbeafe' : '#f3f4f6', 'important');
            btn.style.setProperty('border', isSel ? '1.5px solid #3b82f6' : '1px solid #d1d5db', 'important');
            btn.style.setProperty('box-shadow', isSel ? '0 0 0 2px #93c5fd' : 'none', 'important');
            btn.style.setProperty('color', isSel ? '#1d4ed8' : '#374151', 'important');
            btn.style.fontWeight = isSel ? '700' : 'normal';
            btn.style.opacity = '1';
            btn.style.filter = '';
        }});
    }}

    // ── 야드 지도 확대/축소 ──────────────────────────────────────────────────
    function getMapBlock() {{
        const marker = window.parent.document.getElementById('ypf-map-marker');
        return marker ? marker.closest('[data-testid="stVerticalBlock"]') : null;
    }}
    function getMapComp() {{
        const block = getMapBlock();
        return block ? block.querySelector('[data-testid="stCustomComponentV1"]') : null;
    }}

    function setupMapZoom() {{
        const block = getMapBlock();
        if (!block) return;
        let overlay = block.querySelector('.ypf-map-touch');
        if (!block.dataset.ypfZoomSetup) {{
            block.dataset.ypfZoomSetup = '1';
            block.classList.add('ypf-map-wrap');

            // 지도(iframe) 위를 덮는 투명 오버레이 — 터치/휠 제스처는 iframe 내부 문서로
            // 들어가버려 부모 document 리스너로는 잡히지 않으므로, 오버레이가 먼저 가로챈다.
            overlay = window.parent.document.createElement('div');
            overlay.className = 'ypf-map-touch';
            block.appendChild(overlay);
        }}
        if (overlay && window.parent.__ypfBindMapOverlay) window.parent.__ypfBindMapOverlay(overlay);
    }}

    // 참고: 이 <script>는 Streamlit이 rerun될 때마다 새 iframe에서 통째로 다시 실행된다.
    // 상태(state)는 window.parent에 영속시키되, addEventListener 리스너는 매번 새로
    // (현재 살아있는 realm으로) 다시 등록해야 한다 — 이전 iframe이 destroy되면 그 realm에서
    // 등록한 리스너는 document에는 남아있지만 더 이상 호출되지 않는 현상이 있었음.
    {{
        window.parent.__ypfZoomState = window.parent.__ypfZoomState || {{ scale: 1, tx: 0, ty: 0 }};
        const state = window.parent.__ypfZoomState;

        function clamp(v, lo, hi) {{ return Math.max(lo, Math.min(hi, v)); }}

        function applyTransform() {{
            const comp = getMapComp();
            if (!comp) return;
            const next = `translate(${{state.tx}}px, ${{state.ty}}px) scale(${{state.scale}})`;
            // 동일 값이면 스타일을 다시 쓰지 않음 — MutationObserver 재귀 트리거 방지
            if (comp.dataset.ypfTransform === next) return;
            comp.dataset.ypfTransform = next;
            comp.style.transformOrigin = '0 0';
            comp.style.transform = next;
        }}

        // 지도 iframe의 "변형되지 않은(static)" 기준 좌표계.
        // comp.getBoundingClientRect()는 현재 적용된 transform(translate+scale) 반영값이므로
        // 우리가 직접 걸어둔 state.tx/ty/scale로 역산하면 스크롤/레이아웃과 무관하게 항상
        // 정확한 정적 기준점을 구할 수 있다 (offsetLeft/Top은 컨테이너 구조에 따라 신뢰할 수 없었음).
        function getStaticFrame() {{
            const comp = getMapComp();
            if (!comp) return null;
            const cur = comp.getBoundingClientRect();
            if (cur.width === 0 || cur.height === 0) return null;
            return {{
                left: cur.left - state.tx,
                top: cur.top - state.ty,
                width: cur.width / state.scale,
                height: cur.height / state.scale,
            }};
        }}

        function clampPan(frame) {{
            const minX = -(frame.width  * (state.scale - 1));
            const minY = -(frame.height * (state.scale - 1));
            state.tx = clamp(state.tx, minX, 0);
            state.ty = clamp(state.ty, minY, 0);
        }}

        // cx, cy: getStaticFrame() 기준 상대 좌표(비확대 상태 기준)
        function setScale(newScale, cx, cy, frame) {{
            const old = state.scale;
            newScale = clamp(newScale, 1, 3.5);
            if (Math.abs(newScale - old) < 0.001) return;
            const ratio = newScale / old;
            state.tx = cx - (cx - state.tx) * ratio;
            state.ty = cy - (cy - state.ty) * ratio;
            state.scale = newScale;
            clampPan(frame);
            applyTransform();
        }}

        window.parent.__ypfReapplyZoom = applyTransform;

        // 정류장 탭(클릭) 전달: 오버레이가 제스처를 가로채면 iframe 내부의
        // streamlit_image_coordinates는 클릭을 못 받으므로, 단순 탭으로 판정되면
        // 현재 확대/이동 상태 역산으로 iframe 내부 이미지 좌표를 계산해 클릭을 대신 쏴준다.
        function forwardTap(clientX, clientY) {{
            const comp = getMapComp();
            const frame = getStaticFrame();
            if (!comp || !frame) return;
            let doc;
            try {{ doc = comp.contentDocument; }} catch (err) {{ return; }}
            if (!doc) return;
            const img = doc.querySelector('img');
            if (!img) return;
            const localX = (clientX - frame.left - state.tx) / state.scale;
            const localY = (clientY - frame.top - state.ty) / state.scale;
            const r = img.getBoundingClientRect();
            const cx = r.left + localX, cy = r.top + localY;
            const ev = new MouseEvent('click', {{
                bubbles: true, cancelable: true, clientX: cx, clientY: cy, view: doc.defaultView,
            }});
            img.dispatchEvent(ev);
        }}

        const pointers = new Map();
        let lastDist = null, dragStart = null, downPos = null, moved = false;

        function onWheel(e) {{
            e.preventDefault();
            const frame = getStaticFrame();
            if (!frame) return;
            const cx = e.clientX - frame.left, cy = e.clientY - frame.top;
            const factor = e.deltaY < 0 ? 1.15 : (1 / 1.15);
            setScale(state.scale * factor, cx, cy, frame);
        }}
        function onPointerDown(e) {{
            pointers.set(e.pointerId, {{x: e.clientX, y: e.clientY}});
            if (pointers.size === 1) {{
                downPos = {{x: e.clientX, y: e.clientY}};
                moved = false;
                dragStart = {{x: e.clientX, y: e.clientY, tx: state.tx, ty: state.ty}};
            }} else {{
                moved = true;  // 두 번째 손가락이 닿으면 핀치 — 탭 아님
            }}
        }}
        function onPointerMove(e) {{
            if (!pointers.has(e.pointerId)) return;
            pointers.set(e.pointerId, {{x: e.clientX, y: e.clientY}});
            const frame = getStaticFrame();
            if (!frame) return;
            if (pointers.size === 2) {{
                const pts = [...pointers.values()];
                const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
                if (lastDist != null) {{
                    const cx = (pts[0].x + pts[1].x) / 2 - frame.left;
                    const cy = (pts[0].y + pts[1].y) / 2 - frame.top;
                    setScale(state.scale * (dist / lastDist), cx, cy, frame);
                }}
                lastDist = dist;
            }} else if (pointers.size === 1 && dragStart) {{
                const p = [...pointers.values()][0];
                if (!moved && Math.hypot(p.x - downPos.x, p.y - downPos.y) > 8) moved = true;
                if (moved && state.scale > 1.02) {{
                    state.tx = dragStart.tx + (p.x - dragStart.x);
                    state.ty = dragStart.ty + (p.y - dragStart.y);
                    clampPan(frame);
                    applyTransform();
                }}
            }}
        }}
        function endPointer(e) {{
            pointers.delete(e.pointerId);
            if (pointers.size < 2) lastDist = null;
            if (pointers.size === 0) dragStart = null;
        }}
        function onPointerUp(e) {{
            const wasSingleTap = pointers.size <= 1 && !moved;
            if (wasSingleTap) forwardTap(e.clientX, e.clientY);
            endPointer(e);
            if (pointers.size === 0) {{ downPos = null; moved = false; }}
        }}

        // 오버레이 엘리먼트는 그대로 두되, 리스너는 이 스크립트 실행(=매 rerun)마다
        // 한 번만 재등록한다 — 이전 rerun의 iframe realm에서 등록된 리스너는 그 iframe이
        // destroy되면 더 이상 호출되지 않는 현상이 있었기 때문.
        let overlayBoundThisRun = false;
        window.parent.__ypfBindMapOverlay = function(overlay) {{
            if (overlayBoundThisRun) return;
            overlayBoundThisRun = true;
            const old = window.parent.__ypfZoomListeners;
            if (old && old.el) {{
                old.el.removeEventListener('wheel', old.wheel);
                old.el.removeEventListener('pointerdown', old.pointerdown);
                old.el.removeEventListener('pointermove', old.pointermove);
                old.el.removeEventListener('pointerup', old.pointerup);
                old.el.removeEventListener('pointercancel', old.pointercancel);
            }}
            overlay.addEventListener('wheel', onWheel, {{ passive: false }});
            overlay.addEventListener('pointerdown', onPointerDown);
            overlay.addEventListener('pointermove', onPointerMove);
            overlay.addEventListener('pointerup', onPointerUp);
            overlay.addEventListener('pointercancel', endPointer);
            window.parent.__ypfZoomListeners = {{
                el: overlay, wheel: onWheel, pointerdown: onPointerDown,
                pointermove: onPointerMove, pointerup: onPointerUp, pointercancel: endPointer,
            }};
        }};
    }}

    // ── 종 알림 버튼 ─────────────────────────────────────────────────────────
    {{
        function closeAllMenus(except) {{
            window.parent.document.querySelectorAll('.ypf-bell-menu').forEach(m => {{
                if (m !== except) m.classList.remove('ypf-open');
            }});
        }}

        window.parent.__ypfBellToggle = function(btn) {{
            const menu = btn.nextElementSibling;
            if (!menu) return;
            const willOpen = !menu.classList.contains('ypf-open');
            closeAllMenus(willOpen ? menu : null);
            menu.classList.toggle('ypf-open', willOpen);
        }};

        // 알림음 — AudioContext는 사용자 제스처 없이 나중에(setTimeout 콜백에서) 재생을
        // 시도하면 브라우저 자동재생 정책에 막힐 수 있으므로, 종 메뉴에서 3분전/5분전을
        // "누르는 그 순간"(진짜 사용자 제스처) 미리 만들어 두고 이후에는 재사용한다.
        function ensureAudioCtx() {{
            if (!window.parent.__ypfAudioCtx) {{
                const AC = window.parent.AudioContext || window.parent.webkitAudioContext;
                if (AC) {{
                    try {{ window.parent.__ypfAudioCtx = new AC(); }} catch (e) {{}}
                }}
            }}
            const ctx = window.parent.__ypfAudioCtx;
            if (ctx && ctx.state === 'suspended') {{
                ctx.resume().catch(function() {{}});
            }}
            return ctx;
        }}

        function playBeep() {{
            const ctx = ensureAudioCtx();
            if (!ctx) return;
            try {{
                const now = ctx.currentTime;
                for (let i = 0; i < 3; i++) {{
                    const t0 = now + i * 0.35;
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'sine';
                    osc.frequency.value = 880;
                    gain.gain.setValueAtTime(0.0001, t0);
                    gain.gain.exponentialRampToValueAtTime(0.5, t0 + 0.02);
                    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.28);
                    osc.connect(gain).connect(ctx.destination);
                    osc.start(t0);
                    osc.stop(t0 + 0.3);
                }}
            }} catch (e) {{}}
        }}

        // 인앱 토스트 — 시스템 알림 권한/지원 여부와 무관하게 항상 화면에 표시되는 대비책
        // (iOS Safari 등 일부 브라우저는 일반 웹사이트에서 Notification API 자체를 지원하지 않음)
        function showToast(title, body) {{
            const doc = window.parent.document;
            const toast = doc.createElement('div');
            toast.className = 'ypf-toast';
            toast.innerHTML = '<strong>' + title + '</strong><br>' + body;
            doc.body.appendChild(toast);
            playBeep();
            if (window.parent.navigator && window.parent.navigator.vibrate) {{
                try {{ window.parent.navigator.vibrate([120, 60, 120]); }} catch (e) {{}}
            }}
            window.parent.setTimeout(function() {{
                toast.classList.add('ypf-toast-out');
                window.parent.setTimeout(function() {{ toast.remove(); }}, 400);
            }}, 8000);
        }}

        window.parent.__ypfBellSet = function(btn, hhmm, minutes, label) {{
            const wrap = btn.closest('.ypf-bell-wrap');
            const bellBtn = wrap ? wrap.querySelector('.ypf-bell-btn') : null;
            const menu = wrap ? wrap.querySelector('.ypf-bell-menu') : null;
            const hasNotif = typeof window.parent.Notification !== 'undefined';
            ensureAudioCtx();  // 지금 이 클릭(진짜 사용자 제스처) 안에서 미리 열어둬야 나중에 재생 가능

            function schedule() {{
                const now = new Date();
                // KST(UTC+9) 벽시계 시각을 로컬 getHours()/getMinutes()로 읽기 위한 변환.
                // 기기가 이미 KST면 오프셋이 서로 상쇄돼 now와 같아야 하는데,
                // 부호가 반대로 되어 있어 KST 기기에서 약 18시간이 밀리던 버그가 있었음.
                const kstNow = new Date(now.getTime() + 9 * 3600000 + now.getTimezoneOffset() * 60000);
                const h = parseInt(hhmm.slice(0, 2), 10), m = parseInt(hhmm.slice(2, 4), 10);
                const target = new Date(kstNow);
                // setHours(h, m, ...)는 m이 60 이상이어도(드물게 API가 그런 값을 줌) 다음 시로
                // 자동 올림 처리해준다 — 화면 표시도 원본 hhmm을 그대로 자르지 않고 이 정규화된
                // target에서 다시 읽어야 '18:88' 같은 값이 안 나온다.
                target.setHours(h, m, 0, 0);
                const dispHH = String(target.getHours()).padStart(2, '0');
                const dispMM = String(target.getMinutes()).padStart(2, '0');
                const fireAt = new Date(target.getTime() - minutes * 60000);
                const delay = fireAt.getTime() - kstNow.getTime();
                if (delay <= 0) {{
                    window.parent.alert('이미 ' + minutes + '분 전이 지났어요. 다음 버스로 다시 설정해주세요.');
                    return;
                }}
                if (window.parent.__ypfReminderTimer) {{
                    window.parent.clearTimeout(window.parent.__ypfReminderTimer);
                }}
                window.parent.__ypfReminderInfo = {{ hhmm, minutes, label }};
                window.parent.__ypfReminderTimer = window.parent.setTimeout(function() {{
                    const title = '🚌 버스 도착 ' + minutes + '분 전';
                    const body = label + ' · ' + dispHH + ':' + dispMM + ' 도착 예정';
                    if (hasNotif && window.parent.Notification.permission === 'granted') {{
                        try {{ new window.parent.Notification(title, {{ body: body }}); }} catch (err) {{}}
                    }}
                    // 시스템 알림 성공 여부와 무관하게 탭이 열려있는 한 항상 화면에도 표시
                    showToast(title, body);
                    window.parent.__ypfReminderInfo = null;
                    window.parent.__ypfReminderTimer = null;
                    window.parent.document.querySelectorAll('.ypf-bell-btn').forEach(b => {{
                        b.classList.remove('ypf-bell-active');
                    }});
                }}, delay);
                if (bellBtn) bellBtn.classList.add('ypf-bell-active');
                if (menu) menu.classList.remove('ypf-open');
            }}

            if (!hasNotif) {{
                // 시스템 알림 미지원 브라우저 — 화면 켜둔 상태에서 인앱 토스트로만 알림
                schedule();
                return;
            }}
            if (window.parent.Notification.permission === 'granted') {{
                schedule();
            }} else if (window.parent.Notification.permission !== 'denied') {{
                window.parent.Notification.requestPermission().then(function(perm) {{
                    schedule();  // 거부돼도 인앱 토스트는 동작하므로 예약은 그대로 진행
                }}).catch(function() {{ schedule(); }});
            }} else {{
                schedule();  // 알림 차단 상태 — 인앱 토스트로 대체
            }}
        }};

        window.parent.__ypfBellCancel = function(btn) {{
            const wrap = btn.closest('.ypf-bell-wrap');
            const bellBtn = wrap ? wrap.querySelector('.ypf-bell-btn') : null;
            const menu = wrap ? wrap.querySelector('.ypf-bell-menu') : null;
            if (window.parent.__ypfReminderTimer) {{
                window.parent.clearTimeout(window.parent.__ypfReminderTimer);
            }}
            window.parent.__ypfReminderTimer = null;
            window.parent.__ypfReminderInfo = null;
            if (bellBtn) bellBtn.classList.remove('ypf-bell-active');
            if (menu) menu.classList.remove('ypf-open');
        }};

        // st.markdown 콘텐츠는 onclick 속성이 제거되므로 이벤트 위임으로 처리.
        // 이 리스너도 rerun마다 살아있는 realm 기준으로 재등록해야 한다 (지도 확대 리스너와 동일 사유).
        function onDocClick(e) {{
            const bellBtn = e.target.closest('.ypf-bell-btn');
            if (bellBtn) {{
                e.stopPropagation();
                window.parent.__ypfBellToggle(bellBtn);
                return;
            }}
            const setBtn = e.target.closest('.ypf-bell-menu button[data-remind-minutes]');
            if (setBtn) {{
                e.stopPropagation();
                window.parent.__ypfBellSet(
                    setBtn, setBtn.dataset.hhmm,
                    parseInt(setBtn.dataset.remindMinutes, 10),
                    setBtn.dataset.label || ''
                );
                return;
            }}
            const cancelBtn = e.target.closest('.ypf-bell-menu button[data-remind-cancel]');
            if (cancelBtn) {{
                e.stopPropagation();
                window.parent.__ypfBellCancel(cancelBtn);
                return;
            }}
            if (e.target.closest('.ypf-bell-wrap')) return;
            closeAllMenus(null);
        }}
        if (window.parent.__ypfBellClickHandler) {{
            window.parent.document.removeEventListener('click', window.parent.__ypfBellClickHandler);
        }}
        window.parent.document.addEventListener('click', onDocClick);
        window.parent.__ypfBellClickHandler = onDocClick;
    }}

    function syncBellState() {{
        const active = !!window.parent.__ypfReminderInfo;
        window.parent.document.querySelectorAll('.ypf-bell-btn').forEach(btn => {{
            btn.classList.toggle('ypf-bell-active', active);
        }});
    }}

    // viewport-fit=cover: safe area inset 사용 가능하게
    (function() {{
        const m = window.parent.document.querySelector('meta[name="viewport"]');
        if (m && !m.content.includes('viewport-fit')) {{
            m.content += ', viewport-fit=cover';
        }}
    }})();

    // 첫 진입·새로고침 시에만 사이드바 닫기
    // position:fixed이면 rect 검출 불가 → localStorage로 "expanded" 여부 판단
    (function() {{
        const shouldClose = {'true' if close_sidebar else 'false'};
        if (!shouldClose) return;
        function isExpandedInStorage() {{
            try {{
                for (const k of Object.keys(window.parent.localStorage)) {{
                    if (!/sidebar/i.test(k)) continue;
                    const v = window.parent.localStorage.getItem(k) || '';
                    if (/expand|open/i.test(v) || v === 'true' || v === '"true"') return true;
                }}
            }} catch(e) {{}}
            return false;
        }}
        let done = false;
        function tryClose() {{
            if (done) return;
            if (!isExpandedInStorage()) return;
            const btn = window.parent.document.querySelector('[data-testid="collapsedControl"]');
            if (!btn) return;
            done = true;
            btn.click();
        }}
        setTimeout(tryClose, 300);
        setTimeout(tryClose, 1000);
    }})();

    // 모바일에서 사이드바 토글 버튼에 "정류장" 라벨 추가
    (function() {{
        const isMobile = window.parent.innerWidth <= 900 || window.parent.innerHeight > window.parent.innerWidth;
        if (!isMobile) return;
        const btn = window.parent.document.querySelector('button[data-testid="collapsedControl"]');
        if (!btn || btn.querySelector('.ypf-lbl')) return;
        const lbl = window.parent.document.createElement('span');
        lbl.className = 'ypf-lbl';
        lbl.textContent = '정류장';
        Object.assign(lbl.style, {{
            display:'block', fontSize:'10px', color:'white',
            fontWeight:'700', lineHeight:'1', marginTop:'2px',
            pointerEvents:'none',
        }});
        btn.appendChild(lbl);
    }})();

    function tick() {{
        applyStyles();
        setupMapZoom();
        if (window.parent.__ypfReapplyZoom) window.parent.__ypfReapplyZoom();
        syncBellState();
    }}
    tick();
    new MutationObserver(() => {{ tick(); }})
        .observe(window.parent.document.body, {{childList: true, subtree: true}});
    </script>
    """, height=0)

# ── API 호출 ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _fetch_lines_raw(station_code: str, direction: str) -> list:
    try:
        r = requests.post(BASE_URL + "getAllLineOfStation.webx",
                          data={"station": station_code, "direction": direction},
                          headers=API_HEADERS, timeout=5)
        d = r.json()
        if d.get("errCd") == "0":
            return d["dataSet"]
    except Exception:
        pass
    return []

@st.cache_data(ttl=300, show_spinner=False)
def fetch_all_lines(station_code: str) -> dict:
    result = {}
    for d in ["1", "2"]:
        for l in _fetch_lines_raw(station_code, d):
            lid = l["LINE"]
            if lid not in result:
                result[lid] = {
                    "color": LINE_COLORS.get(lid, l["LINE_COLOR"]),
                    "directions": []
                }
            if d not in result[lid]["directions"]:
                result[lid]["directions"].append(d)
    return result

@st.cache_data(ttl=60, show_spinner=False)
def fetch_timetable(station_code: str, direction: str, line: str) -> list:
    try:
        r = requests.post(BASE_URL + "getTimeTable.webx",
                          data={"station": station_code, "direction": direction, "line": line},
                          headers=API_HEADERS, timeout=5)
        d = r.json()
        if d.get("errCd") == "0":
            return d["dataSet"]
    except Exception:
        pass
    return []

# ── 시간 포맷 ──────────────────────────────────────────────────────────────────
def fmt_time(raw: str) -> str:
    """API가 주는 HHMM 문자열을 HH:MM으로 변환.
    드물게 분(MM)이 60 이상인 비정상 값(예: '1888' → 분이 88)이 내려오는 경우가 있어
    그대로 자르면 '18:88' 같은 말이 안 되는 시각이 나온다. 초과분을 시(H)로 올림 처리한다."""
    try:
        h, m = int(raw[:2]), int(raw[2:4])
    except (ValueError, TypeError, IndexError):
        return raw
    h += m // 60
    m %= 60
    h %= 24
    return f"{h:02d}:{m:02d}"

# ── 다음 버스 표시 ─────────────────────────────────────────────────────────────
def render_next_buses(times: list, line_color: str, T: dict, remind_label: str = "") -> str:
    fmt = fmt_time
    upcoming = [t for t in times if t["TIME_PASS_YN"] == "N"]
    if not times:
        return f"<div style='color:#aaa;padding:8px;text-align:center'>{T['no_timetable']}</div>"
    if not upcoming:
        return f"<div style='color:#aaa;padding:8px;text-align:center'>{T['no_service']}</div>"
    is_last = len(upcoming) == 1
    hhmm = upcoming[0]["TIME"]
    # st.markdown(unsafe_allow_html=True)는 onclick 등 인라인 이벤트 핸들러를 스트립하므로
    # data-* 속성만 심고 실제 이벤트 바인딩은 components.html 스크립트의 이벤트 위임으로 처리
    safe_label = remind_label.replace("\\", "").replace("'", "").replace('"', "")
    bell_svg = (
        "<svg viewBox='0 0 24 24' fill='currentColor'><path d='M12 2c-1.1 0-2 .9-2 2v.29"
        "C7.28 5.15 5.5 7.83 5.5 11v5l-2 2v1h17v-1l-2-2v-5c0-3.17-1.78-5.85-4.5-6.71V4c0-1.1-.9-2-2-2z"
        "m0 20c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2z'/></svg>"
    )
    bell_html = (
        f"<span class='ypf-bell-wrap'>"
        f"<button type='button' class='ypf-bell-btn' title='{T['remind_title']}'>{bell_svg}</button>"
        f"<div class='ypf-bell-menu'>"
        f"<button type='button' data-remind-minutes='3' data-hhmm='{hhmm}' data-label=\"{safe_label}\">{T['remind_3']}</button>"
        f"<button type='button' data-remind-minutes='5' data-hhmm='{hhmm}' data-label=\"{safe_label}\">{T['remind_5']}</button>"
        f"<button type='button' class='ypf-cancel' data-remind-cancel='1'>{T['remind_cancel']}</button>"
        f"</div></span>"
    )
    html = (
        f"<div style='background:{line_color}18;border-left:4px solid {line_color};"
        f"padding:12px 16px;border-radius:6px;margin-bottom:4px;text-align:center'>"
        f"{T['next_bus']}"
        f"{'&nbsp;<span style=\"font-size:0.75em;font-weight:700;color:#e53e3e\">' + T['last_bus'] + '</span>' if is_last else ''}<br>"
        f"<span class='ypf-bell-anchor'>"
        f"<span style='font-size:1.8em;font-weight:800;color:{line_color}'>{fmt(hhmm)}</span>"
        f"{bell_html}</span></div>"
    )
    if not is_last:
        for label, idx in [(T["next2"], 1), (T["next3"], 2)]:
            if len(upcoming) > idx:
                html += (
                    f"<div style='padding:2px 16px;color:#555;font-size:0.92em;text-align:center'>"
                    f"{label} &nbsp;"
                    f"<span style='font-weight:700;color:#333'>{fmt(upcoming[idx]['TIME'])}</span></div>"
                )
    return html

# ── 전체 시간표 표시 ───────────────────────────────────────────────────────────
def render_full_timetable(times: list, line_color: str, T: dict) -> None:
    fmt = fmt_time
    if not times:
        st.caption(T["no_timetable"])
        return
    cells = []
    for t in times:
        passed = t["TIME_PASS_YN"] == "Y"
        style = (
            "display:inline-block;width:50px;text-align:center;"
            "margin:3px 2px;padding:5px 2px;border-radius:5px;font-size:0.87em;"
        )
        if passed:
            style += "color:#bbb;background:#f5f5f5;"
        else:
            style += f"color:{line_color};font-weight:700;background:{line_color}1A;"
        cells.append(f"<span style='{style}'>{fmt(t['TIME'])}</span>")
    st.markdown(
        "<div style='padding:4px 0;line-height:1'>" + "".join(cells) + "</div>",
        unsafe_allow_html=True
    )

# ── 지도 그리기 ────────────────────────────────────────────────────────────────
def load_font(size=13):
    for path in [
        "C:/Windows/Fonts/malgun.ttf",           # Windows
        "C:/Windows/Fonts/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # Linux (Community Cloud)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

STATIONS_FROZEN = tuple((n, d["x"], d["y"]) for n, d in STATIONS.items())

@st.cache_data(show_spinner=False)
def draw_map(selected_station, stations_frozen=STATIONS_FROZEN):
    img  = Image.open("reference/shuttle.jpg").copy()
    draw = ImageDraw.Draw(img)

    for name in STATIONS:
        x, y     = STATIONS[name]["x"], STATIONS[name]["y"]
        is_sel   = name == selected_station
        is_trans = name in TRANSFER_STATIONS

        if is_sel:
            ro, ri = 18, 12
            pr, pcy = 11, y - 30   # 핀 원 반지름, 핀 원 중심 (마커 위)
            # 선택 마커 (먼저 그림)
            draw.ellipse([x-ro, y-ro, x+ro, y+ro], fill="white", outline="#FFD700", width=3)
            draw.ellipse([x-ri, y-ri, x+ri, y+ri], fill="#E74C3C")
            # 핀 꼬리 (선택 마커 위에 겹쳐 그림 — 꼭짓점이 마커 중심 y에 꽂힘)
            draw.polygon([(x-5, pcy+pr), (x+5, pcy+pr), (x, y)], fill="#C0392B")
            # 핀 원
            draw.ellipse([x-pr, pcy-pr, x+pr, pcy+pr], fill="#E74C3C", outline="white", width=2)
            draw.ellipse([x-4, pcy-4, x+4, pcy+4], fill="white")
        elif is_trans:
            ro, ri = 16, 9
            draw.ellipse([x-ro, y-ro, x+ro, y+ro], fill="white", outline="#FF6A00", width=4)
            draw.ellipse([x-ri, y-ri, x+ri, y+ri], fill="#FF6A00")
        else:
            ro, ri = 12, 7
            draw.ellipse([x-ro, y-ro, x+ro, y+ro], fill="white", outline="#555", width=2)
            draw.ellipse([x-ri, y-ri, x+ri, y+ri], fill="#2a5298")

    # ── 범례 마커 오버레이 ─────────────────────────────────────────────────────
    # 환승 정류장 마커 (태극 마커 위치)
    lx1, ly1 = 146, 674
    draw.ellipse([lx1-14, ly1-14, lx1+14, ly1+14], fill="white", outline="#FF6A00", width=3)
    draw.ellipse([lx1-8,  ly1-8,  lx1+8,  ly1+8],  fill="#FF6A00")
    # 일반 정류장 마커 (흰 원 위치)
    lx2, ly2 = 149, 704
    draw.ellipse([lx2-12, ly2-12, lx2+12, ly2+12], fill="white", outline="#555", width=2)
    draw.ellipse([lx2-7,  ly2-7,  lx2+7,  ly2+7],  fill="#2a5298")

    return img

def nearest_station(cx, cy, threshold=35):
    best, best_d = None, threshold
    for name, info in STATIONS.items():
        d = math.hypot(cx - info["x"], cy - info["y"])
        if d < best_d:
            best_d, best = d, name
    return best

# ── 사이드바 ───────────────────────────────────────────────────────────────────
def render_sidebar(T: dict, line_display: dict, lang: str = "ko"):
    routes = load_routes()
    open_route = st.session_state.get("sidebar_open_route", None)

    with st.sidebar:
        # ── 노선 버튼 3열 그리드 ──
        route_ids = list(routes["routes"].keys())
        for row_start in range(0, len(route_ids), 3):
            row = route_ids[row_start : row_start + 3]
            cols = st.columns(len(row))
            for col, line_id in zip(cols, row):
                label   = line_display[line_id]
                is_open = open_route == line_id
                if col.button(label, key=f"sb_route_{line_id}",
                              use_container_width=True,
                              type="primary" if is_open else "secondary"):
                    st.session_state["sidebar_open_route"] = None if is_open else line_id
                    st.rerun()

        # JS에 사이드바 선택 상태 전달
        sb_label = line_display.get(open_route, "")
        st.markdown(f'<div id="ypf-sb" data-val="{sb_label}" style="display:none"></div>',
                    unsafe_allow_html=True)

        # ── 정류장 목록 영역 ──
        st.markdown("---")
        if open_route and open_route in routes["routes"]:
            color = LINE_COLORS.get(open_route, "#888")
            st.markdown(
                f"<div style='text-align:center;font-size:0.85em;font-weight:700;"
                f"color:{color};margin-bottom:6px'>"
                f"{T['route_stops'].format(r=line_display[open_route])}</div>",
                unsafe_allow_html=True
            )
            for station in routes["routes"][open_route]["stations"]:
                is_selected = st.session_state.get("selected") == station
                disp = stn(station, lang)
                if lang not in ("ko", "en"):
                    s_label = (f"◀ {disp} ▶  \n({station})"
                               if is_selected else f"{disp}  \n({station})")
                else:
                    s_label = f"◀ {disp} ▶" if is_selected else disp
                if st.button(s_label, key=f"sb_st_{open_route}_{station}",
                             use_container_width=True):
                    st.session_state["selected"]    = station
                    st.session_state["active_line"] = None
                    st.session_state["active_dir"]  = None
                    st.rerun()
        else:
            st.markdown(
                f"<div style='color:#aaa;font-size:0.82em'>{T['sidebar_hint']}</div>",
                unsafe_allow_html=True
            )


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main():
    # 세션 초기화
    # sidebar_initialized: 첫 렌더(새로고침/최초진입) 감지용 — 이후 rerun에서는 이미 존재
    is_first_render = "sidebar_initialized" not in st.session_state
    for key, default in [("selected", None), ("active_line", None),
                         ("active_dir", None), ("sidebar_open_route", None),
                         ("_last_click", None), ("lang", "ko"),
                         ("sidebar_initialized", True)]:
        if key not in st.session_state:
            st.session_state[key] = default

    lang = st.session_state["lang"]
    T = TEXTS[lang]
    if lang == "en":
        line_display = LINE_DISPLAY_EN
    elif lang == "ja":
        line_display = LINE_DISPLAY_JA
    else:
        line_display = LINE_DISPLAY

    # 타이틀 + 언어 선택기
    LANG_OPTS = [("🇰🇷 한국어", "ko"), ("🇺🇸 English", "en"), ("🇯🇵 日本語", "ja")]
    col_hdr, col_lang = st.columns([5, 1])
    with col_hdr:
        st.markdown(f"## 🚌 {T['title']}", unsafe_allow_html=True)
    with col_lang:
        sel_lang = st.selectbox(
            "", [lbl for lbl, _ in LANG_OPTS],
            index=next(i for i, (_, c) in enumerate(LANG_OPTS) if c == lang),
            label_visibility="collapsed",
        )
        new_lang = next(c for lbl, c in LANG_OPTS if lbl == sel_lang)
        if new_lang != lang:
            st.session_state["lang"] = new_lang
            st.rerun()

    # 방문자 카운트: 세션 최초 렌더 시 1회만 API 호출
    if is_first_render:
        vt, vn = fetch_visitor_counts()
        st.session_state["_visitor_today"] = vt
        st.session_state["_visitor_total"] = vn

    inject_all_css(line_display, close_sidebar=is_first_render,
                   visitor_today=st.session_state.get("_visitor_today", -1),
                   visitor_total=st.session_state.get("_visitor_total", -1))
    render_sidebar(T, line_display, lang)

    col_map, col_info = st.columns([3, 1])

    with col_map:
        st.markdown('<div id="ypf-map-marker" style="display:none"></div>', unsafe_allow_html=True)
        img = draw_map(selected_station=st.session_state["selected"])
        coords = streamlit_image_coordinates(
            img, key="yard_map",
            use_column_width="always",
        )

        if coords and "x" in coords:
            click_key = (coords["x"], coords["y"])
            if click_key != st.session_state["_last_click"]:
                st.session_state["_last_click"] = click_key
                # 표시 크기 기준 비율(0.0~1.0) → 원본 픽셀(1280×720)로 변환
                disp_w = coords.get("width") or 1
                disp_h = coords.get("height") or 1
                cx = int((coords["x"] / disp_w) * 1280)
                cy = int((coords["y"] / disp_h) * 720)
                hit = nearest_station(cx, cy)
                if hit and hit != st.session_state["selected"]:
                    st.session_state["selected"]    = hit
                    st.session_state["active_line"] = None
                    st.session_state["active_dir"]  = None
                    st.rerun()

    # ── 정보 패널 ──
    with col_info:
        sel = st.session_state["selected"]
        if not sel:
            st.info(T["select_station"])
            return

        code = STATIONS[sel]["code"]
        st.markdown(f"### {stn(sel, lang)}")
        if lang not in ("ko", "en"):
            st.caption(sel)

        # STEP 1: 노선 선택
        with st.spinner(T["spinner_lines"]):
            all_lines = fetch_all_lines(code)

        if not all_lines:
            st.warning(T["no_lines"])
        else:
            line_items = list(all_lines.items())
            # 노선이 하나면 자동 선택
            if len(line_items) == 1 and st.session_state["active_line"] != line_items[0][0]:
                st.session_state["active_line"] = line_items[0][0]
                st.session_state["active_dir"]  = None
                st.rerun()
            if len(line_items) == 1:
                line_id, _ = line_items[0]
                label = line_display.get(line_id, line_id)
                if st.button(label, key=f"line_{line_id}",
                             use_container_width=True):
                    st.session_state["active_line"] = line_id
                    st.session_state["active_dir"]  = None
                    st.rerun()
            else:
                # 2→2열, 4→2+2, 3/5/6+→3열
                n = len(line_items)
                cols_per_row = 2 if n in (2, 4) else 3
                for i in range(0, n, cols_per_row):
                    row = line_items[i : i + cols_per_row]
                    row_cols = st.columns(len(row))
                    for col, (line_id, _) in zip(row_cols, row):
                        label = line_display.get(line_id, line_id)
                        if col.button(label, key=f"line_{line_id}",
                                      use_container_width=True):
                            st.session_state["active_line"] = line_id
                            st.session_state["active_dir"]  = None
                            st.rerun()
            # JS에 메인패널 선택 상태 전달
            main_label = line_display.get(st.session_state["active_line"], "")
            st.markdown(f'<div id="ypf-main" data-val="{main_label}" style="display:none"></div>',
                        unsafe_allow_html=True)

        # STEP 2: 방향 선택
        active_line = st.session_state["active_line"]
        if active_line and active_line in all_lines:
            dirs = all_lines[active_line]["directions"]
            terminal_dir = get_terminal_direction(sel, active_line)
            # 방향이 하나뿐이면 자동 선택 (시·종점 또는 API가 단방향만 반환)
            auto_dir = terminal_dir or (dirs[0] if len(dirs) == 1 else None)
            if auto_dir and st.session_state["active_dir"] != auto_dir:
                st.session_state["active_dir"] = auto_dir
                st.rerun()
            elif not auto_dir:
                st.markdown(T["dir_select"])
                for d in ["1", "2"]:
                    end, prev, nxt = get_direction_parts(sel, active_line, d)
                    is_act    = st.session_state.get("active_dir") == d
                    end_d  = stn(end, lang)
                    prev_d = stn(prev, lang) if prev else None
                    nxt_d  = stn(nxt,  lang) if nxt  else None
                    sel_d  = stn(sel,  lang)
                    prev_bold = f"**[{prev_d}]**" if prev_d else ""
                    nxt_bold  = f"**[{nxt_d}]**"  if nxt_d  else ""
                    if lang == "ko":
                        first_line = f"**[{end_d}] 방면**"
                    elif lang == "en":
                        first_line = f"**To [{end_d}]**"
                    else:
                        first_line = f"**[{end_d}]行き**"
                    if lang not in ("ko", "en"):
                        label = f"{first_line}\n\n({end})\n\n{prev_bold} → [{sel_d}] → {nxt_bold}"
                    else:
                        label = f"{first_line}\n\n{prev_bold} → [{sel_d}] → {nxt_bold}"
                    if st.button(label, key=f"dir_{d}", use_container_width=True,
                                 type="primary" if is_act else "secondary"):
                        st.session_state["active_dir"] = d
                        st.rerun()
            # JS에 선택된 방향의 종점 이름 전달
            active_d = st.session_state.get("active_dir", "")
            active_end = ""
            if active_d:
                active_end_ko, _, _ = get_direction_parts(sel, active_line, active_d)
                active_end = stn(active_end_ko, lang)
            st.markdown(
                f'<div id="ypf-dir" data-val="{active_end}" style="display:none"></div>',
                unsafe_allow_html=True
            )

        # STEP 3: 다음 버스
        active_dir = st.session_state["active_dir"]
        if active_line and active_dir:
            line_color = LINE_COLORS.get(active_line, "#888")
            with st.spinner(T["spinner_timetable"]):
                times = fetch_timetable(code, active_dir, active_line)
            remind_label = f"{stn(sel, lang)} · {line_display.get(active_line, active_line)}"
            st.markdown(render_next_buses(times, line_color, T, remind_label), unsafe_allow_html=True)
            with st.expander(T["full_timetable"]):
                render_full_timetable(times, line_color, T)

        st.markdown("")
        if st.button(T["refresh"], use_container_width=True):
            st.session_state["active_line"] = None
            st.session_state["active_dir"]  = None
            st.rerun()


if __name__ == "__main__":
    main()
