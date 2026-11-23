from django.db import models
from django.contrib.auth.models import User


# 1. БАЗОВАЯ МОДЕЛЬ (Абстрактная, как было)
class Product(models.Model):
    SANCTION_STATUS_CHOICES = [
        ('sanctioned', 'Под санкциями (Запрещен)'),
        ('restricted', 'Ограниченное обращение'),
        ('free', 'Доступен без ограничений'),
    ]
    title = models.CharField(max_length=255, verbose_name="Название продукта")
    brand = models.CharField(max_length=155, blank=True, null=True, verbose_name="Бренд/производитель")
    country = models.CharField(max_length=100, verbose_name="Страна происхождения")
    image = models.ImageField(upload_to='products_foto/', blank=True, null=True, verbose_name="Изображение товара")
    sanction_status = models.CharField(max_length=20, choices=SANCTION_STATUS_CHOICES, default='free', verbose_name="Статус санкций")
    sanction_description = models.TextField(blank=True, null=True, verbose_name="Описание ограничений")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.title} ({self.country})"


# 2. МЕДИКАМЕНТЫ (Добавили новые поля для цен и отличий)
class Medication(Product):
    inn_name = models.CharField(max_length=255, verbose_name="МНН (Действующее в-во)")
    dosage = models.CharField(max_length=100, verbose_name="Дозировка")
    from_release = models.CharField(max_length=100, verbose_name="Форма выпуска (таблетки, капсулы)")

    analogs = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=True,
        verbose_name="Аналоги"
    )

    # --- НОВЫЕ ПОЛЯ ---
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Базовая цена (BYN)")
    instruction = models.TextField(blank=True, null=True, verbose_name="Инструкция")
    differences_text = models.TextField(blank=True, null=True, verbose_name="Отличия от импортных аналогов")
    pills_per_pack = models.IntegerField(default=20, verbose_name="Кол-во таблеток в упаковке") # Пригодится для калькулятора

    CATEGORY_CHOICES = [
        ('painkillers', 'Абязбольвальныя'),
        ('cardio', 'Сардэчна-сасудзістыя'),
        ('antibiotics', 'Антыбіётыкі'),
        ('vitamins', 'Вітаміны'),
        ('allergy', 'Ад алергіі'),
        ('stomach', 'Для страўніка'),
    ]
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        blank=True,
        default='',
        verbose_name="Категория"
    )


    class Meta:
        verbose_name = "Медикамент"
        verbose_name_plural = "Медикаменты"


# 3. ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ (Для скидок)
class UserProfile(models.Model):
    DISCOUNT_CHOICES = [
        ('none', 'Без скидки'),
        ('vov', 'Участник ВОВ'),
        ('disabled', 'Инвалид'),
        ('pensioner', 'Пенсионер'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    discount_category = models.CharField(max_length=20, choices=DISCOUNT_CHOICES, default='none', verbose_name="Категория скидки")
    notify_push = models.BooleanField(default=True, verbose_name="Пуш-уведомления")
    notify_email = models.BooleanField(default=False, verbose_name="Email-уведомления")
    notify_in_app = models.BooleanField(default=True, verbose_name="В приложении")

    def __str__(self):
        return f"{self.user.username} ({self.get_discount_category_display()})"


# 4. ЛИЧНАЯ АПТЕЧКА ПОЛЬЗОВАТЕЛЯ (Для напоминаний)
class UserMedication(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='my_medications')
    medication = models.ForeignKey(Medication, on_delete=models.CASCADE)
    quantity_remaining = models.IntegerField(default=0, verbose_name="Осталось таблеток/доз")
    dosage_per_day = models.IntegerField(default=1, verbose_name="Приемов в день")
    reminder_times = models.JSONField(default=list, verbose_name="Время напоминаний (например, ['08:00', '20:00'])")
    course_days_left = models.IntegerField(default=0, verbose_name="Дней до конца курса")

    def __str__(self):
        return f"{self.user.username} - {self.medication.title}"
# 5. АПТЕКИ (Для карты)
class Pharmacy(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название аптеки")
    address = models.CharField(max_length=500, verbose_name="Адрес")
    latitude = models.FloatField(verbose_name="Широта (Latitude)")
    longitude = models.FloatField(verbose_name="Долгота (Longitude)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.address})"

    class Meta:
        verbose_name = "Аптека"
        verbose_name_plural = "Аптеки"


# 6. ЦЕНЫ В АПТЕКАХ (Связь лекарства и аптеки)
class PharmacyPrice(models.Model):
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='prices')
    medication = models.ForeignKey(Medication, on_delete=models.CASCADE, related_name='pharmacy_prices')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена (BYN)")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления цены")

    def __str__(self):
        return f"{self.medication.title} в {self.pharmacy.name} - {self.price} BYN"

    class Meta:
        verbose_name = "Цена в аптеке"
        verbose_name_plural = "Цены в аптеках"
        unique_together = ('pharmacy', 'medication') # В одной аптеке у одного лекарства одна цена