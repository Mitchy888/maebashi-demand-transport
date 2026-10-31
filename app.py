
import io
import zipfile

import folium
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

# ============================================
# 前橋市デマンド交通分析
# データ取得・路線別集計・地図表示
# ============================================

st.set_page_config(
    page_title="前橋市デマンド交通分析",
    page_icon="🚌",
    layout="wide"
)

st.title("🚌 前橋市デマンド交通分析")
st.write(
    "前橋市のデマンド交通の移動実績を、"
    "路線別の集計表と地図で確認します。"
)


# --------------------------------------------
# ライセンス・データ出典・応募用試作品の表示
# --------------------------------------------

st.divider()

st.subheader("データ出典・ライセンス")

st.markdown("""
- **データセット：** [前橋市 デマンド交通（未来シェア提供）](https://ckan.odpt.org/ja/dataset/miraishare_maebashi_demand)
- **データライセンス：** [Creative Commons Attribution 4.0 International（CC BY 4.0）](https://creativecommons.org/licenses/by/4.0/deed.ja)
- **データ提供元：** 未来シェア（Mirai Share）
""")

st.subheader("公共交通オープンデータチャレンジ2026")

st.info(
    "本アプリは、公共交通オープンデータチャレンジ2026への"
    "応募を目的として開発中の試作品です。"
    "主催者・データ提供者の公式アプリではありません。"
)

st.markdown(
    "[公共交通オープンデータチャレンジ2026 公式サイト](https://challenge2026.odpt.org/ja/entry.html)"
)

st.divider()

st.caption(
    "データを集計・加工して、路線別の移動実績と地図を表示しています。"
    "元データそのものを再配布するものではありません。"
)

# --------------------------------------------
# 1. データのURL
# --------------------------------------------

gtfs_url = (
    "https://api-public.odpt.org/api/v4/files/"
    "Demand/data/maebashi_gtfs.zip"
)

demand_url = (
    "https://api-public.odpt.org/api/v4/files/"
    "Demand/data/maebashi_demand.zip"
)

route_names = {
    "1": "ふるさとバス（大胡・宮城・粕川地区）",
    "2": "るんるんバス（富士見・芳賀地区）",
    "3": "城南あおぞら号（城南地区）"
}

group_names = {
    "LG1": "ふるさとバス（大胡・宮城・粕川地区）",
    "LG2": "るんるんバス（富士見・芳賀地区）",
    "LG3": "城南あおぞら号（城南地区）"
}

group_colors = {
    "LG1": "blue",
    "LG2": "green",
    "LG3": "red"
}

# --------------------------------------------
# 2. ZIPファイルを取得してメモリー上で開く
# --------------------------------------------

@st.cache_data(show_spinner=False)
def download_zip(url):
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        files = {
            name: zf.read(name)
            for name in zf.namelist()
            if not name.endswith("/")
        }

    return files


# --------------------------------------------
# 3. テキストファイルを読み込む
# --------------------------------------------

def read_text_table(content):
    for encoding in ["utf-8-sig", "cp932"]:
        try:
            return pd.read_csv(
                io.BytesIO(content),
                encoding=encoding
            )
        except UnicodeDecodeError:
            continue

    raise ValueError("文字コードを判定できませんでした。")


# --------------------------------------------
# 4. データの取得と集計
# --------------------------------------------

