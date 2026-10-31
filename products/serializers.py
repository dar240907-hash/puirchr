from rest_framework import serializers
from .models import Medication, UserMedication, UserProfile

class MedicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medication
        fields = '__all__'

class UserMedicationSerializer(serializers.ModelSerializer):
    # Добавляем вложенные данные о препарате, чтобы фронтенд сразу видел название и цену
    medication_info = MedicationSerializer(source='medication', read_only=True)

    class Meta:
        model = UserMedication
        fields = ['id', 'medication', 'medication_info', 'quantity_remaining', 'dosage_per_day', 'reminder_times', 'course_days_left']

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['discount_category', 'notify_push', 'notify_email', 'notify_in_app']
from .models import Medication, UserMedication, UserProfile, PharmacyPrice

class PharmacyPriceSerializer(serializers.ModelSerializer):
    pharmacy_name = serializers.CharField(source='pharmacy.name', read_only=True)
    pharmacy_address = serializers.CharField(source='pharmacy.address', read_only=True)

    class Meta:
        model = PharmacyPrice
        fields = ['id', 'pharmacy', 'pharmacy_name', 'pharmacy_address', 'medication', 'price', 'updated_at']