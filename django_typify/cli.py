import os
import ast
from .core import extract_reverse_relations, annotate_model_source
from .stubgen import generate_stub_file


def find_model_files(root: str):
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f == "models.py":
                yield os.path.join(dirpath, f)


def process_file(path: str, stub_only: bool = False):
    if stub_only:
        stub_path = path.replace(".py", ".pyi")
        generate_stub_file(path, stub_path)
    else:
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


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Annotate Django model reverse relations."
    )
    parser.add_argument("path", help="Path to the root of the Django project")
    parser.add_argument(
        "--stub-only",
        action="store_true",
        help="Generate .pyi stub files instead of modifying code",
    )

    args = parser.parse_args()

    for file_path in find_model_files(args.path):
        process_file(file_path, stub_only=args.stub_only)


if __name__ == "__main__":
    main()
