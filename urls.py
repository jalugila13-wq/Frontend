"""
URL configuration for project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
"""
URL Configuration untuk Lost Media Backend
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView
)

from api import views

# Setup router untuk ViewSets
router = DefaultRouter()
router.register(r'roles', views.RoleViewSet, basename='role')
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'shows', views.MasterShowsViewSet, basename='show')
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'articles', views.ArticleViewSet, basename='article')
router.register(r'genres', views.GenreViewSet, basename='genre')
router.register(r'media-files', views.MediaFileViewSet, basename='mediafile')

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # JWT Authentication
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('api/auth/register/', views.register_user, name='register'),
    
    # Search endpoints
    path('api/search/', views.simple_search, name='simple_search'),
    path('api/search/advanced/', views.advanced_search, name='advanced_search'),
    
    # Dashboard
    path('api/dashboard/stats/', views.dashboard_stats, name='dashboard_stats'),
    
    # Router URLs (ViewSets)
    path('api/', include(router.urls)),
]