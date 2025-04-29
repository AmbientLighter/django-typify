from django_typify.factories import (
    add_factories_subcommand,
    find_factory_files,
    process_factory_file,
)
from django_typify.models import (
    add_models_subcommand,
    find_model_files,
    process_models_file,
)
from django_typify.views import (
    add_views_subcommand,
    find_view_files,
    process_views_file,
)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Annotate Django model reverse relations."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_models_subcommand(subparsers)
    add_factories_subcommand(subparsers)
    add_views_subcommand(subparsers)

    args = parser.parse_args()

    if args.command == "annotate-models":
        for file_path in find_model_files(args.path):
            process_models_file(file_path)
    elif args.command == "annotate-factories":
        for file_path in find_factory_files(args.path):
            process_factory_file(file_path)
    elif args.command == "annotate-views":
        for file_path in find_view_files(args.path):
            process_views_file(file_path)


if __name__ == "__main__":
    main()
