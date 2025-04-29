import ast
import os

from typing import Dict, List, Tuple


def add_models_subcommand(subparsers):
    annotate_parser = subparsers.add_parser(
        "annotate-models", help="Annotate Django models with reverse relations."
    )
    annotate_parser.add_argument("path", help="Path to the root of the Django project")


def get_model_classes_from_ast(tree: ast.AST) -> Dict[str, ast.ClassDef]:
    model_classes = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            declares_django_fields = any(
                isinstance(stmt, ast.Assign)
                and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, (ast.Attribute, ast.Subscript))
                for stmt in node.body
            )
            if declares_django_fields:
                model_classes[node.name] = node
    return model_classes


def extract_reverse_relations(tree: ast.AST) -> List[Tuple[str, str, str]]:
    """Returns list of (target_model, related_name, source_model)"""
    relations = []

    for class_node in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        current_model = class_node.name

        for stmt in class_node.body:
            if not isinstance(stmt, ast.Assign) or not isinstance(stmt.value, ast.Call):
                continue

            call = stmt.value
            func = call.func
            field_type = None

            if isinstance(func, ast.Attribute):
                if isinstance(func.value, ast.Name) and func.value.id == "models":
                    field_type = func.attr
            elif isinstance(func, ast.Subscript):
                sub_func = func.value
                if isinstance(sub_func, ast.Attribute):
                    if (
                        isinstance(sub_func.value, ast.Name)
                        and sub_func.value.id == "models"
                    ):
                        field_type = sub_func.attr

            if field_type not in {"ForeignKey", "OneToOneField", "ManyToManyField"}:
                continue

            to_model = None
            if call.args:
                first_arg = call.args[0]
                if isinstance(first_arg, ast.Name):
                    to_model = first_arg.id
                elif isinstance(first_arg, ast.Str):
                    to_model = first_arg.s.split(".")[-1]
                elif isinstance(first_arg, ast.Attribute):
                    to_model = first_arg.attr

            for kw in call.keywords:
                if kw.arg == "to":
                    if isinstance(kw.value, ast.Name):
                        to_model = kw.value.id
                    elif isinstance(kw.value, ast.Str):
                        to_model = kw.value.s.split(".")[-1]
                    elif isinstance(kw.value, ast.Attribute):
                        to_model = kw.value.attr

            related_name = None
            for kw in call.keywords:
                if kw.arg == "related_name":
                    if isinstance(kw.value, ast.Str) and kw.value.s != "+":
                        related_name = kw.value.s

            if not to_model and isinstance(func, ast.Subscript):
                slice_node = getattr(func.slice, "value", func.slice)
                if isinstance(slice_node, ast.Str):
                    to_model = slice_node.s
                elif isinstance(slice_node, ast.Name):
                    to_model = slice_node.id

            if to_model and related_name:
                relations.append((to_model, related_name, current_model))

    return relations


def create_annotation(name: str, model: str) -> str:
    return f"    {name}: models.Manager['{model}']"


def annotate_model_source(
    source: str, annotations: Dict[str, List[Tuple[str, str]]]
) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    inserts = {}

    for class_node in tree.body:
        if isinstance(class_node, ast.ClassDef) and class_node.name in annotations:
            insert_line = class_node.lineno

            while insert_line < len(lines) and not lines[
                insert_line - 1
            ].strip().endswith(":"):
                insert_line += 1

            if (
                class_node.body
                and isinstance(class_node.body[0], ast.Expr)
                and isinstance(class_node.body[0].value, ast.Str)
            ):
                docstring_node = class_node.body[0]
                insert_line = (
                    docstring_node.lineno + docstring_node.value.s.count("\n") + 1
                )

            insert_lines = [
                create_annotation(name, model)
                for name, model in annotations[class_node.name]
            ]
            inserts.setdefault(insert_line, []).extend(insert_lines)
            inserts.setdefault(insert_line, []).append("")

    output = []
    for i, line in enumerate(lines, 1):
        output.append(line)
        if i in inserts:
            output.extend(inserts[i])

    return "\n".join(output)


def find_model_files(root: str):
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f == "models.py":
                yield os.path.join(dirpath, f)


def process_models_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    reverse_relations = extract_reverse_relations(tree)

    annotations = {}
    for to_model, related_name, from_model in reverse_relations:
        annotations.setdefault(to_model, []).append((related_name, from_model))

    if not annotations:
        print(f"— No changes in {path}")
        return

    updated = annotate_model_source(source, annotations)
    with open(path, "w", encoding="utf-8") as f:
        f.write(updated)
    print(f"✅ Updated {path}")
