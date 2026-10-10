from django.urls import path
from . import views

urlpatterns = [
    # Главная страница поиска (то, что отдаёт HTML)
    path('', views.search_page, name='search_page'),

    # API для текстового поиска (JSON)
    path('api/search/', views.search_by_text_api, name='search_by_text_api'),

    # API для поиска по фото (JSON)
    path('api/search-by-photo/', views.search_by_photo, name='search_by_photo'),
]