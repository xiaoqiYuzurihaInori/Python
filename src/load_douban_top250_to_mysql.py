import argparse
import os
import re
from pathlib import Path

import pandas as pd
import pymysql


DEFAULT_CSV_PATH = Path("output/douban_top250_movies_list.csv")
DEFAULT_SQL_PATH = Path("sql/create_douban_top250_movies.sql")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将豆瓣 Top250 列表采集结果导入 MySQL")
    parser.add_argument("--csv", default=str(DEFAULT_CSV_PATH), help="待导入的 CSV 文件路径")
    parser.add_argument("--sql", default=str(DEFAULT_SQL_PATH), help="建表 SQL 文件路径")
    parser.add_argument("--host", default=os.getenv("MYSQL_HOST", "127.0.0.1"), help="MySQL 主机")
    parser.add_argument("--port", type=int, default=int(os.getenv("MYSQL_PORT", "3306")), help="MySQL 端口")
    parser.add_argument("--user", default=os.getenv("MYSQL_USER", "root"), help="MySQL 用户名")
    parser.add_argument("--password", default=os.getenv("MYSQL_PASSWORD", ""), help="MySQL 密码")
    parser.add_argument("--database", default=os.getenv("MYSQL_DATABASE", "movie_analysis"), help="MySQL 数据库名")
    parser.add_argument("--table", default=os.getenv("MYSQL_TABLE", "douban_top250_movies"), help="目标表名")
    parser.add_argument("--truncate", action="store_true", help="导入前清空目标表")
    parser.add_argument("--skip-init-schema", action="store_true", help="跳过执行建表 SQL")
    return parser.parse_args()


def load_csv(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"找不到 CSV 文件: {csv_path.resolve()}")

    df = pd.read_csv(csv_path)

    expected_columns = [
        "rank",
        "title_cn",
        "title_other",
        "rating",
        "rating_count",
        "quote",
        "detail_url",
        "poster_url",
        "crawl_time",
    ]

    missing_columns = [column for column in expected_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"CSV 缺少必要字段: {missing_columns}")

    cleaned = df[expected_columns].copy()
    cleaned = cleaned.rename(
        columns={
            "rank": "movie_rank",
            "quote": "quote_text",
        }
    )

    cleaned["movie_rank"] = pd.to_numeric(cleaned["movie_rank"], errors="coerce").astype("Int64")
    cleaned["rating"] = pd.to_numeric(cleaned["rating"], errors="coerce")
    cleaned["rating_count"] = pd.to_numeric(cleaned["rating_count"], errors="coerce").astype("Int64")
    cleaned["crawl_time"] = pd.to_datetime(cleaned["crawl_time"], errors="coerce")

    cleaned = cleaned.dropna(subset=["movie_rank", "title_cn"])
    cleaned = cleaned.drop_duplicates(subset=["detail_url"], keep="last")
    cleaned = cleaned.sort_values(by="movie_rank").reset_index(drop=True)

    return cleaned


def create_connection(args: argparse.Namespace) -> pymysql.connections.Connection:
    return pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        charset="utf8mb4",
        autocommit=False,
    )


def create_server_connection(args: argparse.Namespace) -> pymysql.connections.Connection:
    return pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        charset="utf8mb4",
        autocommit=False,
    )


def validate_identifier(name: str, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError(f"{label} 只能包含字母、数字和下划线: {name}")
    return name


def ensure_database_exists(args: argparse.Namespace) -> None:
    database_name = validate_identifier(args.database, "数据库名")
    connection = create_server_connection(args)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        connection.commit()
    finally:
        connection.close()


def initialize_schema(connection: pymysql.connections.Connection, sql_path: Path) -> None:
    if not sql_path.exists():
        raise FileNotFoundError(f"找不到建表 SQL 文件: {sql_path.resolve()}")

    sql_text = sql_path.read_text(encoding="utf-8")
    with connection.cursor() as cursor:
        for statement in [chunk.strip() for chunk in sql_text.split(";") if chunk.strip()]:
            cursor.execute(statement)


def truncate_table(connection: pymysql.connections.Connection, table_name: str) -> None:
    table_name = validate_identifier(table_name, "表名")
    with connection.cursor() as cursor:
        cursor.execute(f"TRUNCATE TABLE `{table_name}`")


def insert_movies(connection: pymysql.connections.Connection, table_name: str, df: pd.DataFrame) -> int:
    table_name = validate_identifier(table_name, "表名")
    insert_sql = f"""
        INSERT INTO `{table_name}` (
            movie_rank,
            title_cn,
            title_other,
            rating,
            rating_count,
            quote_text,
            detail_url,
            poster_url,
            crawl_time
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON DUPLICATE KEY UPDATE
            movie_rank = VALUES(movie_rank),
            title_cn = VALUES(title_cn),
            title_other = VALUES(title_other),
            rating = VALUES(rating),
            rating_count = VALUES(rating_count),
            quote_text = VALUES(quote_text),
            poster_url = VALUES(poster_url),
            crawl_time = VALUES(crawl_time)
    """

    rows = []
    for row in df.itertuples(index=False):
        rows.append(
            (
                int(row.movie_rank) if pd.notna(row.movie_rank) else None,
                row.title_cn,
                value_or_none(row.title_other),
                float(row.rating) if pd.notna(row.rating) else None,
                int(row.rating_count) if pd.notna(row.rating_count) else None,
                value_or_none(row.quote_text),
                value_or_none(row.detail_url),
                value_or_none(row.poster_url),
                row.crawl_time.to_pydatetime() if pd.notna(row.crawl_time) else None,
            )
        )

    with connection.cursor() as cursor:
        cursor.executemany(insert_sql, rows)
    return len(rows)


def value_or_none(value):
    if pd.isna(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    sql_path = Path(args.sql)

    df = load_csv(csv_path)
    print(f"准备导入 {len(df)} 条记录")

    ensure_database_exists(args)
    print(f"已确认数据库存在: {args.database}")

    connection = create_connection(args)
    try:
        if not args.skip_init_schema:
            initialize_schema(connection, sql_path)
            print(f"已执行建表 SQL: {sql_path.resolve()}")

        if args.truncate:
            truncate_table(connection, args.table)
            print(f"已清空目标表: {args.table}")

        inserted = insert_movies(connection, args.table, df)
        connection.commit()
        print(f"导入完成，共写入 {inserted} 条记录到 {args.database}.{args.table}")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
