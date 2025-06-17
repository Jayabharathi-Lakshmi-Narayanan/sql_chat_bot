from decouple import config
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
import os
from collections import defaultdict


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
        # Load table names
        tables = conn.execute(
            text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = :db AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """),
            {"db": db_name},
        ).fetchall()
        tables = [row[0] for row in tables]

        column_info = {}
        pk_map = {}
        fk_map = defaultdict(dict)
        ref_by = defaultdict(list)

        for table in tables:
            # Get column details
            columns = conn.execute(
                text("""
                    SELECT column_name, column_type, is_nullable, column_comment
                    FROM information_schema.columns
                    WHERE table_schema = :db AND table_name = :table
                    ORDER BY ordinal_position;
                """),
                {"db": db_name, "table": table},
            ).fetchall()
            column_info[table] = columns

            # Get primary keys
            pks = conn.execute(
                text("""
                    SELECT column_name
                    FROM information_schema.key_column_usage
                    WHERE table_schema = :db AND table_name = :table AND constraint_name = 'PRIMARY';
                """),
                {"db": db_name, "table": table},
            ).fetchall()
            pk_map[table] = {row[0] for row in pks}

        # Get foreign keys
        fks = conn.execute(
            text("""
                SELECT table_name, column_name, referenced_table_name, referenced_column_name
                FROM information_schema.key_column_usage
                WHERE table_schema = :db AND referenced_table_name IS NOT NULL
                ORDER BY table_name, column_name;
            """),
            {"db": db_name},
        ).fetchall()

        for table_name, column_name, ref_table, ref_column in fks:
            fk_map[table_name][column_name] = (ref_table, ref_column)
            ref_by[ref_table].append((table_name, column_name))

        output_path = os.path.join(os.path.dirname(__file__), "rich_metadata.txt")

        # Write metadata
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"Database Schema: {db_name}\n")
            f.write("=" * 80 + "\n\n")

            for table in tables:
                f.write(f"Table: {table}\n")
                f.write("-" * (7 + len(table)) + "\n")

                for name, col_type, nullable, comment in column_info[table]:
                    description = f"{name}: "

                    if comment:
                        description += comment
                    else:
                        description += f"A field of type {col_type}"
                        description += (
                            " (optional)." if nullable == "YES" else " (required)."
                        )

                    if name in pk_map[table]:
                        description += " Primary Key."

                    if name in fk_map[table]:
                        ref_table, ref_col = fk_map[table][name]
                        description += f" Foreign Key → {ref_table}.{ref_col}."

                    f.write(f"- {description}\n")

                f.write("\n")

            # Relationship summary
            f.write("\nTable Relationship Summary\n")
            f.write("=" * 80 + "\n")
            for table in tables:
                if table in ref_by:
                    references = ", ".join(
                        [f"{tbl}.{col}" for tbl, col in ref_by[table]]
                    )
                    f.write(f"- {table} is referenced by: {references}\n")

        print(f"✅ LLM-ready schema written to {output_path}")


if __name__ == "__main__":
    get_llm_friendly_metadata()
