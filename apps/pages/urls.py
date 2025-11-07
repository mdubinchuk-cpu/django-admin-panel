from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),  # Главная страница (не меняем на продукты)
    path('products/', views.product_list, name='product_list'),  # Список продуктов: /products/
    path('products/create/', views.create_product_ajax, name='create_product_ajax'),  # AJAX добавление
    path('products/update/<int:pk>/', views.update_product_ajax, name='update_product_ajax'),  # AJAX редактирование
    path('products/delete/<int:pk>/', views.delete_product_ajax, name='delete_product_ajax'),  # AJAX удаление
]