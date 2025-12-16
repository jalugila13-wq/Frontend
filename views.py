from django.db import connection
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Count, Prefetch
from django.shortcuts import get_object_or_404

from .models import (
    User, Role, MasterShows, ListGenre, ShowGenreMapping,
    MediaStatusLog, MediaPopularity, Category, Article, MediaFile
)
from .serializers import (
    UserSerializer, UserRegistrationSerializer, RoleSerializer,
    MasterShowsListSerializer, MasterShowsDetailSerializer,
    ListGenreSerializer, CategorySerializer,
    ArticleListSerializer, ArticleDetailSerializer, ArticleCreateUpdateSerializer,
    MediaFileSerializer, SearchResultSerializer, TrendingMediaSerializer,
    GenreStatSerializer, StatusStatSerializer
)


# ============================================================================
# PAGINATION
# ============================================================================

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ============================================================================
# AUTHENTICATION VIEWS
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """Endpoint untuk registrasi user baru"""
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            'message': 'User registered successfully',
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet untuk roles - read only"""
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [AllowAny]


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet untuk user management"""
    queryset = User.objects.all().select_related('role')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # User biasa hanya bisa lihat diri sendiri, admin bisa lihat semua
        if self.request.user.role.name == 'Admin':
            return self.queryset
        return self.queryset.filter(id=self.request.user.id)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Endpoint untuk get current user info"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


# ============================================================================
# MASTER SHOWS VIEWS
# ============================================================================

class MasterShowsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet untuk Master Shows - Lost Media utama"""
    queryset = MasterShows.objects.all()
    permission_classes = [AllowAny]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title']
    ordering_fields = ['release_year', 'title']
    ordering = ['-release_year']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return MasterShowsDetailSerializer
        return MasterShowsListSerializer
    
    def get_queryset(self):
        queryset = self.queryset
        
        # Filter by year range
        year_from = self.request.query_params.get('year_from', None)
        year_to = self.request.query_params.get('year_to', None)
        
        if year_from:
            queryset = queryset.filter(release_year__gte=year_from)
        if year_to:
            queryset = queryset.filter(release_year__lte=year_to)
        
        # Filter by genre
        genre = self.request.query_params.get('genre', None)
        if genre:
            queryset = queryset.filter(
                showgenremapping__genre__genre_name__icontains=genre
            ).distinct()
        
        # Filter by status
        recovery_status = self.request.query_params.get('status', None)
        if recovery_status:
            if recovery_status.lower() == 'unknown':
                # Shows without status log
                queryset = queryset.exclude(
                    show_id__in=MediaStatusLog.objects.values_list('show_id', flat=True)
                )
            else:
                queryset = queryset.filter(
                    mediastatuslog__recovery_status=recovery_status
                )
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get top 10 trending lost media"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT TOP 10
                    ms.Title,
                    ms.ReleaseYear,
                    mp.SearchCount
                FROM dbo.Master_Shows AS ms
                JOIN dbo.MediaPopularity AS mp ON ms.Show_ID = mp.ID
                ORDER BY mp.SearchCount DESC
            """)
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        serializer = TrendingMediaSerializer(results, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get statistics untuk dashboard"""
        # Total shows
        total_shows = MasterShows.objects.count()
        
        # Status breakdown
        status_stats = []
        status_counts = MediaStatusLog.objects.values('recovery_status').annotate(
            count=Count('show_id')
        )
        
        for stat in status_counts:
            status_stats.append({
                'status': stat['recovery_status'],
                'count': stat['count'],
                'percentage': round((stat['count'] / total_shows) * 100, 2)
            })
        
        # Unknown/Lost count (shows without status log)
        unknown_count = total_shows - sum(s['count'] for s in status_stats)
        if unknown_count > 0:
            status_stats.append({
                'status': 'Unknown/Lost',
                'count': unknown_count,
                'percentage': round((unknown_count / total_shows) * 100, 2)
            })
        
        # Genre distribution
        genre_stats = ShowGenreMapping.objects.values(
            'genre__genre_name'
        ).annotate(
            show_count=Count('show_id')
        ).order_by('-show_count')[:10]
        
        return Response({
            'total_shows': total_shows,
            'status_distribution': status_stats,
            'top_genres': list(genre_stats)
        })


# ============================================================================
# SEARCH VIEWS
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def simple_search(request):
    """Simple search by keyword - menggunakan SP_Search_By_Keyword"""
    keyword = request.GET.get('q', '')
    
    if not keyword:
        return Response({
            'error': 'Parameter "q" is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    with connection.cursor() as cursor:
        cursor.execute("""
            EXEC SP_Search_By_Keyword @Keyword = %s
        """, [keyword])
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    serializer = SearchResultSerializer(results, many=True)
    return Response({
        'count': len(results),
        'results': serializer.data
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def advanced_search(request):
    """Advanced search - menggunakan SP_Advanced_Search_LostMedia"""
    keyword = request.GET.get('keyword', None)
    title_type = request.GET.get('title_type', None)
    genre_name = request.GET.get('genre', None)
    category_name = request.GET.get('category', None)
    recovery_status = request.GET.get('status', None)
    
    with connection.cursor() as cursor:
        cursor.execute("""
            EXEC SP_Advanced_Search_LostMedia 
                @Keyword = %s,
                @TitleType = %s,
                @GenreName = %s,
                @CategoryName = %s,
                @RecoveryStatus = %s
        """, [keyword, title_type, genre_name, category_name, recovery_status])
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    serializer = SearchResultSerializer(results, many=True)
    return Response({
        'count': len(results),
        'filters': {
            'keyword': keyword,
            'title_type': title_type,
            'genre': genre_name,
            'category': category_name,
            'status': recovery_status
        },
        'results': serializer.data
    })


# ============================================================================
# CATEGORY VIEWS
# ============================================================================

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet untuk categories"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    @action(detail=True, methods=['get'])
    def articles(self, request, slug=None):
        """Get articles by category"""
        category = self.get_object()
        articles = Article.objects.filter(
            category=category,
            status='published'
        ).select_related('user', 'category', 'show')
        
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(articles, request)
        
        serializer = ArticleListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ============================================================================
# ARTICLE VIEWS
# ============================================================================

class ArticleViewSet(viewsets.ModelViewSet):
    """ViewSet untuk articles"""
    queryset = Article.objects.all().select_related(
        'user', 'category', 'show'
    ).prefetch_related('media_files')
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ArticleDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ArticleCreateUpdateSerializer
        return ArticleListSerializer
    
    def get_queryset(self):
        queryset = self.queryset
        
        # Filter published articles for non-authenticated users
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(status='published')
        else:
            # Contributors can see their own drafts
            if self.request.user.role.name == 'Contributor':
                queryset = queryset.filter(
                    Q(status='published') | Q(user=self.request.user)
                )
            # Admin can see all
            elif self.request.user.role.name != 'Admin':
                queryset = queryset.filter(status='published')
        
        # Filter by category
        category_slug = self.request.query_params.get('category', None)
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        # Filter by show
        show_id = self.request.query_params.get('show_id', None)
        if show_id:
            queryset = queryset.filter(show_id=show_id)
        
        return queryset
    
    def perform_create(self, serializer):
        """Set user dari request saat create"""
        serializer.save(user=self.request.user)
    
    def perform_update(self, serializer):
        """Ensure only author or admin can update"""
        article = self.get_object()
        if article.user != self.request.user and self.request.user.role.name != 'Admin':
            raise PermissionError("You don't have permission to edit this article")
        serializer.save()
    
    @action(detail=False, methods=['get'])
    def my_articles(self, request):
        """Get current user's articles"""
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=401)
        
        articles = self.get_queryset().filter(user=request.user)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(articles, request)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# ============================================================================
