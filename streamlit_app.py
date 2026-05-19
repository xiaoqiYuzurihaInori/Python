import os
import math
from pathlib import Path

import pandas as pd
import plotly.express as px
import pymysql
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = ROOT_DIR / "output" / "analysis"
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
CSV_FALLBACK = ROOT_DIR / "output" / "douban_top250_movies_list.csv"
ANALYSIS_FALLBACK = ANALYSIS_DIR / "douban_top250_analysis.csv"


def load_local_env(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def get_db_config() -> dict:
    load_local_env(ROOT_DIR / ".env")
    load_local_env(ROOT_DIR / ".env.example")
    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "movie_analysis"),
        "charset": "utf8mb4",
    }


def format_votes(value: float) -> str:
    if pd.isna(value):
        return "-"
    if value >= 10000:
        return f"{value / 10000:.1f} 万"
    return f"{int(value):,}"


@st.cache_data(ttl=300, show_spinner=False)
def load_movies() -> tuple[pd.DataFrame, str]:
    db_config = get_db_config()
    query = """
        SELECT
            movie_rank,
            title_cn,
            title_other,
            rating,
            rating_count,
            quote_text,
            detail_url,
            poster_url,
            crawl_time
        FROM douban_top250_movies
        ORDER BY movie_rank ASC
    """

    try:
        connection = pymysql.connect(**db_config)
        try:
            df = pd.read_sql(query, connection)
        finally:
            connection.close()
        source = "MySQL"
    except Exception:
        fallback_path = ANALYSIS_FALLBACK if ANALYSIS_FALLBACK.exists() else CSV_FALLBACK
        if not fallback_path.exists():
            raise FileNotFoundError("未找到 MySQL 数据，也未找到本地 CSV 回退文件。")
        df = pd.read_csv(fallback_path)
        source = f"CSV 回退: {fallback_path.name}"

    df = normalize_movies(df)
    return df, source


def normalize_movies(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "rank": "movie_rank",
        "quote": "quote_text",
    }
    df = df.rename(columns=rename_map).copy()

    expected_columns = [
        "movie_rank",
        "title_cn",
        "title_other",
        "rating",
        "rating_count",
        "quote_text",
        "detail_url",
        "poster_url",
        "crawl_time",
    ]
    for column in expected_columns:
        if column not in df.columns:
            df[column] = pd.NA

    df["movie_rank"] = pd.to_numeric(df["movie_rank"], errors="coerce")
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df["rating_count"] = pd.to_numeric(df["rating_count"], errors="coerce")
    df["crawl_time"] = pd.to_datetime(df["crawl_time"], errors="coerce")

    df = df.dropna(subset=["movie_rank", "rating", "rating_count", "title_cn"]).copy()
    df["movie_rank"] = df["movie_rank"].astype(int)
    df["rating_count"] = df["rating_count"].astype(int)
    df["rating_count_wan"] = df["rating_count"] / 10000
    df["title_display"] = df["title_cn"].fillna("")
    df["quote_text"] = df["quote_text"].fillna("")
    df["rating_bin"] = pd.cut(
        df["rating"],
        bins=[8.0, 8.5, 9.0, 9.5, 10.0],
        labels=["8.0-8.5", "8.5-9.0", "9.0-9.5", "9.5-10.0"],
        include_lowest=True,
        right=False,
    )
    df["score_index"] = df["rating"] * df["rating_count"].clip(lower=1).map(lambda x: math.log10(x))
    return df.sort_values("movie_rank").reset_index(drop=True)


