from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from cars.views import (
    CarsListView, NewCarCreateView, CarDetailView, CarUpdateView, CarDeleteView,
    cars_api_list, brands_api_list, categorias_api_list,
    car_create_api, car_detail_api, serve_media_view,
)
from accounts.views import register_view, login_view, logout_view


urlpatterns = [
    path('admin/', admin.site.urls),
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('cars/', CarsListView.as_view(), name='cars_list'),
    path('new_car/', NewCarCreateView.as_view(), name='new_car'),
    path('car/<int:pk>/', CarDetailView.as_view(), name='car_detail'),
    path('car/<int:pk>/update/', CarUpdateView.as_view(), name='car_update'),
    path('car/<int:pk>/delete/', CarDeleteView.as_view(), name='car_delete'),
    path('api/v1/cars/', cars_api_list, name='cars_api_list'),
    path('api/v1/brands/', brands_api_list, name='brands_api_list'),
    path('api/v1/categorias/', categorias_api_list, name='categorias_api_list'),
    path('api/v1/car/create/', car_create_api, name='car_create_api'),
    path('api/v1/car/<int:pk>/', car_detail_api, name='car_detail_api'),
    path('media/<path:path>', serve_media_view, name='serve_media'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)