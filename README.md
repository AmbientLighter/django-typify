# django-typify
Automatically decorate Django models

## Key Features

- **Reverse Relation Annotation**: Annotates reverse relations in Django models for better type safety.
- **Factory Annotation**: Enhances Django test factories with type annotations for improved code clarity.
- **CLI Tool**: Provides an easy-to-use command-line interface for annotating models and factories.
- **Seamless Integration**: Designed to integrate smoothly with existing Django projects.

## Usage

Run the following command to annotate reverse relations in your Django models:

```bash
django_typify annotate-models <path-to-your-django-project>
```

To annotate Django test factories with type annotations, use:

```bash
django_typify annotate-factories <path-to-your-django-project>
```

Replace <path-to-your-django-project> with the root directory of your Django project.