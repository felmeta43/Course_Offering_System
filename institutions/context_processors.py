from .models import Institution


def institution(request):
    return {"institution": Institution.get_solo()}
