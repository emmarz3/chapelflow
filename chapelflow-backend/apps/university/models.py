import uuid

from django.db import models


class University(models.Model):
    """
    Top of the ACADEMIC hierarchy (spec section 2). Deliberately separate
    from apps.organizations.Organization/Branch, which model the CHAPEL
    side (Chapel -> Fellowships/Units/Ministries). A member's academic
    affiliation (College/Department) and their Chapel affiliation
    (Fellowship/Unit/Ministry) are independent axes, not one hierarchy.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="universities",
        help_text="The Organization this University belongs to (an Organization may run one or more Universities).",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "university_university"
        ordering = ["name"]

    def __str__(self):
        return self.name


class College(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    university = models.ForeignKey(University, on_delete=models.CASCADE, related_name="colleges")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "university_college"
        unique_together = ("university", "name")

    def __str__(self):
        return self.name


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    college = models.ForeignKey(College, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "university_department"
        unique_together = ("college", "name")

    def __str__(self):
        return self.name