# GENRE VIEWS
# ============================================================================

class GenreViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet untuk genres"""
    queryset = ListGenre.objects.all()
    serializer_class = ListGenreSerializer
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get genre statistics"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    lg.genre_name,
                    COUNT(DISTINCT sgm.Show_ID) AS show_count,
                    ISNULL(SUM(mp.SearchCount), 0) AS TotalSearches
                FROM list_genre lg
                LEFT JOIN Show_Genre_Mapping sgm ON lg.genre_id = sgm.genre_id
                LEFT JOIN MediaPopularity mp ON sgm.Show_ID = mp.ID
                GROUP BY lg.genre_name
                ORDER BY TotalSearches DESC
            """)
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        return Response(results)


# ============================================================================
# MEDIA FILE VIEWS
# ============================================================================

class MediaFileViewSet(viewsets.ModelViewSet):
    """ViewSet untuk media files"""
    queryset = MediaFile.objects.all().select_related('article', 'uploaded_by')
    serializer_class = MediaFileSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        queryset = self.queryset
        
        # Filter by article
        article_id = self.request.query_params.get('article_id', None)
        if article_id:
            queryset = queryset.filter(article_id=article_id)
        
        # Filter by recovery status
        recovery_status = self.request.query_params.get('status', None)
        if recovery_status:
            queryset = queryset.filter(recovery_status=recovery_status)
        
        return queryset
    
    def perform_create(self, serializer):
        """Set uploaded_by dari request"""
        serializer.save(uploaded_by=self.request.user)


# ============================================================================
# DASHBOARD/ANALYTICS VIEWS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """Statistics untuk dashboard (Executive/Admin)"""
    
    # Total counts
    total_shows = MasterShows.objects.count()
    total_articles = Article.objects.filter(status='published').count()
    total_users = User.objects.count()
    
    # Status distribution
    status_dist = MediaStatusLog.objects.values('recovery_status').annotate(
        count=Count('show_id')
    )
    
    # Recent articles
    recent_articles = Article.objects.filter(
        status='published'
    ).select_related('user', 'category')[:5]
    
    # Top trending
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT TOP 5
                ms.Title,
                ms.ReleaseYear,
                mp.SearchCount
            FROM dbo.Master_Shows AS ms
            JOIN dbo.MediaPopularity AS mp ON ms.Show_ID = mp.ID
            ORDER BY mp.SearchCount DESC
        """)
        columns = [col[0] for col in cursor.description]
        trending = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    return Response({
        'total_shows': total_shows,
        'total_articles': total_articles,
        'total_users': total_users,
        'status_distribution': list(status_dist),
        'recent_articles': ArticleListSerializer(recent_articles, many=True).data,
        'trending_media': trending
    })