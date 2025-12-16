from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Role, MasterShows, ListGenre, ShowGenreMapping,
    MediaStatusLog, MediaPopularity, Category, Article, MediaFile
)

# ============================================================================
# USER & ROLE ADMIN
# ============================================================================

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'description']
    search_fields = ['name']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'name', 'role', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'created_at']
    search_fields = ['email', 'name']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('name', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'role', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'last_login']


# ============================================================================
# MASTER SHOWS ADMIN
# ============================================================================

class ShowGenreMappingInline(admin.TabularInline):
    model = ShowGenreMapping
    extra = 1
    raw_id_fields = ['genre']


@admin.register(MasterShows)
class MasterShowsAdmin(admin.ModelAdmin):
    list_display = ['show_id', 'title', 'release_year', 'first_source_table', 'get_status']
    list_filter = ['release_year', 'first_source_table']
    search_fields = ['title', 'first_source_id']
    ordering = ['-release_year', 'title']
    readonly_fields = ['show_id', 'first_source_table', 'first_source_id']
    
    inlines = [ShowGenreMappingInline]
    
    def get_status(self, obj):
        try:
            return obj.mediastatuslog.recovery_status
        except MediaStatusLog.DoesNotExist:
            return 'Unknown/Lost'
    get_status.short_description = 'Recovery Status'
    
    def has_add_permission(self, request):
        # Disable add karena data dari integrasi
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Only admin can delete
        return request.user.is_superuser


@admin.register(ListGenre)
class ListGenreAdmin(admin.ModelAdmin):
    list_display = ['genre_id', 'genre_name', 'get_show_count']
    search_fields = ['genre_name']
    ordering = ['genre_name']
    
    def get_show_count(self, obj):
        return ShowGenreMapping.objects.filter(genre=obj).count()
    get_show_count.short_description = 'Total Shows'
    
    def has_add_permission(self, request):
        return False


# ============================================================================
# MEDIA STATUS & POPULARITY ADMIN
# ============================================================================

@admin.register(MediaStatusLog)
class MediaStatusLogAdmin(admin.ModelAdmin):
    list_display = ['show', 'recovery_status', 'last_updated']
    list_filter = ['recovery_status', 'last_updated']
    search_fields = ['show__title']
    readonly_fields = ['last_updated']
    raw_id_fields = ['show']
    
    def has_add_permission(self, request):
        return True


@admin.register(MediaPopularity)
class MediaPopularityAdmin(admin.ModelAdmin):
    list_display = ['get_show_title', 'search_count']
    search_fields = ['id__title']
    ordering = ['-search_count']
    readonly_fields = ['id']
    
    def get_show_title(self, obj):
        return obj.id.title
    get_show_title.short_description = 'Show'
    
    def has_add_permission(self, request):
        return False


# ============================================================================
# CATEGORY ADMIN
# ============================================================================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'slug', 'get_article_count']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    
    def get_article_count(self, obj):
        return Article.objects.filter(category=obj).count()
    get_article_count.short_description = 'Total Articles'


# ============================================================================
# ARTICLE ADMIN
# ============================================================================

class MediaFileInline(admin.TabularInline):
    model = MediaFile
    extra = 1
    fields = ['file_path', 'file_type', 'original_name', 'recovery_status']
    readonly_fields = ['uploaded_by', 'created_at']


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'status', 'user', 'category', 'show', 'created_at']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['title', 'content', 'user__name']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['show']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'content', 'status')
        }),
        ('Relations', {
            'fields': ('user', 'category', 'show', 'tconst')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [MediaFileInline]
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(MediaFile)
class MediaFileAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_article_title', 'original_name', 'file_type', 
                   'recovery_status', 'uploaded_by', 'created_at']
    list_filter = ['recovery_status', 'file_type', 'created_at']
    search_fields = ['original_name', 'article__title']
    ordering = ['-created_at']
    readonly_fields = ['uploaded_by', 'created_at']
    raw_id_fields = ['article']
    
    def get_article_title(self, obj):
        return obj.article.title
    get_article_title.short_description = 'Article'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


# ============================================================================
# CUSTOM ADMIN SITE CONFIGURATION
# ============================================================================

admin.site.site_header = "Lost Media Administration"
admin.site.site_title = "Lost Media Admin"
admin.site.index_title = "Welcome to Lost Media Administration Portal"