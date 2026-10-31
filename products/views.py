import os
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from .models import Medication, UserMedication, UserProfile
from .serializers import MedicationSerializer, UserMedicationSerializer, UserProfileSerializer

from google import genai
from google.genai import types

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ai_client = genai.Client(api_key=GOOGLE_API_KEY)

# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ИИ (GEMINI)
# ==========================================

def get_inn_from_gemini(product_name: str) -> str | None:
    prompt = (
        f"Ты — фармацевтический помощник. Пользователь ввёл название лекарства: '{product_name}'. "
        "Определи его международное непатентованное наименование (МНН / действующее вещество). "
        "Ответь ТОЛЬКО одним словом на русском языке — название действующего вещества. "
        "Например: 'Ибупрофен', 'Парацетамол', 'Амоксициллин'. "
        "Никаких пояснений, точек, кавычек или лишних слов."
    )
    try:
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        inn = response.text.strip().strip('.,"\'')
        return inn if inn else None
    except Exception as e:
        print(f"[Gemini error] {e}")
        return None

def get_prices_and_reviews_from_ai(product_name: str):
    """Просит ИИ найти цены в аптеках и отзывы, возвращает JSON"""
    prompt = (
        f"Ты — фармацевтический агрегатор. Найди актуальные цены (в белорусских рублях) "
        f"на препарат '{product_name}' в аптеках Беларуси (например, Аптека 36.6, Официальная аптека) и пару отзывов. "
        f"Верни ответ СТРОГО в формате JSON без маркеров markdown: "
        f"{{\"prices\": [{{\"pharmacy\": \"Название\", \"price\": 10.50, \"link\": \"url\"}}], \"reviews\": [{{\"author\": \"Имя\", \"text\": \"Текст отзыва\", \"rating\": 5}}]}}"
    )
    try:
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(text)
    except Exception as e:
        print(f"[Gemini AI Error] {e}")
        return {"prices": [], "reviews": []}

# ==========================================
# СТАРЫЕ API (ПОИСК)
# ==========================================

@csrf_exempt
def search_by_text_api(request):
    if request.method != "GET":
        return JsonResponse({"status": "error", "message": "Ожидался GET-запрос."}, status=400)

    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({"status": "error", "message": "Параметр 'q' пуст."}, status=400)

    found = Medication.objects.filter(Q(title__icontains=query) | Q(inn_name__icontains=query)).first()
    inn_used = None

    if not found:
        inn_used = get_inn_from_gemini(query)
        if inn_used:
            found = Medication.objects.filter(inn_name__icontains=inn_used).first()

    if not found:
        return JsonResponse({"status": "not_found", "message": f"Препарат '{query}' не найден."}, status=404, json_dumps_params={'ensure_ascii': False})

    analogs_qs = found.analogs.all()
    if not analogs_qs.exists() and found.inn_name:
        analogs_qs = Medication.objects.filter(inn_name__icontains=found.inn_name).exclude(id=found.id)

    analogs_list = [{"id": a.id, "title": a.title, "country": a.country, "status": a.get_sanction_status_display(), "price": float(a.base_price)} for a in analogs_qs]

    return JsonResponse({
        "status": "success", "query": query, "inn_used": inn_used or found.inn_name,
        "product": {"id": found.id, "title": found.title, "country": found.country, "price": float(found.base_price), "inn_name": found.inn_name},
        "analogs": analogs_list,
    }, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
def search_by_photo(request):
    if request.method == "POST" and request.FILES.get('image'):
        uploaded_image = request.FILES['image']
        try:
            image_bytes = uploaded_image.read()
            image_part = types.Part.from_bytes(data=image_bytes, mime_type=uploaded_image.content_type)
            prompt = "Ты — встроенный модуль распознавания товаров для аптечного сайта. Прочитай название лекарства на фото и выведи ТОЛЬКО название на русском языке. Без лишних слов."
            response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=[image_part, prompt])
            recognized_text = response.text.strip()

            found_product = Medication.objects.filter(Q(title__icontains=recognized_text) | Q(inn_name__icontains=recognized_text)).first()

            if not found_product:
                inn_used = get_inn_from_gemini(recognized_text)
                if inn_used:
                    found_product = Medication.objects.filter(inn_name__icontains=inn_used).first()

            if found_product:
                analogs_qs = found_product.analogs.all()
                if not analogs_qs.exists() and found_product.inn_name:
                    analogs_qs = Medication.objects.filter(inn_name__icontains=found_product.inn_name).exclude(id=found_product.id)

                analogs_list = [{"id": a.id, "title": a.title, "country": a.country, "price": float(a.base_price)} for a in analogs_qs]

                return JsonResponse({
                    "status": "success", "recognized_text": recognized_text,
                    "product": {"id": found_product.id, "title": found_product.title, "price": float(found_product.base_price)},
                    "analogs": analogs_list
                }, json_dumps_params={'ensure_ascii': False})

            return JsonResponse({"status": "not_found", "recognized_text": recognized_text, "message": "Препарат не найден в базе."}, status=404, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({"status": "error", "message": f"Ошибка: {str(e)}"}, status=500)
    return JsonResponse({"status": "error", "message": "Ожидался файл изображения."}, status=400)

# ==========================================
# НОВЫЕ API (ДЕТАЛИ, ЦЕНЫ, КАЛЬКУЛЯТОР)
# ==========================================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_medication_details(request, med_id):
    """Детали препарата + ИИ ищет цены и отзывы"""
    try:
        med = Medication.objects.get(id=med_id)
    except Medication.DoesNotExist:
        return Response({"error": "Препарат не найден"}, status=status.HTTP_404_NOT_FOUND)

    ai_data = get_prices_and_reviews_from_ai(med.title)

    data = MedicationSerializer(med).data
    data['ai_prices'] = ai_data.get('prices', [])
    data['ai_reviews'] = ai_data.get('reviews', [])

    return Response(data)

@api_view(['POST'])
@permission_classes([AllowAny])
def calculate_course_cost(request):
    """Калькулятор стоимости с учетом скидок"""
    med_id = request.data.get('medication_id')
    days = int(request.data.get('days', 1))
    times_per_day = int(request.data.get('times_per_day', 1))

    try:
        med = Medication.objects.get(id=med_id)
    except Medication.DoesNotExist:
        return Response({"error": "Препарат не найден"}, status=status.HTTP_404_NOT_FOUND)

    pills_needed = days * times_per_day
    pills_per_pack = med.pills_per_pack if med.pills_per_pack > 0 else 20

    total_cost = (float(med.base_price) / pills_per_pack) * pills_needed

    # Скидки для авторизованных
    discount = 0
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if profile.discount_category == 'vov': discount = 0.50
            elif profile.discount_category == 'disabled': discount = 0.30
            elif profile.discount_category == 'pensioner': discount = 0.10
        except Exception:
            pass

    final_cost = total_cost * (1 - discount)

    return Response({
        "medication": med.title,
        "pills_needed": pills_needed,
        "base_cost": round(total_cost, 2),
        "discount_percent": discount * 100,
        "final_cost": round(final_cost, 2)
    })

# ==========================================
# ЛИЧНЫЙ КАБИНЕТ (ТРЕБУЕТ АВТОРИЗАЦИИ)
# ==========================================

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def my_profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        return Response(UserProfileSerializer(profile).data)

    elif request.method == 'PUT':
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def my_medications(request):
    if request.method == 'GET':
        meds = UserMedication.objects.filter(user=request.user)
        return Response(UserMedicationSerializer(meds, many=True).data)

    elif request.method == 'POST':
        serializer = UserMedicationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)