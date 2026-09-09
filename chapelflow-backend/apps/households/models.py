import uuid

from django.db import models


class Household(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT, related_name="households")
    name = models.CharField(max_length=255, help_text="e.g. 'The Adeyemi Family'")
    head = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="headed_households"
    )
    address = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "households_household"

    def __str__(self):
        return self.name
