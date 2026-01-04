from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserProfile, MedicalReport


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    fields = ('date_of_birth', 'gender', 'institution', 'license_number', 'license_expiry')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Profile', {'fields': ('profile_picture', 'specialization', 'bio', 'is_verified')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
    )
    list_display = ('email', 'first_name', 'last_name', 'is_verified', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_verified')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    inlines = [UserProfileInline]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'institution', 'created_at')
    search_fields = ('user__email', 'institution')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('User', {'fields': ('user',)}),
        ('Personal Information', {'fields': ('date_of_birth', 'gender')}),
        ('Professional Information', {'fields': ('institution', 'license_number', 'license_expiry')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(MedicalReport)
class MedicalReportAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'user', 'file_type', 'file_size', 'upload_date')
    list_filter = ('file_type', 'upload_date')
    search_fields = ('file_name', 'user__email', 'description')
    readonly_fields = ('upload_date', 'updated_at', 'file_size')
    fieldsets = (
        ('Document Information', {'fields': ('user', 'file', 'file_name', 'file_type', 'file_size')}),
        ('Details', {'fields': ('description',)}),
        ('Timestamps', {'fields': ('upload_date', 'updated_at'), 'classes': ('collapse',)}),
    )
    ordering = ('-upload_date',)

