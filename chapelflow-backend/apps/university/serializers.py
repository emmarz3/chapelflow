from rest_framework import serializers

from .models import College, Department, University


class UniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = University
        fields = ["id", "organization", "name", "slug", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class CollegeSerializer(serializers.ModelSerializer):
    class Meta:
        model = College
        fields = ["id", "university", "name", "code", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class DepartmentSerializer(serializers.ModelSerializer):
    """
    Phase 4: Validates that the department's college relationship is
    consistent. When updating a department, the college must remain within
    the same university hierarchy to prevent orphaned/inconsistent academic
    relationships (e.g., Department A belonging to College B from a
    different University than what's stored in Department A's college_id).
    """
    class Meta:
        model = Department
        fields = ["id", "college", "name", "code", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
    
    def validate_college(self, college):
        """
        Phase 4: Ensure college exists and is active. Additional validation
        in validate() checks university consistency if both fields present.
        """
        if not college.is_active:
            raise serializers.ValidationError(
                "Cannot assign department to an inactive college."
            )
        return college
    
    def validate(self, attrs):
        """
        Phase 4: When creating/updating a department, if the instance already
        exists and the college is being changed, verify the new college
        belongs to the same university. This prevents creating departments
        that span multiple universities through API manipulation.
        """
        college = attrs.get('college')
        
        # On update: prevent moving department to a different university
        if self.instance and college:
            if college.id != self.instance.college_id:
                old_university = self.instance.college.university
                new_university = college.university
                
                if old_university.id != new_university.id:
                    raise serializers.ValidationError({
                        'college': f"Cannot move department from {old_university.name} "
                                   f"to {new_university.name}. Delete and recreate instead."
                    })
        
        return attrs
