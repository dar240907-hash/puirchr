import os
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from .models import Medication

# Импортируем официальный новый клиент для работы с ИИ от Google
from google import genai
from google.genai import types

# НАСТРОЙКА GOOGLE GEMINI AI
# Ограничения бесплатного тарифа: 15 запросов в минуту
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# Инициализируем клиента нейросети Google
ai_client = genai.Client(api_key=GOOGLE_API_KEY)


def get_inn_from_gemini(product_name: str) -> str | None:
    """
    Отправляет название препарата в Gemini и получает МНН (действующее вещество).
    Возвращает строку с МНН или None, если не удалось.
    """
    prompt = (
        f"Ты — фармацевтический помощник. Пользователь ввёл название лекарства: '{product_name}'. "
        "Определи его международное непатентованное наименование (МНН / действующее вещество). "
        "Ответь ТОЛЬКО одним словом на русском языке — название действующего вещества. "
        "Например: 'Ибупрофен', 'Парацетамол', 'Амоксициллин'. "
        "Никаких пояснений, точек, кавычек или лишних слов."
    )
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        inn = response.text.strip().strip('.,"\'')
        return inn if inn else None
    except Exception as e:
        print(f"[Gemini error] {e}")
        return None


def search_page(request):
    """
    Отображает форму поиска лекарств.
    Логика:
    1. Ищем в базе по названию или МНН.
    2. Если не нашли — спрашиваем у Gemini МНН.
    3. Ищем в базе все лекарства с этим МНН (аналоги).
    """
    query = request.GET.get('q', '').strip()
    results = []
    source = None  # чтобы показать, откуда взялись результаты

    if query:
        # Шаг 1: прямой поиск по названию или МНН
        results = list(Medication.objects.filter(
            Q(title__icontains=query) | Q(inn_name__icontains=query)
        ))
        if results:
            source = "database"

        # Шаг 2: если ничего не нашли — пробуем через ИИ
        if not results:
            inn = get_inn_from_gemini(query)
            if inn:
                # Ищем все лекарства с этим МНН
                # Если нужно только белорусские — добавь filter(country__icontains="Беларусь")
                results = list(Medication.objects.filter(inn_name__icontains=inn))
                source = f"gemini (МНН: {inn})"

    return render(request, 'products/search.html', {
        'results': results,
        'query': query,
        'source': source,
    })


@csrf_exempt
def search_by_text_api(request):
    """
    API-версия поиска по тексту (для AJAX с фронтенда).
    Возвращает JSON с найденными аналогами.
    """
    if request.method != "GET":
        return JsonResponse({"status": "error", "message": "Ожидался GET-запрос."}, status=400)

    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({"status": "error", "message": "Параметр 'q' пуст."}, status=400)

    # Прямой поиск
    found = Medication.objects.filter(
        Q(title__icontains=query) | Q(inn_name__icontains=query)
    ).first()

    inn_used = None
    if not found:
        # Через ИИ
        inn_used = get_inn_from_gemini(query)
        if inn_used:
            found = Medication.objects.filter(inn_name__icontains=inn_used).first()

    if not found:
        return JsonResponse({
            "status": "not_found",
            "message": f"Препарат '{query}' не найден, и ИИ не смог определить МНН.",
        }, status=404, json_dumps_params={'ensure_ascii': False})

    # Собираем аналоги: сначала из ManyToMany, если пусто — по МНН
    analogs_qs = found.analogs.all()
    if not analogs_qs.exists() and found.inn_name:
        analogs_qs = Medication.objects.filter(inn_name__icontains=found.inn_name).exclude(id=found.id)

    analogs_list = [
        {
            "id": a.id,
            "title": a.title,
            "country": a.country,
            "status": a.get_sanction_status_display(),
            "inn_name": a.inn_name,
        } for a in analogs_qs
    ]

    return JsonResponse({
        "status": "success",
        "query": query,
        "inn_used": inn_used or found.inn_name,
        "product": {
            "id": found.id,
            "title": found.title,
            "country": found.country,
            "status": found.get_sanction_status_display(),
            "inn_name": found.inn_name,
        },
        "analogs": analogs_list,
    }, json_dumps_params={'ensure_ascii': False})


# БЛОК НЕЙРОСЕТИ: РАСПОЗНАВАНИЕ ТОВАРА ПО ФОТО (оставляем как было, но можно тоже улучшить)
@csrf_exempt
def search_by_photo(request):
    """
    Принимает фото упаковки, распознаёт название через Gemini,
    затем ищет аналоги по МНН.
    """
    if request.method == "POST" and request.FILES.get('image'):
        uploaded_image = request.FILES['image']
        try:
            image_bytes = uploaded_image.read()
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type=uploaded_image.content_type
            )
            prompt = (
                "Ты — встроенный модуль распознавания товаров для аптечного сайта. "
                "Посмотри на это фото упаковки лекарства. Твоя задача — прочитать текст на упаковке "
                "и вывести ТОЛЬКО коммерческое название медицинского препарата (одно или два слова). "
                "Не пиши никаких лишних слов, дозировок или пояснений. Только чистое название на русском языке."
            )
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[image_part, prompt]
            )
            recognized_text = response.text.strip()

            if not recognized_text:
                return JsonResponse({"status": "error", "message": "Нейросеть не смогла прочитать название."}, status=400)

            # Ищем по названию или МНН
            found_product = Medication.objects.filter(
                Q(title__icontains=recognized_text) | Q(inn_name__icontains=recognized_text)
            ).first()

            # Если не нашли — пробуем через ИИ определить МНН
            inn_used = None
            if not found_product:
                inn_used = get_inn_from_gemini(recognized_text)
                if inn_used:
                    found_product = Medication.objects.filter(inn_name__icontains=inn_used).first()

            if found_product:
                analogs_qs = found_product.analogs.all()
                if not analogs_qs.exists() and found_product.inn_name:
                    analogs_qs = Medication.objects.filter(
                        inn_name__icontains=found_product.inn_name
                    ).exclude(id=found_product.id)

                analogs_list = [
                    {
                        "id": a.id,
                        "title": a.title,
                        "country": a.country,
                        "status": a.get_sanction_status_display()
                    } for a in analogs_qs
                ]
                return JsonResponse({
                    "status": "success",
                    "recognized_text": recognized_text,
                    "inn_used": inn_used or found_product.inn_name,
                    "product": {
                        "title": found_product.title,
                        "country": found_product.country,
                        "status": found_product.get_sanction_status_display()
                    },
                    "analogs": analogs_list
                }, json_dumps_params={'ensure_ascii': False})

            return JsonResponse({
                "status": "not_found",
                "recognized_text": recognized_text,
                "message": f"Распознано '{recognized_text}', но в базе нет ни самого препарата, ни его МНН."
            }, status=404, json_dumps_params={'ensure_ascii': False})

        except Exception as e:
            return JsonResponse({"status": "error", "message": f"Ошибка Gemini: {str(e)}"}, status=500)

    return JsonResponse({"status": "error", "message": "Ожидался POST-запрос с файлом изображения."}, status=400)