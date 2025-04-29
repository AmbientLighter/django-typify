import ast
import os

def add_factories_subcommand(subparsers):
    annotate_factories_parser = subparsers.add_parser(
        "annotate-factories",
        help="Annotate Django test factories with type annotations.",
    )
    annotate_factories_parser.add_argument(
        "path", help="Path to the root of the Django project"
    )

def find_factory_files(root: str):
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f.endswith("factories.py"):
                yield os.path.join(dirpath, f)


def process_factory_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    lines = source.splitlines()
    updated_lines = lines[:]
    needs_import = False

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        
        # Check if it's a factory class by looking at the text
        class_text = "\n".join(lines[node.lineno-1:node.end_lineno])
        if "DjangoModelFactory" not in class_text:
            continue

        # Skip if metaclass is already defined
        if any(k.arg == 'metaclass' for k in node.keywords):
            continue

        # Look for Meta class and model assignment
        for stmt in node.body:
            if isinstance(stmt, ast.ClassDef) and stmt.name == "Meta":
                for meta_stmt in stmt.body:
                    if (
                        isinstance(meta_stmt, ast.Assign)
                        and len(meta_stmt.targets) == 1
                        and isinstance(meta_stmt.targets[0], ast.Name)
                        and meta_stmt.targets[0].id == "model"
                    ):
                        # Get the full model path as text from the original source
                        model_line = lines[meta_stmt.lineno - 1]
                        model_value = model_line.split("=")[1].strip()
                        
                        # Update the factory class definition line
                        class_def_line = node.lineno - 1
                        updated_lines[class_def_line] = (
                            f"class {node.name}(factory.django.DjangoModelFactory, "
                            f"metaclass=BaseMetaFactory[{model_value}]):"
                        )
                        needs_import = True
                        break
                break

    # Add import if changes were made
    if needs_import:
        updated_lines.insert(0, "from waldur_core.core.tests.types import BaseMetaFactory")

    # Check if any changes were made
    if updated_lines != lines:
        updated_source = "\n".join(updated_lines)
        with open(path, "w", encoding="utf-8") as f:
            f.write(updated_source)
        print(f"✅ Updated {path}")
    else:
        print(f"— No changes in {path}")
