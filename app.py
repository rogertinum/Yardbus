import streamlit as st
import streamlit.components.v1 as components
from streamlit_image_coordinates import streamlit_image_coordinates
from PIL import Image, ImageDraw, ImageFont
import math, requests, os, json, datetime
from functools import lru_cache

_KST = datetime.timezone(datetime.timedelta(hours=9))
BUILD_TIME = datetime.datetime.fromtimestamp(os.path.getmtime(__file__), tz=_KST).strftime("%m/%d %H:%M")

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
def inject_all_css():
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
    .block-container [data-testid="stMarkdown"]:first-child { margin-bottom: 0 !important; }
    #root > div:first-child { padding-top: 0 !important; }
    hr { margin: 6px 0 !important; }
    /* 사이드바 오버레이 — 메인 영역 폭 변화 없음 */
    section[data-testid="stSidebar"] {
        position: fixed !important;
        z-index: 999 !important;
        top: 0 !important;
        left: 0 !important;
        height: 100dvh !important;
    }
    [data-testid="stAppViewContainer"] > .main {
        margin-left: 0 !important;
    }
    /* 사이드바 토글 버튼 — 화면 중앙 왼쪽, 눈에 띄게 */
    button[data-testid="collapsedControl"] {
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
    }
    /* 터치 반응성 — 300ms 딜레이 제거 */
    button { touch-action: manipulation !important; }
    /* 버튼 래퍼 배경 투명 — 다크모드 흰 꼭짓점 방지 */
    div[data-testid="stButton"] {
        background: transparent !important;
        background-color: transparent !important;
    }
    /* 노선 버튼: CSS grid 3열 레이아웃 (PC/모바일 공통) */
    [data-testid="stColumn"] [data-testid="stHorizontalBlock"] {
        display: grid !important;
        grid-template-columns: repeat(3, 1fr) !important;
        gap: 4px !important;
    }
    [data-testid="stColumn"] [data-testid="stColumn"] {
        min-width: 0 !important;
        max-width: 100% !important;
        width: 100% !important;
        flex: unset !important;
    }
    /* ── 모바일 반응형 (768px 이하) ───────────────────────────────────────── */
    @media (max-width: 768px) {
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
            background: white !important;
        }
        /* 정보 패널 컬럼: 지도 뒤로 */
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {
            position: relative !important;
            z-index: 1 !important;
        }
        /* only-child: first+last 규칙 충돌 방지 (예: 노선 2개 이하 레이아웃) */
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:only-child {
            position: static !important;
            top: auto !important;
            z-index: auto !important;
            background: transparent !important;
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
    }
    </style>
    """, unsafe_allow_html=True)

    color_map = {
        LINE_DISPLAY[k]: {"bg": v, "text": LINE_TEXT_COLOR.get(k, "white")}
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

            // strong 태그 스타일: 1번째=종점방면(2em), 2번째 이후=이전/다음 정류장(1.4em)
            const strongs = btn.querySelectorAll('p strong, strong');
            if (strongs.length > 0) {{
                strongs[0].style.setProperty('font-size', '2em', 'important');
                strongs[0].style.setProperty('display', 'block', 'important');
                strongs[0].style.setProperty('margin', '0 0 2px 0', 'important');
                strongs[0].style.setProperty('line-height', '1', 'important');
            }}
            for (let i = 1; i < strongs.length; i++) {{
                strongs[i].style.setProperty('font-size', '1.4em', 'important');
                strongs[i].style.setProperty('line-height', '1', 'important');
            }}

            // 버튼 간격 축소: stButton 래퍼 margin 줄이기
            const wrapper = btn.closest('[data-testid="stButton"]');
            if (wrapper) wrapper.style.setProperty('margin-bottom', '-8px', 'important');

            // 활성 감지: 종점 이름이 버튼 텍스트 앞부분에 포함되는지 확인 (띄어쓰기 포함)
            const isActive = activeDirEnd !== '' && text.startsWith('[' + activeDirEnd + '] 방면');
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

        // 사이드바 정류장 버튼
        if (!sidebar) return;
        sidebar.querySelectorAll('[data-testid="stButton"] button').forEach(btn => {{
            const text = btn.innerText.trim();
            if (routeNames.has(text)) return;
            if (text.startsWith('▸')) return;
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

    // viewport-fit=cover: safe area inset 사용 가능하게
    (function() {{
        const m = window.parent.document.querySelector('meta[name="viewport"]');
        if (m && !m.content.includes('viewport-fit')) {{
            m.content += ', viewport-fit=cover';
        }}
    }})();

    // 세션 첫 진입 시: PC(가로>세로)는 닫기, 모바일(세로>가로)은 열기
    if (!window.parent.sessionStorage.getItem('ypf_init')) {{
        window.parent.sessionStorage.setItem('ypf_init', '1');
        setTimeout(() => {{
            const btn = window.parent.document.querySelector('[data-testid="collapsedControl"]');
            const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
            if (!btn || !sidebar) return;
            const isPortrait = window.parent.innerHeight > window.parent.innerWidth;
            const rect = sidebar.getBoundingClientRect();
            const isOpen = rect.left > -50;
            if (isPortrait && !isOpen) {{ btn.click(); }}   // 모바일: 열기
            else if (!isPortrait && isOpen) {{ btn.click(); }} // PC: 닫기
        }}, 600);
    }}

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

    applyStyles();
    new MutationObserver(() => {{ applyStyles(); }})
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

# ── 다음 버스 표시 ─────────────────────────────────────────────────────────────
def render_next_buses(times: list, line_color: str) -> str:
    def fmt(raw): return raw[:2] + ":" + raw[2:]
    upcoming = [t for t in times if t["TIME_PASS_YN"] == "N"]
    if not times:
        return "<div style='color:#aaa;padding:8px;text-align:center'>시간표 없음</div>"
    if not upcoming:
        return "<div style='color:#aaa;padding:8px;text-align:center'>🚫 오늘 운행 종료</div>"
    is_last = len(upcoming) == 1
    html = (
        f"<div style='background:{line_color}18;border-left:4px solid {line_color};"
        f"padding:12px 16px;border-radius:6px;margin-bottom:4px;text-align:center'>"
        f"🚌 다음 버스"
        f"{'&nbsp;<span style=\"font-size:0.75em;font-weight:700;color:#e53e3e\">막차</span>' if is_last else ''}<br>"
        f"<span style='font-size:1.8em;font-weight:800;color:{line_color}'>"
        f"{fmt(upcoming[0]['TIME'])}</span></div>"
    )
    if not is_last:
        for label, idx in [("그 다음", 1), ("그 다다음", 2)]:
            if len(upcoming) > idx:
                html += (
                    f"<div style='padding:2px 16px;color:#555;font-size:0.92em;text-align:center'>"
                    f"{label} &nbsp;"
                    f"<span style='font-weight:700;color:#333'>{fmt(upcoming[idx]['TIME'])}</span></div>"
                )
    return html

# ── 전체 시간표 표시 ───────────────────────────────────────────────────────────
def render_full_timetable(times: list, line_color: str) -> None:
    def fmt(raw): return raw[:2] + ":" + raw[2:]
    if not times:
        st.caption("시간표 없음")
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
def render_sidebar():
    routes = load_routes()
    open_route = st.session_state.get("sidebar_open_route", None)

    with st.sidebar:
        # ── 노선 버튼 3열 그리드 ──
        route_ids = list(routes["routes"].keys())
        for row_start in range(0, len(route_ids), 3):
            row = route_ids[row_start : row_start + 3]
            cols = st.columns(len(row))
            for col, line_id in zip(cols, row):
                label   = LINE_DISPLAY[line_id]
                is_open = open_route == line_id
                if col.button(label, key=f"sb_route_{line_id}",
                              use_container_width=True,
                              type="primary" if is_open else "secondary"):
                    st.session_state["sidebar_open_route"] = None if is_open else line_id
                    st.rerun()

        # JS에 사이드바 선택 상태 전달
        sb_label = LINE_DISPLAY.get(open_route, "")
        st.markdown(f'<div id="ypf-sb" data-val="{sb_label}" style="display:none"></div>',
                    unsafe_allow_html=True)

        # ── 정류장 목록 영역 ──
        st.markdown("---")
        if open_route and open_route in routes["routes"]:
            color = LINE_COLORS.get(open_route, "#888")
            st.markdown(
                f"<div style='text-align:center;font-size:0.85em;font-weight:700;"
                f"color:{color};margin-bottom:6px'>{LINE_DISPLAY[open_route]} 정류장</div>",
                unsafe_allow_html=True
            )
            for station in routes["routes"][open_route]["stations"]:
                is_selected = st.session_state.get("selected") == station
                s_label = f"◀ {station} ▶" if is_selected else station
                if st.button(s_label, key=f"sb_st_{open_route}_{station}",
                             use_container_width=True):
                    st.session_state["selected"]    = station
                    st.session_state["active_line"] = None
                    st.session_state["active_dir"]  = None
                    st.rerun()
        else:
            st.markdown(
                "<div style='color:#aaa;font-size:0.82em'>노선을 선택하면 정류장 목록이 표시됩니다.</div>",
                unsafe_allow_html=True
            )


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main():
    st.markdown(f"## 🚌 야드 버스 시간표 <span style='font-size:0.45em;color:#999;font-weight:400;white-space:nowrap'>{BUILD_TIME}</span>", unsafe_allow_html=True)

    # 세션 초기화
    for key, default in [("selected", None), ("active_line", None),
                         ("active_dir", None), ("sidebar_open_route", None),
                         ("_last_click", None)]:
        if key not in st.session_state:
            st.session_state[key] = default

    inject_all_css()
    render_sidebar()

    col_map, col_info = st.columns([3, 1])

    with col_map:
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
            st.info("지도 또는 사이드바에서 정류장을 선택하세요.")
            return

        code = STATIONS[sel]["code"]
        st.markdown(f"### {sel}")

        # STEP 1: 노선 선택 (3열 그리드)
        with st.spinner("노선 조회 중..."):
            all_lines = fetch_all_lines(code)

        if not all_lines:
            st.warning("운행 노선 정보를 불러올 수 없습니다.")
        else:
            line_items = list(all_lines.items())
            if len(line_items) == 1:
                # 1개 노선: st.columns(1) stHorizontalBlock 생성 없이 직접 렌더링
                line_id, _ = line_items[0]
                label = LINE_DISPLAY.get(line_id, line_id)
                if st.button(label, key=f"line_{line_id}",
                             use_container_width=True):
                    st.session_state["active_line"] = line_id
                    st.session_state["active_dir"]  = None
                    st.rerun()
            else:
                cols = st.columns(len(line_items))
                for col, (line_id, _) in zip(cols, line_items):
                    label = LINE_DISPLAY.get(line_id, line_id)
                    if col.button(label, key=f"line_{line_id}",
                                  use_container_width=True):
                        st.session_state["active_line"] = line_id
                        st.session_state["active_dir"]  = None
                        st.rerun()
            # JS에 메인패널 선택 상태 전달
            main_label = LINE_DISPLAY.get(st.session_state["active_line"], "")
            st.markdown(f'<div id="ypf-main" data-val="{main_label}" style="display:none"></div>',
                        unsafe_allow_html=True)

        # STEP 2: 방향 선택
        active_line = st.session_state["active_line"]
        if active_line and active_line in all_lines:
            terminal_dir = get_terminal_direction(sel, active_line)
            if terminal_dir and st.session_state["active_dir"] != terminal_dir:
                # 시·종점: 방향 자동 선택, 버튼 미표시
                st.session_state["active_dir"] = terminal_dir
                st.rerun()
            elif not terminal_dir:
                st.markdown("**방향 선택**")
                for d in ["1", "2"]:
                    end, prev, nxt = get_direction_parts(sel, active_line, d)
                    is_act   = st.session_state.get("active_dir") == d
                    prev_bold = f"**[{prev}]**" if prev else ""
                    nxt_bold  = f"**[{nxt}]**" if nxt else ""
                    label = f"**[{end}] 방면**  \n{prev_bold} → [{sel}] → {nxt_bold}"
                    if st.button(label, key=f"dir_{d}", use_container_width=True,
                                 type="primary" if is_act else "secondary"):
                        st.session_state["active_dir"] = d
                        st.rerun()
            # JS에 선택된 방향의 종점 이름 전달
            active_d = st.session_state.get("active_dir", "")
            active_end = ""
            if active_d:
                active_end, _, _ = get_direction_parts(sel, active_line, active_d)
            st.markdown(
                f'<div id="ypf-dir" data-val="{active_end}" style="display:none"></div>',
                unsafe_allow_html=True
            )

        # STEP 3: 다음 버스
        active_dir = st.session_state["active_dir"]
        if active_line and active_dir:
            line_color = LINE_COLORS.get(active_line, "#888")
            with st.spinner("시간표 불러오는 중..."):
                times = fetch_timetable(code, active_dir, active_line)
            st.markdown(render_next_buses(times, line_color), unsafe_allow_html=True)
            with st.expander("📋 전체 시간표"):
                render_full_timetable(times, line_color)

        st.markdown("")
        if st.button("🔄 새로고침", use_container_width=True):
            st.session_state["active_line"] = None
            st.session_state["active_dir"]  = None
            st.rerun()


if __name__ == "__main__":
    main()
