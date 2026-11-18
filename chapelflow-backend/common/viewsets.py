from rest_framework import viewsets


class EnvelopeMixin:
    """
    Wraps every ModelViewSet response (list/retrieve/create/update/destroy)
    in the standard {success, message, data} envelope, matching the shape
    APIViews already produce via common.utils.responses. Paginated list
    responses are left alone since StandardResultsSetPagination already
    wraps them in the same envelope (with pagination metadata added).
    """

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)

        data = getattr(response, "data", None)
        already_wrapped = isinstance(data, dict) and "success" in data
        if data is not None and not already_wrapped:
            response.data = {
                "success": response.status_code < 400,
                "message": "OK" if response.status_code < 400 else "Request failed.",
                "data": data,
            }
        return response


class StandardModelViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    pass


class StandardReadOnlyModelViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    pass
