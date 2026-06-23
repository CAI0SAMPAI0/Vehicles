from django.urls import reverse_lazy
from django.http import JsonResponse
from cars.models import Car
from cars.forms import CarModelForm
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, UpdateView, DeleteView, DetailView, CreateView
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache


class CarsListView(ListView):
    model = Car
    template_name = 'cars.html'
    context_object_name = 'cars'

    def get_queryset(self):
        cars = super().get_queryset().order_by('model')
        search = self.request.GET.get('search')
        if search:
            cars = cars.filter(model__icontains=search)
        return cars


@method_decorator(login_required(login_url='login'), name='dispatch')
class NewCarCreateView(CreateView):
    model = Car
    form_class = CarModelForm
    template_name = 'new_car.html'
    success_url = '/cars/'


class CarDetailView(DetailView):
    model = Car
    template_name = 'car_detail.html'


class CarUpdateView(UpdateView):
    model = Car
    form_class = CarModelForm
    template_name = 'car_update.html'

    def get_success_url(self):
        return reverse_lazy('car_detail', kwargs={'pk': self.object.pk})


class CarDeleteView(DeleteView):
    model = Car
    template_name = 'car_delete.html'
    success_url = '/cars/'


def _build_foto_url(car_or_img, settings):
    """Constrói a URL da foto do carro ou imagem adicional de forma centralizada.
    Prioriza `photo_url` (URL externa persistida no PostgreSQL) antes do campo
    `photo` (arquivo local, efêmero em ambientes como HF Spaces).
    """
    # 1. Prioriza photo_url (URL externa, persiste no banco)
    photo_url = getattr(car_or_img, 'photo_url', None)
    if photo_url:
        return photo_url

    # 2. Fallback para photo (arquivo local — compatibilidade retroativa)
    field = getattr(car_or_img, 'photo', None) or getattr(car_or_img, 'image', None)
    if not field:
        return None
    photo_path = str(field)
    if not photo_path:
        return None
    if photo_path.startswith('http'):
        return photo_path
    return f"{settings.MEDIA_URL}{photo_path}"


def cars_api_list(request):
    search = request.GET.get('search', '')
    brand = request.GET.get('brand', '')
    categoria = request.GET.get('categoria', '')
    ordering = request.GET.get('ordering', '')
    page = request.GET.get('page', '1')

    try:
        page = int(page)
    except ValueError:
        page = 1

    cache_key = f'cars_api_list_{search}_{brand}_{categoria}_{ordering}_{page}'
    cached_cars = cache.get(cache_key)
    if cached_cars:
        return JsonResponse(cached_cars)

    cars = Car.objects.select_related('brand').all()
    
    if ordering == 'price_asc':
        cars = cars.order_by('value')
    elif ordering == 'price_desc':
        cars = cars.order_by('-value')
    elif ordering == 'year_desc':
        cars = cars.order_by('-model_year')
    elif ordering == 'year_asc':
        cars = cars.order_by('model_year')
    else:
        cars = cars.order_by('model')

    if search:
        log_search_to_cache(search)
        from django.db.models import Q
        cars = cars.filter(
            Q(model__icontains=search) |
            Q(brand__name__icontains=search) |
            Q(bio__icontains=search)
        )
    if brand:
        cars = cars.filter(brand__name=brand)
    if categoria:
        cars = cars.filter(categoria=categoria)

    total_count = cars.count()

    page_size = 30
    start = (page - 1) * page_size
    end = start + page_size
    cars_page = cars[start:end]

    data = []
    from django.conf import settings

    for car in cars_page:
        data.append({
            'id': car.id,
            'marca': car.brand.name if car.brand else None,
            'modelo': car.model,
            'ano': car.model_year,
            'preco': car.value,
            'moeda': car.currency,
            'foto': _build_foto_url(car, settings),
            'placeholder': car.photo_placeholder,
            'descricao': car.bio,
            'categoria': car.categoria,
        })

    response_data = {
        'results': data,
        'count': total_count,
        'has_next': end < total_count,
    }

    cache.set(cache_key, response_data, 60 * 60 * 24)
    return JsonResponse(response_data)


