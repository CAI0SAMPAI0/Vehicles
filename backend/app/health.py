from django.http import JsonResponse


def health_view(request):
    """
    Endpoint de keep-alive para o Render.com.
    Não acessa banco de dados nem cache — retorna em < 5ms.
    Usado pelo cron job externo para evitar o spin-down do plano free.
    """
    return JsonResponse({'status': 'ok'})