def render_header(source: str, df: pd.DataFrame) -> None:
    st.markdown(
        """
        <style>
        .main {
            background:
                radial-gradient(circle at top left, rgba(239, 208, 122, 0.14), transparent 34%),
                linear-gradient(180deg, #f6f1e8 0%, #f2ede2 100%);
        }
        .block-container {
            max-width: 1260px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        .hero {
            padding: 1.4rem 1.6rem;
            border-radius: 24px;
            background: linear-gradient(135deg, #1d2d44 0%, #344e41 48%, #6b705c 100%);
            color: #fff8ea;
            box-shadow: 0 24px 60px rgba(29, 45, 68, 0.18);
        }
        .hero h1 {
            margin: 0 0 0.4rem 0;
            font-size: 2.2rem;
        }
        .hero p {
            margin: 0;
            font-size: 1rem;
            line-height: 1.6;
            opacity: 0.92;
        }
        .metric-card {
            padding: 1rem 1.1rem;
            border-radius: 20px;
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid rgba(29, 45, 68, 0.08);
            backdrop-filter: blur(10px);
        }
        .quote-card {
            padding: 1rem 1.1rem;
            border-radius: 18px;
            background: #fffaf0;
            border-left: 5px solid #d4a373;
            min-height: 120px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    latest_crawl = df["crawl_time"].max()
    latest_text = latest_crawl.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(latest_crawl) else "未知"

    st.markdown(
        f"""
        <div class="hero">
            <h1>豆瓣 Top250 电影交互式看板</h1>
            <p>从 {source} 读取数据，围绕榜单排名、豆瓣评分、评价热度和短评内容进行交互式探索。</p>
            <p>当前数据量：{len(df)} 部电影；最近采集时间：{latest_text}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metrics(df: pd.DataFrame) -> None:
    top_movie = df.sort_values(["rating", "rating_count"], ascending=[False, False]).iloc[0]
    popular_movie = df.sort_values("rating_count", ascending=False).iloc[0]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("电影数量", len(df))
    with col2:
        st.metric("平均评分", f"{df['rating'].mean():.2f}")
    with col3:
        st.metric("平均评价人数", format_votes(df["rating_count"].mean()))
    with col4:
        st.metric("最高评分电影", top_movie["title_cn"])

    quote_col, popular_col = st.columns(2)
    with quote_col:
        st.markdown(
            f"""
            <div class="quote-card">
                <strong>高分代表</strong>
                <p style="margin:0.6rem 0 0.4rem 0;font-size:1.1rem;">《{top_movie['title_cn']}》</p>
                <p style="margin:0;color:#5b4b36;">评分 {top_movie['rating']}，评价人数 {format_votes(top_movie['rating_count'])}</p>
                <p style="margin:0.7rem 0 0;color:#6b705c;">{top_movie['quote_text'] or '暂无短评摘录'}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with popular_col:
        st.markdown(
            f"""
            <div class="quote-card">
                <strong>热度代表</strong>
                <p style="margin:0.6rem 0 0.4rem 0;font-size:1.1rem;">《{popular_movie['title_cn']}》</p>
                <p style="margin:0;color:#5b4b36;">评分 {popular_movie['rating']}，评价人数 {format_votes(popular_movie['rating_count'])}</p>
                <p style="margin:0.7rem 0 0;color:#6b705c;">{popular_movie['quote_text'] or '暂无短评摘录'}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("筛选条件")
    rank_range = st.sidebar.slider(
        "排名范围",
        min_value=int(df["movie_rank"].min()),
        max_value=int(df["movie_rank"].max()),
        value=(int(df["movie_rank"].min()), int(df["movie_rank"].max())),
    )
    rating_range = st.sidebar.slider(
        "评分范围",
        min_value=float(df["rating"].min()),
        max_value=float(df["rating"].max()),
        value=(float(df["rating"].min()), float(df["rating"].max())),
        step=0.1,
    )
    min_votes = st.sidebar.number_input(
        "最低评价人数",
        min_value=0,
        max_value=int(df["rating_count"].max()),
        value=0,
        step=10000,
    )
    keyword = st.sidebar.text_input("标题关键词")
    sort_by = st.sidebar.selectbox(
        "表格排序",
        options=[
            ("movie_rank", "排名"),
            ("rating", "评分"),
            ("rating_count", "评价人数"),
            ("score_index", "综合指数"),
        ],
        format_func=lambda item: item[1],
    )
    sort_desc = st.sidebar.toggle("降序排序", value=False)

    filtered = df[
        (df["movie_rank"].between(rank_range[0], rank_range[1]))
        & (df["rating"].between(rating_range[0], rating_range[1]))
        & (df["rating_count"] >= min_votes)
    ].copy()

    if keyword.strip():
        filtered = filtered[filtered["title_cn"].str.contains(keyword.strip(), case=False, na=False)]

    filtered = filtered.sort_values(sort_by[0], ascending=not sort_desc).reset_index(drop=True)
    return filtered


def render_charts(df: pd.DataFrame) -> None:
    st.subheader("评分与热度概览")
    left, right = st.columns(2)

    with left:
        fig_rating = px.histogram(
            df,
            x="rating",
            nbins=12,
            title="评分分布",
            color_discrete_sequence=["#bc6c25"],
        )
        fig_rating.update_layout(margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig_rating, use_container_width=True)

    with right:
        rating_bins = df["rating_bin"].astype(str).replace("nan", "未分类")
        fig_bin = px.histogram(
            x=rating_bins,
            title="评分区间分布",
            color_discrete_sequence=["#606c38"],
        )
        fig_bin.update_layout(
            xaxis_title="评分区间",
            yaxis_title="电影数量",
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig_bin, use_container_width=True)

    lower, upper = st.columns(2)

    with lower:
        fig_rank = px.scatter(
            df,
            x="movie_rank",
            y="rating",
            size="rating_count",
            hover_data=["title_cn", "rating_count"],
            title="排名与评分关系",
            color="rating",
            color_continuous_scale="YlGnBu",
        )
        fig_rank.update_layout(margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig_rank, use_container_width=True)

    with upper:
        fig_popularity = px.scatter(
            df,
            x="rating",
            y="rating_count_wan",
            size="rating_count",
            hover_data=["title_cn", "movie_rank"],
            title="评分与热度关系",
            color="movie_rank",
            color_continuous_scale="Sunset",
        )
        fig_popularity.update_layout(
            xaxis_title="评分",
            yaxis_title="评价人数（万）",
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig_popularity, use_container_width=True)


def render_rankings(df: pd.DataFrame) -> None:
    st.subheader("榜单视图")
    tab1, tab2, tab3 = st.tabs(["评分 Top10", "热度 Top10", "综合指数 Top10"])

    with tab1:
        top_rating = df.sort_values(["rating", "rating_count"], ascending=[False, False]).head(10)
        st.dataframe(
            top_rating[["movie_rank", "title_cn", "rating", "rating_count", "quote_text"]],
            use_container_width=True,
            hide_index=True,
        )

    with tab2:
        top_popular = df.sort_values("rating_count", ascending=False).head(10)
        fig_top_popular = px.bar(
            top_popular.sort_values("rating_count"),
            x="rating_count_wan",
            y="title_cn",
            orientation="h",
            title="评价人数 Top10",
            color="rating",
            color_continuous_scale="Tealgrn",
        )
        fig_top_popular.update_layout(
            xaxis_title="评价人数（万）",
            yaxis_title="电影",
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig_top_popular, use_container_width=True)

    with tab3:
        top_index = df.sort_values("score_index", ascending=False).head(10).copy()
        top_index["score_index"] = top_index["score_index"].round(3)
        st.dataframe(
            top_index[["movie_rank", "title_cn", "rating", "rating_count", "score_index", "quote_text"]],
            use_container_width=True,
            hide_index=True,
        )


def render_table(df: pd.DataFrame) -> None:
    st.subheader("明细表")
    display_df = df[
        ["movie_rank", "title_cn", "title_other", "rating", "rating_count", "quote_text", "detail_url", "crawl_time"]
    ].copy()
    display_df["rating_count"] = display_df["rating_count"].map(format_votes)
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="豆瓣 Top250 可视化看板", page_icon="🎬", layout="wide")

    df_movies, source = load_movies()
    if df_movies.empty:
        st.error("当前没有可展示的数据，请先执行采集与入库流程。")
        return

    render_header(source, df_movies)
    filtered_df = render_sidebar(df_movies)

    if filtered_df.empty:
        st.warning("当前筛选条件下没有结果，请调整侧边栏筛选条件。")
        return

    render_metrics(filtered_df)
    render_charts(filtered_df)
    render_rankings(filtered_df)
    render_table(filtered_df)


if __name__ == "__main__":
    main()
