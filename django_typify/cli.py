import os
import ast
from .core import extract_reverse_relations, annotate_model_source


def find_model_files(root: str):
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f == "models.py":
                yield os.path.join(dirpath, f)


def find_factory_files(root: str):
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f.endswith("_factory.py") or f.endswith("_factories.py"):
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


def process_factory_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    lines = source.splitlines()
    updated_lines = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            base_classes = [base.id for base in node.bases if isinstance(base, ast.Name)]
            if "DjangoModelFactory" in base_classes:
                for stmt in node.body:
                    if isinstance(stmt, ast.ClassDef) and stmt.name == "Meta":
                        for meta_stmt in stmt.body:
                            if (
                                isinstance(meta_stmt, ast.Assign)
                                and len(meta_stmt.targets) == 1
                                and isinstance(meta_stmt.targets[0], ast.Name)
                                and meta_stmt.targets[0].id == "model"
                            ):
                                model_name = meta_stmt.value.attr
                                updated_lines.append(
                                    f"class {node.name}(factory.django.DjangoModelFactory, metaclass=BaseMetaFactory[models.{model_name}]):"
                                )
                                break
                        else:
                            updated_lines.append(lines[node.lineno - 1])
                    else:
                        updated_lines.append(lines[node.lineno - 1])
            else:
                updated_lines.append(lines[node.lineno - 1])
        else:
            updated_lines.append(lines[node.lineno - 1])

    updated_source = "\n".join(updated_lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(updated_source)
    print(f"✅ Updated {path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Annotate Django model reverse relations."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    annotate_parser = subparsers.add_parser(
        "annotate-models", help="Annotate Django models with reverse relations."
    )
    annotate_parser.add_argument("path", help="Path to the root of the Django project")

    annotate_factories_parser = subparsers.add_parser(
        "annotate-factories", help="Annotate Django test factories with type annotations."
    )
    annotate_factories_parser.add_argument(
        "path", help="Path to the root of the Django project"
    )

    args = parser.parse_args()

    if args.command == "annotate-models":
        for file_path in find_model_files(args.path):
            process_models_file(file_path)
    elif args.command == "annotate-factories":
        for file_path in find_factory_files(args.path):
            process_factory_file(file_path)


if __name__ == "__main__":
    main()
