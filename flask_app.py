import math
import os
from pathlib import Path

import pandas as pd
import pymysql
from flask import Flask, jsonify, render_template, request


ROOT_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = ROOT_DIR / "output" / "analysis"
CSV_FALLBACK = ROOT_DIR / "output" / "douban_top250_movies_list.csv"
ANALYSIS_FALLBACK = ANALYSIS_DIR / "douban_top250_analysis.csv"

app = Flask(__name__, template_folder=str(ROOT_DIR / "templates"), static_folder=str(ROOT_DIR / "static"))


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
    df["quote_text"] = df["quote_text"].fillna("")
    df["title_other"] = df["title_other"].fillna("")
    df["rating_bin"] = pd.cut(
        df["rating"],
        bins=[8.0, 8.5, 9.0, 9.5, 10.0],
        labels=["8.0-8.5", "8.5-9.0", "9.0-9.5", "9.5-10.0"],
        include_lowest=True,
        right=False,
    )
    df["score_index"] = df["rating"] * df["rating_count"].clip(lower=1).map(lambda x: math.log10(x))
    return df.sort_values("movie_rank").reset_index(drop=True)


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

    return normalize_movies(df), source


def filter_movies(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    rank_min = int(params.get("rank_min", int(df["movie_rank"].min())))
    rank_max = int(params.get("rank_max", int(df["movie_rank"].max())))
    rating_min = float(params.get("rating_min", float(df["rating"].min())))
    rating_max = float(params.get("rating_max", float(df["rating"].max())))
    min_votes = int(params.get("min_votes", 0))
    keyword = params.get("keyword", "").strip()
    sort_by = params.get("sort_by", "movie_rank")
    sort_dir = params.get("sort_dir", "asc")

    allowed_sorts = {"movie_rank", "rating", "rating_count", "score_index"}
    if sort_by not in allowed_sorts:
        sort_by = "movie_rank"

    filtered = df[
        (df["movie_rank"].between(rank_min, rank_max))
        & (df["rating"].between(rating_min, rating_max))
        & (df["rating_count"] >= min_votes)
    ].copy()

    if keyword:
        filtered = filtered[filtered["title_cn"].str.contains(keyword, case=False, na=False)]

    ascending = sort_dir != "desc"
    filtered = filtered.sort_values(sort_by, ascending=ascending).reset_index(drop=True)
    return filtered


def format_votes(value: float) -> str:
    if pd.isna(value):
        return "-"
    if value >= 10000:
        return f"{value / 10000:.1f} 万"
    return f"{int(value):,}"


def json_safe(value):
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def build_payload(df: pd.DataFrame, source: str) -> dict:
    top_movie = df.sort_values(["rating", "rating_count"], ascending=[False, False]).iloc[0]
    popular_movie = df.sort_values("rating_count", ascending=False).iloc[0]
    top_rating = df.sort_values(["rating", "rating_count"], ascending=[False, False]).head(10)
    top_popular = df.sort_values("rating_count", ascending=False).head(10)
    top_score = df.sort_values("score_index", ascending=False).head(10)
    rating_bin_counts = df["rating_bin"].astype(str).replace("nan", "未分类").value_counts().sort_index()
    latest_crawl = df["crawl_time"].max()

    rows = []
    for row in df.head(120).itertuples(index=False):
        rows.append(
            {
                "movie_rank": int(row.movie_rank),
                "title_cn": row.title_cn,
                "title_other": json_safe(row.title_other) or "",
                "rating": float(row.rating),
                "rating_count": int(row.rating_count),
                "rating_count_text": format_votes(row.rating_count),
                "quote_text": json_safe(row.quote_text) or "",
                "detail_url": json_safe(row.detail_url) or "",
                "crawl_time": json_safe(row.crawl_time) or "",
            }
        )

    return {
        "source": source,
        "summary": {
            "count": int(len(df)),
            "avg_rating": round(float(df["rating"].mean()), 3),
            "avg_votes": format_votes(df["rating_count"].mean()),
            "max_rating_movie": json_safe(top_movie["title_cn"]) or "",
            "latest_crawl": latest_crawl.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(latest_crawl) else "未知",
            "top_movie": {
                "title_cn": json_safe(top_movie["title_cn"]) or "",
                "rating": float(top_movie["rating"]),
                "rating_count": format_votes(top_movie["rating_count"]),
                "quote_text": (json_safe(top_movie["quote_text"]) or "暂无短评摘录"),
            },
            "popular_movie": {
                "title_cn": json_safe(popular_movie["title_cn"]) or "",
                "rating": float(popular_movie["rating"]),
                "rating_count": format_votes(popular_movie["rating_count"]),
                "quote_text": (json_safe(popular_movie["quote_text"]) or "暂无短评摘录"),
            },
        },
        "charts": {
            "rating_hist": {
                "x": [round(float(v), 1) for v in df["rating"].tolist()],
            },
            "rating_bins": {
                "x": rating_bin_counts.index.tolist(),
                "y": [int(v) for v in rating_bin_counts.values.tolist()],
            },
            "rank_rating": [
                {
                    "name": row.title_cn,
                    "value": [int(row.movie_rank), float(row.rating), int(row.rating_count)],
                }
                for row in df.itertuples(index=False)
            ],
            "rating_popularity": [
                {
                    "name": row.title_cn,
                    "value": [float(row.rating), round(float(row.rating_count_wan), 3), int(row.rating_count), int(row.movie_rank)],
                }
                for row in df.itertuples(index=False)
            ],
            "top_popular": {
                "x": [round(float(v), 2) for v in top_popular.sort_values("rating_count")["rating_count_wan"].tolist()],
                "y": top_popular.sort_values("rating_count")["title_cn"].tolist(),
                "rating": [float(v) for v in top_popular.sort_values("rating_count")["rating"].tolist()],
            },
        },
        "rankings": {
            "top_rating": sanitize_records(
                top_rating[["movie_rank", "title_cn", "rating", "rating_count", "quote_text"]].to_dict("records")
            ),
            "top_popular": sanitize_records(
                top_popular[["movie_rank", "title_cn", "rating", "rating_count", "quote_text"]].to_dict("records")
            ),
            "top_score": sanitize_records(
                top_score[["movie_rank", "title_cn", "rating", "rating_count", "score_index", "quote_text"]]
            .round({"score_index": 3})
            .to_dict("records")
            ),
        },
        "table_rows": rows,
    }


def sanitize_records(records: list[dict]) -> list[dict]:
    return [{key: json_safe(value) for key, value in record.items()} for record in records]


@app.route("/")
def index():
    df, source = load_movies()
    payload = build_payload(df, source)
    initial_filters = {
        "rank_min": int(df["movie_rank"].min()),
        "rank_max": int(df["movie_rank"].max()),
        "rating_min": float(df["rating"].min()),
        "rating_max": float(df["rating"].max()),
        "min_votes": 0,
    }
    return render_template("dashboard.html", payload=payload, filters=initial_filters)


@app.route("/api/dashboard")
def api_dashboard():
    df, source = load_movies()
    filtered = filter_movies(df, request.args)
    if filtered.empty:
        return jsonify({"error": "当前筛选条件下没有数据"}), 404
    return jsonify(build_payload(filtered, source))


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
