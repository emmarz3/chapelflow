from apps.organizations.models import Branch


def get_chrisland_chapel_branch():
    """Return the canonical active Chrisland University Chapel branch."""
    return Branch.objects.filter(
        name__iexact="Chrisland University Chapel",
        is_active=True,
    ).order_by("id").first()
