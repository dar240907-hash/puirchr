from django.urls import path
from . import views, page_views, extra_api
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # Страницы сайта (HTML)
    path('', page_views.home_page, name='home'),
    path('search/', page_views.catalog_page, name='catalog'),
    path('medications/<int:med_id>/', page_views.medication_page, name='medication'),
    path('login/', page_views.login_page, name='login'),
    path('profile/', page_views.profile_page, name='profile'),
    path('my-medications/', page_views.my_kit_page, name='my_kit'),
    path('about/', page_views.about_page, name='about'),
    path('contacts/', page_views.contacts_page, name='contacts'),

    # Поиск
    path('api/search/', views.search_by_text_api, name='search_by_text_api'),
    path('api/search-by-photo/', views.search_by_photo, name='search_by_photo'),

    # Детали и калькулятор (доступно гостям)
    path('api/medications/<int:med_id>/', views.get_medication_details, name='medication_details'),
    path('api/calculate-cost/', views.calculate_course_cost, name='calculate_cost'),

    # Личный кабинет (только для авторизованных)
    path('api/profile/', views.my_profile, name='my_profile'),
    path('api/my-medications/', views.my_medications, name='my_medications'),
    path('api/my-medications/<int:pk>/', extra_api.my_medication_detail, name='my_medication_detail'),

    # Регистрация и токены (вход/обновление)
    path('api/register/', extra_api.register, name='register'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/map-prices/', views.get_prices_on_map, name='map_prices'),
]
