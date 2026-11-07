from rest_framework import serializers

from common.serializers.validators import ScopedFKValidationMixin
from .models import Household


class HouseholdSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    member_count = serializers.IntegerField(source="members.count", read_only=True)

    class Meta:
        model = Household
        fields = ["id", "branch", "name", "head", "address", "member_count", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
    
    def validate_branch(self, branch):
        """Phase 3: Validate user can access this branch."""
        return self.validate_branch_fk(branch)
    
    def validate_head(self, head):
        """Phase 3: Validate household head belongs to accessible branch."""
        return self.validate_member_fk(head)
