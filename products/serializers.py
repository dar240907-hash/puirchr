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
        fields = ['discount_category']