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


def _build_foto_url(car, settings):
    """Constrói a URL da foto do carro de forma centralizada."""
    if not car.photo:
        return None
    photo_path = str(car.photo)
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


@csrf_exempt
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
            'descricao': car.bio,
            'categoria': car.categoria,
        })

    elif request.method == 'POST':
        form = CarModelForm(request.POST, request.FILES, instance=car)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)

    elif request.method == 'DELETE':
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
