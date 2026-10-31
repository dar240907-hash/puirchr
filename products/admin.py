from django.contrib import admin

# Register your models here.
from .models import Pharmacy, PharmacyPrice

@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'latitude', 'longitude')

@admin.register(PharmacyPrice)
class PharmacyPriceAdmin(admin.ModelAdmin):
    list_display = ('medication', 'pharmacy', 'price', 'updated_at')
    list_filter = ('pharmacy', 'medication')
