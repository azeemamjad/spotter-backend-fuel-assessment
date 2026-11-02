from django.urls import path
from routing import views

urlpatterns = [path('', views.index), path('api/route-plan/', views.route_plan), path('api/health/', views.health), path('map/<uuid:plan_id>/', views.plan_map)]
