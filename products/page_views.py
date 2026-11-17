"""Представления HTML-страниц сайта (главная, каталог, о проекте, контакты).

API-эндпоинты остаются в views.py — здесь только отрисовка шаблонов.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404, render

from .models import Medication

# Как в БД записана Беларусь — подправьте под свои данные
BELARUS_NAMES = {'беларусь', 'республика беларусь', 'belarus', 'рб'}

STATUS_LABELS = {
    'free': 'Даступны',
    'restricted': 'Абмежаваны',
    'sanctioned': 'Пад санкцыямі',
}
STATUS_CLASSES = {
    'free': 'status-free',
    'restricted': 'status-restricted',
    'sanctioned': 'status-sanctioned',
}

# (вид картинки, цвет полосы на упаковке, цвет таблеток) — для препаратов без фото
PIC_PALETTE = [
    ('blister', '#9fcdea', '#ffffff'),
    ('blister', '#f08a84', '#f4a6a6'),
    ('capsule', '#2bb3a8', '#f5c04a'),
    ('bottle', '#f08a2c', '#f6bf4b'),
    ('blister', '#a5dba8', '#ffffff'),
    ('blister', '#b266d9', '#c9a2ec'),
]

# TODO: в модели Medication нет поля category — пока список статичный (как в макете).
# Когда добавите поле, считайте количество через annotate/Count.
CATEGORIES = [
    {'name': 'Абязбольвальныя', 'count_label': '6 прэпаратаў', 'pic': 0},
    {'name': 'Сардэчна-сасудзістыя', 'count_label': '5 прэпаратаў', 'pic': 1},
    {'name': 'Антыбіётыкі', 'count_label': '4 прэпараты', 'pic': 2},
    {'name': 'Вітаміны', 'count_label': '3 прэпараты', 'pic': 3},
    {'name': 'Ад алергіі', 'count_label': '4 прэпараты', 'pic': 4},
    {'name': 'Для страўніка', 'count_label': '4 прэпараты', 'pic': 5},
]


def _is_belarus(med):
    return (med.country or '').strip().lower() in BELARUS_NAMES


def _decorate(meds):
    """Добавляет к препаратам поля, нужные шаблону карточки."""
    result = []
    for med in meds:
        kind, color, pill = PIC_PALETTE[med.pk % len(PIC_PALETTE)]
        release = (med.from_release or '').lower()
        if 'капсул' in release:
            kind = 'capsule'
        elif kind == 'capsule':
            kind = 'blister'
        med.is_by = _is_belarus(med)
        med.status_label = STATUS_LABELS.get(med.sanction_status, med.get_sanction_status_display())
        med.status_class = STATUS_CLASSES.get(med.sanction_status, 'status-free')
        med.pic_kind, med.pic_color, med.pic_pill = kind, color, pill
        result.append(med)
    return result


def _categories():
    items = []
    for cat in CATEGORIES:
        kind, color, pill = PIC_PALETTE[cat['pic']]
        items.append({**cat, 'kind': kind, 'color': color, 'pill': pill})
    return items


def home_page(request):
    meds = [m for m in _decorate(Medication.objects.all().order_by('title')) if m.is_by][:4]
    return render(request, 'index.html', {'popular': meds, 'categories': _categories()})


def catalog_page(request):
    meds = _decorate(Medication.objects.all())
    meds.sort(key=lambda m: (not m.is_by, m.title.lower()))
    return render(request, 'search.html', {'medications': meds, 'categories': _categories()})


def medication_page(request, med_id):
    med = get_object_or_404(Medication, pk=med_id)

    # Аналоги: связанные вручную, а если их нет — препараты с тем же МНН (как в API поиска)
    analogs = list(med.analogs.all())
    if not analogs and med.inn_name:
        analogs = list(Medication.objects.filter(inn_name__icontains=med.inn_name).exclude(pk=med.pk))

    _decorate([med, *analogs])
    for analog in analogs:
        analog.saving = None
        if med.base_price and analog.base_price is not None and analog.base_price < med.base_price:
            analog.saving = int(round((med.base_price - analog.base_price) / med.base_price * 100)) or None
    analogs.sort(key=lambda a: (not a.is_by, a.base_price))

    return render(request, 'medication.html', {'med': med, 'analogs': analogs})


def login_page(request):
    return render(request, 'login.html')


def profile_page(request):
    return render(request, 'profile.html')


def my_kit_page(request):
    return render(request, 'my_kit.html')


def about_page(request):
    return render(request, 'about.html')


def contacts_page(request):
    return render(request, 'contacts.html')
