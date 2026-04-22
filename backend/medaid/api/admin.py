from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserProfile, MedicalReport, ChatConversation, ChatMessage


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


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    fields = ('role', 'content', 'tokens_used', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'is_active', 'total_tokens_used', 'last_activity', 'created_at')
    list_filter = ('is_active', 'created_at', 'last_activity')
    search_fields = ('user__email', 'title')
    readonly_fields = ('created_at', 'updated_at', 'last_activity')
    fieldsets = (
        ('Conversation Info', {'fields': ('user', 'title', 'is_active')}),
        ('Context Management', {'fields': ('total_tokens_used',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at', 'last_activity'), 'classes': ('collapse',)}),
    )
    inlines = [ChatMessageInline]
    ordering = ('-last_activity',)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'role', 'content_preview', 'tokens_used', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('content', 'conversation__title', 'conversation__user__email')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Message Info', {'fields': ('conversation', 'role', 'content')}),
        ('Metadata', {'fields': ('metadata', 'tokens_used')}),
        ('Timestamps', {'fields': ('created_at',)}),
    )
    ordering = ('-created_at',)
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content Preview'

