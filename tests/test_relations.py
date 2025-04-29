import ast
from django_typify.models import extract_reverse_relations


def test_extract_reverse_relation():
    source = """
from django.db import models

class User(models.Model):
    pass

class Post(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="posts",
    )
"""
    tree = ast.parse(source)
    relations = extract_reverse_relations(tree)

    assert relations == [
        ("User", "posts", "Post"),
    ]


def test_extract_reverse_relations_with_related_name_plus():
    source = """
from django.db import models

class User(models.Model):
    pass

class Post(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="+",
    )
"""
    tree = ast.parse(source)
    relations = extract_reverse_relations(tree)

    assert relations == []


def test_extract_reverse_relations_with_to_parameter():
    source = """

class User(models.Model):
    pass

class Post(models.Model):
    author = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        related_name="posts",
    )
"""
    tree = ast.parse(source)
    relations = extract_reverse_relations(tree)

    assert relations == [
        ("User", "posts", "Post"),
    ]


def test_extract_reverse_relations_with_inheritance():
    source = """

class BaseModel(models.Model):
    class Meta:
        abstract = True

class User(BaseModel):
    pass

class Post(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="posts",
    )
"""
    tree = ast.parse(source)
    relations = extract_reverse_relations(tree)

    assert relations == [
        ("User", "posts", "Post"),
    ]
