from django.contrib import admin
from .models import SurveyQuestion, DailyCheckIn

@admin.register(SurveyQuestion)
class SurveyQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_key', 'question_text', 'category_main', 'order', 'is_active')
    list_filter = ('is_active', 'category_main')
    search_fields = ('question_key', 'question_text', 'category_main')
    ordering = ('order',)
    list_editable = ('order', 'is_active')

@admin.register(DailyCheckIn)
class DailyCheckInAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'morning_fasting_weight', 'created_at', 'updated_at')
    list_filter = ('date', 'user')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at')
