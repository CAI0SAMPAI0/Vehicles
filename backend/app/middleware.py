from django.http import JsonResponse

class SimpleCORSMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'OPTIONS':
            response = JsonResponse({'detail': 'Preflight OK'})
        else:
            response = self.get_response(request)

        # Permite qualquer origem com credenciais para permitir cookies de sessão
        origin = request.headers.get('Origin')
        if origin:
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Credentials'] = 'true'
        else:
            response['Access-Control-Allow-Origin'] = '*'

        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, X-CSRFToken, Accept, Origin, Cache-Control'
        response['Access-Control-Max-Age'] = '86400'
        return response
