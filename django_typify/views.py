import ast
import os

from ast import get_source_segment


def add_views_subcommand(subparsers):
    annotate_views_parser = subparsers.add_parser(
        "annotate-views",
        help="Annotate Django views with type annotations.",
    )
    annotate_views_parser.add_argument(
        "path", help="Path to the root of the Django project"
    )
    # Optional: Add flag to control overwrite behavior or output diff
    # annotate_views_parser.add_argument(
    #     "--dry-run", action="store_true", help="Print changes instead of modifying files."
    # )


def find_view_files(root: str):
    """Recursively finds all 'views.py' files within the root directory."""
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f == "views.py":
                yield os.path.join(dirpath, f)


def _extract_model_from_queryset(node_value: ast.expr) -> tuple[str | None, str | None]:
    """
    Attempts to extract the base model name from a queryset assignment value node.
    Handles patterns like Model.objects.all(), module.Model.objects.filter(), etc.

    Returns:
        A tuple (simple_model_name, full_model_path) or (None, None) if not found.
        e.g., ('Node', 'models.Node') or ('ProjectUpdateRequest', 'ProjectUpdateRequest')
    """
    # Handle different patterns of queryset expressions
    # First try to find .objects
    current = node_value

    # Print debug info for complex queries
    # print(f"Analyzing node_value type: {type(node_value)}")

    # Handle call chains like .objects.all().order_by('name')
    while isinstance(current, ast.Call):
        current = current.func

    # Now look for the .objects attribute
    while isinstance(current, ast.Attribute):
        if current.attr == "objects":
            # Found .objects - now get the model part
            model_node = current.value

            if isinstance(model_node, ast.Name):
                # Direct model reference (Model.objects)
                model_name = model_node.id
                return model_name, model_name

            elif isinstance(model_node, ast.Attribute):
                # Module.Model reference (models.Model.objects)
                if isinstance(model_node.value, ast.Name):
                    # Simple module.Model pattern
                    module_name = model_node.value.id
                    model_name = model_node.attr
                    return model_name, f"{module_name}.{model_name}"
                else:
                    # Complex module path - try to reconstruct
                    # This could be app.models.Model.objects
                    model_name = model_node.attr
                    # Try to build full path
                    path_parts = []
                    current_node = model_node.value
                    path_parts.append(model_name)

                    while isinstance(current_node, ast.Attribute):
                        path_parts.append(current_node.attr)
                        current_node = current_node.value

                    if isinstance(current_node, ast.Name):
                        path_parts.append(current_node.id)

                    # Reverse to get proper order
                    path_parts.reverse()
                    full_path = ".".join(path_parts)

                    # For complex paths, typically return the closest module + model
                    # For example, for app.models.Model, return models.Model
                    if len(path_parts) >= 2:
                        simple_path = f"{path_parts[-2]}.{path_parts[-1]}"
                        return path_parts[-1], simple_path

                    return model_name, full_path

        # Continue traversing up the attribute chain
        current = current.value
        if not isinstance(current, (ast.Attribute, ast.Name)):
            break

    # Special case: If we got here and found no .objects,
    # try one more approach for direct queryset references like ClassName.objects.all().order_by()
    # Start over with the original node_value
    current = node_value

    # For complex call chains, try to extract from the outermost call's func
    if isinstance(current, ast.Call):
        chain = []
        while isinstance(current, ast.Call):
            if not isinstance(current.func, ast.Attribute):
                break
            chain.append(current.func.attr)
            current = current.func.value

        # If we found a chain that looks like xxx().order_by().all() etc.
        # current should now point to the model part
        if chain and isinstance(current, ast.Attribute) and current.attr == "objects":
            model_node = current.value
            if isinstance(model_node, ast.Name):
                # Direct model reference (Model.objects)
                model_name = model_node.id
                return model_name, model_name
            elif isinstance(model_node, ast.Attribute):
                # Module.Model reference
                model_name = model_node.attr
                if isinstance(model_node.value, ast.Name):
                    module_name = model_node.value.id
                    return model_name, f"{module_name}.{model_name}"

    return None, None


