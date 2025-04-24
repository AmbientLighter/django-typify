import ast
from typing import Dict, List, Tuple

from .core import extract_reverse_relations


def generate_stub_lines(annotations: Dict[str, List[Tuple[str, str]]]) -> List[str]:
    lines = ["from django.db import models", ""]

    for model_name, rels in annotations.items():
        lines.append(f"class {model_name}:")
        for related_name, source_model in rels:
            lines.append(f"    {related_name}: models.Manager['{source_model}']")
        lines.append("")  # Spacer between classes

    return lines


def generate_stub_file(py_path: str, stub_path: str):
    with open(py_path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    reverse_relations = extract_reverse_relations(tree)

    annotations: Dict[str, List[Tuple[str, str]]] = {}
    for to_model, related_name, from_model in reverse_relations:
        annotations.setdefault(to_model, []).append((related_name, from_model))

    if not annotations:
        print(f"— No reverse relations found in {py_path}")
        return

    stub_lines = generate_stub_lines(annotations)
    with open(stub_path, "w", encoding="utf-8") as f:
        f.write("\n".join(stub_lines))

    print(f"📄 Stub written to {stub_path}")
