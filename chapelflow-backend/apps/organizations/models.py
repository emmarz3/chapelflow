import uuid

from django.db import models


class Organization(models.Model):
    """Top-level entity: a denomination, church network, or single church."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    logo_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "org_organization"

    def __str__(self):
        return self.name


class Branch(models.Model):
    """
    A branch, campus, or chapel under an Organization. Self-referencing
    parent supports Organization -> Branch -> Campus -> Chapel -> Department
    style hierarchies without hardcoding depth.
    """

    class BranchType(models.TextChoices):
        BRANCH = "BRANCH", "Branch"
        CAMPUS = "CAMPUS", "Campus"
        CHAPEL = "CHAPEL", "Chapel"
        DEPARTMENT = "DEPARTMENT", "Department"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="branches")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    name = models.CharField(max_length=255)
    branch_type = models.CharField(max_length=20, choices=BranchType.choices, default=BranchType.BRANCH)
    address = models.CharField(max_length=500, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    timezone = models.CharField(max_length=64, default="Africa/Lagos")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "org_branch"
        indexes = [models.Index(fields=["organization", "branch_type"])]

    def __str__(self):
        return f"{self.name} ({self.branch_type})"