def process_one_file(source: str):
    tree = ast.parse(source)
    lines = source.splitlines()
    updated_lines = lines[:]
    modified = False

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Find queryset attribute to determine model type
        queryset_model = None
        full_model_path = None
        for item in node.body:
            # Look for direct assignment: queryset = ...
            if isinstance(item, ast.Assign):
                # Check if 'queryset' is one of the targets
                is_queryset_assign = False
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "queryset":
                        is_queryset_assign = True
                        break

                if is_queryset_assign:
                    queryset_model, full_model_path = _extract_model_from_queryset(
                        item.value
                    )
                    # Debug info
                    # print(f"Found queryset in {node.name}, model: {queryset_model}, path: {full_model_path}")
                    if full_model_path:
                        # Found it, no need to look further in this class body
                        break
            # TODO: Could potentially look for get_queryset(self) method definition
            #       and try to parse its return statement for more complex cases.

        # If we couldn't determine the model from queryset, skip annotating methods in this class
        if not full_model_path:
            # print(f"Skipping class {node.name} - couldn't determine model")
            continue

        # Process methods to find get_object calls and serializer.save() calls
        for method in node.body:
            if not isinstance(method, ast.FunctionDef):
                continue

            # Use ast.walk to find assignments anywhere within the method,
            # including nested blocks (if, for, etc.)
            for stmt in ast.walk(method):
                if not isinstance(stmt, ast.Assign):
                    continue

                # We only handle single targets for simplicity, e.g., var = ...
                # Cases like a = b = self.get_object() are not explicitly handled differently.
                if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                    continue

                target = stmt.targets[0]
                target_name = target.id
                value_node = stmt.value

                # Check line number validity
                if (
                    not hasattr(stmt, "lineno")
                    or stmt.lineno <= 0
                    or stmt.lineno > len(updated_lines)
                ):
                    continue

                line_num = stmt.lineno - 1
                old_line = updated_lines[line_num]

                # Check if line already seems annotated (basic check)
                # Example: avoid re-annotating "instance: Model = self.get_object()"
                # This check is simple and might miss complex existing annotations.
                if f"{target_name}:" in old_line.split("=")[0]:
                    continue

                annotation_needed = False

                # Case 1: self.get_object() call
                if (
                    isinstance(value_node, ast.Call)
                    and isinstance(value_node.func, ast.Attribute)
                    and value_node.func.attr == "get_object"
                    and isinstance(value_node.func.value, ast.Name)
                    and value_node.func.value.id == "self"
                ):
                    # Always annotate any variable that's assigned the result of self.get_object()
                    annotation_needed = True
                    # print(f"Adding annotation for {target_name} = self.get_object() in method {method.name}")

                # Case 2: serializer.save() call
                # Allow for different variable names for the serializer
                elif (
                    isinstance(value_node, ast.Call)
                    and isinstance(value_node.func, ast.Attribute)
                    and value_node.func.attr == "save"
                    and isinstance(value_node.func.value, ast.Name)
                    # Removed check for value.id == "serializer" to be more general
                ):
                    # Convert target name (snake_case) to potential model name (PascalCase)
                    target_words = target_name.split("_")
                    potential_model_name = "".join(
                        word.capitalize() for word in target_words
                    )

                    # Heuristic: Only annotate if target name suggests an instance
                    if (
                        target_name in ("instance", "obj", "object")
                        or target_name == queryset_model.lower()
                        or potential_model_name == queryset_model
                    ):
                        annotation_needed = True
                    # Allow annotation if target name matches model name convention
                    elif (
                        target_name.replace("_", "").lower()
                        == queryset_model.replace("_", "").lower()
                    ):
                        annotation_needed = True
                    # Allow common DRF pattern variable name
                    elif (
                        target_name == "created_instance"
                        or target_name == "updated_instance"
                    ):
                        annotation_needed = True

                if annotation_needed:
                    # Get the original source segment for the right-hand side
                    rhs_source = None
                    try:
                        rhs_source = get_source_segment(source, value_node)
                    except Exception:  # Broad except as various things can fail
                        pass  # Fallback below

                    if rhs_source is None:
                        # Fallback: split the original line string (less robust)
                        try:
                            rhs_source = old_line.split("=", 1)[1].strip()
                        except IndexError:
                            print("Warning: Could not parse RHS for assignment")
                            continue  # Skip this assignment if split fails

                    # Calculate indentation
                    indent = len(old_line) - len(old_line.lstrip(" "))

                    # Construct the new line with annotation
                    new_line = (
                        f"{' ' * indent}{target_name}: {full_model_path} = {rhs_source}"
                    )

                    # Only mark as modified if the line actually changes
                    if updated_lines[line_num] != new_line:
                        updated_lines[line_num] = new_line
                        modified = True

    updated_source = "\n".join(updated_lines)
    # Add a trailing newline if the original source had one
    if source.endswith("\n"):
        updated_source += "\n"
    return modified, updated_source


def process_views_file(path: str):
    """Parses a views.py file and adds type hints where possible."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return

    try:
        modified, updated_source = process_one_file(source)
    except SyntaxError as e:
        print("Error parsing file:", path, e)
        return

    # Write changes back to the file if modified
    if modified:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(updated_source)
            print(f"✅ Annotated {path}")
        except Exception as e:
            print(f"Error writing changes to {path}: {e}")
    else:
        print(f"— No changes needed in {path}")
