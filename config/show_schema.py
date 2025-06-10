from decouple import config
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text


def get_llm_friendly_metadata():
    # Load DB credentials
    db_user = quote_plus(config("DB_USER"))
    db_password = quote_plus(config("DB_PASSWORD"))
    db_host = config("DB_HOST", default="localhost")
    db_port = config("DB_PORT", default="3306")
    db_name = config("DB_NAME")

    # SQLAlchemy connection string
    connection_string = (
        f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )
    engine = create_engine(connection_string)

    with engine.connect() as conn:
        # Load table list
        tables = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = :db AND table_type = 'BASE TABLE' "
                "ORDER BY table_name;"
            ),
            {"db": db_name},
        ).fetchall()
        tables = [row[0] for row in tables]

        # Load column info
        column_info = {}
        for table in tables:
            result = conn.execute(
                text(
                    """
                    SELECT column_name, column_type, is_nullable, column_comment
                    FROM information_schema.columns
                    WHERE table_schema = :db AND table_name = :table
                    ORDER BY ordinal_position;
                    """
                ),
                {"db": db_name, "table": table},
            ).fetchall()
            column_info[table] = result

        # Load foreign keys
        fk_map = {}
        fks = conn.execute(
            text(
                """
                SELECT table_name, column_name, referenced_table_name, referenced_column_name
                FROM information_schema.key_column_usage
                WHERE table_schema = :db AND referenced_table_name IS NOT NULL
                ORDER BY table_name, column_name;
                """
            ),
            {"db": db_name},
        ).fetchall()

        for table_name, column_name, ref_table, ref_column in fks:
            fk_map.setdefault(table_name, {})[column_name] = (ref_table, ref_column)

        # Write output
        output_file = "rich_metadata.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"Database Schema: {db_name}\n")
            f.write("=" * 80 + "\n\n")

            for table in tables:
                f.write(f"Table: {table}\n")
                f.write("-" * (7 + len(table)) + "\n")

                columns = column_info[table]
                for name, col_type, nullable, comment in columns:
                    description = f"{name}: "

                    if comment:
                        description += comment
                    else:
                        # Fallback description
                        description += f"A field of type {col_type}"
                        if nullable == "YES":
                            description += " (optional)."
                        else:
                            description += " (required)."

                    if table in fk_map and name in fk_map[table]:
                        ref_table, ref_col = fk_map[table][name]
                        description += f" Refers to {ref_table}.{ref_col}."

                    f.write(f"- {description}\n")

                f.write("\n")

        print(f"✅ LLM-ready schema written to {output_file}")


if __name__ == "__main__":
    get_llm_friendly_metadata()
