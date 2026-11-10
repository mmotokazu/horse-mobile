"""
一口馬主 モバイル専用Webアプリ (deploy_mobile/app_mobile.py)

【アプリケーションの目的】
- 外出先やベッドの中から、iPhone単体で現役愛馬の出走予定・戦績・直近3ヶ月の近況メモを爆速で閲覧できる特化型ダッシュボード。
- PCの電源がOFFでも、Streamlit Community Cloud上で24時間いつでも完全稼働。
- ユーザー合意仕様（2026/11決定）:
  1. 2大タブ構成（「🎯 出走予定＆動向」タブ ＋ 「🏇 愛馬カルテ」タブ）
  2. 出走カードから該当馬カルテへワンタップで連動
  3. 近況メモ: 「最新5件は常に全文展開 ＋ 過去分（3ヶ月以内）は日付アコーディオンでスッキリ整理」
  4. クラブ公式カラー完全準拠（東サラ:赤、シルク:水色、キャロット:緑）
"""

import os
import json
from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd

# ページ基本設定（iPhone最適化）
st.set_page_config(
    page_title="一口馬主 モバイル",
    page_icon="🏇",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ----------------------------------------------------
# クラブ別イメージカラー設定
# ----------------------------------------------------
CLUB_THEMES = {
    "東京サラブレッドクラブ": {
        "short_name": "東サラ",
        "primary": "#ef4444",
        "border": "#ef4444",
        "bg_badge": "#fee2e2",
        "text_badge": "#b91c1c",
        "accent": "#dc2626"
    },
    "シルクホースクラブ": {
        "short_name": "シルク",
        "primary": "#0284c7",
        "border": "#0ea5e9",
        "bg_badge": "#e0f2fe",
        "text_badge": "#0369a1",
        "accent": "#0284c7"
    },
    "キャロットクラブ": {
        "short_name": "キャロット",
        "primary": "#059669",
        "border": "#10b981",
        "bg_badge": "#dcfce7",
        "text_badge": "#15803d",
        "accent": "#059669"
    }
}

def get_club_theme(club_name: str):
    club_str = str(club_name or "")
    if "東サラ" in club_str or "東京サラブレッド" in club_str:
        return CLUB_THEMES["東京サラブレッドクラブ"]
    elif "シルク" in club_str:
        return CLUB_THEMES["シルクホースクラブ"]
    elif "キャロット" in club_str:
        return CLUB_THEMES["キャロットクラブ"]
    return {
        "short_name": club_str.replace("クラブ", "").replace("ホース", "") or "クラブ",
        "primary": "#64748b",
        "border": "#94a3b8",
        "bg_badge": "#f1f5f9",
        "text_badge": "#475569",
        "accent": "#64748b"
    }


# ----------------------------------------------------
# データ読み込み
# ----------------------------------------------------
@st.cache_data
def load_mobile_data():
    data_path = Path(__file__).resolve().parent / "data" / "mobile_uma_data.json"
    if not data_path.exists():
        return None
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        return None

app_data = load_mobile_data()

if not app_data:
    st.warning("⚠️ モバイル用データが見つかりません。自宅PCのアプリ側から「☁️ iPhone用データをクラウド同期」を実行してください。")
    st.stop()

metadata = app_data.get("metadata", {})
this_week_horses = app_data.get("this_week_horses", [])
upcoming_calendar = app_data.get("upcoming_calendar", [])
kanban = app_data.get("kanban", {})
horses = app_data.get("horses", {})

# ----------------------------------------------------
# カスタムCSS（スマホ特化スタイル）
# ----------------------------------------------------
st.markdown("""
<style>
/* スマホ画面の余白最適化 */
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 2rem !important;
    padding-left: 0.8rem !important;
    padding-right: 0.8rem !important;
}
/* タブのスタイル調整 */
button[data-baseweb="tab"] {
    font-size: 1.0rem !important;
    font-weight: 800 !important;
    padding: 8px 16px !important;
}
/* カードのタップ演出 */
.mobile-card {
    background: white;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    border: 1px solid #e2e8f0;
}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------
# ヘッダーバナー
# ----------------------------------------------------
updated_time = metadata.get("last_updated", "-")
total_horses = metadata.get("total_active_horses", len(horses))

col_h1, col_h2 = st.columns([2.5, 1.5])
with col_h1:
    st.markdown("<h3 style='margin:0; padding:0; color:#0f172a;'>🏇 一口馬主モバイル</h3>", unsafe_allow_html=True)
with col_h2:
    st.markdown(f"<div style='text-align:right; font-size:0.75rem; color:#64748b; margin-top:6px;'>現役 {total_horses}頭<br>🕒 {updated_time[5:16]}</div>", unsafe_allow_html=True)

st.markdown("<hr style='margin: 8px 0 12px 0;'>", unsafe_allow_html=True)


# ----------------------------------------------------
# セッション状態管理（タブ切り替え ＆ 愛馬選択）
# ----------------------------------------------------
if "selected_horse" not in st.session_state:
    st.session_state.selected_horse = list(horses.keys())[0] if horses else ""

# クエリパラメータ連動
query_params = st.query_params
if "horse" in query_params and query_params["horse"] in horses:
    st.session_state.selected_horse = query_params["horse"]

# 2大タブ構成
tab_track, tab_karte = st.tabs(["🎯 出走予定 ＆ 動向", "🏇 愛馬カルテ"])


# ====================================================
# 【タブ1】🎯 出走予定 ＆ 動向ボード
# ====================================================
with tab_track:
    # 1. 🔥 今週出走プレミアムバナー
    if this_week_horses:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 50%, #fff7ed 100%); border: 2px solid #f59e0b; border-left: 8px solid #ef4444; border-radius: 8px; padding: 10px 14px; margin-bottom: 14px; box-shadow: 0 2px 6px rgba(245, 158, 11, 0.15);">
        <div style="font-weight: 900; font-size: 0.95rem; color: #b45309; margin-bottom: 6px;">
        🔥 今週出走確定愛馬 ({len_horses}頭)
        </div>
        """.replace("{len_horses}", str(len(this_week_horses))), unsafe_allow_html=True)

        for tw in this_week_horses:
            theme = get_club_theme(tw.get("club", ""))
            j_txt = f" / {tw['jockey']}" if tw.get("jockey") else ""
            c_label = str(tw.get("countdown_label", "")).replace("⚡ ", "").replace("🔥 ", "")

            st.markdown(f"""
            <div style="background: white; border: 1px solid #fde68a; border-left: 5px solid {theme['border']}; border-radius: 6px; padding: 8px 12px; margin-top: 6px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="font-weight:900; font-size:1.0rem; color:#0f172a;">{tw['horse_name']}</span>
                    <span style="font-size:0.72rem; background:{theme['bg_badge']}; color:{theme['text_badge']}; padding:1px 6px; border-radius:3px; font-weight:700; margin-left:4px;">{theme['short_name']}</span>
                </div>
                <span style="background:#ef4444; color:white; padding:2px 7px; border-radius:4px; font-weight:800; font-size:0.75rem;">⚡ {c_label}</span>
            </div>
            <div style="font-size:0.86rem; font-weight:700; color:#b91c1c; margin-top:3px;">
                🎯 {tw['target_race']}{j_txt}
            </div>
            <div style="display:flex; justify-content:space-between; font-size:0.74rem; color:#64748b; margin-top:3px;">
                <span>現在地: {tw['facility']}</span>
                <span style="color:{theme['primary']}; font-weight:700;">📅 {tw['date_badge']}</span>
            </div>
            </div>
            """, unsafe_allow_html=True)

            # カルテへジャンプするボタン
            if st.button(f"🏇 {tw['horse_name']} のカルテを開く", key=f"btn_tw_{tw['horse_name']}", width="stretch"):
                st.session_state.selected_horse = tw['horse_name']
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # 2. 📅 直近出走スケジュール一覧
    st.markdown("<h4 style='margin:12px 0 6px 0; color:#1e293b;'>📅 直近出走カレンダー</h4>", unsafe_allow_html=True)
    if not upcoming_calendar:
        st.info("現在予定されているレースはありません。")
    else:
        for cal in upcoming_calendar:
            theme = get_club_theme(cal.get("club", ""))
            j_txt = f" / {cal['jockey']}" if cal.get("jockey") else ""
            date_badge = f"📅 {cal['date_badge']}" if cal.get("date_badge") else "🎯 開催目標"

            st.markdown(f"""
            <div class="mobile-card" style="border-left: 5px solid {theme['border']};">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="font-weight:800; font-size:0.95rem; color:#0f172a;">{cal['horse_name']}</span>
                    <span style="font-size:0.72rem; background:{theme['bg_badge']}; color:{theme['text_badge']}; padding:1px 6px; border-radius:3px; font-weight:700; margin-left:4px;">{theme['short_name']}</span>
                </div>
                <span style="font-size:0.78rem; background:{theme['primary']}; color:white; padding:2px 7px; border-radius:4px; font-weight:800;">{date_badge}</span>
            </div>
            <div style="font-size:0.86rem; font-weight:700; color:#0f172a; margin-top:4px;">
                {cal['target_race']}{j_txt}
            </div>
            <div style="font-size:0.74rem; color:#64748b; margin-top:3px;">
                現在地: {cal['facility']}
            </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<hr style='margin: 14px 0 10px 0;'>", unsafe_allow_html=True)

    # 3. 📍 滞在拠点ステータスボード（アコーディオン形式で展開可能）
    st.markdown("<h4 style='margin:10px 0 6px 0; color:#1e293b;'>📍 滞在拠点ステータス</h4>", unsafe_allow_html=True)

    tc_list = kanban.get("tc", [])
    farm_list = kanban.get("farm", [])
    hok_list = kanban.get("hok", [])

    with st.expander(f"🟢 トレセン在厩 ({len(tc_list)}頭)", expanded=True):
        if not tc_list:
            st.caption("現在在厩の馬はいません。")
        else:
            for item in tc_list:
                tgt = f" ｜ 🎯 {item['target_race']}" if item.get("target_race") else ""
                st.markdown(f"**{item['horse_name']}** ({item['facility']}) - {item['trainer']}{tgt}")

    with st.expander(f"🟡 近郊外厩・調整中 ({len(farm_list)}頭)", expanded=False):
        if not farm_list:
            st.caption("現在外厩調整中の馬はいません。")
        else:
            for item in farm_list:
                tgt = f" ｜ 🎯 {item['target_race']}" if item.get("target_race") else ""
                st.markdown(f"**{item['horse_name']}** ({item['facility']}) - {item['trainer']}{tgt}")

    with st.expander(f"🔵 北海道・休養/育成 ({len(hok_list)}頭)", expanded=False):
        if not hok_list:
            st.caption("現在北海道滞在の馬はいません。")
        else:
            for item in hok_list:
                st.markdown(f"**{item['horse_name']}** ({item['facility']})")


# ====================================================
# 【タブ2】🏇 愛馬カルテ（戦績 ＆ 3ヶ月近況）
# ====================================================
with tab_karte:
    horse_names = list(horses.keys())
    
    # 馬名セレクター
    curr_idx = horse_names.index(st.session_state.selected_horse) if st.session_state.selected_horse in horse_names else 0
    selected_name = st.selectbox("愛馬を選択", horse_names, index=curr_idx, key="sb_horse_select")
    st.session_state.selected_horse = selected_name

    horse = horses.get(selected_name, {})
    theme = get_club_theme(horse.get("club", ""))

    # 基本プロファイルカード
    wt_str = f"⚖️ {horse.get('weight')}" if horse.get('weight') and horse.get('weight') != "-" else "体重 -"
    tgt_info = f"🎯 次走目標: <b>{horse['target_race']}</b>" if horse.get('target_race') else "次走: 未定"

    st.markdown(f"""
    <div style="background: white; border: 1px solid #cbd5e1; border-top: 5px solid {theme['border']}; border-radius: 8px; padding: 12px 14px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
            <span style="font-weight:900; font-size:1.15rem; color:#0f172a;">{horse.get('horse_name')}</span>
            <span style="font-size:0.75rem; background:{theme['bg_badge']}; color:{theme['text_badge']}; padding:2px 7px; border-radius:3px; font-weight:700; margin-left:6px;">{theme['short_name']}</span>
        </div>
        <span style="font-size:0.78rem; color:#059669; font-weight:800; background:#ecfdf5; padding:2px 8px; border-radius:4px;">{horse.get('category')}</span>
    </div>
    <div style="font-size:0.82rem; color:#475569; margin-top:6px;">
        🏛️ {horse.get('trainer')} ｜ 📍 {horse.get('facility')} ｜ {wt_str}
    </div>
    <div style="font-size:0.78rem; color:#64748b; margin-top:2px;">
        血統: {horse.get('sire')} × {horse.get('dam')} ｜ 募集価格: {horse.get('price_man')}万円
    </div>
    <div style="font-size:0.84rem; color:#b91c1c; margin-top:6px; padding-top:6px; border-top:1px dashed #e2e8f0;">
        {tgt_info}
    </div>
    </div>
    """, unsafe_allow_html=True)

    # サブセクション: 確定戦績テーブル
    races = horse.get("races", [])
    confirmed_races = [r for r in races if r.get("rank") is not None or r.get("rank_disp") in ["中止", "除外", "取消"]]

    with st.expander(f"📊 通算戦績一覧 ({len(confirmed_races)}戦)", expanded=False):
        if not confirmed_races:
            st.caption("出走履歴はまだありません。")
        else:
            race_rows = []
            for r in confirmed_races:
                # メダル表記
                rk = r.get("rank")
                if rk == 1:
                    rk_badge = "🥇 1着"
                elif rk == 2:
                    rk_badge = "🥈 2着"
                elif rk == 3:
                    rk_badge = "🥉 3着"
                elif r.get("rank_disp"):
                    rk_badge = str(r["rank_disp"])
                else:
                    rk_badge = f"{rk}着" if rk else "-"

                race_rows.append({
                    "日付": r.get("date"),
                    "場/R": f"{r.get('place')}{r.get('round')}",
                    "レース名": r.get("race_name"),
                    "着順": rk_badge,
                    "タイム": r.get("time"),
                    "着差": r.get("margin"),
                    "騎手": r.get("jockey")
                })
            df_r_disp = pd.DataFrame(race_rows)
            st.dataframe(df_r_disp, hide_index=True, width="stretch")

    # サブセクション: 直近3ヶ月の近況メモ（ユーザーご指定仕様）
    diaries = horse.get("diaries", [])
    st.markdown(f"<h4 style='margin:16px 0 8px 0; color:#1e293b;'>📝 直近3ヶ月の近況メモ ({len(diaries)}件)</h4>", unsafe_allow_html=True)

    if not diaries:
        st.info("直近3ヶ月以内の近況メモはありません。")
    else:
        # ① 最新5件: 常に全文展開
        top_5 = diaries[:5]
        past_diaries = diaries[5:]

        st.caption("⚡ 最新の近況動向（直近5件）")
        for i, d in enumerate(top_5):
            d_date = d.get("date", "-")
            content = d.get("content", "")
            wt_badge = f" <span style='font-size:0.75rem; color:#64748b;'>({d['weight']}kg)</span>" if d.get("weight") else ""

            # 調教時計メモかコメントかの視覚的差別化
            is_training = content.strip().startswith("＜調教＞")
            card_border = "#e2e8f0"
            tag_color = "#3b82f6" if is_training else "#059669"
            tag_text = "時計" if is_training else "近況"

            st.markdown(f"""
            <div style="background:white; border:1px solid {card_border}; border-radius:6px; padding:10px 12px; margin-bottom:8px; box-shadow:0 1px 2px rgba(0,0,0,0.03);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                <span style="font-weight:800; font-size:0.86rem; color:#1e293b;">📅 {d_date}{wt_badge}</span>
                <span style="font-size:0.7rem; background:{tag_color}15; color:{tag_color}; font-weight:800; padding:1px 6px; border-radius:3px;">{tag_text}</span>
            </div>
            <div style="font-size:0.84rem; color:#334155; line-height:1.55; white-space:pre-wrap;">{content}</div>
            </div>
            """, unsafe_allow_html=True)

        # ② 過去分（6件目以降、3ヶ月以内）: 日付アコーディオンでスッキリ整理
        if past_diaries:
            st.caption(f"📂 過去の近況メモ（{len(past_diaries)}件）- タップして閲覧")
            for d in past_diaries:
                d_date = d.get("date", "-")
                content = d.get("content", "")
                wt_badge = f" ({d['weight']}kg)" if d.get("weight") else ""
                first_line = content.split("\n")[0][:25] + "..." if len(content) > 25 else content

                with st.expander(f"📅 {d_date}{wt_badge} ｜ {first_line}"):
                    st.markdown(f"<div style='font-size:0.84rem; color:#334155; line-height:1.55; white-space:pre-wrap;'>{content}</div>", unsafe_allow_html=True)
