from rest_framework import serializers

from .models import ReportJob


class ReportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportJob
        fields = [
            "id", "branch", "requested_by", "report_type", "export_format",
            "filters", "status", "file_url", "error_message", "created_at", "completed_at",
        ]
        read_only_fields = ["id", "requested_by", "status", "file_url", "error_message", "created_at", "completed_at"]
    
    def validate_filters(self, filters):
        """
        Phase 15: Validate report filters for security.
        
        Prevents:
        - SQL injection via malicious filter values
        - Arbitrary model field access
        - Cross-branch data access attempts
        
        Allowed filter keys per report type:
        - MEMBERSHIP: membership_status
        - ATTENDANCE: date_from, date_to, event_id
        - GIVING: date_from, date_to, category_id
        - EVENTS: date_from, date_to, event_type, category_id
        - VISITORS: date_from, date_to, follow_up_status, visit_count_min
        - MINISTRIES: group_type, is_active
        - VOLUNTEERS: date_from, date_to, status, ministry_id
        """
        if not filters:
            return filters
        
        report_type = self.initial_data.get('report_type')
        
        # Define allowed filters per report type
        ALLOWED_FILTERS = {
            'MEMBERSHIP': {'membership_status'},
            'ATTENDANCE': {'date_from', 'date_to', 'event_id'},
            'GIVING': {'date_from', 'date_to', 'category_id'},
            'EVENTS': {'date_from', 'date_to', 'event_type', 'category_id'},
            'VISITORS': {'date_from', 'date_to', 'follow_up_status', 'visit_count_min'},
            'MINISTRIES': {'group_type', 'is_active'},
            'VOLUNTEERS': {'date_from', 'date_to', 'status', 'ministry_id'},
        }
        
        allowed = ALLOWED_FILTERS.get(report_type, set())
        
        # Check for unauthorized filter keys
        provided_keys = set(filters.keys())
        unauthorized = provided_keys - allowed
        
        if unauthorized:
            raise serializers.ValidationError(
                f"Invalid filters for {report_type} report: {', '.join(unauthorized)}. "
                f"Allowed filters: {', '.join(allowed)}"
            )
        
        # Validate filter value types
        for key, value in filters.items():
            # Date filters must be ISO format strings
            if key in {'date_from', 'date_to'}:
                if not isinstance(value, str):
                    raise serializers.ValidationError(
                        f"Filter '{key}' must be a date string (ISO format)"
                    )
                # Try parsing to validate format
                try:
                    from datetime import datetime
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    raise serializers.ValidationError(
                        f"Filter '{key}' must be a valid ISO date string"
                    )
            
            # ID filters must be valid UUIDs or integers
            elif key.endswith('_id'):
                if not isinstance(value, (str, int)):
                    raise serializers.ValidationError(
                        f"Filter '{key}' must be a string or integer"
                    )
            
            # Count/numeric filters
            elif 'count' in key or key == 'visit_count_min':
                if not isinstance(value, int) or value < 0:
                    raise serializers.ValidationError(
                        f"Filter '{key}' must be a non-negative integer"
                    )
            
            # Boolean filters
            elif key == 'is_active':
                if not isinstance(value, bool):
                    raise serializers.ValidationError(
                        f"Filter '{key}' must be a boolean"
                    )
            
            # String filters (status, type, etc.)
            else:
                if not isinstance(value, str):
                    raise serializers.ValidationError(
                        f"Filter '{key}' must be a string"
                    )
                # Prevent SQL injection patterns
                dangerous_patterns = ['--', ';', 'DROP', 'DELETE', 'UPDATE', 'INSERT', 'EXEC']
                value_upper = str(value).upper()
                for pattern in dangerous_patterns:
                    if pattern in value_upper:
                        raise serializers.ValidationError(
                            f"Filter '{key}' contains forbidden pattern: {pattern}"
                        )
        
        return filters