@st.cache_data(show_spinner=False)
def prepare_data():
    gtfs_files = download_zip(gtfs_url)
    demand_files = download_zip(demand_url)

    gtfs_tables = {
        name: read_text_table(content)
        for name, content in gtfs_files.items()
    }

    demand_df = read_text_table(
        demand_files["maebashi_demand.txt"]
    )

    stops = gtfs_tables["stops.txt"]
    location_group_stops = gtfs_tables[
        "location_group_stops.txt"
    ]

    # 停留所に路線グループIDを付ける
    map_stops = stops.merge(
        location_group_stops,
        on="stop_id",
        how="left",
        validate="one_to_one"
    )

    # 乗車地点名を付ける
    pickup_stops = stops[
        ["stop_id", "stop_name"]
    ].rename(
        columns={
            "stop_id": "pickup_stop_id",
            "stop_name": "乗車地点名"
        }
    )

    # 降車地点名を付ける
    dropoff_stops = stops[
        ["stop_id", "stop_name"]
    ].rename(
        columns={
            "stop_id": "drop_off_stop_id",
            "stop_name": "降車地点名"
        }
    )

    demand_df = demand_df.merge(
        pickup_stops,
        on="pickup_stop_id",
        how="left"
    )

    demand_df = demand_df.merge(
        dropoff_stops,
        on="drop_off_stop_id",
        how="left"
    )

    # 停留所の緯度・経度を付ける
    pickup_coords = stops[
        ["stop_id", "stop_lat", "stop_lon"]
    ].rename(
        columns={
            "stop_id": "pickup_stop_id",
            "stop_lat": "乗車緯度",
            "stop_lon": "乗車経度"
        }
    )

    dropoff_coords = stops[
        ["stop_id", "stop_lat", "stop_lon"]
    ].rename(
        columns={
            "stop_id": "drop_off_stop_id",
            "stop_lat": "降車緯度",
            "stop_lon": "降車経度"
        }
    )

    demand_df = demand_df.merge(
        pickup_coords,
        on="pickup_stop_id",
        how="left"
    )

    demand_df = demand_df.merge(
        dropoff_coords,
        on="drop_off_stop_id",
        how="left"
    )

    # 路線・乗車地点・降車地点ごとに集計
    od_table = (
        demand_df.groupby(
            [
                "route_id",
                "pickup_stop_id",
                "drop_off_stop_id",
                "乗車地点名",
                "降車地点名",
                "乗車緯度",
                "乗車経度",
                "降車緯度",
                "降車経度"
            ],
            dropna=False
        )
        .size()
        .reset_index(name="移動記録件数")
    )

    od_table["route_id_text"] = (
        od_table["route_id"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
    )

    return demand_df, od_table, map_stops


# --------------------------------------------
# 5. 地図を作る
# --------------------------------------------

def create_map(map_stops, od_table):
    # 有効な緯度・経度がある停留所を使う
    valid_stops = map_stops.dropna(
        subset=["stop_lat", "stop_lon"]
    ).copy()

    if valid_stops.empty:
        raise ValueError("地図に表示できる停留所がありません。")

    center_lat = valid_stops["stop_lat"].mean()
    center_lon = valid_stops["stop_lon"].mean()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles="OpenStreetMap"
    )

    # 路線グループごとに停留所を色分け
    for _, stop in valid_stops.iterrows():
        group_id = str(stop.get("location_group_id", ""))

        color = group_colors.get(group_id, "gray")
        group_label = group_names.get(
            group_id,
            "路線グループ不明"
        )

        popup_text = (
            f"停留所：{stop['stop_name']}<br>"
            f"停留所ID：{stop['stop_id']}<br>"
            f"グループ：{group_label}"
        )

        folium.CircleMarker(
            location=[
                float(stop["stop_lat"]),
                float(stop["stop_lon"])
            ],
            radius=4,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            tooltip=str(stop["stop_name"]),
            popup=folium.Popup(
                popup_text,
                max_width=300
            )
        ).add_to(m)

    # 乗車地点から降車地点への移動を線で表示
    valid_od = od_table.dropna(
        subset=[
            "乗車緯度",
            "乗車経度",
            "降車緯度",
            "降車経度"
        ]
    )

    for _, od in valid_od.iterrows():
        count = int(od["移動記録件数"])

        route_id = str(od["route_id_text"])
        route_label = route_names.get(
            route_id,
            f"路線ID {route_id}"
        )

        popup_text = (
            f"路線：{route_label}<br>"
            f"乗車地点：{od['乗車地点名']}<br>"
            f"降車地点：{od['降車地点名']}<br>"
            f"移動記録件数：{count:,}件"
        )

        # 件数が多い移動ほど線を太くする
        line_weight = 1 + min(count / 200, 3)

        folium.PolyLine(
            locations=[
                [
                    float(od["乗車緯度"]),
                    float(od["乗車経度"])
                ],
                [
                    float(od["降車緯度"]),
                    float(od["降車経度"])
                ]
            ],
            color="purple",
            weight=line_weight,
            opacity=0.35,
            tooltip=(
                f"{od['乗車地点名']} → "
                f"{od['降車地点名']}：{count:,}件"
            ),
            popup=folium.Popup(
                popup_text,
                max_width=350
            )
        ).add_to(m)

    # 地図の凡例
    legend_html = """
    <div style="
        position: fixed;
        bottom: 30px;
        right: 20px;
        z-index: 9999;
        background-color: white;
        border: 2px solid grey;
        border-radius: 5px;
        padding: 10px;
        font-size: 12px;
        ">
        <b>停留所グループ</b><br>
        <span style="color:blue;">●</span>
        LG1：ふるさとバス<br>
        <span style="color:green;">●</span>
        LG2：るんるんバス<br>
        <span style="color:red;">●</span>
        LG3：城南あおぞら号<br>
        <span style="color:purple;">━</span>
        移動記録
    </div>
    """

    m.get_root().html.add_child(
        folium.Element(legend_html)
    )

    return m