def brands_api_list(request):
    from cars.models import Brand
    brands = Brand.objects.all().order_by('name')
    data = [{'id': b.id, 'name': b.name} for b in brands]
    return JsonResponse(data, safe=False)


def categorias_api_list(request):
    """Retorna a lista de categorias disponíveis com labels em português."""
    categorias = [
        {'value': 'SEDAN',     'label': 'Sedan'},
        {'value': 'SUV',       'label': 'SUV'},
        {'value': 'HATCH',     'label': 'Hatch'},
        {'value': 'PICAPE',    'label': 'Picape'},
        {'value': 'ESPORTIVO', 'label': 'Esportivo'},
        {'value': 'MINIVAN',   'label': 'Minivan'},
        {'value': 'ELETRICO',  'label': 'Elétrico'},
        {'value': 'CLASSICO',  'label': 'Clássico'},
        {'value': 'OUTRO',     'label': 'Outro'},
    ]
    return JsonResponse(categorias, safe=False)


from accounts.jwt_helper import token_required, validate_token_header

@csrf_exempt
@token_required
def car_create_api(request):
    if request.method == 'POST':
        form = CarModelForm(request.POST, request.FILES)
        if form.is_valid():
            car = form.save()
            return JsonResponse({'success': True, 'id': car.id})
        else:
            return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


@csrf_exempt
def car_detail_api(request, pk):
    try:
        car = Car.objects.select_related('brand').get(pk=pk)
    except Car.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Carro não encontrado'}, status=404)

    if request.method == 'GET':
        from django.conf import settings
        return JsonResponse({
            'id': car.id,
            'brand': car.brand.id if car.brand else None,
            'marca': car.brand.name if car.brand else None,
            'modelo': car.model,
            'ano_fabricacao': car.factory_year,
            'ano_modelo': car.model_year,
            'placa': car.plate,
            'preco': car.value,
            'moeda': car.currency,
            'foto': _build_foto_url(car, settings),
            'placeholder': car.photo_placeholder,
            'descricao': car.bio,
            'categoria': car.categoria,
            'imagens_adicionais': [
                {
                    'id': img.id,
                    'foto': _build_foto_url(img, settings),
                    'placeholder': img.photo_placeholder
                } for img in car.images.all()
            ]
        })

    elif request.method == 'POST':
        user = validate_token_header(request)
        if not user:
            return JsonResponse({'success': False, 'error': 'Autenticação necessária.'}, status=401)
        form = CarModelForm(request.POST, request.FILES, instance=car)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)

    elif request.method == 'DELETE':
        user = validate_token_header(request)
        if not user:
            return JsonResponse({'success': False, 'error': 'Autenticação necessária.'}, status=401)
        car.delete()
        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


from django.http import FileResponse, Http404
import os
from django.conf import settings


def serve_media_view(request, path):
    """
    Serve arquivos da pasta de media dinamicamente,
    permitindo que fotos baixadas em background sejam exibidas na Render.
    """
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'))
    raise Http404("Arquivo de mídia não encontrado")


import json

