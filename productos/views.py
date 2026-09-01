from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

class StockDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'productos/stock_dashboard.html'

class ProductoListView(LoginRequiredMixin, TemplateView):
    template_name = 'productos/stock_index.html'