# --------------------------------------------
# 6. データ読み込みボタン
# --------------------------------------------

if st.button(
    "データを読み込んで分析する",
    type="primary"
):
    try:
        with st.spinner("データを取得・集計しています..."):
            demand_df, od_table, map_stops = prepare_data()

        st.session_state["demand_df"] = demand_df
        st.session_state["od_table"] = od_table
        st.session_state["map_stops"] = map_stops

        st.success("データの取得と集計が完了しました。")

    except Exception as e:
        st.error(
            f"データ処理中にエラーが発生しました：{e}"
        )


# --------------------------------------------
# 7. 集計表と地図の表示
# --------------------------------------------

if "od_table" in st.session_state:
    demand_df = st.session_state["demand_df"]
    od_table = st.session_state["od_table"]
    map_stops = st.session_state["map_stops"]

    route_options = {
        "全路線": "all",
        "路線ID 1：ふるさとバス": "1",
        "路線ID 2：るんるんバス": "2",
        "路線ID 3：城南あおぞら号": "3"
    }

    selected_label = st.selectbox(
        "表示する路線を選んでください",
        list(route_options.keys())
    )

    selected_route = route_options[selected_label]

    if selected_route == "all":
        filtered = od_table.copy()
        filtered_demand = demand_df
    else:
        filtered = od_table[
            od_table["route_id_text"] == selected_route
        ].copy()

        normalized_route_ids = (
            demand_df["route_id"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
        )

        filtered_demand = demand_df[
            normalized_route_ids == selected_route
        ]

    trip_count = len(filtered_demand)

    filtered = filtered.sort_values(
        "移動記録件数",
        ascending=False
    )

    col1, col2 = st.columns(2)

    col1.metric(
        "移動記録件数",
        f"{trip_count:,}件"
    )

    col2.metric(
        "乗車・降車の組み合わせ数",
        f"{len(filtered):,}組"
    )

    st.subheader("移動実績の上位20組")

    display_table = filtered[
        [
            "route_id",
            "乗車地点名",
            "降車地点名",
            "移動記録件数"
        ]
    ].head(20).rename(
        columns={
            "route_id": "路線ID",
            "乗車地点名": "乗車地点",
            "降車地点名": "降車地点"
        }
    )

    st.dataframe(
        display_table.reset_index(drop=True),
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "移動記録件数は、路線・乗車地点・降車地点の組み合わせごとに集計しています。"
    )

    # 地図は、選択した路線の移動だけを表示する
    st.subheader("停留所と移動実績の地図")

    if selected_route == "all":
        map_od_table = od_table
    else:
        map_od_table = od_table[
            od_table["route_id_text"] == selected_route
        ]

    try:
        with st.spinner("地図を作成しています..."):
            m = create_map(map_stops, map_od_table)

        components.html(
            m.get_root().render(),
            height=650,
            scrolling=True
        )

    except Exception as e:
        st.error(f"地図の作成中にエラーが発生しました：{e}")

    st.caption(
        "停留所の色は路線グループを示します。"
        "紫色の線は乗車地点から降車地点への移動記録です。"
        "線の太さは移動記録件数に応じて変わります。"
    )
else:
    st.info(
        "「データを読み込んで分析する」を押すと、"
        "集計表と地図が表示されます。"
    )
