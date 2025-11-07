from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.generic.edit import UpdateView, CreateView, DeleteView
from django.urls import reverse_lazy
from django.db.migrations.recorder import MigrationRecorder  # Для миграций (если нужно)
from .models import Product  # Для продуктов
from .forms import ProductForm  # Импорт формы

def index(request):
    # Page from the theme
    return render(request, 'pages/index.html')

def tables_view(request):
    migration_records = MigrationRecorder.Migration.objects.all().order_by('-applied')
    print(f"DEBUG: Загружено {migration_records.count()} миграций")
    context = {
        'migrations': migration_records,
        'title': 'Миграции Django',
        'card_title': 'Миграции БД',
    }
    return render(request, 'pages/tables/data.html', context)

# Список продуктов
def product_list(request):
    products = Product.objects.all()
    context = {'products': products, 'title': 'Продукты'}
    return render(request, 'pages/product_list.html', context)

# UpdateView для редактирования (Django CBV)
class ProductUpdateView(UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'pages/product_form.html'
    success_url = reverse_lazy('product_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        return JsonResponse({'success': True, 'id': self.object.id})

# CreateView для добавления
class ProductCreateView(CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'pages/product_form.html'
    success_url = reverse_lazy('product_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        return JsonResponse({'success': True, 'id': self.object.id})

# DeleteView для удаления
class ProductDeleteView(DeleteView):
    model = Product
    success_url = reverse_lazy('product_list')

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        return JsonResponse({'success': True})

# AJAX-обработчик для обновления
@require_http_methods(["POST"])
def update_product_ajax(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST, instance=product)
    if form.is_valid():
        form.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'errors': form.errors})

# AJAX для создания
@require_http_methods(["POST"])
def create_product_ajax(request):
    form = ProductForm(request.POST)
    if form.is_valid():
        product = form.save()
        return JsonResponse({'success': True, 'id': product.id})
    return JsonResponse({'success': False, 'errors': form.errors})

# AJAX для удаления
@require_http_methods(["POST"])
def delete_product_ajax(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    return JsonResponse({'success': True})