# D:\jb\chat_with_mysql\rag_utils\schema_chunker.py

import re


def chunk_schema(schema_text: str) -> list[dict]:
    chunks = []
    table_names = []

    # Match each table section
    matches = re.findall(r"Table: (\w+)\n(.*?)\n(?=Table:|\Z)", schema_text, re.DOTALL)
    for table_name, block in matches:
        table_names.append(table_name)

        column_lines = block.strip().splitlines()
        formatted_columns = "\n".join(
            [
                f"{line.strip()}"
                for line in column_lines
                if line.strip() and not line.startswith("Table:")
            ]
        )

        # Capture relationship summary if available
        rel_matches = re.search(rf"- {table_name} is referenced by: (.*)", schema_text)
        relationship_info = (
            f"\nRelationship: {rel_matches.group(0)}" if rel_matches else ""
        )

        content = f"Table: {table_name}\n{formatted_columns}{relationship_info}"

        chunks.append({"table": table_name, "content": content})

    # Save table list (optional for debugging)
    with open("table_list.txt", "w") as f:
        f.write(", ".join(table_names))

    return chunks
