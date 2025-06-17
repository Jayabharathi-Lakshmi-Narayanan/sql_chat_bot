# D:\jb\chat_with_mysql\rag_utils\schema_chunker.py

import re


def chunk_schema(schema_text: str) -> list[dict]:
    chunks = []
    table_names = []

    matches = re.findall(r"Table: (\w+)\n(.*?)\n(?=Table:|\Z)", schema_text, re.DOTALL)
    for table_name, block in matches:
        table_names.append(table_name)
        column_lines = block.strip().splitlines()
        formatted_columns = "\n".join([f"- {line.strip()}" for line in column_lines])
        content = f"Table: {table_name}\nColumns:\n{formatted_columns}"

        chunks.append({"table": table_name, "content": content})

    # Save table list to file for reference/debugging
    with open("table_list.txt", "w") as f:
        f.write(", ".join(table_names))

    return chunks
