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
# ГЛАВНАЯ СТРАНИЦА ПОИСКА
def search_page(request):
    """
    Отображает форму поиска лекарств по базе данных.
    """
    query = request.GET.get('q', '').strip()
    results = []
    if query:
        # Регистронезависимый поиск по названию ИЛИ по действующему веществу (МНН)
        results = Medication.objects.filter(
            Q(title__icontains=query) | Q(inn_name__icontains=query)
        )  
    return render(request, 'products/search.html', {'results': results, 'query': query})
# БЛОК НЕЙРОСЕТИ: РАСПОЗНАВАНИЕ ТОВАРА ПО ФОТО ЧЕРЕЗ GOOGLE GEMINI
@csrf_exempt
def search_by_photo(request):
    """
    Принимает фото упаковки с телефона, отправляет его в Google Gemini,
    получает распознанное название лекарства и ищет аналоги в нашей SQLite.
    """
    if request.method == "POST" and request.FILES.get('image'):
        uploaded_image = request.FILES['image']
        
        try:
            # Читаем картинку, которую прислал фронтенд с камеры телефона
            image_bytes = uploaded_image.read()
            
            # Конвертируем картинку в понятный для Google API формат данных
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type=uploaded_image.content_type # автоматически определит jpeg/png
            )
            
            # Строгая системная инструкция для ИИ, чтобы он выдавал только название
            prompt = (
                "Ты — встроенный модуль распознавания товаров для аптечного сайта. "
                "Посмотри на это фото упаковки лекарства. Твоя задача — прочитать текст на упаковке "
                "и вывести ТОЛЬКО коммерческое название медицинского препарата (одно или два слова, например: 'Аспирин' или 'Ибупрофен'). "
                "Не пиши никаких лишних слов, приветствий, дозировок или пояснений. Только чистое название на русском языке."
            )
            
            # Вызываем мультимодальную модель Gemini 2.5 Flash
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[image_part, prompt]
            )
            
            # Забираем очищенный текст ответа
            recognized_text = response.text.strip()
            
            if not recognized_text:
                return JsonResponse({"status": "error", "message": "Нейросеть Google не смогла прочитать название на фото."}, status=400)
            # ПОИСК АНАЛОГОВ В НАШЕЙ БАЗЕ ДАННЫХ
            # Сначала ищем совпадение по названию товара
            found_product = Medication.objects.filter(title__icontains=recognized_text).first()
            
            # Если не нашли, проверяем, вдруг Google выдал МНН (действующее вещество)
            if not found_product:
                found_product = Medication.objects.filter(inn_name__icontains=recognized_text).first()

            if found_product:
                # Вытягиваем все привязанные аналоги из базы данных
                analogs_list = [
                    {
                        "id": analog.id,
                        "title": analog.title,
                        "country": analog.country,
                        "status": analog.get_sanction_status_display()
                    } for analog in found_product.analogs.all()
                ]
                
                # Возвращаем JSON-структуру для фронтенда
                return JsonResponse({
                    "status": "success",
                    "recognized_text": recognized_text,
                    "product": {
                        "title": found_product.title,
                        "country": found_product.country,
                        "status": found_product.get_sanction_status_display()
                    },
                    "analogs": analogs_list
                }, json_dumps_params={'ensure_ascii': False})
                
            # Если ИИ прочитал слово, но мы этот товар еще не завели в админку
            return JsonResponse({
                "status": "not_found", 
                "recognized_text": recognized_text,
                "message": f"Google распознал на фото '{recognized_text}', но в нашей базе данных этого препарата пока нет."
            }, status=404, json_dumps_params={'ensure_ascii': False})

        except Exception as e:
            # Защита от падения сервера при сбое сети или ошибках ключа API
            return JsonResponse({"status": "error", "message": f"Ошибка интеграции с Google AI: {str(e)}"}, status=500)
            
    return JsonResponse({"status": "error", "message": "Ожидался POST-запрос с файлом изображения."}, status=400)
