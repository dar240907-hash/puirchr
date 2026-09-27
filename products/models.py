from django.db import models

#базовая модель товара, абстактный метод, не является частью бд
class Product(models.Model):
    SANCTION_STATUS_CHOICES =[
        ('sanctioned', 'Под санкциями (Запрещен)'),
        ('restricted', 'Ограниченное обращение'),
        ('free', 'Доступен без ограничений'),
    ]
    title = models.CharField(max_length = 255, verbose_name="Название продукта")
    brand = models.CharField(max_length = 155, blank=True, null=True, verbose_name ="Бренд/производитель")
    country = models.CharField(max_length= 100, verbose_name = "Страна происхождения")
    image = models.ImageField(upload_to='products_foto/', blank=True, null = True, verbose_name = "Изображение товара")
    sanction_status = models.CharField(max_length=20, choices=SANCTION_STATUS_CHOICES, default='free', verbose_name="Статус санкций")
    sanction_description = models.TextField(blank=True, null=True, verbose_name="Описание ограничений")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    class Meta:
        abstract = True
    def __str__(self):
        return f"{self.title} ({self.country})"
#медикоменты, наследует от продуктов + свои поля
class Medication(Product):
    #действующее вещество, по нему основное совпадение
    inn_name = models.CharField(max_length=255, verbose_name="МНН (Действующее в-во)")
    dosage = models.CharField(max_length=100, verbose_name="Дозировка")
    from_release = models.CharField(max_length=100, verbose_name="Форма выпуска(таблетки, капсулы)")
    # Если импортное лекарство связано с белорусским аналогом, связь автоматически станет двусторонней
    analogs = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=True,
        verbose_name="Аналоги"
    )
    class Meta:
        verbose_name = "Медикомент"
        verbose_name_plural = "Медикоменты"