@csrf_exempt
def semantic_search_api(request):
    """
    Usa a IA da Groq para interpretar uma consulta conversacional
    e convertê-la em filtros de banco de dados (marca, modelo, categoria, preço máximo, etc.)
    ou realizar uma busca semântica inteligente nos carros.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        query = data.get('query', '').strip()
        if not query:
            return JsonResponse({'results': [], 'count': 0})
        log_search_to_cache(query)
            
        from openai_api.client import get_groq_client
        client = get_groq_client()
        if not client:
            return JsonResponse({'success': False, 'error': 'Groq client not configured'}, status=500)
            
        # Pede para a IA extrair filtros estruturados em JSON
        prompt = f"""
        Você é uma IA especializada em analisar buscas conversacionais de carros.
        Analise a seguinte busca do usuário: "{query}"
        E retorne APENAS um JSON válido contendo filtros correspondentes com os seguintes campos (todos opcionais):
        - "marca" (string, nome da marca como Ford, Honda, etc.)
        - "categoria" (string, um dos seguintes valores exatos: SEDAN, SUV, HATCH, PICAPE, ESPORTIVO, MINIVAN, ELETRICO, CLASSICO, OUTRO)
        - "preco_max" (float, preço máximo buscado)
        - "preco_min" (float, preço mínimo buscado)
        - "ano_min" (int, ano mínimo do modelo)
        - "ano_max" (int, ano máximo do modelo)
        - "modelo_keyword" (string, palavra-chave do modelo)
        - "explicacao" (string, breve explicação em português do que entendeu da busca, máx 80 caracteres)
        
        Exemplo: "Quero ver sedans da Toyota de até 80 mil de 2018 para cima"
        Retorno:
        {{"categoria": "SEDAN", "marca": "Toyota", "preco_max": 80000.0, "ano_min": 2018, "explicacao": "Sedans Toyota de até R$ 80.000,00 e ano a partir de 2018"}}
        
        Retorne APENAS o JSON válido. Não inclua markdown, não inclua blocos ```json ou explicações extras.
        """
        
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.0,
            max_tokens=200
        )
        
        result_text = response.choices[0].message.content.strip()
        # Limpa blocos de código se a IA os gerou
        if result_text.startswith("```"):
            result_text = result_text.replace("```json", "").replace("```", "").strip()
            
        filters = json.loads(result_text)
        
        # Constrói a query no banco
        cars = Car.objects.select_related('brand').all()
        
        marca = filters.get('marca')
        categoria = filters.get('categoria')
        preco_max = filters.get('preco_max')
        preco_min = filters.get('preco_min')
        ano_min = filters.get('ano_min')
        ano_max = filters.get('ano_max')
        modelo_keyword = filters.get('modelo_keyword')
        
        if marca:
            cars = cars.filter(brand__name__icontains=marca)
        if categoria:
            cars = cars.filter(categoria=categoria)
        if preco_max:
            cars = cars.filter(value__lte=preco_max)
        if preco_min:
            cars = cars.filter(value__gte=preco_min)
        if ano_min:
            cars = cars.filter(model_year__gte=ano_min)
        if ano_max:
            cars = cars.filter(model_year__lte=ano_max)
        if modelo_keyword:
            cars = cars.filter(model__icontains=modelo_keyword)
            
        # Se nenhum filtro específico foi capturado ou nenhum resultado foi encontrado por filtros, 
        # fazemos uma busca de texto comum no modelo/marca/descrição.
        if not (marca or categoria or preco_max or preco_min or ano_min or ano_max or modelo_keyword) or cars.count() == 0:
            from django.db.models import Q
            cars = Car.objects.select_related('brand').filter(
                Q(model__icontains=query) |
                Q(brand__name__icontains=query) |
                Q(bio__icontains=query)
            )
            
        total_count = cars.count()
        data = []
        from django.conf import settings
        
        for car in cars[:15]:  # limita a 15 resultados na busca IA
            data.append({
                'id': car.id,
                'marca': car.brand.name if car.brand else None,
                'modelo': car.model,
                'ano': car.model_year,
                'preco': car.value,
                'moeda': car.currency,
                'foto': _build_foto_url(car, settings),
                'placeholder': car.photo_placeholder,
                'descricao': car.bio,
                'categoria': car.categoria,
            })
            
        return JsonResponse({
            'success': True,
            'results': data,
            'count': total_count,
            'explicacao': filters.get('explicacao', f'Resultados para: "{query}"')
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
def chatbot_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        messages = data.get('messages', [])
        car_id = data.get('car_id') # opcional, se estiver na tela de detalhes
        
        if not messages:
            return JsonResponse({'success': False, 'error': 'Messages are required.'}, status=400)
            
        from openai_api.client import get_groq_client
        client = get_groq_client()
        if not client:
            return JsonResponse({'success': False, 'error': 'Groq client not configured.'}, status=500)
            
        # Coleta contexto do veículo atual se houver
        car_context = ""
        if car_id:
            try:
                car = Car.objects.select_related('brand').get(pk=car_id)
                car_context = f"O usuário está visualizando o veículo atual: {car.brand.name} {car.model} ({car.model_year}), preço: {car.currency} {car.value}, categoria: {car.categoria}, descrição: {car.bio}.\n"
            except Car.DoesNotExist:
                pass
                
        # Coleta os outros veículos ativos (limita a 10)
        all_cars = Car.objects.select_related('brand').exclude(id=car_id if car_id else 0)[:10]
        inventory_context = "Outros veículos disponíveis na concessionária:\n"
        for c in all_cars:
            inventory_context += f"- {c.brand.name} {c.model} ({c.model_year}), preço: {c.currency} {c.value}, categoria: {c.categoria}.\n"
            
        system_prompt = f"""
        Você é o AutoDrive AI Chatbot, um assistente virtual e vendedor de veículos de alto nível para a concessionária AutoDrive.
        Seu tom é profissional, prestativo, persuasivo e polido.
        Use os seguintes dados sobre o estoque da concessionária para embasar suas respostas e recomendações:
        {car_context}
        {inventory_context}
        
        Seja conciso, responda em no máximo 3 parágrafos curtos. Tente sempre engajar o cliente a agendar uma visita ou enviar mensagem no WhatsApp (telefone: +55 11 99999-9999).
        """
        
        api_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages[-6:]:
            api_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
            
        response = client.chat.completions.create(
            messages=api_messages,
            model="llama-3.1-8b-instant",
            temperature=0.7,
            max_tokens=400
        )
        
        reply = response.choices[0].message.content.strip()
        return JsonResponse({'success': True, 'reply': reply})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


def log_search_to_cache(query):
    if not query:
        return
    try:
        logs = cache.get('dashboard_search_logs') or []
        if not logs or logs[0] != query:
            logs.insert(0, query)
            cache.set('dashboard_search_logs', logs[:100], 60 * 60 * 24 * 7)
    except Exception:
        pass


@csrf_exempt
def car_alert_api(request, pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    try:
        car = Car.objects.get(pk=pk)
    except Car.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Carro não encontrado'}, status=404)
        
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        if not email or '@' not in email:
            return JsonResponse({'success': False, 'error': 'E-mail inválido.'}, status=400)
            
        from cars.models import PriceAlert
        alert, created = PriceAlert.objects.get_or_create(car=car, email=email)
        return JsonResponse({'success': True, 'created': created})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
def dashboard_stats_api(request):
    user = validate_token_header(request)
    if not user:
        return JsonResponse({'success': False, 'error': 'Acesso negado. Autenticação necessária.'}, status=401)
        
    try:
        from django.db.models import Count, Sum
        from cars.models import Car
        
        total_cars = Car.objects.count()
        
        usd_to_brl = 5.50
        try:
            import urllib.request
            import json as urllib_json
            with urllib.request.urlopen('https://economia.awesomeapi.com.br/json/last/USD-BRL', timeout=2) as res:
                c_data = urllib_json.loads(res.read().decode())
                if 'USDBRL' in c_data:
                    usd_to_brl = float(c_data['USDBRL']['bid'])
        except Exception:
            pass
            
        val_brl = Car.objects.filter(currency='BRL').aggregate(total=Sum('value'))['total'] or 0.0
        val_usd = Car.objects.filter(currency='USD').aggregate(total=Sum('value'))['total'] or 0.0
        
        total_value_brl = val_brl + (val_usd * usd_to_brl)
        total_value_usd = val_usd + (val_brl / usd_to_brl)
        
        by_brand_qs = Car.objects.values('brand__name').annotate(count=Count('id')).order_by('-count')
        by_brand = [{'marca': item['brand__name'] or 'Sem Marca', 'quantidade': item['count']} for item in by_brand_qs]
        
        by_category_qs = Car.objects.values('categoria').annotate(count=Count('id')).order_by('-count')
        by_category = [{'categoria': item['categoria'] or 'NÃO DEFINIDA', 'quantidade': item['count']} for item in by_category_qs]
        
        search_logs = cache.get('dashboard_search_logs') or []
        
        return JsonResponse({
            'success': True,
            'total_cars': total_cars,
            'total_value_brl': total_value_brl,
            'total_value_usd': total_value_usd,
            'cambio': usd_to_brl,
            'agrupado_por_marca': by_brand,
            'agrupado_por_categoria': by_category,
            'buscas_recentes': search_logs[:10]
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
