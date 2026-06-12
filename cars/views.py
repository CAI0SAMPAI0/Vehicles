from django.urls import reverse_lazy
from django.http import JsonResponse
from cars.models import Car
from cars.forms import CarModelForm
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, UpdateView, DeleteView, DetailView, CreateView


class CarsListView(ListView):
    model = Car
    template_name = 'cars.html'
    context_object_name = 'cars'

    def get_queryset(self):
        cars = super().get_queryset().order_by('model') # filtrando como cars = Car.objects.all().order_by('model') porém usando Heranças
        search = self.request.GET.get('search')
        # tratando a varíavel
        if search:
            cars = cars.filter(model__icontains=search)
        return cars
    
# protegendo view fazendo autenticação
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

def cars_api_list(request):
    cars = Car.objects.all().order_by('model')
    data = []
    for car in cars:
        data.append({
            'id': car.id,
            'marca': car.brand.name if car.brand else None,
            'modelo': car.model,
            'ano': car.model_year,
            'preco': car.value,
            'foto': car.photo.url if car.photo else None,
            'descricao': car.bio,
        })
    return JsonResponse(data, safe=False)
